#!/usr/bin/env python3
"""
record_dataset.py — Record teleoperated demonstrations into a LeRobotDataset.

Runs the same single-bus leader-follower tick as teleop.py (see its
docstring), but also captures both cameras each tick and writes every
(observation, action) pair into a standard `LeRobotDataset` via
`add_frame()`/`save_episode()`. The result is consumable by LeRobot's
stock `lerobot-train` / `lerobot-eval` / `lerobot-replay` unmodified —
only the *recording* step is custom.

Why not `lerobot-record`: hexarm runs both arms on ONE shared
FeetechMotorsBus/port (see teleop.py's docstring for why) instead of
LeRobot's default one-port-per-arm layout, and `lerobot-record`
constructs its Robot and Teleoperator as two independent objects, each
normally opening its own port — sharing one physical port between two
independent bus instances isn't safe. `lerobot-record`'s keyboard
control (pynput) also expects a display/event backend, which doesn't
work headless over SSH; this reuses the raw-termios SSH key reading
already established in go_neutral.py's --diagnostic mode instead.

Parameters:
  --repo-id         Required. Dataset identifier, e.g. hexarm/pick_and_place.
  --task            Required. Single-sentence task description, stored per-frame.
  --episodes        Number of episodes to record this session. Default: 50.
  --fps             Control-loop / recording rate in Hz. Default: 30.
  --reset-seconds   Pause between episodes to reposition the object. Default: 10.
  --port            Serial port for the shared servo bus. Default: /dev/ttyACM0.
  --overhead-index  /dev/videoN index for the overhead camera. Default: 0.
  --wrist-index     /dev/videoN index for the wrist camera. Default: 2.
  --nostartseq      Skip the recorded startup-sequence choreography; go straight to neutral.
  --resume          Add episodes to an existing local dataset at --repo-id instead of creating a new one.

Usage (from hexarm root, conda lerobot env):
  source /data/lerobot-env/bin/activate
  python software/control/record_dataset.py \
      --repo-id hexarm/pick_and_place \
      --task "Pick up the block and place it in the bin" \
      --episodes 5 \
      --nostartseq

To Resume from a partially completed dataset (in this example, 3 sessions were already recorded - 47 remaining)
python software/control/record_dataset.py \
    --repo-id hexarm/pick_and_place \
    --task "Pick up the block and place it in the bin" \
    --episodes 47 \
    --resume \
    --nostartseq

Controls (raw SSH terminal, same convention as go_neutral.py --diagnostic):
  ENTER — finish this episode (saves it), then reset and continue
  r     — redo: discard this episode, record it again from the same start
  q     — abort this episode (discarded) and stop the whole session

Prerequisites:
  - Same as teleop.py: both arms calibrated, neutral pose captured,
    startup sequence recorded (software/config/*.json)
  - Both cameras connected — check framing first with
    software/vision/camera_preview.py before recording for real.
"""

import argparse
import json
import select
import shutil
import sys
import termios
import time
import tty
from pathlib import Path

# Add repo root (hexarm/) to path — NOT software/, which would shadow the
# pip-installed scservo_sdk with our local copy and break LeRobot imports.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from software.calibration.go_neutral import go_neutral, safe_enable_torque  # noqa: E402
from software.calibration.run_startup_sequence import run_startup_sequence  # noqa: E402

import cv2

from lerobot.cameras.opencv import OpenCVCamera, OpenCVCameraConfig
from lerobot.datasets import LeRobotDataset
from lerobot.datasets.video_utils import VideoEncodingManager
from lerobot.motors.feetech import FeetechMotorsBus
from lerobot.motors.motors_bus import Motor, MotorCalibration, MotorNormMode
from lerobot.utils.constants import ACTION, HF_LEROBOT_HOME, OBS_STR
from lerobot.utils.feature_utils import build_dataset_frame, combine_feature_dicts, hw_to_dataset_features

# ── Constants ─────────────────────────────────────────────────────────────────

JOINT_NAMES = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]

FOLLOWER_NAMES = [f"follower_{j}" for j in JOINT_NAMES]
LEADER_NAMES   = [f"leader_{j}"   for j in JOINT_NAMES]

CONFIG_DIR   = Path("software/config")
DEFAULT_PORT = "/dev/ttyACM0"

