#!/usr/bin/env python3
"""
calibrate_lerobot.py — LeRobot calibration for leader or follower arm

Workflow:
  1. Run this script with the arm powered and connected.
  2. Torque disables — sweep every joint to its full physical min AND max.
  3. Press Enter when done.
  4. Homing offsets are set at the arm's current position (arbitrary — doesn't matter).
  5. Calibration is written to servo EPROM and saved as JSON backup.

  Note: This script only records joint limits. Neutral pose is defined separately
  via capture_neutral.py after both arms are calibrated.

Usage (from hexarm root, conda lerobot env):
  conda activate lerobot
  python software/control/calibrate_lerobot.py --arm follower
  python software/control/calibrate_lerobot.py --arm leader --joints 4

Arguments:
  --arm      follower | leader  (required)
  --joints   number of joints to calibrate, starting from joint 1 (default: 6)
  --port     serial port (default: /dev/ttyACM0)

Output:
  software/config/calibration_follower.json
  software/config/calibration_leader.json
"""

import argparse
import json
import dataclasses
from pathlib import Path

from lerobot.motors.feetech import FeetechMotorsBus
from lerobot.motors.motors_bus import Motor, MotorCalibration, MotorNormMode

# ── Motor definitions ─────────────────────────────────────────────────────────

JOINT_NAMES = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]

ARM_ID_OFFSET = {"follower": 0, "leader": 6}
DRIVE_MODE    = 0
DEFAULT_PORT  = "/dev/ttyACM0"
CONFIG_DIR    = Path("software/config")

# ── Helpers ───────────────────────────────────────────────────────────────────

def build_motors(arm: str, n_joints: int) -> dict[str, Motor]:
    id_offset = ARM_ID_OFFSET[arm]
    return {
        JOINT_NAMES[i]: Motor(
            id=i + 1 + id_offset,
            model="sts3215",
            norm_mode=MotorNormMode.RANGE_0_100,
        )
        for i in range(n_joints)
    }

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="LeRobot calibration for leader or follower arm")
    parser.add_argument("--arm",    required=True, choices=["leader", "follower"])
    parser.add_argument("--joints", type=int, default=6,
                        help="Number of joints to calibrate (default: 6)")
    parser.add_argument("--port",   default=DEFAULT_PORT)
    args = parser.parse_args()

    if not 1 <= args.joints <= 6:
        parser.error("--joints must be between 1 and 6")

    motors   = build_motors(args.arm, args.joints)
    out_path = CONFIG_DIR / f"calibration_{args.arm}.json"

    print(f"Calibrating {args.arm} arm — {args.joints} joint(s)")
    print(f"Motor IDs: { {n: m.id for n, m in motors.items()} }\n")

    bus = FeetechMotorsBus(port=args.port, motors=motors)
    bus.connect()
    print(f"Connected to {args.port}")

    # ── Step 1: Sweep to find physical limits ──────────────────────────────
    print("\nStep 1: Sweep — finding range of motion.")
    print("  Move every joint slowly to its FULL physical minimum AND maximum.")
    print("  Take your time — this defines the joint limits.")
    print("  Press Enter when done.\n")
    input("  Press Enter to disable torque and start recording...")

    bus.disable_torque()
    raw_mins, raw_maxes = bus.record_ranges_of_motion()

    print("\nRaw ranges recorded:")
    for name in motors:
        print(f"  {name:<16}  min={raw_mins[name]}  max={raw_maxes[name]}")

    # ── Step 2: Set homing offsets at current position ────────────────────
    # Position is arbitrary here — normalization handles the rest.
    print("\nStep 2: Setting homing offsets at current position...")
    bus.enable_torque()
    homing_offsets = bus.set_half_turn_homings()
    print("Homing offsets written:")
    for name, offset in homing_offsets.items():
        print(f"  {name:<16} offset={offset}")

    # ── Step 3: Derive homed min/max ──────────────────────────────────────
    homed_mins  = {n: raw_mins[n]  + homing_offsets[n] for n in motors}
    homed_maxes = {n: raw_maxes[n] + homing_offsets[n] for n in motors}

    # ── Step 4: Build and write calibration ───────────────────────────────
    calibration: dict[str, MotorCalibration] = {
        name: MotorCalibration(
            id=motor.id,
            drive_mode=DRIVE_MODE,
            homing_offset=homing_offsets[name],
            range_min=homed_mins[name],
            range_max=homed_maxes[name],
        )
        for name, motor in motors.items()
    }

    print("\nStep 3: Writing calibration to servo EPROM registers...")
    bus.write_calibration(calibration)
    print("Calibration written.")

    # ── Step 5: Save JSON backup ───────────────────────────────────────────
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    backup = {name: dataclasses.asdict(cal) for name, cal in calibration.items()}
    with open(out_path, "w") as f:
        json.dump(backup, f, indent=2)
    print(f"JSON backup saved to {out_path}")

    bus.disable_torque()
    bus.disconnect()
    print("\nDone. Run capture_neutral.py next to define the rest pose.")


if __name__ == "__main__":
    main()
