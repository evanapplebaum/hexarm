#!/usr/bin/env python3
"""
calibrate_lerobot.py — LeRobot calibration for leader or follower arm

Workflow (per joint):
  1. configure_motors() — clears Phase bit so Present_Position reports in
     single-turn mod-4096 mode. Required for wrap-around joints.
  2. Clear any stale homing offsets from EPROM (clean slate).
  3. For each joint:
     a. User moves joint to CENTER of its travel range.
     b. set_half_turn_homings() — servo reads current position, writes
        Homing_Offset = 2047 - present_pos. Parks the encoder seam in the
        dead gap (the arc the joint never travels through).
     c. User sweeps joint to both physical stops.
     d. record_ranges_of_motion() — records min/max in the now-homed frame.
        No wrap-around issue because the seam is already in the dead gap.
  4. write_calibration() — writes Homing_Offset + Min/Max_Position_Limit
     to servo EPROM and saves JSON backup.

  Note: Neutral pose is defined separately via record_neutral.py.

Usage (from hexarm root, conda lerobot env):
  conda activate lerobot
  python software/calibration/calibrate_lerobot.py --arm follower
  python software/calibration/calibrate_lerobot.py --arm leader --joints 4

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
    Prevents snapping to a stale goal from a previous run."""
    positions = bus.sync_read("Present_Position", normalize=False)
    for name, pos in positions.items():
        bus.write("Goal_Position", name, int(float(pos)), normalize=False)
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

    # ── Step 1: Configure motors ──────────────────────────────────────────
    # Clears the Phase bit (bit 4 of the Mode register) on each servo so
    # Present_Position reports in single-turn mod-4096 mode. Without this,
    # wrap-around joints may report incorrectly.
    print("\nStep 1: Configuring motors (clearing Phase bit)...")
    bus.configure_motors()
    print("  Done.")

    # ── Step 2: Clear stale homing offsets ────────────────────────────────
    # Zero out any offsets from previous calibration runs so all reads
    # reflect raw encoder values (0–4095) during the homing step.
    print("\nStep 2: Clearing stale homing offsets...")
    for name in motors:
        bus.write("Homing_Offset", name, 0, normalize=False)
    print("  Done.")

    # ── Step 3: Per-joint calibration ─────────────────────────────────────
    # For each joint:
    #   (a) Home at center — parks the encoder seam in the dead gap.
    #   (b) Sweep both stops — records min/max in the safe homed frame.
    print("\nStep 3: Per-joint calibration.")
    print("  For each joint you will be prompted twice:")
    print("  First: move to CENTER of travel range, press Enter.")
    print("  Then:  sweep to BOTH physical stops, press Enter.\n")

    bus.disable_torque()

    homing_offsets: dict[str, int] = {}
    range_mins:     dict[str, int] = {}
    range_maxes:    dict[str, int] = {}

    for name in motors:
        # (a) Home at center
        input(f"  [{name}] Move to CENTER of travel. Press Enter to set homing offset...")
        offsets = bus.set_half_turn_homings(motors=[name])
        homing_offsets[name] = int(offsets[name])
        print(f"    → Homing offset written: {homing_offsets[name]}")

        # (b) Record ranges in homed frame
        input(f"  [{name}] Sweep to BOTH stops. Press Enter when done...")
        mins, maxes = bus.record_ranges_of_motion(motors=[name])
        range_mins[name]   = int(mins[name])
        range_maxes[name]  = int(maxes[name])
        span = range_maxes[name] - range_mins[name]
        print(f"    → min={range_mins[name]}  max={range_maxes[name]}  "
              f"span={span} counts ({span / 4096 * 360:.1f}°)\n")

    print("Calibration summary:")
    for name in motors:
        print(f"  {name:<16}  offset={homing_offsets[name]:>5}  "
              f"min={range_mins[name]:>4}  max={range_maxes[name]:>4}")

    # ── Step 4: Build and write calibration ───────────────────────────────
    calibration: dict[str, MotorCalibration] = {
        name: MotorCalibration(
            id=motor.id,
            drive_mode=DRIVE_MODE,
            homing_offset=homing_offsets[name],
            range_min=range_mins[name],
            range_max=range_maxes[name],
        )
        for name, motor in motors.items()
    }

    print("\nStep 4: Writing calibration to servo EPROM...")
    bus.write_calibration(calibration)
    print("  Done.")

    # ── Step 5: Save JSON backup ───────────────────────────────────────────
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    backup = {name: dataclasses.asdict(cal) for name, cal in calibration.items()}
    with open(out_path, "w") as f:
        json.dump(backup, f, indent=2)
    print(f"  JSON backup saved to {out_path}")

    safe_enable_torque(bus)
    bus.disconnect()
    print("\nDone. Run record_neutral.py next to define the rest pose.")


if __name__ == "__main__":
    main()
