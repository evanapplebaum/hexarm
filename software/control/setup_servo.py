#!/usr/bin/env python3
"""
setup_servo.py
--------------
Configure a single STS3215 servo: assign a unique ID, set return delay, and/or
change the baud rate.

Run this script with ONE servo connected to the bus at a time.
All servos ship with factory default ID=1 — if multiple are connected
simultaneously they will collide on the bus and none will respond.

ID, return delay, and baud rate are all EPROM registers — written once, persist
across power cycles. All EPROM writes are done in a single unlock/lock cycle.

Return delay (register 7): delay before servo sends its status packet response.
Unit is 2us per count. Use this to give the host's UART time to switch from
TX to RX direction before the servo response arrives. Recommended: 30 (= 60us).
See docs/debugging/ for the direction-switching timing analysis.

Baud rate (register 6): communication speed. Both Pi and servo must match.
Supported: 1000000, 500000, 250000, 128000, 115200, 57600, 38400, 19200, 9600.
Factory default: 1000000. After changing, power-cycle and use --baud <new_rate>.

--force flag: skips the initial ping and uses broadcast ID (0xFE) for all writes.
Use this when the SDK cannot read a full status packet due to direction-switching
timing issues (i.e. return delay has not been set yet). ONE servo on bus only.

Workflow (repeat for each servo):
  1. Connect one servo to the Waveshare board (power + data)
  2. Run this script with desired options
  3. Wait for confirmation, then unplug that servo
  4. Connect the next servo and repeat

Usage (Pi, run from repo root):
    python3 software/control/setup_servo.py --new-id 2
    python3 software/control/setup_servo.py --new-id 2 --return-delay 30
    python3 software/control/setup_servo.py --current-id 5 --return-delay 30
    python3 software/control/setup_servo.py --current-id 9 --new-baud 250000 --force
    python3 software/control/setup_servo.py --current-id 9 --return-delay 30 --force

ID assignments for hexarm:
    Leader arm:   1, 2, 3, 4, 5, 6   (base -> tip)
    Follower arm: 7, 8, 9, 10, 11, 12 (base -> tip)

Requirements:
    - scservo_sdk present at software/scservo_sdk/ (not a pip package -- local folder)
    - pyserial installed: pip install pyserial
"""

import sys
import os
import argparse

# Local control package — _serial_utils handles VMIN fix + SDK retry wrappers.
sys.path.insert(0, os.path.dirname(__file__))
from _serial_utils import open_sdk_port, ping_with_retry, write_byte_with_retry

# --- register addresses (EPROM) ---
REG_ID           = 5    # Servo ID (0-253; 254 = broadcast)
REG_BAUD         = 6    # Baud rate index (see BAUD_MAP)
REG_RETURN_DELAY = 7    # Return delay time (unit: 2us, range: 0-254, max = 508us)
REG_LOCK         = 55   # EPROM lock (matches scservo_sdk.sms_sts.SMS_STS_LOCK)

# Baud rate register values for STS3215 (register 6)
BAUD_MAP = {
    1_000_000: 0,
      500_000: 1,
      250_000: 2,
      128_000: 3,
      115_200: 4,
       57_600: 5,
       38_400: 6,
       19_200: 7,
        9_600: 8,
}

# --- defaults ---
DEFAULT_PORT       = "/dev/ttyACM0"
DEFAULT_BAUD       = 1_000_000
FACTORY_DEFAULT_ID = 1


