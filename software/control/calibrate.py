#!/usr/bin/env python3
"""
calibrate.py
------------
Interactive joint-limit calibration for STS3215 servos.

For each servo, the user physically moves the arm to each limit and records
the position. Three measurements are taken per servo:
  - MIN  : one mechanical/software limit
  - MAX  : the other mechanical/software limit
  - MID  : a position clearly inside the valid operating range

The MID point disambiguates which side of MIN/MAX is the valid operating range,
since the servo's 0-4095 encoder range doesn't tell you which direction is "in".

Results are written to software/config/limits.json as:
  {
    "1": {"min": 412, "max": 3680, "mid": 2048},
    "2": { ... },
    ...
  }
Existing entries for other IDs are preserved; re-running for the same ID overwrites it.

CONTROLS (during measurement):
  Tab   — cycle active slot (MIN → MAX → MID → MIN ...)
  Enter — record current live position into the active slot
  q     — quit without saving this servo

SETUP:
  Torque is disabled on the servo being calibrated so it can be moved freely by hand.
  All other servos on the bus are unaffected.

USAGE:
  python software/control/calibrate.py
  python software/control/calibrate.py --port /dev/cu.usbmodem5B141112771  # Mac USB
  python software/control/calibrate.py --port /dev/ttyAMA0 --baud 1000000  # Pi UART

Requirements:
  - scservo_sdk at software/scservo_sdk/ (local copy, not a pip package)
  - pyserial:  pip install pyserial
  - readchar:  pip install readchar
"""

import sys
import os
import argparse
import json
import time

import readchar

# scservo_sdk lives in software/ — one level up from software/control/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scservo_sdk import PortHandler, sms_sts, COMM_SUCCESS

# --- register addresses ---
REG_TORQUE_ENABLE = 40  # SRAM — 0 = torque off (free to move), 1 = torque on

# --- defaults ---
DEFAULT_PORT = "/dev/ttyAMA0"
DEFAULT_BAUD = 1_000_000

# Path to limits file — relative to this script's location
LIMITS_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "limits.json")

# Measurement slot names in tab-cycle order
SLOTS = ["min", "max", "mid"]
SLOT_PROMPTS = {
    "min": "MIN  (one travel limit)",
    "max": "MAX  (other travel limit)",
    "mid": "MID  (a position clearly inside the valid operating range)",
}


# ---------------------------------------------------------------------------
# Terminal helpers
# ---------------------------------------------------------------------------

def clear_line():
    sys.stdout.write("\r\033[K")
    sys.stdout.flush()


def render_status(servo_id, slot_idx, measurements, current_pos, comm_ok):
    """Render the live one-line status display. Overwrites the current line."""
    slot = SLOTS[slot_idx]
    pos_str = f"{current_pos:4d}" if comm_ok else " ERR"

    parts = []
    for s in SLOTS:
        val = measurements.get(s)
        marker = ">" if s == slot else " "
        val_str = f"{val:4d}" if val is not None else "----"
        parts.append(f"{marker}{s.upper()}={val_str}")

    slots_display = "  |  ".join(parts)
    clear_line()
    sys.stdout.write(
        f"  ID {servo_id:2d}  |  Live: {pos_str}  |  {slots_display}"
        f"  |  [Tab]=cycle  [Enter]=record  [q]=quit"
    )
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Serial helpers
# ---------------------------------------------------------------------------

def open_port(port, baud):
    port_handler = PortHandler(port)
    st = sms_sts(port_handler)

    if not port_handler.openPort():
        print(f"ERROR: Could not open port {port}.")
        print("  Check: board powered (12V barrel)? Mode switch set correctly?")
        sys.exit(1)

    if not port_handler.setBaudRate(baud):
        print(f"ERROR: Could not set baud rate {baud}.")
        port_handler.closePort()
        sys.exit(1)

    return port_handler, st


def ping_servo(st, servo_id):
    """Ping a servo. Returns True on success."""
    model, result, error = st.ping(servo_id)
    if result == COMM_SUCCESS:
        print(f"  ✓ Servo {servo_id} online (model {model})")
        return True
    print(f"  ✗ No response from servo {servo_id}: {st.getTxRxResult(result)}")
    return False


def disable_torque(st, servo_id):
    """Disable torque so the servo can be moved freely by hand."""
    result, error = st.write1ByteTxRx(servo_id, REG_TORQUE_ENABLE, 0)
    if result != COMM_SUCCESS:
        print(f"  WARNING: Could not disable torque on servo {servo_id}: {st.getTxRxResult(result)}")


def read_position(st, servo_id):
    """Read present encoder position. Returns (pos, ok)."""
    pos, result, error = st.ReadPos(servo_id)
    if result == COMM_SUCCESS:
        return pos, True
    return 0, False


# ---------------------------------------------------------------------------
# Per-servo calibration loop
# ---------------------------------------------------------------------------

