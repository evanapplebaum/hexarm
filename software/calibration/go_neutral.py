#!/usr/bin/env python3
"""
go_neutral.py — Move arm slowly to the captured neutral pose.

Sets Maximum_Velocity_Limit and Acceleration on each joint so the servo
hardware profiles the move, then commands Goal_Position. Polls
Present_Velocity until each joint stops before moving to the next.

Usage (from hexarm root, conda lerobot env):
  conda activate lerobot
  python software/calibration/go_neutral.py --arm follower
  python software/calibration/go_neutral.py --arm leader --velocity 200 --acceleration 30
  python software/calibration/go_neutral.py --arm follower --order 3 1 2 4 5 6

Arguments:
  --arm           follower | leader  (required)
  --velocity      max joint speed in counts/s (default: 100 ≈ 8.8°/s)
  --acceleration  ramp rate in counts/s² (default: 20)
  --order         joint index numbers (1–6) in the order to move them.
                  If omitted, all joints move simultaneously.
  --port          serial port (default: /dev/ttyACM0)
"""

import argparse
import json
import time
from pathlib import Path

from lerobot.motors.feetech import FeetechMotorsBus
from lerobot.motors.motors_bus import Motor, MotorCalibration, MotorNormMode

# ── Constants ─────────────────────────────────────────────────────────────────

JOINT_NAMES   = ["shoulder_pan", "shoulder_lift", "elbow_flex",
                 "wrist_flex", "wrist_roll", "gripper"]
ARM_ID_OFFSET = {"follower": 0, "leader": 6}
DEFAULT_PORT  = "/dev/ttyACM0"
CONFIG_DIR    = Path("software/config")

DEFAULT_VELOCITY      = 100   # counts/s  ≈ 8.8°/s
DEFAULT_ACCELERATION  = 20    # counts/s²
VELOCITY_STOP_THRESH  = 10    # counts/s — "close enough to stopped"
POLL_HZ               = 20

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing config file: {path}")
    with open(path) as f:
        return json.load(f)


def build_motors(arm: str, names: list[str]) -> dict[str, Motor]:
    id_offset = ARM_ID_OFFSET[arm]
    return {
        name: Motor(
            id=JOINT_NAMES.index(name) + 1 + id_offset,
            model="sts3215",
            norm_mode=MotorNormMode.RANGE_0_100,
        )
        for name in names
    }


def safe_enable_torque(bus: FeetechMotorsBus) -> None:
    """Write Goal_Position = Present_Position before enabling torque."""
    positions = bus.sync_read("Present_Position", normalize=True)
    bus.sync_write("Goal_Position", positions, normalize=True)
    bus.enable_torque()


def move_and_wait(bus: FeetechMotorsBus, name: str,
                  target: float, velocity: int, acceleration: int, timeout: float) -> float:
    """Command one joint to target and block until it stops. Returns elapsed time."""
    bus.write("Maximum_Velocity_Limit", name, velocity,     normalize=False)
    bus.write("Acceleration",           name, acceleration, normalize=False)
    bus.write("Goal_Position",          name, target,       normalize=True)

    t_start = time.time()
    while time.time() - t_start < timeout:
        v = bus.read("Present_Velocity", name, normalize=False)
        if abs(float(v)) < VELOCITY_STOP_THRESH:
            break
        time.sleep(1 / POLL_HZ)
    return time.time() - t_start

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Move arm to neutral pose")
    parser.add_argument("--arm",          required=True, choices=["leader", "follower"])
    parser.add_argument("--velocity",     type=int, default=DEFAULT_VELOCITY,
                        help=f"Max speed in counts/s (default: {DEFAULT_VELOCITY} ≈ 8.8°/s)")
    parser.add_argument("--acceleration", type=int, default=DEFAULT_ACCELERATION,
                        help=f"Ramp rate in counts/s² (default: {DEFAULT_ACCELERATION})")
    parser.add_argument("--order",        type=int, nargs="+", metavar="N",
                        help="Joint indices (1–6) in move order. Omit to move all at once.")
    parser.add_argument("--port",         default=DEFAULT_PORT)
    args = parser.parse_args()

    cal_data     = load_json(CONFIG_DIR / f"calibration_{args.arm}.json")
    neutral_data = load_json(CONFIG_DIR / f"neutral_{args.arm}.json")

    # Only move joints present in both files
    active_joints = [n for n in JOINT_NAMES if n in cal_data and n in neutral_data]
    skipped = [n for n in JOINT_NAMES if n not in active_joints]
    if skipped:
        print(f"Skipping joints with missing calibration or neutral: {skipped}")
    if not active_joints:
        raise RuntimeError("No joints to move — run calibrate_lerobot.py and record_neutral.py first.")

    # Resolve --order to joint names
    if args.order:
        for idx in args.order:
            if not (1 <= idx <= len(JOINT_NAMES)):
                raise ValueError(f"--order index {idx} out of range (1–{len(JOINT_NAMES)})")
        move_order = [JOINT_NAMES[i - 1] for i in args.order
                      if JOINT_NAMES[i - 1] in active_joints]
        sequential = True
    else:
        move_order = active_joints
        sequential = False

    calibration = {name: MotorCalibration(**cal_data[name]) for name in active_joints}
    neutral     = {name: float(neutral_data[name]) for name in active_joints}
    motors      = build_motors(args.arm, active_joints)

    velocity = args.velocity
    timeout  = int(4096 / velocity) + 5  # generous: full range at chosen speed + 5s buffer

    bus = FeetechMotorsBus(port=args.port, motors=motors, calibration=calibration)
    bus.connect()
    print(f"Connected to {args.port}")
    print(f"velocity={velocity} counts/s  accel={args.acceleration}  "
          f"{'sequential' if sequential else 'simultaneous'}\n")

    safe_enable_torque(bus)

    if sequential:
        # Move one joint at a time in the specified order
        for name in move_order:
            print(f"  Moving {name} → {neutral[name]:.1f}...", end=" ", flush=True)
            elapsed = move_and_wait(bus, name, neutral[name], velocity, args.acceleration, timeout)
            print(f"done ({elapsed:.2f}s)")
    else:
        # Set motion profile for all joints, then fire simultaneously
        for name in active_joints:
            bus.write("Maximum_Velocity_Limit", name, velocity,     normalize=False)
            bus.write("Acceleration",           name, args.acceleration, normalize=False)

        print(f"Moving all joints to neutral...", end=" ", flush=True)
        bus.sync_write("Goal_Position", neutral, normalize=True)

        t_start = time.time()
        while time.time() - t_start < timeout:
            velocities = bus.sync_read("Present_Velocity", normalize=False)
            if all(abs(float(v)) < VELOCITY_STOP_THRESH for v in velocities.values()):
                break
            time.sleep(1 / POLL_HZ)
        print(f"done ({time.time() - t_start:.2f}s)")

    # Restore velocity limit to 0 (= no limit) so other scripts are unaffected
    for name in active_joints:
        bus.write("Maximum_Velocity_Limit", name, 0, normalize=False)

    print("\nFinal positions:")
    final = bus.sync_read("Present_Position", normalize=True)
    for name in active_joints:
        print(f"  {name:<16}  {float(final[name]):.1f}  (target {neutral[name]:.1f})")

    bus.disconnect()


if __name__ == "__main__":
    main()
