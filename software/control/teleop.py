#!/usr/bin/env python3
"""
teleop.py — Leader-follower teleoperation.

Leader arm runs torque-free (move it by hand). Follower tracks the leader
in real time at a fixed rate using calibrated normalized positions (0–100).

Startup sequence (handled automatically):
  1. Both arms torque-enabled and moved to the shared neutral pose (the same
     normalized values on both arms — see record_neutral.py/go_neutral.py
     for why this matters: two independently-captured per-arm neutrals are
     never bit-identical, which used to make the follower snap the instant
     leader torque dropped in step 3).
  2. Recorded startup sequence played back on both arms simultaneously,
     then both arms carefully return to neutral (see run_startup_sequence.py
     and set_startup_sequence.py).
  3. Leader torque disabled — move it freely.
  4. Teleop loop starts — follower tracks leader from neutral.

Prerequisites:
  - Both arms calibrated       (software/config/calibration_*.json)
  - Neutral pose captured      (software/config/neutral.json)
  - Startup sequence recorded  (software/config/startup_sequence.json,
    via set_startup_sequence.py)

Usage (from hexarm root, conda lerobot env):
  conda activate lerobot
  python software/control/teleop.py

Ctrl-C to stop. Torque is disabled on exit.
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Add repo root (hexarm/) to path — NOT software/, which would shadow the
# pip-installed scservo_sdk with our local copy and break LeRobot imports.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from software.calibration.run_startup_sequence import run_startup_sequence  # noqa: E402

from lerobot.motors.feetech import FeetechMotorsBus
from lerobot.motors.motors_bus import Motor, MotorCalibration, MotorNormMode

# ── Constants ──────────────────────────────────────────────────────────────────

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
DEFAULT_HZ   = 50

# ── Helpers ────────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing config file: {path}")
    with open(path) as f:
        return json.load(f)


def build_bus(port: str, cal_follower: dict, cal_leader: dict) -> FeetechMotorsBus:
    """
    Construct a single FeetechMotorsBus containing all 12 motors.

    Both arms share one physical bus (/dev/ttyACM0). Motor names are prefixed
    (follower_shoulder_pan, leader_shoulder_pan, ...) so both arms can live in
    the same dict without name collisions.

    Follower IDs: 1–6   (joints 1–6 in order)
    Leader IDs:   7–12  (same joints, +6 offset)
    """
    motors: dict[str, Motor] = {}
    for i, joint in enumerate(JOINT_NAMES):
        motors[f"follower_{joint}"] = Motor(
            id=i + 1,
            model="sts3215",
            norm_mode=MotorNormMode.RANGE_0_100,
        )
        motors[f"leader_{joint}"] = Motor(
            id=i + 7,
            model="sts3215",
            norm_mode=MotorNormMode.RANGE_0_100,
        )

    calibration: dict[str, MotorCalibration] = {}
    for joint, data in cal_follower.items():
        calibration[f"follower_{joint}"] = MotorCalibration(**data)
    for joint, data in cal_leader.items():
        calibration[f"leader_{joint}"] = MotorCalibration(**data)

    return FeetechMotorsBus(port=port, motors=motors, calibration=calibration)


def safe_enable_torque(bus: FeetechMotorsBus, motor_names: list[str]) -> None:
    """
    Enable torque on the named motors without a snap-to-stale-goal.

    Reads each motor's current position and writes it as the Goal_Position
    before enabling torque. This freezes the motor in place on engage.
    """
    for name in motor_names:
        pos = bus.read("Present_Position", name, normalize=False, num_retry=3)
        bus.write("Goal_Position", name, int(float(pos)), normalize=False, num_retry=3)
    bus.enable_torque(motors=motor_names)


# ── Teleop loop ────────────────────────────────────────────────────────────────

def run_teleop(bus: FeetechMotorsBus, hz: int = DEFAULT_HZ) -> None:
    """Stream leader joint positions to the follower arm at `hz` Hz."""
    period = 1.0 / hz
    print(f"Teleop running at {hz} Hz.  Ctrl-C to stop.\n")

    while True:
        t0 = time.monotonic()

        # Read all 6 leader joint positions in one SYNC_READ transaction.
        # normalize=True applies calibration + drive_mode → values in 0–100.
        leader_pos = bus.sync_read("Present_Position", motors=LEADER_NAMES, normalize=True)

        # Map leader joint names → follower joint names (1:1 normalized).
        # drive_mode in calibration handles any physical direction inversions.
        follower_goals = {
            f"follower_{joint}": leader_pos[f"leader_{joint}"]
            for joint in JOINT_NAMES
        }

        # Send all 6 follower goals in one SYNC_WRITE transaction.
        bus.sync_write("Goal_Position", follower_goals, normalize=True)

        elapsed = time.monotonic() - t0
        time.sleep(max(0.0, period - elapsed))


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Leader-follower teleoperation")
    parser.add_argument("--port", default=DEFAULT_PORT,
                        help=f"Serial port (default: {DEFAULT_PORT})")
    parser.add_argument("--hz",   type=int, default=DEFAULT_HZ,
                        help=f"Control loop rate in Hz (default: {DEFAULT_HZ})")
    args = parser.parse_args()

    cal_follower = load_json(CONFIG_DIR / "calibration_follower.json")
    cal_leader   = load_json(CONFIG_DIR / "calibration_leader.json")
    neutral      = load_json(CONFIG_DIR / "neutral.json")
    sequence     = load_json(CONFIG_DIR / "startup_sequence.json")

    bus = build_bus(args.port, cal_follower, cal_leader)
    bus.connect()
    print(f"Connected to {args.port}  ({len(bus.motors)} motors)\n")

    # Enable torque on both arms so go_neutral can move them
    safe_enable_torque(bus, FOLLOWER_NAMES + LEADER_NAMES)
    print("Both arms torque: ON")

    # Neutral -> startup sequence -> neutral, on both arms, with identical
    # normalized targets on both — see module docstring.
    neutral_all = {f"follower_{k}": v for k, v in neutral.items()}
    neutral_all.update({f"leader_{k}": v for k, v in neutral.items()})
    run_startup_sequence(bus, neutral_all, sequence)

    # Drop leader torque — operator moves it freely from here
    bus.disable_torque(motors=LEADER_NAMES)
    print("Leader torque: OFF  (move freely)\n")

    # Follower stays torque-enabled and will immediately track the leader
    try:
        run_teleop(bus, hz=args.hz)
    except KeyboardInterrupt:
        print("\nCtrl-C — stopping.")
    finally:
        bus.disable_torque()
        bus.disconnect()
        print("Torque disabled. Disconnected.")


if __name__ == "__main__":
    main()
