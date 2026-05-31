#!/usr/bin/env python3
"""
calibrate_lerobot.py — LeRobot calibration for follower arm

Workflow:
  1. Position the arm at its neutral/center pose using keyboard_follower.py first.
  2. Run this script (arm must already be at neutral when it starts).
  3. Script sets homing offsets (current position → 2047 on each motor).
  4. Torque disables — move each joint by hand to its min and max limits.
  5. Press Enter when all joints have been swept.
  6. Calibration is written to servo EPROM registers and saved as JSON backup.

Usage (from hexarm root, conda lerobot env):
  conda activate lerobot
  python software/control/calibrate_lerobot.py [--port /dev/ttyACM0]

Output:
  software/config/calibration_follower.json  ← backup of calibration data
"""

import argparse
import json
import dataclasses
from pathlib import Path

from lerobot.motors.feetech import FeetechMotorsBus
from lerobot.motors.motors_bus import Motor, MotorCalibration, MotorNormMode

# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_PORT    = "/dev/ttyACM0"
CALIBRATION_OUT = Path("software/config/calibration_follower.json")

# Follower arm — IDs 1–6
MOTORS: dict[str, Motor] = {
    "shoulder_pan":  Motor(id=1, model="sts3215", norm_mode=MotorNormMode.RANGE_0_100),
    "shoulder_lift": Motor(id=2, model="sts3215", norm_mode=MotorNormMode.RANGE_0_100),
    "elbow_flex":    Motor(id=3, model="sts3215", norm_mode=MotorNormMode.RANGE_0_100),
    "wrist_flex":    Motor(id=4, model="sts3215", norm_mode=MotorNormMode.RANGE_0_100),
    "wrist_roll":    Motor(id=5, model="sts3215", norm_mode=MotorNormMode.RANGE_0_100),
    "gripper":       Motor(id=6, model="sts3215", norm_mode=MotorNormMode.RANGE_0_100),
}

# drive_mode=0 for all follower motors (no axis mirroring — keyboard control only)
DRIVE_MODE = 0

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="LeRobot calibration for follower arm")
    parser.add_argument("--port", default=DEFAULT_PORT, help="Serial port (default: /dev/ttyACM0)")
    args = parser.parse_args()

    bus = FeetechMotorsBus(port=args.port, motors=MOTORS)
    bus.connect()
    print(f"Connected to {args.port}")

    # ── Step 1: Set homing offsets ─────────────────────────────────────────
    # Arm must be at neutral pose now. Each motor's current position → 2047.
    print("\nStep 1: Setting homing offsets (arm should be at neutral pose)...")
    homing_offsets = bus.set_half_turn_homings()
    print("Homing offsets set:")
    for name, offset in homing_offsets.items():
        print(f"  {name:<16} offset={offset}")

    # ── Step 2: Record ranges of motion ───────────────────────────────────
    print("\nStep 2: Recording ranges of motion.")
    print("  Torque will be disabled. Move each joint to its FULL min and max by hand.")
    print("  Press Enter when done.\n")
    input("  Press Enter to disable torque and start recording...")

    bus.disable_torque()
    mins, maxes = bus.record_ranges_of_motion()
    bus.enable_torque()

    print("\nRanges recorded:")
    for name in MOTORS:
        print(f"  {name:<16} min={mins[name]}  max={maxes[name]}")

    # ── Step 3: Build calibration dict ────────────────────────────────────
    calibration: dict[str, MotorCalibration] = {
        name: MotorCalibration(
            id=motor.id,
            drive_mode=DRIVE_MODE,
            homing_offset=homing_offsets[name],
            range_min=mins[name],
            range_max=maxes[name],
        )
        for name, motor in MOTORS.items()
    }

    # ── Step 4: Write to servo EPROM + cache ──────────────────────────────
    print("\nStep 3: Writing calibration to servo EPROM registers...")
    bus.write_calibration(calibration)
    print("Calibration written.")

    # ── Step 5: Save JSON backup ───────────────────────────────────────────
    CALIBRATION_OUT.parent.mkdir(parents=True, exist_ok=True)
    backup = {name: dataclasses.asdict(cal) for name, cal in calibration.items()}
    with open(CALIBRATION_OUT, "w") as f:
        json.dump(backup, f, indent=2)
    print(f"JSON backup saved to {CALIBRATION_OUT}")

    bus.disconnect()
    print("\nDone. Disconnected.")


if __name__ == "__main__":
    main()
