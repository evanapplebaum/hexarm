#!/usr/bin/env python3
"""
raw_ping.py
-----------
Sends a raw PING packet directly over serial and prints whatever bytes come back.
Bypasses the SDK entirely — purely for diagnosing the hardware path.

Usage:
    python software/control/raw_ping.py --port /dev/cu.usbmodem5B141112771 --id 7
"""

import serial
import time
import argparse


def ping_packet(servo_id):
    """Build a raw ping packet: FF FF ID 02 01 CHECKSUM"""
    checksum = (~(servo_id + 0x02 + 0x01)) & 0xFF
    return bytes([0xFF, 0xFF, servo_id, 0x02, 0x01, checksum])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="/dev/cu.usbmodem5B141112771")
    parser.add_argument("--id",   default=7, type=int)
    parser.add_argument("--baud", default=1000000, type=int)
    args = parser.parse_args()

    pkt = ping_packet(args.id)
    print(f"Port:   {args.port}")
    print(f"Baud:   {args.baud}")
    print(f"Packet: {' '.join(f'{b:02X}' for b in pkt)}")

    ser = serial.Serial(args.port, baudrate=args.baud, timeout=0.1)
    ser.reset_input_buffer()

    ser.write(pkt)
    ser.flush()

    time.sleep(0.05)  # give servo 50ms to respond

    raw = ser.read(32)
    if raw:
        print(f"Got {len(raw)} byte(s): {' '.join(f'{b:02X}' for b in raw)}")
    else:
        print("No bytes received.")

    ser.close()


if __name__ == "__main__":
    main()
