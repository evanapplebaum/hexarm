#!/usr/bin/env python3
"""
ping_one.py
-----------
First-contact test for a single STS3215 servo via scservo_sdk.
Pings servo ID 1 and prints whether it responded.

Usage (Jetson via USB Waveshare board):
    python software/control/ping_one.py
    python software/control/ping_one.py --port /dev/ttyACM0 --id 1 --baud 1000000
Usage (Mac via USB Waveshare board):
    python software/control/ping_one.py --port /dev/cu.usbmodem5B141112771

Requirements:
    - scservo_sdk present at software/scservo_sdk/ (not a pip package — local folder)
    - pyserial: pip install pyserial
    - Run from repo root so sys.path resolves correctly, OR from software/control/
"""

import sys
import os
import argparse

# Local control package — _serial_utils handles VMIN fix + SDK retry wrappers.
sys.path.insert(0, os.path.dirname(__file__))
from _serial_utils import open_sdk_port, ping_with_retry

# --- defaults ---
DEFAULT_PORT  = "/dev/ttyACM0"   # Jetson USB — override with --port /dev/cu.usbmodem* for Mac
DEFAULT_ID    = 1
DEFAULT_BAUD  = 1000000  # factory default for STS3215


def main():
    parser = argparse.ArgumentParser(description="Ping a single STS3215 servo.")
    parser.add_argument("--port",  default=DEFAULT_PORT,  help="Serial port")
    parser.add_argument("--id",    default=DEFAULT_ID,    type=int, help="Servo ID to ping")
    parser.add_argument("--baud",  default=DEFAULT_BAUD,  type=int, help="Baud rate")
    args = parser.parse_args()

    print(f"Opening port {args.port} at {args.baud} baud...")
    port_handler, st = open_sdk_port(args.port, args.baud)

    print(f"Pinging servo ID {args.id}...")
    ok, model_number = ping_with_retry(st, args.id)

    if ok:
        print(f"  ✓ Servo ID {args.id} responded — model number: {model_number}")
    else:
        print(f"  ✗ No response from servo ID {args.id} after retries")
        print(f"    Check ID with: python software/control/baud_scan.py")

    port_handler.closePort()


if __name__ == "__main__":
    main()
