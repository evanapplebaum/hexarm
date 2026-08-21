#!/usr/bin/env python3
"""
run_policy.py — Run a trained policy on the follower arm (dead-man's-switch gated).

First autonomous run of a trained checkpoint: no leader arm involved, the
policy predicts the follower's next action directly from camera + joint-state
observations, the same way `record_dataset.py` recorded the leader's position
as the "action" a human demonstrated.

Same DIAGNOSTIC dead-man's-switch convention as go_neutral.py's --diagnostic
mode: the policy's predicted action is only ever written to the servos while
SPACE is held down. Release it and the arm freezes exactly where it is,
instantly — no key-up event exists over a raw SSH terminal, so "held" is
inferred the same way go_neutral.py does (OS keyboard auto-repeat within
SPACE_HOLD_WINDOW). This is the safety scaffold for a policy that's only
been checked on offline loss numbers so far, never watched moving the real
arm — nothing autonomous happens unless a human is actively holding the key
and can let go the instant something looks wrong.

Why not `lerobot-eval`/`lerobot-rollout`: same reason `record_dataset.py`
doesn't use `lerobot-record` — this hardware isn't one of LeRobot's built-in
--robot.type options, and the raw-termios SSH key reading (vs. pynput, which
needs a display backend) doesn't work headless over SSH either.

Parameters:
  --checkpoint      Path to a pretrained_model dir. Default: the final
                     checkpoint of the v3 run (outputs/train/act_pick_and_place_v3/checkpoints/last),
                     which supersedes v2 — v2 ran on hardware and worked but
                     left tight margins (see docs/debugging/postmortems.md #10);
                     v3 was retrained on a re-recorded dataset to fix that.
  --task            Task description string, must match what the dataset
                     was recorded with. Default: "Pick up the block and
                     place it in the bin" (confirmed via meta/tasks.parquet).
  --fps             Control-loop rate in Hz. Default: 30 (matches training data).
  --port            Serial port for the follower's servo bus. Default: /dev/ttyACM0.
  --overhead-index  /dev/videoN index for the overhead camera. Default: 0.
  --wrist-index     /dev/videoN index for the wrist camera. Default: 2.
  --velocity        Max joint speed in counts/s for the policy loop. Default: 50
                     (~8.8°/s, same as go_neutral.py's default), or 15 (~2.6°/s)
                     with --slowmo.
  --acceleration    Ramp rate in counts/s² for the policy loop. Default: 10, or 3
                     with --slowmo.
  --slowmo          Cap velocity/acceleration to the conservative values above —
                     for watching an untested policy's first moves. Explicit
                     --velocity/--acceleration override this if both are given.

Usage (from hexarm root):
  source /data/lerobot-env/bin/activate
  python software/control/run_policy.py

Controls (raw SSH terminal, same convention as go_neutral.py --diagnostic):
  HOLD SPACE — let the policy's predicted action apply this tick
  release    — freeze in place immediately
  q          — stop the session (freezes in place, then returns to neutral)

Prerequisites:
  - Follower arm calibrated, neutral pose captured (software/config/*.json)
  - Both cameras connected — same indices used during recording
  - Leader arm/bus is NOT used here — only the follower moves
"""

import argparse
import select
import sys
import termios
import time
import tty
from pathlib import Path

# Add repo root (hexarm/) to path — same reasoning as record_dataset.py:
# adding software/ directly would shadow the pip-installed scservo_sdk.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from software.calibration.go_neutral import go_neutral, safe_enable_torque  # noqa: E402

import cv2
import torch

from lerobot.cameras.opencv import OpenCVCamera, OpenCVCameraConfig
from lerobot.common.control_utils import predict_action
from lerobot.configs.policies import PreTrainedConfig
from lerobot.datasets.lerobot_dataset import LeRobotDatasetMetadata
from lerobot.motors.feetech import FeetechMotorsBus
from lerobot.motors.motors_bus import Motor, MotorCalibration, MotorNormMode
from lerobot.policies.factory import get_policy_class, make_pre_post_processors
from lerobot.utils.constants import OBS_STR
from lerobot.utils.feature_utils import build_dataset_frame

# ── Constants ─────────────────────────────────────────────────────────────────

JOINT_NAMES = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]

CONFIG_DIR   = Path("software/config")
DEFAULT_PORT = "/dev/ttyACM0"
DEFAULT_FPS  = 30  # matches the dataset's recorded fps

DEFAULT_OVERHEAD_INDEX = 0
DEFAULT_WRIST_INDEX    = 2
CAMERA_WIDTH  = 1280
CAMERA_HEIGHT = 800

DEFAULT_CHECKPOINT = "outputs/train/act_pick_and_place_v3/checkpoints/last/pretrained_model"
DEFAULT_TASK        = "Pick up the block and place it in the bin"
DATASET_REPO_ID      = "hexarm/pick_and_place_v3"
DATASET_ROOT          = "/data/lerobot_home/hexarm/pick_and_place_v3"

