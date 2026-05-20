#!/usr/bin/env python3
"""
raw_ping.py
-----------
Sends a raw PING packet directly over serial and prints the response.
Bypasses the SDK entirely — purely for diagnosing the hardware path.

The STS3215 ping response is always 6 bytes: FF FF ID 02 ERR CHECKSUM
VMIN=1 on ttyAMA0 means read() returns after the first available byte,
so we read one byte at a time in a loop until we have the full packet.

Usage (Pi via UART):
    python3 software/control/raw_ping.py --port /dev/ttyAMA0 --id 1
Usage (Mac via USB Waveshare board):
    python3 software/control/raw_ping.py --port /dev/cu.usbmodem5B141112771 --id 1
"""

import serial
import time
import argparse

PING_RESPONSE_LEN = 6  # FF FF ID LEN ERR CHECKSUM


def ping_packet(servo_id):
    """Build a raw ping packet: FF FF ID 02 01 CHECKSUM"""
    checksum = (~(servo_id + 0x02 + 0x01)) & 0xFF
    return bytes([0xFF, 0xFF, servo_id, 0x02, 0x01, checksum])


def read_n_bytes(ser, n, timeout=0.5):
    """Read exactly n bytes one at a time, respecting VMIN=1 on ttyAMA0."""
    buf = bytearray()
    deadline = time.time() + timeout
    while len(buf) < n and time.time() < deadline:
        b = ser.read(1)
        if b:
            buf.extend(b)
    return bytes(buf)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="/dev/ttyAMA0",
                        help="Serial port. Pi UART: /dev/ttyAMA0  Mac USB: /dev/cu.usbmodem*")
    parser.add_argument("--id",   default=1, type=int,
                        help="Servo ID to ping (factory default = 1)")
    parser.add_argument("--baud", default=1000000, type=int)
    args = parser.parse_args()

    pkt = ping_packet(args.id)
    print(f"Port:     {args.port}")
    print(f"Baud:     {args.baud}")
    print(f"Packet:   {' '.join(f'{b:02X}' for b in pkt)}")

    ser = serial.Serial(args.port, baudrate=args.baud, timeout=0.1)
    ser.reset_input_buffer()
    ser.write(pkt)

    raw = read_n_bytes(ser, PING_RESPONSE_LEN)
    ser.close()

    print(f"Response: {' '.join(f'{b:02X}' for b in raw)} ({len(raw)}/{PING_RESPONSE_LEN} bytes)")

    if len(raw) < PING_RESPONSE_LEN:
        print("  x Incomplete response — servo may not be present")
        return

    # Parse response: FF FF ID LEN ERR CHECKSUM
    header   = raw[0:2]
    servo_id = raw[2]
    length   = raw[3]
    err      = raw[4]
    checksum = raw[5]

    expected_checksum = (~(servo_id + length + err)) & 0xFF

    if header != b'\xFF\xFF':
        print(f"  x Bad header: {header.hex()}")
        return

    if checksum != expected_checksum:
        print(f"  x Checksum mismatch: got {checksum:02X}, expected {expected_checksum:02X}")
        return

    if err == 0:
        print(f"  + Servo ID {servo_id} alive — no errors")
    else:
        print(f"  ! Servo ID {servo_id} responded with error byte: 0x{err:02X}")


if __name__ == "__main__":
    main()
