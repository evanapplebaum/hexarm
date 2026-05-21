#!/usr/bin/env python3
"""
raw_ping.py
-----------
Sends a raw PING packet directly over serial and prints the response.
Bypasses the SDK entirely — purely for diagnosing the hardware path.

The STS3215 ping response is always 6 bytes: FF FF ID 02 ERR CHECKSUM

ttyAMA0 quirk: pyserial sets VMIN=0 VTIME=0 on open, which persists after
close. This causes read() to return immediately with 0 bytes on subsequent
runs. Fix: set VMIN=6 via termios after opening the port so read(6) blocks
until all 6 bytes arrive.

Turnaround framing error: at the TX→RX bus turnaround, the servo's line-driver
turn-on transient can corrupt the start bit of the first response byte. The
PL011 flags a framing error and the Linux tty layer silently discards the byte.
Fix: resync parser that accepts a response missing the leading 0xFF, validated
by checksum. Retry up to MAX_RETRIES times on a completely empty response
(means the outgoing ping was corrupted and the servo never replied).

Usage (Pi via UART):
    python3 software/control/raw_ping.py --port /dev/ttyAMA0 --id 1
Usage (Mac via USB Waveshare board):
    python3 software/control/raw_ping.py --port /dev/cu.usbmodem5B141112771 --id 1
"""

import sys
import serial
import termios
import argparse

PING_RESPONSE_LEN = 6   # FF FF ID LEN ERR CHECKSUM
MAX_RETRIES       = 2   # retries on empty response (0/6 case)


def ping_packet(servo_id):
    """Build a raw ping packet: FF FF ID 02 01 CHECKSUM"""
    checksum = (~(servo_id + 0x02 + 0x01)) & 0xFF
    return bytes([0xFF, 0xFF, servo_id, 0x02, 0x01, checksum])


def set_vmin(ser, vmin, vtime=0):
    """Set VMIN/VTIME on the serial port to control read() blocking behaviour.
    pyserial sets VMIN=0 VTIME=0 on open and the settings persist after close.
    Setting VMIN=n makes read(n) block until exactly n bytes are available.
    """
    fd = ser.fileno()
    attrs = termios.tcgetattr(fd)
    attrs[6][termios.VMIN]  = vmin
    attrs[6][termios.VTIME] = vtime
    termios.tcsetattr(fd, termios.TCSANOW, attrs)


def parse_response(raw):
    """
    Resync parser for a STS3215 ping response.

    Tries FF FF header first (clean case). If not found, tries a lone FF
    header — this handles the case where the leading 0xFF was silently
    discarded by the tty layer due to a framing error at the bus turnaround.

    Checksum is the only real integrity guarantee: ~(ID + LEN + ERR) & 0xFF.

    Returns (servo_id, err, note_str) on success, or None if unparseable.
    """
    # --- clean case: FF FF ID LEN ERR CHECKSUM ---
    for i in range(len(raw) - 1):
        if raw[i] == 0xFF and raw[i + 1] == 0xFF:
            pkt = raw[i:]
            if len(pkt) >= 6:
                sid, length, err, chk = pkt[2], pkt[3], pkt[4], pkt[5]
                if ((~(sid + length + err)) & 0xFF) == chk:
                    return sid, err, "clean"

    # --- resynced case: FF ID LEN ERR CHECKSUM (first 0xFF dropped) ---
    for i in range(len(raw)):
        if raw[i] == 0xFF:
            pkt = raw[i:]
            if len(pkt) >= 5:
                sid, length, err, chk = pkt[1], pkt[2], pkt[3], pkt[4]
                if ((~(sid + length + err)) & 0xFF) == chk:
                    return sid, err, "resynced — first 0xFF dropped by framing error"

    return None


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
    set_vmin(ser, PING_RESPONSE_LEN)

    raw = b''
    for attempt in range(1, MAX_RETRIES + 2):
        ser.reset_input_buffer()
        ser.write(pkt)
        raw = ser.read(PING_RESPONSE_LEN)
        if raw:
            break
        if attempt <= MAX_RETRIES:
            print(f"  Empty response, retrying ({attempt}/{MAX_RETRIES})...")

    ser.close()

    print(f"Response: {' '.join(f'{b:02X}' for b in raw)} ({len(raw)}/{PING_RESPONSE_LEN} bytes)")

    result = parse_response(raw)

    if result is None:
        print("  x Could not parse response — servo not present or garbage on bus")
        return

    servo_id, err, note = result
    if note != "clean":
        print(f"  ~ Parser note: {note}")

    if err == 0:
        print(f"  + Servo ID {servo_id} alive — no errors")
    else:
        print(f"  ! Servo ID {servo_id} responded with error byte: 0x{err:02X}")


if __name__ == "__main__":
    main()
