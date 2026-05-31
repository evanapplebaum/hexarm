#!/usr/bin/env python3
"""
keyboard_follower.py — Keyboard control of follower arm via LeRobot FeetechMotorsBus

Works in raw encoder counts (0–4095). Run LeRobot calibration before switching
to normalized/degree modes. Hardware angle limits should also be flashed first
via flash_angle_limits.py to prevent mechanical overtravel.

Keys:
  1–6    Select joint
  w / s  Fine move   (+/- 30 counts ≈ ±2.6°)
  W / S  Coarse move (+/- 150 counts ≈ ±13°)
  p      Print all joint positions
  q      Quit (disables torque)

Usage (from hexarm root, conda lerobot env):
  conda activate lerobot
  python software/control/keyboard_follower.py [--port /dev/ttyACM0]
"""

import argparse
import sys
import tty
import termios

from lerobot.motors.feetech import FeetechMotorsBus
from lerobot.motors.motors_bus import Motor, MotorNormMode

# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_PORT = "/dev/ttyACM0"
FINE_STEP    = 30    # raw counts (~2.6°)
COARSE_STEP  = 150   # raw counts (~13°)
RAW_MIN      = 0
RAW_MAX      = 4095

# Follower arm — IDs 1–6, one bus, one driver board
MOTORS: dict[str, Motor] = {
    "shoulder_pan":  Motor(id=1, model="sts3215", norm_mode=MotorNormMode.RANGE_0_100),
    "shoulder_lift": Motor(id=2, model="sts3215", norm_mode=MotorNormMode.RANGE_0_100),
    "elbow_flex":    Motor(id=3, model="sts3215", norm_mode=MotorNormMode.RANGE_0_100),
    "wrist_flex":    Motor(id=4, model="sts3215", norm_mode=MotorNormMode.RANGE_0_100),
    "wrist_roll":    Motor(id=5, model="sts3215", norm_mode=MotorNormMode.RANGE_0_100),
    "gripper":       Motor(id=6, model="sts3215", norm_mode=MotorNormMode.RANGE_0_100),
}

JOINT_NAMES = list(MOTORS.keys())

# ── Helpers ───────────────────────────────────────────────────────────────────

def getch() -> str:
    """Read one character from stdin without echo or line buffering."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def clamp(val: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, val))


def print_positions(bus: FeetechMotorsBus) -> None:
    positions = bus.sync_read("Present_Position", normalize=False)
    print("\nCurrent positions (raw counts):")
    for i, name in enumerate(JOINT_NAMES):
        print(f"  [{i + 1}] {name:<16} {int(positions[name])}")

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Keyboard control of follower arm")
    parser.add_argument("--port", default=DEFAULT_PORT, help="Serial port (default: /dev/ttyACM0)")
    args = parser.parse_args()

    bus = FeetechMotorsBus(port=args.port, motors=MOTORS)
    bus.connect()
    print(f"Connected to {args.port}")

    bus.enable_torque()
    print("Torque enabled")

    selected = 0
    print_positions(bus)
    print(f"\nSelected: [1] {JOINT_NAMES[selected]}")
    print("1–6: select joint | w/s: fine | W/S: coarse | p: positions | q: quit\n")

    try:
        while True:
            key = getch()

            if key == "q":
                break

            elif key == "p":
                print_positions(bus)

            elif key in "123456":
                selected = int(key) - 1
                pos = bus.read("Present_Position", JOINT_NAMES[selected], normalize=False)
                print(f"\nSelected: [{key}] {JOINT_NAMES[selected]}  (pos={int(pos)})")

            elif key in ("w", "W", "s", "S"):
                name = JOINT_NAMES[selected]
                step  = FINE_STEP if key in ("w", "s") else COARSE_STEP
                delta = step if key in ("w", "W") else -step

                current = bus.read("Present_Position", name, normalize=False)
                new_pos = clamp(int(current) + delta, RAW_MIN, RAW_MAX)
                bus.write("Goal_Position", name, new_pos, normalize=False)
                print(f"\r  {name}: {new_pos}    ", end="", flush=True)

    finally:
        bus.disable_torque()
        bus.disconnect()
        print("\n\nTorque disabled. Disconnected.")


if __name__ == "__main__":
    main()
