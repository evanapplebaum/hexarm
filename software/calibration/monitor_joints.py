#!/usr/bin/env python3
"""
monitor_joints.py — Live joint position monitor (raw + normalized).

Displays a refreshing table of Present_Position for each joint on the
specified arm, showing both raw counts (0–4095) and normalized (0–100).
Requires calibration to be present for normalized values.

Usage (from hexarm root, conda lerobot env):
  conda activate lerobot
  python software/calibration/monitor_joints.py --arm follower
  python software/calibration/monitor_joints.py --arm leader

Arguments:
  --arm    follower | leader  (required)
  --port   serial port (default: /dev/ttyACM0)
  --hz     refresh rate in Hz (default: 10)

Press Ctrl+C to exit.
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


def load_calibration(arm: str) -> dict[str, MotorCalibration] | None:
    path = CONFIG_DIR / f"calibration_{arm}.json"
    if not path.exists():
        return None
    with open(path) as f:
        data = json.load(f)
    return {name: MotorCalibration(**vals) for name, vals in data.items()}

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Live joint position monitor")
    parser.add_argument("--arm",  required=True, choices=["leader", "follower"])
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--hz",   type=float, default=10.0,
                        help="Refresh rate in Hz (default: 10)")
    args = parser.parse_args()

    calibration = load_calibration(args.arm)
    if calibration is None:
        print("Warning: no calibration found — normalized column will be absent.")

    active_joints = (list(calibration.keys()) if calibration
                     else JOINT_NAMES)
    motors = build_motors(args.arm, active_joints)

    bus = FeetechMotorsBus(port=args.port, motors=motors,
                           calibration=calibration)
    bus.connect()
    bus.disable_torque()

    header  = f"{'Joint':<16}  {'Raw':>6}  {'Norm':>8}"
    divider = "-" * len(header)
    n_lines = len(active_joints) + 3  # header + divider + joints + blank

    print(f"\nMonitoring {args.arm} arm at {args.hz}Hz. Ctrl+C to exit.\n")
    print(header)
    print(divider)
    for _ in active_joints:
        print()  # reserve lines

    try:
        while True:
            raw  = bus.sync_read("Present_Position", normalize=False)
            norm = (bus.sync_read("Present_Position", normalize=True)
                    if calibration else {})

            # Move cursor up to overwrite the table
            print(f"\033[{n_lines - 1}A", end="")
            print(header)
            print(divider)
            for name in active_joints:
                r = int(float(raw[name]))
                n = f"{float(norm[name]):6.1f}" if name in norm else "  n/a "
                print(f"{name:<16}  {r:>6}  {n:>8}")

            time.sleep(1 / args.hz)

    except KeyboardInterrupt:
        print("\n\nStopped.")
    finally:
        bus.disconnect()


if __name__ == "__main__":
    main()
