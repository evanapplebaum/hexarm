#!/usr/bin/env python3
"""
record_neutral.py — Capture the current arm pose as the neutral (rest) pose.

Positions are saved normalized (0–100) using the existing calibration, so the
values remain valid across recalibrations. Load calibration first — if no
calibration file exists for the arm, run calibrate_lerobot.py first.

Usage (from hexarm root, conda lerobot env):
  conda activate lerobot
  python software/calibration/record_neutral.py --arm follower
  python software/calibration/record_neutral.py --arm leader

Arguments:
  --arm    follower | leader  (required)
  --port   serial port (default: /dev/ttyACM0)

Output:
  software/config/neutral_follower.json
  software/config/neutral_leader.json
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
    parser = argparse.ArgumentParser(description="Capture current arm pose as neutral")
    parser.add_argument("--arm",  required=True, choices=["leader", "follower"])
    parser.add_argument("--port", default=DEFAULT_PORT)
    args = parser.parse_args()

    motors     = build_motors(args.arm)
    calibration = load_calibration(args.arm)
    out_path   = CONFIG_DIR / f"neutral_{args.arm}.json"

    bus = FeetechMotorsBus(port=args.port, motors=motors, calibration=calibration)
    bus.connect()
    print(f"Connected to {args.port}")

    bus.disable_torque()
    print(f"\nTorque disabled. Pose the {args.arm} arm in its neutral/rest position.")
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
