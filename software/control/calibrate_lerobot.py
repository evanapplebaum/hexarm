#!/usr/bin/env python3
"""
calibrate_lerobot.py — LeRobot calibration for leader or follower arm

Workflow (per joint):
  1. Clears any existing homing offsets from servo EPROM (clean slate so
     Present_Position == raw encoder value when set_half_turn_homings runs).
  2. configure_motors() — clears Phase register bit so Present_Position is
     reported as single-turn mod-4096 (required for correct homing).
  3. Per joint:
     a. User moves joint to the CENTER of its physical travel arc.
     b. set_half_turn_homings() — reads current raw position, writes
        Homing_Offset = 2047 - raw_center. The encoder seam (0↔4095 jump)
        is relocated to the dead gap opposite center, so the full travel arc
        becomes a contiguous range in 0–4095.
     c. User sweeps joint to both physical stops.
     d. record_ranges_of_motion() — reads Present_Position live (already in
        homed frame). Both limits land positive, no wrap-around artifact.
  4. Builds MotorCalibration from the recorded ranges and writes to EPROM + JSON.

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
    """Return a dict of motor name → Motor for the first n_joints of the arm."""
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
    """Write Goal_Position = Present_Position before enabling torque.
    Prevents servos from snapping to a stale goal from a previous run."""
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

    motors   = build_motors(args.arm, args.joints)
    out_path = CONFIG_DIR / f"calibration_{args.arm}.json"

    print(f"Calibrating {args.arm} arm — {args.joints} joint(s)")
    print(f"Motor IDs: { {n: m.id for n, m in motors.items()} }\n")

    bus = FeetechMotorsBus(port=args.port, motors=motors)
    bus.connect()
    print(f"Connected to {args.port}")

    # ── Step 1: Clear existing homing offsets ─────────────────────────────
    # Previous calibration runs may have written offsets to EPROM. Zero them
    # so Present_Position == raw encoder value when set_half_turn_homings runs.
    print("\nStep 1: Clearing existing homing offsets (clean slate)...")
    for name in motors:
        bus.write("Homing_Offset", name, 0, normalize=False)
    print("  Homing offsets cleared.")

    # ── Step 2: Per-joint calibration ─────────────────────────────────────
    # configure_motors() clears the Phase register bit (0x10) so the servo
    # reports Present_Position as single-turn mod-4096 — required for
    # set_half_turn_homings to compute the correct seam offset.
    bus.disable_torque()
    bus.configure_motors()

    homing_offsets: dict[str, int] = {}
    homed_mins:     dict[str, int] = {}
    homed_maxes:    dict[str, int] = {}

    print("\nStep 2: Per-joint calibration.")
    print("  For each joint: move to center, then sweep both stops.\n")

    for name in motors:
        # Phase A — center the joint, then write the homing offset.
        # set_half_turn_homings reads Present_Position (raw, since offset=0)
        # and writes Homing_Offset = 2047 - raw_center to servo EPROM.
        # After this, Present_Position(center) == 2047, and the encoder seam
        # sits in the dead gap on the far side of the arc.
        input(f"  [{name}] Move to the CENTER of this joint's travel arc. Press Enter...")
        offsets = bus.set_half_turn_homings([name])
        homing_offsets[name] = int(offsets[name])
        print(f"    → homing_offset = {homing_offsets[name]}")

        # Phase B — sweep to both physical stops.
        # record_ranges_of_motion reads Present_Position live (now in homed
        # frame) and tracks min/max until Enter is pressed. Because the seam
        # is parked in the dead gap, the full travel arc is contiguous and
        # both limits land in 0–4095 with no wrap-around.
        print(f"  [{name}] Sweep to BOTH physical stops. Press Enter when done.")
        mins, maxes = bus.record_ranges_of_motion(motors=[name])
        homed_mins[name]  = int(mins[name])
        homed_maxes[name] = int(maxes[name])
        span = homed_maxes[name] - homed_mins[name]
        print(f"    → min={homed_mins[name]}  max={homed_maxes[name]}  "
              f"span={span} counts ({span / 4096 * 360:.1f}°)\n")

    print("Homed ranges (used for normalization):")
    for name in motors:
        print(f"  {name:<16}  min={homed_mins[name]}  max={homed_maxes[name]}")

    # ── Step 3: Build and write calibration ───────────────────────────────
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
