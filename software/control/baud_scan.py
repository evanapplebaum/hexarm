#!/usr/bin/env python3
"""
baud_scan.py
------------
Tries every supported baud rate and IDs 1-20 looking for any servo response.
Also sends a broadcast torque enable at each baud — watch for physical stiffening.

Usage (Pi via UART):
    python software/control/baud_scan.py --port /dev/ttyAMA0
Usage (Mac via USB Waveshare board):
    python software/control/baud_scan.py --port /dev/cu.usbmodem5B141112771
"""

import serial
import time
import argparse

BAUDS = [9600, 19200, 38400, 57600, 115200, 250000, 500000, 1000000]

def ping_packet(servo_id):
    checksum = (~(servo_id + 0x02 + 0x01)) & 0xFF
    return bytes([0xFF, 0xFF, servo_id, 0x02, 0x01, checksum])

def broadcast_torque_enable():
    # FF FF FE 04 03 28 01 D1
    return bytes([0xFF, 0xFF, 0xFE, 0x04, 0x03, 0x28, 0x01, 0xD1])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="/dev/ttyAMA0",
                        help="Serial port. Pi UART: /dev/ttyAMA0  Mac USB: /dev/cu.usbmodem*")
    args = parser.parse_args()

    for baud in BAUDS:
        print(f"\n--- Baud: {baud} ---")
        try:
            ser = serial.Serial(args.port, baudrate=baud, timeout=0.15)
        except Exception as e:
            print(f"  Could not open port: {e}")
            continue

        # Broadcast torque enable — watch for physical stiffening
        ser.reset_input_buffer()
        ser.write(broadcast_torque_enable())
        ser.flush()
        time.sleep(0.1)

        # Ping IDs 1-20
        for servo_id in range(1, 21):
            ser.reset_input_buffer()
            ser.write(ping_packet(servo_id))
            ser.flush()
            time.sleep(0.1)
            raw = ser.read(32)
            if raw:
                print(f"  *** GOT RESPONSE from ID {servo_id}: {' '.join(f'{b:02X}' for b in raw)}")

        ser.close()
        print(f"  Done (no responses at {baud})")

    print("\nScan complete.")

if __name__ == "__main__":
    main()
