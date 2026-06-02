#!/usr/bin/env python3
"""
go_neutral.py — Move arm slowly to the captured neutral pose.

Sets Max_Velocity and Acceleration on each joint so the servo hardware
profiles the move, then fires a single Goal_Position command. Polls
Present_Velocity until motion stops.

Usage (from hexarm root, conda lerobot env):
  conda activate lerobot
  python software/control/go_neutral.py --arm follower
  python software/control/go_neutral.py --arm leader --duration 3.0

Arguments:
  --arm       follower | leader  (required)
  --duration  approximate move duration in seconds (default: 2.0)
              Used to compute Max_Velocity: assumes ~2048 counts of travel.
  --port      serial port (default: /dev/ttyACM0)
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


# ── Helpers ───────────────────────────────────────────────────────────────────

# reads json file @ passed path location
# returns a 
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

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Move arm to neutral pose")
    parser.add_argument("--arm",      required=True, choices=["leader", "follower"])
    parser.add_argument("--duration", type=float, default=2.0,
                        help="Approximate move duration in seconds (default: 2.0)")
    parser.add_argument("--port",     default=DEFAULT_PORT)
    args = parser.parse_args()

    cal_data     = load_json(CONFIG_DIR / f"calibration_{args.arm}.json")
    neutral_data = load_json(CONFIG_DIR / f"neutral_{args.arm}.json")

    # Only move joints present in both files
    active_joints = [n for n in JOINT_NAMES
                     if n in cal_data and n in neutral_data]
    skipped = [n for n in JOINT_NAMES if n not in active_joints]
    if skipped:
        print(f"Skipping joints with missing calibration or neutral: {skipped}")
    if not active_joints:
        raise RuntimeError("No joints to move — run calibrate_lerobot.py and record_neutral.py first.")

    calibration = {name: MotorCalibration(**cal_data[name]) for name in active_joints}
    neutral     = {name: float(neutral_data[name]) for name in active_joints}
    motors      = build_motors(args.arm, active_joints)

    # Velocity limit derived from desired duration.
    # Clamped to [10, 2000] to avoid stalling or unsafe speeds.
    velocity = max(10, min(2000, int(TYPICAL_TRAVEL_COUNTS / args.duration)))

    bus = FeetechMotorsBus(port=args.port, motors=motors, calibration=calibration)
    bus.connect()
    print(f"Connected to {args.port}")

    safe_enable_torque(bus)

    # Set motion profile on each joint before commanding the goal.
    # Max_Velocity limits servo speed in position mode (counts/s).
    # Acceleration ramps the velocity up/down (counts/s²).
    for name in active_joints:
        bus.write("Max_Velocity",  name, velocity,     normalize=False)
        bus.write("Acceleration",  name, ACCELERATION, normalize=False)

    print(f"Moving {args.arm} arm to neutral "
          f"(velocity={velocity} counts/s, accel={ACCELERATION})...")
    bus.sync_write("Goal_Position", neutral, normalize=True)

    # Poll Present_Velocity until all joints stop (threshold: <10 counts/s).
    # Timeout is 2× the requested duration as a safety net.
    timeout   = args.duration * 2
    t_start   = time.time()
    poll_hz   = 20
    while time.time() - t_start < timeout:
        velocities = bus.sync_read("Present_Velocity", normalize=False)
        if all(abs(float(v)) < 10 for v in velocities.values()):
            break
        time.sleep(1 / poll_hz)

    elapsed = time.time() - t_start
    print(f"Reached neutral in {elapsed:.2f}s:")

    # Restore Max_Velocity to 0 (= no limit) so other scripts are unaffected.
    for name in active_joints:
        bus.write("Max_Velocity", name, 0, normalize=False)

    final = bus.sync_read("Present_Position", normalize=True)
    for name in active_joints:
        print(f"  {name:<16}  {float(final[name]):.1f}  (target {neutral[name]:.1f})")

    bus.disconnect()


if __name__ == "__main__":
    main()