DEFAULT_FPS            = 30   # matches AGENT_GUIDE's recommended dataset default
DEFAULT_EPISODES       = 50   # "start small" — see AGENT_GUIDE §5.5
DEFAULT_RESET_SECONDS  = 10

# Device indices match camera_preview.py's default `--indices 0 2`.
DEFAULT_OVERHEAD_INDEX = 0
DEFAULT_WRIST_INDEX    = 2
CAMERA_WIDTH  = 1280
CAMERA_HEIGHT = 800

# Frames are captured at the camera's native resolution (confirmed exact —
# requesting a smaller size like 640x400 directly gets silently rounded to
# 640x480 by the driver, a different aspect ratio (4:3 vs native 8:5) that
# would crop/distort relative to the already-locked camera framing), then
# downscaled in software before being written. Measured ~3.4x faster PNG
# writes + video encoding at this size vs. full 1280x800, with the same
# aspect ratio preserved.
RECORD_WIDTH  = 640
RECORD_HEIGHT = 400

def _print_recording_banner() -> None:
    """Full-width solid-color block so 'recording started' is readable from
    across the room, not just at the keyboard — plain text is too small to
    make out at a distance, but a wall of color is."""
    width = shutil.get_terminal_size(fallback=(60, 20)).columns
    bar = "\033[1;97;42m" + " " * width + "\033[0m"
    label = "\033[1;97;42m" + "RECORDING — GO".center(width) + "\033[0m"
    print(f"\n{bar}\n{bar}\n{label}\n{bar}\n{bar}\n")


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
    with open(path) as f:
        return json.load(f)


def build_bus(port: str, cal_follower: dict, cal_leader: dict) -> FeetechMotorsBus:
    """Identical construction to teleop.py's build_bus — one shared bus,
    both arms' motors prefixed follower_/leader_ to avoid name collisions."""
    motors: dict[str, Motor] = {}
    for i, joint in enumerate(JOINT_NAMES):
        motors[f"follower_{joint}"] = Motor(id=i + 1, model="sts3215", norm_mode=MotorNormMode.RANGE_0_100)
        motors[f"leader_{joint}"]   = Motor(id=i + 7, model="sts3215", norm_mode=MotorNormMode.RANGE_0_100)

    calibration: dict[str, MotorCalibration] = {}
    for joint, data in cal_follower.items():
        calibration[f"follower_{joint}"] = MotorCalibration(**data)
    for joint, data in cal_leader.items():
        calibration[f"leader_{joint}"] = MotorCalibration(**data)

    return FeetechMotorsBus(port=port, motors=motors, calibration=calibration)


def connect_cameras(overhead_index: int, wrist_index: int, fps: int) -> dict[str, OpenCVCamera]:
    # MJPG (compressed) is required to hit 30fps at 1280x800 — the driver's default
    # uncompressed format exceeds USB bandwidth at this resolution and silently caps
    # at ~10fps instead (same fix camera_preview.py already applies).
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


def build_dataset_features(cameras: dict[str, OpenCVCamera]) -> dict:
    """{joint}.pos for both observation (follower) and action (leader), plus
    one image feature per camera — same shape hw_to_dataset_features()
    expects from a Robot's observation_features/action_features."""
    obs_hw: dict[str, type | tuple] = {f"{joint}.pos": float for joint in JOINT_NAMES}
    for name in cameras:
        obs_hw[name] = (RECORD_HEIGHT, RECORD_WIDTH, 3)
    action_hw: dict[str, type] = {f"{joint}.pos": float for joint in JOINT_NAMES}

    return combine_feature_dicts(
        hw_to_dataset_features(obs_hw, OBS_STR),
        hw_to_dataset_features(action_hw, ACTION),
    )