def calibrate_servo(st, servo_id):
    """
    Interactively collect MIN, MAX, MID measurements for one servo.
    Returns {"min": int, "max": int, "mid": int}, or None if user quit.
    """
    print(f"\n--- Servo {servo_id} ---")
    print(f"  Disabling torque — move the joint freely by hand.")
    print(f"  Tab = cycle slot  |  Enter = record  |  q = quit\n")
    print(f"  Start with: {SLOT_PROMPTS[SLOTS[0]]}\n")

    disable_torque(st, servo_id)

    measurements = {}
    slot_idx = 0

    while True:
        # Read live position
        current_pos, comm_ok = read_position(st, servo_id)

        # Render status line
        render_status(servo_id, slot_idx, measurements, current_pos, comm_ok)

        # Wait for keypress (blocks — position updates on next iteration)
        key = readchar.readkey()

        if key == readchar.key.TAB:
            slot_idx = (slot_idx + 1) % len(SLOTS)
            sys.stdout.write(f"\n  → Active: {SLOT_PROMPTS[SLOTS[slot_idx]]}\n")
            sys.stdout.flush()

        elif key in (readchar.key.ENTER, "\r", "\n"):
            if not comm_ok:
                sys.stdout.write(f"\n  WARNING: Comm error — position unreliable, try again.\n")
                sys.stdout.flush()
                continue

            slot = SLOTS[slot_idx]
            measurements[slot] = current_pos
            sys.stdout.write(f"\n  ✓ {slot.upper()} = {current_pos}\n")
            sys.stdout.flush()

            # All three slots filled?
            if all(s in measurements for s in SLOTS):
                sys.stdout.write("  All slots recorded.\n")
                sys.stdout.flush()
                break

            # Auto-advance to next unfilled slot
            for i, s in enumerate(SLOTS):
                if s not in measurements:
                    slot_idx = i
                    sys.stdout.write(f"  → Next: {SLOT_PROMPTS[SLOTS[slot_idx]]}\n")
                    sys.stdout.flush()
                    break

        elif key in ("q", "Q", readchar.key.CTRL_C):
            sys.stdout.write("\n  Quit — no data saved for this servo.\n")
            sys.stdout.flush()
            return None

        time.sleep(0.02)  # brief pause so display doesn't spam on held keys

    return measurements


# ---------------------------------------------------------------------------
# limits.json helpers
# ---------------------------------------------------------------------------

def load_limits():
    """Load existing limits.json. Returns empty dict if file absent or empty."""
    if os.path.exists(LIMITS_FILE) and os.path.getsize(LIMITS_FILE) > 0:
        with open(LIMITS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_limits(limits):
    """Write limits dict to limits.json, pretty-printed."""
    os.makedirs(os.path.dirname(LIMITS_FILE), exist_ok=True)
    with open(LIMITS_FILE, "w") as f:
        json.dump(limits, f, indent=2)
    print(f"  Saved → {os.path.relpath(LIMITS_FILE)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Interactively calibrate joint limits for STS3215 servos.",
        epilog="Example: python software/control/calibrate.py --port /dev/ttyAMA0"
    )
    parser.add_argument("--port", default=DEFAULT_PORT,
                        help=f"Serial port (default: {DEFAULT_PORT})")
    parser.add_argument("--baud", default=DEFAULT_BAUD, type=int,
                        help=f"Baud rate (default: {DEFAULT_BAUD})")
    args = parser.parse_args()

    print(f"\nOpening {args.port} at {args.baud} baud...")
    port_handler, st = open_port(args.port, args.baud)

    # Load existing limits so we don't clobber other servos' data
    limits = load_limits()
    if limits:
        print(f"  Existing limits found for servo IDs: {', '.join(sorted(limits.keys(), key=int))}")

    try:
        while True:
            # --- prompt for servo ID ---
            print()
            try:
                raw = input("Servo ID to calibrate (1–12): ").strip()
                servo_id = int(raw)
                if not (1 <= servo_id <= 253):
                    print("  Invalid — must be 1–253.")
                    continue
            except ValueError:
                print("  Please enter a number.")
                continue

            # --- ping ---
            print(f"  Pinging servo {servo_id}...")
            if not ping_servo(st, servo_id):
                print("  Cannot calibrate — servo not responding. Check wiring/ID.")
                continue

            # --- calibrate ---
            result = calibrate_servo(st, servo_id)

            if result is not None:
                limits[str(servo_id)] = result
                save_limits(limits)
                print(f"  Servo {servo_id}: {result}")

            # --- loop or exit ---
            print()
            again = input("Calibrate another servo? [y/n]: ").strip().lower()
            if again != "y":
                break

    except KeyboardInterrupt:
        print("\n\nInterrupted.")

    finally:
        port_handler.closePort()
        print("Port closed.\n")


if __name__ == "__main__":
    main()