# Motion profile for the policy loop itself — separate from go_neutral()'s own
# internal defaults, which it explicitly resets to 0 (= unlimited) after every
# move it makes. Without setting these again afterward, the policy would drive
# the servos at full uncapped speed with no governor at all.
# DEFAULT_VELOCITY/DEFAULT_ACCELERATION are loaded further down (after
# load_json() is defined) from software/config/motion_profile.json — shared
# with go_neutral.py so there's one number to tune, not two hardcoded copies.
SLOWMO_VELOCITY      = 15  # counts/s ≈ 2.6°/s
SLOWMO_ACCELERATION  = 3   # counts/s²

# Same reasoning as go_neutral.py: no key-up event over a raw SSH terminal,
# so "held" is inferred from OS keyboard auto-repeat within this window.
SPACE_HOLD_WINDOW = 0.2  # seconds

# ── Raw-terminal key polling (same convention as go_neutral.py --diagnostic) ──

def _read_available_key() -> str | None:
    if select.select([sys.stdin], [], [], 0)[0]:
        return sys.stdin.read(1)
    return None


class _RawTerminal:
    def __enter__(self):
        self._fd = sys.stdin.fileno()
        self._old = termios.tcgetattr(self._fd)
        tty.setraw(self._fd)
        return self

    def __exit__(self, *exc_info):
        termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old)

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing config file: {path}")
    import json
    with open(path) as f:
        return json.load(f)


# Shared with go_neutral.py via software/config/motion_profile.json — a single
# source of truth so tuning one file updates the default for both scripts,
# instead of two independent hardcoded copies silently drifting apart.
_motion_defaults = load_json(CONFIG_DIR / "motion_profile.json")
DEFAULT_VELOCITY     = _motion_defaults["velocity"]      # counts/s — 50 ≈ 8.8°/s
DEFAULT_ACCELERATION = _motion_defaults["acceleration"]  # counts/s²


def build_follower_bus(port: str, cal_follower: dict) -> FeetechMotorsBus:
    """Follower only — no leader bus/arm involved in policy-driven control."""
    active_joints = [n for n in JOINT_NAMES if n in cal_follower]
    skipped = [n for n in JOINT_NAMES if n not in active_joints]
    if skipped:
        print(f"Skipping joints with missing calibration: {skipped}")

    motors = {
        name: Motor(id=JOINT_NAMES.index(name) + 1, model="sts3215", norm_mode=MotorNormMode.RANGE_0_100)
        for name in active_joints
    }
    calibration = {name: MotorCalibration(**cal_follower[name]) for name in active_joints}
    return FeetechMotorsBus(port=port, motors=motors, calibration=calibration)


def connect_cameras(overhead_index: int, wrist_index: int, fps: int) -> dict[str, OpenCVCamera]:
    # Same MJPG-at-native-resolution reasoning as record_dataset.py's connect_cameras.
    cameras = {
        "overhead": OpenCVCamera(OpenCVCameraConfig(
            index_or_path=overhead_index, fps=fps, width=CAMERA_WIDTH, height=CAMERA_HEIGHT, fourcc="MJPG")),
        "wrist": OpenCVCamera(OpenCVCameraConfig(
            index_or_path=wrist_index, fps=fps, width=CAMERA_WIDTH, height=CAMERA_HEIGHT, fourcc="MJPG")),
    }
    for name, cam in cameras.items():
        cam.connect()
        print(f"Camera '{name}' connected (index {cam.index_or_path}).")
    return cameras


def load_policy(checkpoint_dir: str, device: torch.device):
    """Load the trained ACT policy + its saved pre/post-processor pipelines
    (normalization stats baked in from training) from a pretrained_model dir."""
    cfg = PreTrainedConfig.from_pretrained(checkpoint_dir)
    cfg.pretrained_path = checkpoint_dir
    policy_cls = get_policy_class(cfg.type)
    policy = policy_cls.from_pretrained(pretrained_name_or_path=checkpoint_dir)
    policy.to(device)
    policy.eval()
    preprocessor, postprocessor = make_pre_post_processors(cfg, pretrained_path=checkpoint_dir)
    return policy, preprocessor, postprocessor


def freeze_in_place(bus: FeetechMotorsBus) -> None:
    current = bus.sync_read("Present_Position", normalize=False)
    bus.sync_write("Goal_Position", {n: int(float(v)) for n, v in current.items()}, normalize=False)


