#!/usr/bin/env python3
"""
record_neutral.py — Capture the follower arm's pose as the shared neutral
(rest) pose for BOTH arms.

Position is saved normalized (0–100) using the follower's calibration.
go_neutral.py then drives both arms to this exact same normalized pose —
since the arms are physically identical with drive_mode=0, matching
normalized values means matching physical poses (the same invariant
teleop.py's 1:1 leader→follower mapping already relies on). Capturing one
shared pose from the follower — instead of posing each arm separately —
is what prevents the follower from snapping to the leader's position the
instant teleop drops leader torque: two independently hand-posed neutrals
are never bit-identical, so teleop used to start with a small offset
between them.

Load calibration first — if no calibration file exists for the follower,
run calibrate_lerobot.py first.

Usage (from hexarm root, conda lerobot env):
  source /data/lerobot-env/bin/activate
  python software/calibration/record_neutral.py

Arguments:
  --port   serial port (default: /dev/ttyACM0)

Output:
  software/config/neutral.json
"""

import argparse
import json
import dataclasses
from pathlib import Path

from lerobot.motors.feetech import FeetechMotorsBus
from lerobot.motors.motors_bus import Motor, MotorCalibration, MotorNormMode

# ── Constants ─────────────────────────────────────────────────────────────────

JOINT_NAMES = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]

ARM_ID_OFFSET = {"follower": 0, "leader": 6}
DEFAULT_PORT  = "/dev/ttyACM0"
CONFIG_DIR    = Path("software/config")

# ── Helpers ───────────────────────────────────────────────────────────────────

def build_motors(arm: str) -> dict[str, Motor]:
    """Return all 6 motors for the arm."""
    id_offset = ARM_ID_OFFSET[arm]
    return {
        JOINT_NAMES[i]: Motor(
            id=i + 1 + id_offset,
            model="sts3215",
            norm_mode=MotorNormMode.RANGE_0_100,
        )
        for i in range(6)
    }


def load_calibration(arm: str) -> dict[str, MotorCalibration]:
    """Load calibration from JSON backup. Raises if file doesn't exist."""
    cal_path = CONFIG_DIR / f"calibration_{arm}.json"
    if not cal_path.exists():
        raise FileNotFoundError(
            f"No calibration file found at {cal_path}. "
            f"Run calibrate_lerobot.py --arm {arm} first."
        )
    with open(cal_path) as f:
        raw = json.load(f)
    return {name: MotorCalibration(**data) for name, data in raw.items()}

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture the follower's pose as the shared neutral for both arms")
    parser.add_argument("--port", default=DEFAULT_PORT)
    args = parser.parse_args()

    motors      = build_motors("follower")
    calibration = load_calibration("follower")
    out_path    = CONFIG_DIR / "neutral.json"

    bus = FeetechMotorsBus(port=args.port, motors=motors, calibration=calibration)
    bus.connect()
    print(f"Connected to {args.port}")

    bus.disable_torque()
    print("\nTorque disabled. Pose the follower arm in its neutral/rest position.")
    print("(go_neutral.py will drive the leader to this exact same normalized pose.)")
    input("Press Enter to capture...\n")

    positions = bus.sync_read("Present_Position", normalize=True)
    positions = {name: round(float(pos), 2) for name, pos in positions.items()}

    print("Captured positions (normalized 0–100):")
    for name, pos in positions.items():
        print(f"  {name:<16}  {pos:.2f}")

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(positions, f, indent=2)
    print(f"\nSaved to {out_path}")

    bus.disconnect()


if __name__ == "__main__":
    main()
