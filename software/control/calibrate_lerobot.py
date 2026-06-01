#!/usr/bin/env python3
"""
calibrate_lerobot.py — LeRobot calibration for leader or follower arm

Workflow:
  1. Clears any existing homing offsets from servo EPROM (clean slate).
  2. Sweeps each joint individually to its physical stops (avoids gravity
     swinging unsupported joints during multi-joint sweep).
  3. Computes homing offset per joint so center of travel = 2047.
  4. Writes calibration to servo EPROM and saves JSON backup.

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

# creates dictionary of which motor ids are to be calibrated
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
        bus.write("Goal_Position", name, int(pos), normalize=False)
    bus.enable_torque()

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="LeRobot calibration for leader OR follower arm")
    parser.add_argument("--arm",    required=True, choices=["leader", "follower"])
    parser.add_argument("--joints", type=int, default=6,
                        help="Number of joints to calibrate (default: 6)")
    parser.add_argument("--port",   default=DEFAULT_PORT)
    args = parser.parse_args()

    if not 1 <= args.joints <= 6:
        parser.error("--joints must be between 1 and 6")

    # use motors helper; specify where to write calibration values
    motors   = build_motors(args.arm, args.joints)
    out_path = CONFIG_DIR / f"calibration_{args.arm}.json"

    print(f"Calibrating {args.arm} arm — {args.joints} joint(s)")
    print(f"Motor IDs: { {n: m.id for n, m in motors.items()} }\n")

    # bus (from feetech.py) defines which port to talk to which motors on (based on provided ids) 
    bus = FeetechMotorsBus(port=args.port, motors=motors)
    bus.connect()
    print(f"Connected to {args.port}")

    # ── Step 1: Clear existing homing offsets ─────────────────────────────
    # Previous calibration attempts may have written offsets to EPROM.
    # Zero them out so all reads are raw encoder values (0–4095).
    print("\nStep 1: Clearing existing homing offsets (clean slate)...")
    for name in motors:
        bus.write("Homing_Offset", name, 0, normalize=False)
    print("  Homing offsets cleared.")

    # ── Step 2: Per-joint sweep ────────────────────────────────────────────
    # Sweep one joint at a time. This prevents unsupported joints from
    # swinging freely under gravity and recording spurious extremes.
    print("\nStep 2: Per-joint sweep.")
    print("  For each joint: move it to its full min AND max physical stop.")
    print("  Hold other joints still. Press Enter when done with each joint.\n")

    bus.disable_torque()
    bus.configure_motors()

    raw_mins: dict[str, int] = {}
    raw_maxes: dict[str, int] = {}

    for name in motors:
        input(f"  [{name}] Move to min and max. Press Enter when done...")
        mins, maxes = bus.record_ranges_of_motion(motors=[name])
        raw_mins[name]  = int(mins[name])
        raw_maxes[name] = int(maxes[name])
        span = raw_maxes[name] - raw_mins[name]
        print(f"    → min={raw_mins[name]}  max={raw_maxes[name]}  "
              f"span={span} counts ({span / 4096 * 360:.1f}°)\n")

    print("Ranges recorded:")
    for name in motors:
        print(f"  {name:<16}  min={raw_mins[name]}  max={raw_maxes[name]}")

    # ── Step 3: Compute homing offsets ────────────────────────────────────
    # Shift each joint so its center of travel reads as 2047.
    # This ensures both stops are well within the 0–4095 register range.
    homing_offsets: dict[str, int] = {}
    for name in motors:
        raw_mid = (raw_mins[name] + raw_maxes[name]) // 2
        homing_offsets[name] = 2047 - raw_mid

    print("\nStep 3: Writing homing offsets (center of travel → 2047)...")
    for name, offset in homing_offsets.items():
        bus.write("Homing_Offset", name, offset, normalize=False)
        print(f"  {name:<16} raw_mid={(raw_mins[name]+raw_maxes[name])//2}  offset={offset}")

    # ── Step 4: Compute homed limits ──────────────────────────────────────
    # Homed position = raw + homing_offset.
    # Apply same offset to the raw limits recorded in step 2.
    homed_mins  = {n: raw_mins[n]  + homing_offsets[n] for n in motors}
    homed_maxes = {n: raw_maxes[n] + homing_offsets[n] for n in motors}

    print("\nHomed ranges (used for normalization):")
    for name in motors:
        print(f"  {name:<16}  min={homed_mins[name]}  max={homed_maxes[name]}")

    # ── Step 5: Build and write calibration ───────────────────────────────
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

    print("\nStep 4: Writing calibration to servo EPROM registers...")
    bus.write_calibration(calibration)
    print("Calibration written.")

    # ── Step 6: Save JSON backup ───────────────────────────────────────────
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
