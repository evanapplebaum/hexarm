#!/usr/bin/env python3
"""
calibrate.py
------------
Record joint travel limits for one arm by manually moving each joint
to its physical minimum and maximum, then saving the encoder values.

This script uses the scservo_sdk directly — no LeRobot dependency.
Run it on the Pi (or Mac with USB board) after all servo IDs are assigned.

The arm must be in torque-disabled (passive) mode so you can move joints
freely by hand. This script disables torque on all servos at startup.

Output: software/config/limits.json
Format: { "joint_name": { "min": <encoder>, "max": <encoder> }, ... }
Encoder range is 0–4095 (12-bit absolute), centered at ~2048 = neutral.

Usage (Pi, run from repo root):
    python software/control/calibrate.py --arm leader
    python software/control/calibrate.py --arm follower
    python software/control/calibrate.py --arm leader --port /dev/ttyAMA0
"""

import sys
import os
import json
import argparse

# scservo_sdk lives in software/ — one level up from software/control/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scservo_sdk import PortHandler, sms_sts, COMM_SUCCESS

# --- register addresses ---
ADDR_TORQUE_ENABLE    = 40   # SRAM: 1=enabled, 0=disabled
ADDR_PRESENT_POSITION = 56   # SRAM: present encoder position (low byte; high byte at 57)

# --- arm motor definitions ---
# Order: base → tip (matches physical chain)
# IDs must match what was assigned with assign_id.py
LEADER_MOTORS = {
    "shoulder_pan":   1,
    "shoulder_raise": 2,
    "elbow_adduct":   3,
    "wrist_adduct":   4,
    "wrist_rotate":   5,
    "claw":           6,
}

FOLLOWER_MOTORS = {
    "shoulder_pan":   7,
    "shoulder_raise": 8,
    "elbow_adduct":   9,
    "wrist_adduct":   10,
    "wrist_rotate":   11,
    "claw":           12,
}

DEFAULT_PORT      = "/dev/ttyAMA0"
DEFAULT_BAUD      = 1_000_000
LIMITS_FILE       = os.path.join(os.path.dirname(__file__), "..", "config", "limits.json")


def read_position(st: sms_sts, servo_id: int) -> int | None:
    """Read present encoder position from a servo. Returns None on failure."""
    pos, result, error = st.ReadPos(servo_id)
    if result != COMM_SUCCESS:
        return None
    return pos


def set_torque(st: sms_sts, motors: dict, enable: bool) -> None:
    """Enable or disable torque on all servos in the motor map."""
    value = 1 if enable else 0
    label = "enabled" if enable else "disabled"
    for name, servo_id in motors.items():
        result, error = st.write1ByteTxRx(servo_id, ADDR_TORQUE_ENABLE, value)
        if result == COMM_SUCCESS:
            print(f"  {name} (ID {servo_id}) torque {label}")
        else:
            print(f"  WARNING: could not set torque on {name} (ID {servo_id}): {st.getTxRxResult(result)}")


def ping_all(st: sms_sts, motors: dict) -> bool:
    """Ping every servo. Returns True if all respond."""
    all_ok = True
    for name, servo_id in motors.items():
        _, result, _ = st.ping(servo_id)
        if result == COMM_SUCCESS:
            print(f"  ✓ {name} (ID {servo_id})")
        else:
            print(f"  ✗ {name} (ID {servo_id}) — no response")
            all_ok = False
    return all_ok


def load_existing_limits() -> dict:
    """Load existing limits.json if it exists, else return empty dict."""
    if os.path.exists(LIMITS_FILE):
        with open(LIMITS_FILE) as f:
            return json.load(f)
    return {}


def main():
    parser = argparse.ArgumentParser(
        description="Record joint travel limits by manually moving each joint.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Calibration procedure for each joint:
  1. Script prompts: "Move to LOWER limit"
     -> Push joint to its physical minimum position
     -> Press Enter to record
  2. Script prompts: "Move to UPPER limit"
     -> Push joint to its physical maximum position
     -> Press Enter to record

Limits are saved to software/config/limits.json.
Running twice (once per arm) merges both into the same file.
        """
    )
    parser.add_argument("--arm",  choices=["leader", "follower"], required=True,
                        help="Which arm to calibrate")
    parser.add_argument("--port", default=DEFAULT_PORT,
                        help=f"Serial port (default: {DEFAULT_PORT})")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD,
                        help=f"Baud rate (default: {DEFAULT_BAUD})")
    args = parser.parse_args()

    motors = LEADER_MOTORS if args.arm == "leader" else FOLLOWER_MOTORS

    print(f"\n{'='*50}")
    print(f"  hexarm calibration -- {args.arm} arm")
    print(f"{'='*50}")
    print(f"  Port: {args.port} @ {args.baud} baud")
    print(f"  Servos: {list(motors.values())}\n")

    # --- open port ---
    port_handler = PortHandler(args.port)
    st = sms_sts(port_handler)

    if not port_handler.openPort():
        print("ERROR: Failed to open port.")
        sys.exit(1)

    if not port_handler.setBaudRate(args.baud):
        print("ERROR: Failed to set baud rate.")
        port_handler.closePort()
        sys.exit(1)

    # --- ping all servos ---
    print("Checking servos...")
    all_ok = ping_all(st, motors)
    if not all_ok:
        print("\nERROR: One or more servos did not respond.")
        print("  - Are all servo IDs assigned? (run assign_id.py for each servo first)")
        print("  - Is the arm powered and connected?")
        port_handler.closePort()
        sys.exit(1)

    # --- disable torque so arm is backdrivable ---
    print("\nDisabling torque (arm will be limp -- you can move joints freely)...")
    set_torque(st, motors, enable=False)

    # --- record limits ---
    print(f"\nStarting calibration for {len(motors)} joints.")
    print("Move each joint slowly and firmly to each limit when prompted.\n")

    limits = {}

    for joint_name, servo_id in motors.items():
        print(f"--- {joint_name} (ID {servo_id}) ---")

        input(f"  Move to LOWER limit, then press Enter...")
        lower = read_position(st, servo_id)
        if lower is None:
            print(f"  ERROR: Could not read position from ID {servo_id}. Aborting.")
            port_handler.closePort()
            sys.exit(1)
        print(f"  Lower = {lower}")

        input(f"  Move to UPPER limit, then press Enter...")
        upper = read_position(st, servo_id)
        if upper is None:
            print(f"  ERROR: Could not read position from ID {servo_id}. Aborting.")
            port_handler.closePort()
            sys.exit(1)
        print(f"  Upper = {upper}")

        # Swap if user moved in wrong direction
        if lower > upper:
            lower, upper = upper, lower
            print(f"  (swapped -- min={lower}, max={upper})")

        limits[joint_name] = {"min": lower, "max": upper}
        print()

    port_handler.closePort()

    # --- merge with existing limits and save ---
    existing = load_existing_limits()
    existing.update(limits)

    os.makedirs(os.path.dirname(LIMITS_FILE), exist_ok=True)
    with open(LIMITS_FILE, "w") as f:
        json.dump(existing, f, indent=4)

    print(f"Limits saved to {LIMITS_FILE}")
    print(json.dumps(limits, indent=4))


if __name__ == "__main__":
    main()
