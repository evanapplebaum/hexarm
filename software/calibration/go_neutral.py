#!/usr/bin/env python3
"""
go_neutral.py — Move arm slowly to the captured neutral pose.

Sets Maximum_Velocity_Limit and Acceleration on each joint, commands
Goal_Position for all joints simultaneously, then polls Present_Position
until all joints are within ±0.5 of their targets (normalized 0–100).

Can be used standalone or imported by other scripts (e.g. teleop.py):

  Standalone:
    conda activate lerobot
    python software/calibration/go_neutral.py --arm follower
    python software/calibration/go_neutral.py --arm leader --velocity 200 --acceleration 30
    python software/calibration/go_neutral.py --arm both

  Imported:
    from software.calibration.go_neutral import go_neutral
    go_neutral(bus, neutral, velocity=100, acceleration=20)

Arguments (standalone):
  --arm           follower | leader | both  (required)
  --velocity      max joint speed in counts/s (default: 100 ≈ 8.8°/s)
  --acceleration  ramp rate in counts/s² (default: 20)
  --port          serial port (default: /dev/ttyACM0)

--arm both moves both arms simultaneously on one bus (one sync_write for all
12 joints), the same prefixed-motor-name approach teleop.py uses.

Torque is left ENABLED on exit (standalone mode only — the importable
go_neutral() function never touches torque either way). Run torque_off.py
separately if you want it disabled afterward.
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

DEFAULT_VELOCITY     = 100   # counts/s  ≈ 8.8°/s
DEFAULT_ACCELERATION = 20    # counts/s²
POSITION_TOLERANCE   = 0.5   # normalized units (0–100 scale)
POLL_HZ              = 20

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing config file: {path}")
    with open(path) as f:
        return json.load(f)


def build_motors(arm: str, names: list[str], prefix: str = "") -> dict[str, Motor]:
    id_offset = ARM_ID_OFFSET[arm]
    return {
        f"{prefix}{name}": Motor(
            id=JOINT_NAMES.index(name) + 1 + id_offset,
            model="sts3215",
            norm_mode=MotorNormMode.RANGE_0_100,
        )
        for name in names
    }


def safe_enable_torque(bus: FeetechMotorsBus) -> None:
    """Write Goal_Position = Present_Position before enabling torque.
    Prevents servos from snapping to a stale goal on enable."""
    positions = bus.sync_read("Present_Position", normalize=False)
    for name, pos in positions.items():
        bus.write("Goal_Position", name, int(float(pos)), normalize=False)
    bus.enable_torque()


def go_neutral(
    bus: FeetechMotorsBus,
    neutral: dict[str, float],
    velocity: int = DEFAULT_VELOCITY,
    acceleration: int = DEFAULT_ACCELERATION,
) -> None:
    """Move all joints to neutral positions and block until all arrive.

    Args:
        bus:          Open, torque-enabled FeetechMotorsBus.
        neutral:      Dict of {joint_name: target_normalized (0–100)}.
        velocity:     Maximum joint speed in counts/s.
        acceleration: Ramp rate in counts/s².
    """
    active_joints = list(neutral.keys())
    timeout = int(4096 / velocity) + 5  # generous: full range at chosen speed + 5s

    # Set motion profile on all joints
    for name in active_joints:
        bus.write("Maximum_Velocity_Limit", name, velocity,     normalize=False)
        bus.write("Acceleration",           name, acceleration, normalize=False)

    # Fire all joints simultaneously
    bus.sync_write("Goal_Position", neutral, normalize=True)
    print(f"Moving {len(active_joints)} joints to neutral "
          f"(velocity={velocity}, accel={acceleration})...")

    t_start = time.time()
    while time.time() - t_start < timeout:
        positions = bus.sync_read("Present_Position", normalize=True)
        if all(abs(float(positions[n]) - neutral[n]) < POSITION_TOLERANCE
               for n in active_joints):
            break
        time.sleep(1 / POLL_HZ)
    else:
        # Loop completed without break — timed out
        positions = bus.sync_read("Present_Position", normalize=True)
        stalled = [n for n in active_joints
                   if abs(float(positions[n]) - neutral[n]) >= POSITION_TOLERANCE]
        print(f"WARNING: timed out after {timeout}s. "
              f"Joints not at target: {stalled}")

    elapsed = time.time() - t_start

    # Restore motion profile to 0 (= no limit) so other scripts are unaffected
    for name in active_joints:
        bus.write("Maximum_Velocity_Limit", name, 0, normalize=False)
        bus.write("Acceleration",           name, 0, normalize=False)

    print(f"Done ({elapsed:.2f}s). Final positions:")
    final = bus.sync_read("Present_Position", normalize=True)
    for name in active_joints:
        print(f"  {name:<16}  {float(final[name]):.1f}  (target {neutral[name]:.1f})")

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Move arm to neutral pose")
    parser.add_argument("--arm",          required=True, choices=["leader", "follower", "both"])
    parser.add_argument("--velocity",     type=int, default=DEFAULT_VELOCITY,
                        help=f"Max speed in counts/s (default: {DEFAULT_VELOCITY} ≈ 8.8°/s)")
    parser.add_argument("--acceleration", type=int, default=DEFAULT_ACCELERATION,
                        help=f"Ramp rate in counts/s² (default: {DEFAULT_ACCELERATION})")
    parser.add_argument("--port",         default=DEFAULT_PORT)
    args = parser.parse_args()

    arm_list = ["follower", "leader"] if args.arm == "both" else [args.arm]

    motors: dict[str, Motor] = {}
    calibration: dict[str, MotorCalibration] = {}
    neutral: dict[str, float] = {}

    for arm in arm_list:
        cal_data     = load_json(CONFIG_DIR / f"calibration_{arm}.json")
        neutral_data = load_json(CONFIG_DIR / f"neutral_{arm}.json")

        active_joints = [n for n in JOINT_NAMES if n in cal_data and n in neutral_data]
        skipped = [n for n in JOINT_NAMES if n not in active_joints]
        if skipped:
            print(f"Skipping {arm} joints with missing calibration or neutral: {skipped}")

        # Prefix motor names when running both arms on one bus, so the
        # identically-named joints (e.g. "shoulder_pan") don't collide —
        # same convention teleop.py uses.
        prefix = f"{arm}_" if args.arm == "both" else ""
        calibration.update({f"{prefix}{n}": MotorCalibration(**cal_data[n]) for n in active_joints})
        neutral.update({f"{prefix}{n}": float(neutral_data[n]) for n in active_joints})
        motors.update(build_motors(arm, active_joints, prefix=prefix))

    if not neutral:
        raise RuntimeError("No joints to move — run calibrate_lerobot.py and record_neutral.py first.")

    bus = FeetechMotorsBus(port=args.port, motors=motors, calibration=calibration)
    bus.connect()
    print(f"Connected to {args.port}  ({len(motors)} motor(s))")

    safe_enable_torque(bus)
    go_neutral(bus, neutral, velocity=args.velocity, acceleration=args.acceleration)

    # disable_torque=False: leave torque enabled on exit. FeetechMotorsBus's
    # default disconnect() disables torque, which was silently undoing the
    # whole point of moving to neutral. Run torque_off.py separately instead.
    bus.disconnect(disable_torque=False)
    print("Torque left enabled — run torque_off.py if you want it disabled.")


if __name__ == "__main__":
    main()