def run_policy_loop(
    bus: FeetechMotorsBus,
    cameras: dict[str, OpenCVCamera],
    policy,
    preprocessor,
    postprocessor,
    ds_features: dict,
    task: str,
    fps: int,
    device: torch.device,
    record_sizes: dict[str, tuple[int, int]],
) -> None:
    """Dead-man's-switch gated: the policy's predicted action is only written
    to the servos while SPACE is held. Release freezes in place. 'q' stops."""
    period = 1 / fps
    action_names = ds_features["action"]["names"]

    policy.reset()  # clears the action-chunk queue / temporal ensembler
    print("DIAGNOSTIC MODE — hold SPACE to let the policy act, release to freeze in place. 'q' to stop.")

    held_until = 0.0
    with _RawTerminal():
        while True:
            t0 = time.monotonic()

            key = _read_available_key()
            if key == " ":
                held_until = time.time() + SPACE_HOLD_WINDOW
            elif key in ("q", "\x03"):
                break

            follower_pos = bus.sync_read("Present_Position", normalize=True)
            obs_values = {f"{j}.pos": float(follower_pos[j]) for j in JOINT_NAMES}
            for name, cam in cameras.items():
                frame = cam.read_latest()
                obs_values[name] = cv2.resize(frame, record_sizes[name], interpolation=cv2.INTER_AREA)

            observation_frame = build_dataset_frame(ds_features, obs_values, prefix=OBS_STR)
            action = predict_action(
                observation_frame, policy, device, preprocessor, postprocessor,
                use_amp=False, task=task, robot_type="hexarm",
            )
            # predict_action's docstring claims the batch dim is removed, but it
            # isn't — shape is [1, action_dim], confirmed directly against this checkpoint.
            action = action.squeeze(0)
            goal = {
                name.removesuffix(".pos"): float(action[i])
                for i, name in enumerate(action_names)
            }

            if time.time() < held_until:
                bus.sync_write("Goal_Position", goal, normalize=True)
            else:
                freeze_in_place(bus)

            elapsed = time.monotonic() - t0
            time.sleep(max(0.0, period - elapsed))

    freeze_in_place(bus)
    print("Stopped — frozen in place.")

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Run a trained policy on the follower arm (dead-man's-switch gated)")
    parser.add_argument("--checkpoint", default=DEFAULT_CHECKPOINT)
    parser.add_argument("--task",       default=DEFAULT_TASK)
    parser.add_argument("--fps",        type=int, default=DEFAULT_FPS)
    parser.add_argument("--port",       default=DEFAULT_PORT)
    parser.add_argument("--overhead-index", type=int, default=DEFAULT_OVERHEAD_INDEX)
    parser.add_argument("--wrist-index",    type=int, default=DEFAULT_WRIST_INDEX)
    parser.add_argument("--velocity",     type=int, default=None,
                         help=f"Max joint speed in counts/s for the policy loop "
                              f"(default: {DEFAULT_VELOCITY}, or {SLOWMO_VELOCITY} with --slowmo)")
    parser.add_argument("--acceleration", type=int, default=None,
                         help=f"Ramp rate in counts/s² for the policy loop "
                              f"(default: {DEFAULT_ACCELERATION}, or {SLOWMO_ACCELERATION} with --slowmo)")
    parser.add_argument("--slowmo", action="store_true",
                         help="Cap velocity/acceleration to conservative values — for watching "
                              "an untested policy's first moves. Overridden by explicit "
                              "--velocity/--acceleration if both are given.")
    args = parser.parse_args()

    velocity = args.velocity if args.velocity is not None else (
        SLOWMO_VELOCITY if args.slowmo else DEFAULT_VELOCITY)
    acceleration = args.acceleration if args.acceleration is not None else (
        SLOWMO_ACCELERATION if args.slowmo else DEFAULT_ACCELERATION)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    cal_follower = load_json(CONFIG_DIR / "calibration_follower.json")
    neutral      = load_json(CONFIG_DIR / "neutral.json")

    print(f"Loading policy from {args.checkpoint} ...")
    policy, preprocessor, postprocessor = load_policy(args.checkpoint, device)

    ds_meta = LeRobotDatasetMetadata(repo_id=DATASET_REPO_ID, root=DATASET_ROOT)

    bus = build_follower_bus(args.port, cal_follower)
    bus.connect()
    print(f"Connected to {args.port}  ({len(bus.motors)} motor(s), follower only)")

    cameras = connect_cameras(args.overhead_index, args.wrist_index, args.fps)

    record_sizes = {
        name: (
            ds_meta.features[f"{OBS_STR}.images.{name}"]["shape"][1],
            ds_meta.features[f"{OBS_STR}.images.{name}"]["shape"][0],
        )
        for name in cameras
    }

    try:
        safe_enable_torque(bus)
        print("Follower torque: ON")
        go_neutral(bus, neutral)

        # Cap motion speed for the policy loop itself — must happen AFTER
        # go_neutral() returns, since it resets these to 0/unlimited once its
        # own move finishes.
        for name in bus.motors:
            bus.write("Maximum_Velocity_Limit", name, velocity,     normalize=False, num_retry=3)
            bus.write("Acceleration",           name, acceleration, normalize=False, num_retry=3)
        print(f"Policy motion capped: velocity={velocity} (~{velocity / 5.68:.1f}°/s), "
              f"acceleration={acceleration}")

        run_policy_loop(
            bus, cameras, policy, preprocessor, postprocessor,
            ds_meta.features, args.task, args.fps, device, record_sizes,
        )

        print("Returning to neutral...")
        safe_enable_torque(bus)
        go_neutral(bus, neutral)
    finally:
        for cam in cameras.values():
            cam.disconnect()
        # Same reasoning as go_neutral.py standalone: leave torque enabled on
        # exit so the arm holds its last commanded pose instead of going limp.
        bus.disconnect(disable_torque=False)
        print("Torque left enabled — run torque_off.py if you want it disabled.")


if __name__ == "__main__":
    main()
