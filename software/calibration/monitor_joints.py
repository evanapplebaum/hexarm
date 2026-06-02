#!/usr/bin/env python3
"""
monitor_joints.py — Live joint monitor with interactive position control.

Displays a live table of Present_Position (raw + normalized) for the specified
arm. While monitoring, you can command any joint to a target position and it
will move there very slowly.

Usage (from hexarm root, conda lerobot env):
  conda activate lerobot
  python software/calibration/monitor_joints.py --arm follower
  python software/calibration/monitor_joints.py --arm leader

Arguments:
  --arm    follower | leader  (required)
  --port   serial port (default: /dev/ttyACM0)
  --hz     display refresh rate in Hz (default: 10)

Controls:
  Enter          open command prompt
  <n> <target>   move joint n to normalized target (e.g. '2 75.0')
  Ctrl+C         exit
"""

import argparse
import json
import sys
import threading
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

SLOW_VELOCITY = 100  # counts/s — ~13°/s, very slow
SLOW_ACCEL    = 20   # counts/s²

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


def safe_enable_torque(bus: FeetechMotorsBus) -> None:
    """Set Goal_Position = Present_Position for all joints before enabling."""
    positions = bus.sync_read("Present_Position", normalize=False)
    for name, pos in positions.items():
        bus.write("Goal_Position", name, int(float(pos)), normalize=False)
    bus.enable_torque()

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Live joint monitor + control")
    parser.add_argument("--arm",  required=True, choices=["leader", "follower"])
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--hz",   type=float, default=10.0)
    args = parser.parse_args()

    calibration = load_calibration(args.arm)
    if calibration is None:
        print("Warning: no calibration found — normalized column will show n/a.")

    active_joints = list(calibration.keys()) if calibration else JOINT_NAMES
    motors        = build_motors(args.arm, active_joints)

    bus = FeetechMotorsBus(port=args.port, motors=motors, calibration=calibration)
    bus.connect()
    bus.disable_torque()

    torque_on  = False
    bus_lock   = threading.Lock()
    paused     = threading.Event()   # set = display paused

    header  = f" {'#':>2}  {'Joint':<16}  {'Raw':>6}  {'Norm':>8}"
    divider = "─" * len(header)
    n_lines = len(active_joints) + 2  # header + divider + joints

    # ── Display thread ────────────────────────────────────────────────────────
    def display_loop():
        while not paused.is_set():
            with bus_lock:
                try:
                    raw  = bus.sync_read("Present_Position", normalize=False)
                    norm = (bus.sync_read("Present_Position", normalize=True)
                            if calibration else {})
                except Exception:
                    time.sleep(0.1)
                    continue

            # Always cursor-up — blank lines reserved before thread starts
            sys.stdout.write(f"\033[{n_lines}A")
            sys.stdout.write(header + "\n")
            sys.stdout.write(divider + "\n")
            for i, name in enumerate(active_joints, 1):
                r = int(float(raw.get(name, 0)))
                n = (f"{float(norm[name]):8.1f}" if name in norm else "     n/a")
                sys.stdout.write(f" {i:>2}  {name:<16}  {r:>6}  {n}\n")
            sys.stdout.flush()

            time.sleep(1 / args.hz)

    thread = threading.Thread(target=display_loop, daemon=True)

    print(f"\nMonitoring {args.arm} arm. Press Enter to issue a command, Ctrl+C to exit.\n")
    # Reserve exactly n_lines lines so cursor-up always lands at table start
    sys.stdout.write("\n" * n_lines)
    sys.stdout.flush()
    thread.start()

    # ── Input loop ────────────────────────────────────────────────────────────
    try:
        while True:
            input()  # block until Enter

            # Pause display and wait for thread to finish its current cycle
            paused.set()
            time.sleep(1 / args.hz + 0.05)

            try:
                cmd = input(f"  Joint (1–{len(active_joints)}) + target [0–100]"
                            f"  (e.g. '2 75.0'), or Enter to resume: ").strip()
            except KeyboardInterrupt:
                break

            if not cmd:
                # Resume with a clean redraw
                paused.clear()
                thread = threading.Thread(target=display_loop, daemon=True)
                thread.start()
                continue

            parts = cmd.split()
            valid = True

            if len(parts) != 2:
                print("  Format: <joint_number> <target>  e.g. '2 75.0'")
                valid = False

            if valid:
                try:
                    joint_idx = int(parts[0])
                    target    = float(parts[1])
                except ValueError:
                    print("  Invalid — joint must be an integer, target a number.")
                    valid = False

            if valid and not (1 <= joint_idx <= len(active_joints)):
                print(f"  Joint must be 1–{len(active_joints)}")
                valid = False

            if valid and not (0.0 <= target <= 100.0):
                print("  Target must be between 0 and 100.")
                valid = False

            if valid:
                name = active_joints[joint_idx - 1]
                with bus_lock:
                    if not torque_on:
                        safe_enable_torque(bus)
                        torque_on = True
                    bus.write("Maximum_Velocity_Limit", name, SLOW_VELOCITY, normalize=False)
                    bus.write("Acceleration", name, SLOW_ACCEL,    normalize=False)
                    bus.write("Goal_Position", name, target, normalize=True)
                print(f"  → Moving {name} to {target:.1f}  (velocity={SLOW_VELOCITY} counts/s)")

            # Brief pause so user can read feedback, then resume display
            time.sleep(0.8)
            first_draw[0] = True
            paused.clear()
            thread = threading.Thread(target=display_loop, daemon=True)
            thread.start()

    except KeyboardInterrupt:
        pass

    print("\n\nStopped.")
    bus.disconnect()


if __name__ == "__main__":
    main()