def main():
    parser = argparse.ArgumentParser(
        description="Configure ID and return delay on one STS3215 servo.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Assign ID only (no return delay change):
  python3 software/control/setup_servo.py --new-id 2

  # Assign ID and set return delay to 30 units (60us):
  python3 software/control/setup_servo.py --new-id 2 --return-delay 30

  # Set return delay only on a servo already at ID 9:
  python3 software/control/setup_servo.py --current-id 9 --return-delay 30
        """
    )
    parser.add_argument("--new-id",       type=int, default=None,
                        help="New ID to assign (1-253). Omit to keep current ID.")
    parser.add_argument("--current-id",   type=int, default=FACTORY_DEFAULT_ID,
                        help=f"Current ID of servo on bus (default: {FACTORY_DEFAULT_ID})")
    parser.add_argument("--return-delay", type=int, default=None,
                        help="Return delay in 2us units (0-254). 30 = 60us recommended.")
    parser.add_argument("--new-baud",     type=int, default=None,
                        help=f"New baud rate to write to servo EPROM. "
                             f"Supported: {', '.join(str(b) for b in BAUD_MAP)}. "
                             f"Power-cycle servo after changing, then use --baud <new_rate>.")
    parser.add_argument("--port",         default=DEFAULT_PORT,
                        help=f"Serial port (default: {DEFAULT_PORT})")
    parser.add_argument("--baud",         type=int, default=DEFAULT_BAUD,
                        help=f"Baud rate (default: {DEFAULT_BAUD})")
    parser.add_argument("--force",        action="store_true",
                        help="Skip ping verification and use broadcast ID (0xFE) for all writes. "
                             "Use when return delay is not yet set and SDK cannot read status packets. "
                             "ONE servo on bus only.")
    args = parser.parse_args()

    # Resolve target ID (what the servo will be after this script)
    target_id = args.new_id if args.new_id is not None else args.current_id
    change_id = args.new_id is not None and args.new_id != args.current_id

    # Validate
    if args.new_id is not None and not (1 <= args.new_id <= 253):
        print(f"ERROR: --new-id must be 1-253 (got {args.new_id}). 254 is the broadcast address.")
        sys.exit(1)
    if args.return_delay is not None and not (0 <= args.return_delay <= 254):
        print(f"ERROR: --return-delay must be 0-254 (got {args.return_delay}).")
        sys.exit(1)
    if args.new_baud is not None and args.new_baud not in BAUD_MAP:
        print(f"ERROR: --new-baud {args.new_baud} not supported.")
        print(f"  Supported rates: {', '.join(str(b) for b in BAUD_MAP)}")
        sys.exit(1)
    if not change_id and args.return_delay is None and args.new_baud is None:
        print("Nothing to do — specify --new-id, --return-delay, and/or --new-baud.")
        sys.exit(0)

    print(f"\nPort:         {args.port} @ {args.baud} baud")
    print(f"Current ID:   {args.current_id}")
    if change_id:
        print(f"New ID:       {target_id}")
    if args.return_delay is not None:
        print(f"Return delay: {args.return_delay} units = {args.return_delay * 2}us")
    if args.new_baud is not None:
        print(f"New baud:     {args.new_baud} (register value {BAUD_MAP[args.new_baud]})")
    print()

    # --- open port (handles VMIN fix internally) ---
    port_handler, st = open_sdk_port(args.port, args.baud)

    # In --force mode, all writes go to broadcast ID (0xFE).
    # Servo acts on broadcast packets but sends no response — no ACK checking.
    # Use when return delay is not yet set and SDK cannot parse status packets.
    write_id = 0xFE if args.force else args.current_id

    def do_write(label, addr, value):
        """Write one EPROM byte. In broadcast (--force) mode no response is
        expected, so retry is skipped. Otherwise retry with the standard
        framing-error budget. Aborts the script on failure (after re-locking
        EPROM if possible)."""
        print(f"{label} (ID {write_id:#04x})...")
        if args.force:
            # Broadcast — fire and forget; SDK call returns RX_TIMEOUT, ignore.
            st.write1ByteTxRx(write_id, addr, value)
            print(f"  + {label.split('—')[0].strip()} sent (broadcast)")
            return
        ok, result = write_byte_with_retry(st, write_id, addr, value)
        if not ok:
            print(f"  x Write failed: {st.getTxRxResult(result)}")
            # Try to leave EPROM in a sane state before bailing.
            st.LockEprom(write_id)
            port_handler.closePort()
            sys.exit(1)
        print(f"  + {label.split('—')[0].strip()} sent")

    # --- step 1: ping (skipped in --force mode) ---
    if args.force:
        print("Step 1 — Skipping ping (--force mode). Ensure exactly ONE servo is on the bus.")
    else:
        print(f"Step 1 — Pinging ID {args.current_id}...")
        ok, model_number = ping_with_retry(st, args.current_id)

        if not ok:
            print(f"  x No response from ID {args.current_id} after retries.")
            print("\n  Possible causes:")
            print("  - More than one servo connected (ID collision)")
            print("  - Servo already has a different ID -- use --current-id to specify it")
            print("  - Wiring issue or board not powered")
            print("  - Return delay not set yet -- retry with --force to skip ping")
            port_handler.closePort()
            sys.exit(1)

        print(f"  + Servo present -- model: {model_number}")

    # --- step 2: unlock EPROM ---
    do_write("Step 2 — Unlocking EPROM", REG_LOCK, 0)

    # --- step 3a: write new ID (if changing) ---
    if change_id:
        do_write(f"Step 3a — Writing new ID {target_id} to register {REG_ID}",
                 REG_ID, target_id)

    # --- step 3b: write return delay (if requested) ---
    if args.return_delay is not None:
        do_write(f"Step 3b — Writing return delay {args.return_delay} "
                 f"({args.return_delay * 2}us) to register {REG_RETURN_DELAY}",
                 REG_RETURN_DELAY, args.return_delay)

    # --- step 3c: write baud rate (if requested) ---
    if args.new_baud is not None:
        reg_val = BAUD_MAP[args.new_baud]
        do_write(f"Step 3c — Writing baud rate {args.new_baud} "
                 f"(register value {reg_val}) to register {REG_BAUD}",
                 REG_BAUD, reg_val)

    # --- step 4: lock EPROM ---
    do_write("Step 4 — Locking EPROM", REG_LOCK, 1)

    if args.force:
        print(f"\nForce mode -- no verification possible. Power-cycle the servo, then")
        print(f"re-run without --force to confirm settings took effect.")
        if args.new_baud is not None:
            print(f"  Note: servo is now at {args.new_baud} baud. Use --baud {args.new_baud} on next run.")
    else:
        # --- verify: ping the target ID ---
        print(f"\nVerifying -- pinging ID {target_id}...")
        ok, model_number = ping_with_retry(st, target_id)

        if ok:
            print(f"  + SUCCESS -- Servo responds as ID {target_id}")
        else:
            print(f"  x No response on ID {target_id} after retries")

    port_handler.closePort()
    print()


if __name__ == "__main__":
    main()
