#!/usr/bin/env python3
"""
ping_one.py
-----------
First-contact test for a single STS3215 servo via scservo_sdk.
Pings servo ID 1 and prints whether it responded.

Usage (Pi via UART, run from repo root):
    python software/control/ping_one.py --port /dev/ttyAMA0
    python software/control/ping_one.py --port /dev/ttyAMA0 --id 1 --baud 1000000
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

# scservo_sdk lives in software/ — one level up from software/control/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scservo_sdk import PortHandler, sms_sts, COMM_SUCCESS

# --- defaults ---
DEFAULT_PORT  = "/dev/ttyAMA0"   # Pi UART — override with --port /dev/cu.usbmodem* for Mac
DEFAULT_ID    = 1
DEFAULT_BAUD  = 1000000  # factory default for STS3215


def main():
    parser = argparse.ArgumentParser(description="Ping a single STS3215 servo.")
    parser.add_argument("--port",  default=DEFAULT_PORT,  help="Serial port")
    parser.add_argument("--id",    default=DEFAULT_ID,    type=int, help="Servo ID to ping")
    parser.add_argument("--baud",  default=DEFAULT_BAUD,  type=int, help="Baud rate")
    args = parser.parse_args()

    port_handler = PortHandler(args.port)
    st = sms_sts(port_handler)

    print(f"Opening port {args.port} at {args.baud} baud...")
    if not port_handler.openPort():
        print("ERROR: Failed to open port. Check the port name with: ls /dev/tty.*")
        sys.exit(1)

    if not port_handler.setBaudRate(args.baud):
        print("ERROR: Failed to set baud rate.")
        port_handler.closePort()
        sys.exit(1)

    print(f"Pinging servo ID {args.id}...")
    model_number, result, error = st.ping(args.id)

    if result == COMM_SUCCESS:
        print(f"  ✓ Servo ID {args.id} responded — model number: {model_number}")
    else:
        print(f"  ✗ No response from servo ID {args.id}")
        print(f"    result: {st.getTxRxResult(result)}")
        if error:
            print(f"    error:  {st.getRxPacketError(error)}")

    port_handler.closePort()


if __name__ == "__main__":
    main()