def record_episode(
    bus: FeetechMotorsBus,
    cameras: dict[str, OpenCVCamera],
    dataset: LeRobotDataset,
    task: str,
    fps: int,
    record_sizes: dict[str, tuple[int, int]],
) -> str:
    """Tick the single-bus teleop loop, writing one dataset frame per tick,
    until the operator presses ENTER, 'r', or 'q'/Ctrl-C. Returns 'save'/'redo'/'stop'.
    """
    period = 1 / fps
    print("Recording... ENTER to finish+save, 'r' to redo, 'q' or Ctrl-C to abort+stop.")
    _print_recording_banner()

    with _RawTerminal():
        while True:
            t0 = time.monotonic()

            key = _read_available_key()
            if key in ("\r", "\n"):
                return "save"
            if key == "r":
                return "redo"
            # Raw terminal mode (tty.setraw) disables the tty driver's normal
            # SIGINT-on-Ctrl-C behavior, so "\x03" arrives here as a literal
            # byte instead of killing the process — treat it the same as 'q'.
            if key in ("q", "\x03"):
                return "stop"

            # Same tick as teleop.py's run_teleop(): leader -> follower goal.
            leader_pos = bus.sync_read("Present_Position", motors=LEADER_NAMES, normalize=True)
            follower_goals = {f"follower_{j}": leader_pos[f"leader_{j}"] for j in JOINT_NAMES}
            bus.sync_write("Goal_Position", follower_goals, normalize=True)

            follower_pos = bus.sync_read("Present_Position", motors=FOLLOWER_NAMES, normalize=True)

            obs_values = {f"{j}.pos": float(follower_pos[f"follower_{j}"]) for j in JOINT_NAMES}
            for name, cam in cameras.items():
                frame = cam.read_latest()
                obs_values[name] = cv2.resize(frame, record_sizes[name], interpolation=cv2.INTER_AREA)
            action_values = {f"{j}.pos": float(leader_pos[f"leader_{j}"]) for j in JOINT_NAMES}

            observation_frame = build_dataset_frame(dataset.features, obs_values, prefix=OBS_STR)
            action_frame = build_dataset_frame(dataset.features, action_values, prefix=ACTION)
            dataset.add_frame({**observation_frame, **action_frame, "task": task})

            elapsed = time.monotonic() - t0
            time.sleep(max(0.0, period - elapsed))


