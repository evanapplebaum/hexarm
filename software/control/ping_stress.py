#!/usr/bin/env python3
"""
ping_stress.py
--------------
Repeatedly pings one STS3215 servo and records every result to a log file.
Used to diagnose intermittent response patterns (e.g. 0/6, 0/6, 6/6).

Two modes:
  --mode reopen    Re-opens the serial port for every ping (default).
                   Mimics running raw_ping.py manually each time.
                   Tests whether the open/close cycle is the cause.

  --mode keepopen  Keeps the port open for all pings.
                   Tests whether direction-switching timing is the cause.

Output columns (CSV):
  run, timestamp_s, mode, delay_between_pings_ms, bytes_received, hex_bytes, result

Usage:
    python3 ping_stress.py --id 9 --count 100 --mode reopen   --out reopen.csv
    python3 ping_stress.py --id 9 --count 100 --mode keepopen --out keepopen.csv
    python3 ping_stress.py --id 9 --count 100 --mode keepopen --gap 500  # 500ms between pings
"""

import serial
import termios
import argparse
import time
import csv
import sys

PING_RESPONSE_LEN = 6  # FF FF ID LEN ERR CHECKSUM


def ping_packet(servo_id: int) -> bytes:
    checksum = (~(servo_id + 0x02 + 0x01)) & 0xFF
    return bytes([0xFF, 0xFF, servo_id, 0x02, 0x01, checksum])


def set_vmin(ser, vmin, vtime=0):
    fd = ser.fileno()
    attrs = termios.tcgetattr(fd)
    attrs[6][termios.VMIN]  = vmin
    attrs[6][termios.VTIME] = vtime
    termios.tcsetattr(fd, termios.TCSANOW, attrs)


def open_port(port: str, baud: int) -> serial.Serial:
    ser = serial.Serial(port, baudrate=baud, timeout=0.1)
    set_vmin(ser, PING_RESPONSE_LEN)
    return ser


def do_ping(ser, pkt: bytes) -> tuple[int, str]:
    """Send ping, return (bytes_received, hex_string)."""
    ser.reset_input_buffer()
    ser.write(pkt)
    raw = ser.read(PING_RESPONSE_LEN)
    hex_str = ' '.join(f'{b:02X}' for b in raw) if raw else '—'
    return len(raw), hex_str


def result_label(n: int) -> str:
    if n == PING_RESPONSE_LEN:
        return 'OK'
    elif n == 0:
        return 'MISS'
    else:
        return f'PARTIAL_{n}'


def main():
    parser = argparse.ArgumentParser(
        description="Stress-ping one STS3215 servo and log every result."
    )
    parser.add_argument('--id',    type=int, default=1,
                        help='Servo ID to ping')
    parser.add_argument('--port',  default='/dev/ttyAMA0')
    parser.add_argument('--baud',  type=int, default=1_000_000)
    parser.add_argument('--count', type=int, default=50,
                        help='Number of pings to send')
    parser.add_argument('--gap',   type=float, default=200,
                        help='Milliseconds to wait between pings (default: 200)')
    parser.add_argument('--mode',  choices=['reopen', 'keepopen'], default='reopen',
                        help='reopen: open/close port each ping  '
                             'keepopen: keep port open throughout')
    parser.add_argument('--out',   default=None,
                        help='Output CSV file (default: ping_stress_<mode>.csv)')
    args = parser.parse_args()

    out_file = args.out or f'ping_stress_{args.mode}.csv'
    pkt = ping_packet(args.id)
    gap_s = args.gap / 1000.0

    print(f"Servo ID:  {args.id}")
    print(f"Port:      {args.port} @ {args.baud} baud")
    print(f"Mode:      {args.mode}")
    print(f"Pings:     {args.count}")
    print(f"Gap:       {args.gap} ms between pings")
    print(f"Output:    {out_file}")
    print(f"Packet:    {' '.join(f'{b:02X}' for b in pkt)}")
    print()

    counts = {'OK': 0, 'MISS': 0, 'PARTIAL': 0}

    with open(out_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['run', 'timestamp_s', 'mode', 'gap_ms',
                         'bytes_received', 'hex_bytes', 'result'])

        ser = None
        if args.mode == 'keepopen':
            ser = open_port(args.port, args.baud)

        t0 = time.time()

        for i in range(1, args.count + 1):
            if args.mode == 'reopen':
                ser = open_port(args.port, args.baud)

            ts = round(time.time() - t0, 4)
            n, hex_str = do_ping(ser, pkt)
            label = result_label(n)

            if label == 'OK':
                counts['OK'] += 1
            elif label == 'MISS':
                counts['MISS'] += 1
            else:
                counts['PARTIAL'] += 1

            writer.writerow([i, ts, args.mode, args.gap, n, hex_str, label])
            f.flush()  # write immediately so you can tail -f

            status = f'  {"✓" if n == PING_RESPONSE_LEN else "✗"} [{i:>4}/{args.count}]  {n}/{PING_RESPONSE_LEN} bytes  {label:<12}  {hex_str}'
            print(status)

            if args.mode == 'reopen':
                ser.close()

            if i < args.count:
                time.sleep(gap_s)

        if args.mode == 'keepopen' and ser:
            ser.close()

    print()
    print(f"Done. Results saved to {out_file}")
    print(f"  OK:      {counts['OK']}")
    print(f"  MISS:    {counts['MISS']}")
    print(f"  PARTIAL: {counts['PARTIAL']}")
    total = args.count
    print(f"  Success rate: {counts['OK']/total*100:.1f}%")


if __name__ == '__main__':
    main()
