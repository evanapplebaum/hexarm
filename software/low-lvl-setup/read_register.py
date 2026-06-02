#!/usr/bin/env python3
"""
read_register.py
----------------
Read a single byte from any EPROM/SRAM register on an STS3215 servo.
Uses raw pyserial (no SDK) — works even when return delay is not set.

Useful for verifying register values after writing, e.g. checking
that return delay (register 7) was actually written correctly.

Usage (Pi, run from software/control/):
    python3 read_register.py --id 9 --reg 7        # read return delay
    python3 read_register.py --id 1 --reg 5        # read servo ID
    python3 read_register.py --id 9 --reg 7 --raw  # show raw response bytes too

Common registers:
    5  = ID
    6  = Baud rate
    7  = Return delay (unit: 2us)
    8  = Response status level
    40 = Torque enable (SRAM)
    56 = Present position low byte (SRAM)
"""

import serial
import time
import argparse


def read_packet(servo_id: int, reg_addr: int, n_bytes: int = 1) -> bytes:
    """Build a READ instruction packet."""
    length = 4  # INST + START_ADDR + N_BYTES + CHECKSUM
    checksum = (~(servo_id + length + 0x02 + reg_addr + n_bytes)) & 0xFF
    return bytes([0xFF, 0xFF, servo_id, length, 0x02, reg_addr, n_bytes, checksum])


def main():
    parser = argparse.ArgumentParser(description="Read a register from an STS3215 servo.")
    parser.add_argument("--id",   type=int, required=True, help="Servo ID")
    parser.add_argument("--reg",  type=int, required=True, help="Register address to read")
    parser.add_argument("--port", default="/dev/ttyACM0")
    parser.add_argument("--baud", type=int, default=1_000_000)
    parser.add_argument("--raw",  action="store_true", help="Print raw response bytes")
    args = parser.parse_args()

    pkt = read_packet(args.id, args.reg)
    print(f"Port:    {args.port} @ {args.baud} baud")
    print(f"Servo:   ID {args.id}, register {args.reg} (0x{args.reg:02X})")
    print(f"Packet:  {' '.join(f'{b:02X}' for b in pkt)}")

    ser = serial.Serial(args.port, baudrate=args.baud, timeout=0.5)
    ser.reset_input_buffer()
    ser.write(pkt)
    time.sleep(0.1)

    raw = ser.read(32)
    ser.close()

    if args.raw:
        print(f"Raw response ({len(raw)} byte(s)): {' '.join(f'{b:02X}' for b in raw)}")

    # Response format: FF FF ID LEN ERR DATA... CHECKSUM
    # For a 1-byte read: FF FF ID 03 ERR DATA CHECKSUM = 7 bytes total
    if len(raw) < 7:
        print(f"Got {len(raw)} byte(s) — incomplete response (direction-switching timing issue?)")
        if len(raw) == 2:
            # Likely just the last 2 bytes of the response
            print(f"Hint: got tail bytes {' '.join(f'{b:02X}' for b in raw)}")
        return

    # Parse: find FF FF header
    for i in range(len(raw) - 1):
        if raw[i] == 0xFF and raw[i+1] == 0xFF:
            packet = raw[i:]
            if len(packet) >= 7:
                servo_id_resp = packet[2]
                err           = packet[4]
                value         = packet[5]
                print(f"\nServo ID: {servo_id_resp}")
                print(f"Error:    0x{err:02X} ({'OK' if err == 0 else 'ERROR'})")
                print(f"Register {args.reg} value: {value} (0x{value:02X})")
                if args.reg == 7:
                    print(f"  -> Return delay = {value * 2}us")
            return

    print("Could not parse response — no valid header found.")


if __name__ == "__main__":
    main()