def reset_environment(bus: FeetechMotorsBus, neutral_all: dict[str, float], reset_seconds: int) -> None:
    """Both arms back to neutral (needs leader torque back on to get there),
    then leader torque off again so the operator can reposition for the
    next episode."""
    safe_enable_torque(bus)
    go_neutral(bus, neutral_all)
    bus.disable_torque(motors=LEADER_NAMES)
    print(f"Reset. Reposition the object — recording resumes in {reset_seconds}s...")
    time.sleep(reset_seconds)

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Record teleoperated demonstrations into a LeRobotDataset")
    parser.add_argument("--repo-id",  required=True, help="e.g. hexarm/pick_and_place")
    parser.add_argument("--task",     required=True, help="Single-sentence task description")
    parser.add_argument("--episodes", type=int, default=DEFAULT_EPISODES)
    parser.add_argument("--fps",      type=int, default=DEFAULT_FPS)
    parser.add_argument("--reset-seconds", type=int, default=DEFAULT_RESET_SECONDS)
    parser.add_argument("--port",     default=DEFAULT_PORT)
    parser.add_argument("--overhead-index", type=int, default=DEFAULT_OVERHEAD_INDEX)
    parser.add_argument("--wrist-index",    type=int, default=DEFAULT_WRIST_INDEX)
    parser.add_argument("--nostartseq", action="store_true",
                         help="Skip the recorded startup-sequence choreography; go straight to neutral.")
    parser.add_argument("--resume", action="store_true",
                         help="Add episodes to an existing local dataset at --repo-id instead of creating a new one.")
    args = parser.parse_args()

    cal_follower = load_json(CONFIG_DIR / "calibration_follower.json")
    cal_leader   = load_json(CONFIG_DIR / "calibration_leader.json")
    neutral      = load_json(CONFIG_DIR / "neutral.json")
    sequence     = None if args.nostartseq else load_json(CONFIG_DIR / "startup_sequence.json")

    bus = build_bus(args.port, cal_follower, cal_leader)
    bus.connect()
    print(f"Connected to {args.port}  ({len(bus.motors)} motors)")

    cameras = connect_cameras(args.overhead_index, args.wrist_index, args.fps)

    # LeRobot's own AsyncImageWriter guidance is 4 threads *per camera*, not
    # 4 total shared across all cameras — undersizing this leaves a growing
    # backlog of unwritten PNGs queued during recording (queue.put() never
    # blocks), which then stalls save_episode()'s queue.join() at episode end
    # for however long the backlog takes to drain, with zero console feedback
    # in the meantime.
    image_writer_threads = 4 * len(cameras)

    # Everything below can fail mid-setup (e.g. a stale dataset dir, a bus
    # fault) — once cameras/bus are connected, cleanup must run regardless,
    # or their background threads get torn down mid native call on the way
    # out (same failure mode the camera_preview.py Ctrl-C bug hit).
    dataset = None
    try:
        if args.resume:
            dataset = LeRobotDataset.resume(
                repo_id=args.repo_id,
                root=HF_LEROBOT_HOME / args.repo_id,
                image_writer_threads=image_writer_threads,
            )
            print(f"Resuming dataset: {dataset.root} ({dataset.num_episodes} episode(s) recorded so far)")
        else:
            dataset = LeRobotDataset.create(
                repo_id=args.repo_id,
                fps=args.fps,
                features=build_dataset_features(cameras),
                robot_type="hexarm",
                image_writer_threads=image_writer_threads,
            )
            print(f"Dataset created: {dataset.root}")

        # Derived from the dataset's own declared feature shape rather than
        # the RECORD_WIDTH/RECORD_HEIGHT constants directly — a resumed
        # dataset may already have episodes locked in at a different
        # resolution (e.g. one created before this recording size existed),
        # and writing frames at a shape that doesn't match the dataset's
        # schema silently produces uncommitted "phantom" episodes: LeRobot's
        # writer advances its episode counter before the mismatched
        # data/video actually fails to merge, corrupting meta/info.json's
        # totals without saving anything. cv2.resize wants (width, height);
        # feature shape is (height, width, channels).
        record_sizes = {
            name: (
                dataset.features[f"{OBS_STR}.images.{name}"]["shape"][1],
                dataset.features[f"{OBS_STR}.images.{name}"]["shape"][0],
            )
            for name in cameras
        }

        # Same startup ritual as teleop.py: both arms enabled -> neutral -> (optionally)
        # recorded sequence -> neutral, then leader goes free for the operator.
        safe_enable_torque(bus)
        print("Both arms torque: ON")
        neutral_all = {f"follower_{k}": v for k, v in neutral.items()}
        neutral_all.update({f"leader_{k}": v for k, v in neutral.items()})
        if args.nostartseq:
            go_neutral(bus, neutral_all)
        else:
            run_startup_sequence(bus, neutral_all, sequence)
        bus.disable_torque(motors=LEADER_NAMES)
        print("Leader torque: OFF  (move freely)\n")

        with VideoEncodingManager(dataset):
            recorded = 0
            while recorded < args.episodes:
                print(f"\n=== Episode {recorded + 1}/{args.episodes} this session "
                      f"(dataset total after this: {dataset.num_episodes + 1}) ===")
                outcome = record_episode(bus, cameras, dataset, args.task, args.fps, record_sizes)
                print("Flushing image writer queue... (can take several seconds — do not press keys again)")

                if outcome == "redo":
                    dataset.clear_episode_buffer()
                    print("Discarded — recording this episode again.")
                    reset_environment(bus, neutral_all, args.reset_seconds)
                    continue

                if outcome == "stop":
                    dataset.clear_episode_buffer()
                    print("Aborted — stopping session.")
                    break

                dataset.save_episode()
                recorded += 1
                print(f"Saved episode {recorded}/{args.episodes} this session "
                      f"(dataset total: {dataset.num_episodes}).")

                if recorded < args.episodes:
                    reset_environment(bus, neutral_all, args.reset_seconds)

            if recorded == args.episodes:
                print("\nAll episodes recorded — returning both arms to neutral...")
                safe_enable_torque(bus)
                go_neutral(bus, neutral_all)
    finally:
        for cam in cameras.values():
            cam.disconnect()
        bus.disable_torque()
        bus.disconnect()
        if dataset is not None:
            dataset.finalize()
            print(f"\nRecorded {dataset.num_episodes} episode(s) to {dataset.root}. Disconnected.")
        else:
            print("\nSetup failed before the dataset was ready — cameras/bus disconnected, nothing recorded.")


if __name__ == "__main__":
    main()
