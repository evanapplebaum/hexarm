#!/usr/bin/env python3
"""
calibrate_lerobot.py — LeRobot calibration for leader or follower arm

Workflow:
  1. Run this script with the arm powered and connected.
  2. Homing offsets are set at the arm's current position (arbitrary).
  3. Torque disables — sweep every joint to its PHYSICAL mechanical stops (min AND max).
     Do NOT force past where the arm naturally stops.
  4. Press Enter when done sweeping.
  5. Calibration is written to servo EPROM and saved as JSON backup.

  Note: Neutral pose is defined separately via capture_neutral.py.

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


def safe_enable_torque(bus: FeetechMotorsBus) -> None:
    """Set Goal_Position = Present_Position before enabling torque.
    Prevents the servo from snapping to a stale goal from a previous run."""
    positions = bus.sync_read("Present_Position", normalize=False)
    for name, pos in positions.items():
        bus.write("Goal_Position", name, int(pos), normalize=False)
    bus.enable_torque()

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

    # ── Step 1: Set homing offsets BEFORE sweep ────────────────────────────
    # Arm is wherever it is — position here is arbitrary.
    # Homing shifts the coordinate frame so the sweep records clean values.
    print("\nStep 1: Setting homing offsets at current position...")
    bus.disable_torque()
    homing_offsets = bus.set_half_turn_homings()
    print("Homing offsets written:")
    for name, offset in homing_offsets.items():
        print(f"  {name:<16} offset={offset}")

    # ── Step 2: Sweep to find physical limits (in homed frame) ────────────
    print("\nStep 2: Sweep — finding range of motion.")
    print("  Move every joint slowly to its physical mechanical stop — min AND max.")
    print("  Only go as far as the arm naturally stops. Do NOT force past stops.")
    print("  Press Enter when all joints have been swept.\n")
    input("  Press Enter to start recording (torque already off)...")

    mins, maxes = bus.record_ranges_of_motion()

    print("\nRanges recorded (homed frame):")
    for name in motors:
        lo, hi = mins[name], maxes[name]
        span   = hi - lo
        print(f"  {name:<16}  min={lo}  max={hi}  span={span} counts ({span/4096*360:.1f}°)")

    # Warn if any joint captured the full encoder range (likely swept past stops)
    for name in motors:
        if mins[name] <= 10 or maxes[name] >= 4085:
            print(f"\n  ⚠️  {name}: range looks like full encoder range — "
                  f"did you sweep past the mechanical stop?")

    # ── Step 3: Build and write calibration ───────────────────────────────
    # mins/maxes from record_ranges_of_motion are already in the homed frame.
    calibration: dict[str, MotorCalibration] = {
        name: MotorCalibration(
            id=motor.id,
            drive_mode=DRIVE_MODE,
            homing_offset=homing_offsets[name],
            range_min=int(mins[name]),
            range_max=int(maxes[name]),
        )
        for name, motor in motors.items()
    }

    print("\nStep 3: Writing calibration to servo EPROM registers...")
    bus.write_calibration(calibration)
    print("Calibration written.")

    # ── Step 4: Save JSON backup ───────────────────────────────────────────
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    backup = {name: dataclasses.asdict(cal) for name, cal in calibration.items()}
    with open(out_path, "w") as f:
        json.dump(backup, f, indent=2)
    print(f"JSON backup saved to {out_path}")

    safe_enable_torque(bus)
    bus.disconnect()
    print("\nDone. Run capture_neutral.py next to define the rest pose.")


if __name__ == "__main__":
    main()
