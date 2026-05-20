#!/usr/bin/env python3
"""
assign_id.py
------------
Assign a unique ID to a single STS3215 servo over the UART bus.

Run this script with ONE servo connected to the bus at a time.
All servos ship with factory default ID=1 — if multiple are connected
simultaneously they will collide on the bus and none will respond.

Workflow (repeat for each servo):
  1. Connect one servo to the Waveshare board (power + data)
  2. Run this script with --new-id <target_id>
  3. Wait for confirmation, then unplug that servo
  4. Connect the next servo and repeat

Usage (Pi, run from repo root):
    python software/control/assign_id.py --new-id 2
    python software/control/assign_id.py --new-id 5 --port /dev/ttyAMA0

ID assignments for hexarm:
    Leader arm:   1, 2, 3, 4, 5, 6   (base → tip)
    Follower arm: 7, 8, 9, 10, 11, 12 (base → tip)

Requirements:
    - scservo_sdk present at software/scservo_sdk/ (not a pip package — local folder)
    - pyserial installed: pip install pyserial
"""

import sys
import os
import argparse

# scservo_sdk lives in software/ — one level up from software/control/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scservo_sdk import PortHandler, sms_sts, COMM_SUCCESS

# --- defaults ---
DEFAULT_PORT      = "/dev/ttyAMA0"   # Pi hardware UART (PL011, GPIO 14/15)
DEFAULT_BAUD      = 1_000_000        # STS3215 factory default
FACTORY_DEFAULT_ID = 1               # All servos ship as ID=1
SMS_STS_ID_ADDR   = 5                # EPROM register address for servo ID


def main():
    parser = argparse.ArgumentParser(
        description="Assign a unique ID to one STS3215 servo on the bus.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python software/control/assign_id.py --new-id 1          # first servo, leader base
  python software/control/assign_id.py --new-id 7          # first servo, follower base
  python software/control/assign_id.py --new-id 3 --current-id 1   # explicit current ID
        """
    )
    parser.add_argument("--new-id",     type=int, required=True,
                        help="ID to write to the servo (1–253)")
    parser.add_argument("--current-id", type=int, default=FACTORY_DEFAULT_ID,
                        help=f"Current ID of the servo on the bus (default: {FACTORY_DEFAULT_ID})")
    parser.add_argument("--port",       default=DEFAULT_PORT,
                        help=f"Serial port (default: {DEFAULT_PORT})")
    parser.add_argument("--baud",       type=int, default=DEFAULT_BAUD,
                        help=f"Baud rate (default: {DEFAULT_BAUD})")
    args = parser.parse_args()

    # Validate new ID range
    if not (1 <= args.new_id <= 253):
        print(f"ERROR: --new-id must be 1–253 (got {args.new_id}). ID 254 is the broadcast address.")
        sys.exit(1)

    print(f"\nPort:       {args.port} @ {args.baud} baud")
    print(f"Current ID: {args.current_id}")
    print(f"New ID:     {args.new_id}\n")

    # --- open port ---
    port_handler = PortHandler(args.port)
    st = sms_sts(port_handler)

    if not port_handler.openPort():
        print("ERROR: Failed to open port.")
        print("  Check: is the Waveshare board powered (12V barrel)? Mode switch on UART-Servo?")
        sys.exit(1)

    if not port_handler.setBaudRate(args.baud):
        print("ERROR: Failed to set baud rate.")
        port_handler.closePort()
        sys.exit(1)

    # --- step 1: ping to confirm servo is present ---
    print(f"Step 1/4 — Pinging ID {args.current_id}...")
    model_number, result, error = st.ping(args.current_id)

    if result != COMM_SUCCESS:
        print(f"  ✗ No response from ID {args.current_id}.")
        print(f"    {st.getTxRxResult(result)}")
        print("\n  Possible causes:")
        print("  - More than one servo connected (ID collision)")
        print("  - Servo already has a different ID — use --current-id to specify it")
        print("  - Wiring issue or board not powered")
        port_handler.closePort()
        sys.exit(1)

    print(f"  ✓ Servo present — model: {model_number}")

    # Skip if already correct
    if args.current_id == args.new_id:
        print(f"\nServo is already ID {args.new_id}. Nothing to do.")
        port_handler.closePort()
        sys.exit(0)

    # --- step 2: unlock EPROM ---
    print(f"Step 2/4 — Unlocking EPROM on ID {args.current_id}...")
    result, error = st.unLockEprom(args.current_id)

    if result != COMM_SUCCESS:
        print(f"  ✗ EPROM unlock failed: {st.getTxRxResult(result)}")
        port_handler.closePort()
        sys.exit(1)

    print("  ✓ EPROM unlocked")

    # --- step 3: write new ID ---
    print(f"Step 3/4 — Writing new ID {args.new_id} to register {SMS_STS_ID_ADDR}...")
    result, error = st.write1ByteTxRx(args.current_id, SMS_STS_ID_ADDR, args.new_id)

    if result != COMM_SUCCESS:
        print(f"  ✗ ID write failed: {st.getTxRxResult(result)}")
        # Try to re-lock EPROM even on failure
        st.LockEprom(args.current_id)
        port_handler.closePort()
        sys.exit(1)

    print(f"  ✓ ID written")

    # --- step 4: lock EPROM (using new ID — servo now responds to new_id) ---
    print(f"Step 4/4 — Locking EPROM on new ID {args.new_id}...")
    result, error = st.LockEprom(args.new_id)

    if result != COMM_SUCCESS:
        print(f"  ✗ EPROM lock failed: {st.getTxRxResult(result)}")
        print(f"    WARNING: EPROM is unlocked. Power-cycle the servo to re-lock automatically.")
        port_handler.closePort()
        sys.exit(1)

    print("  ✓ EPROM locked")

    # --- verify: ping the new ID ---
    print(f"\nVerifying — pinging new ID {args.new_id}...")
    model_number, result, error = st.ping(args.new_id)

    if result == COMM_SUCCESS:
        print(f"  ✓ SUCCESS — Servo now responds as ID {args.new_id}")
    else:
        print(f"  ✗ Servo did not respond on new ID {args.new_id} — check if ID write succeeded")
        print(f"    {st.getTxRxResult(result)}")

    port_handler.closePort()
    print()


if __name__ == "__main__":
    main()
