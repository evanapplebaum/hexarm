#!/usr/bin/env python3
"""
sdk_diag.py
-----------
Diagnostic to isolate why raw_ping.py works on the Pi but the SDK path
doesn't. Runs four read patterns against the SAME servo, on the SAME port,
back-to-back, and reports bytes received + timing for each.

Variants (run in order, each repeated N times):
  A. RAW   — pyserial only, VMIN=6, single ser.read(6)               (works in raw_ping.py)
  B. VMIN1 — pyserial only, VMIN=1, single ser.read(6)               (does VMIN=1 break the single read?)
  C. LOOP  — pyserial only, VMIN=1, ser.read(1) x 6 in a loop        (does the loop pattern break?)
  D. SDK   — PortHandler+sms_sts ping() via the patched stack         (the actually-broken path)

Between variants we also print the current termios VMIN/VTIME so we can
catch the case where pyserial silently resets VMIN.

Usage on the Pi:
  python3 software/control/sdk_diag.py --id 2
"""

import sys
import os
import time
import serial
import termios
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scservo_sdk import PortHandler, sms_sts, COMM_SUCCESS

PING_LEN = 6


def ping_packet(sid):
    chk = (~(sid + 0x02 + 0x01)) & 0xFF
    return bytes([0xFF, 0xFF, sid, 0x02, 0x01, chk])


def get_vmin_vtime(ser):
    attrs = termios.tcgetattr(ser.fileno())
    return attrs[6][termios.VMIN], attrs[6][termios.VTIME]


def set_vmin(ser, vmin, vtime=0):
    fd = ser.fileno()
    attrs = termios.tcgetattr(fd)
    attrs[6][termios.VMIN] = vmin
    attrs[6][termios.VTIME] = vtime
    termios.tcsetattr(fd, termios.TCSANOW, attrs)


def variant_raw(port, baud, sid, attempts):
    """A. Mirrors raw_ping.py exactly."""
    print("\n--- A. RAW (pyserial, VMIN=6, single read(6)) ---")
    pkt = ping_packet(sid)
    ok = 0
    for i in range(1, attempts + 1):
        ser = serial.Serial(port, baudrate=baud, timeout=0.1)
        set_vmin(ser, PING_LEN)
        vmin, vtime = get_vmin_vtime(ser)
        ser.reset_input_buffer()
        t0 = time.perf_counter()
        ser.write(pkt)
        raw = ser.read(PING_LEN)
        dt = (time.perf_counter() - t0) * 1000
        ser.close()
        print(f"  [{i}] VMIN={vmin} VTIME={vtime}  bytes={len(raw)}/{PING_LEN}  dt={dt:.1f}ms  raw={raw.hex(' ')}")
        if len(raw) >= 5:  # accept resync case
            ok += 1
    print(f"  RAW total: {ok}/{attempts} got >=5 bytes")
    return ok


def variant_vmin1(port, baud, sid, attempts):
    """B. Like RAW but VMIN=1. Does the single-shot read still work?"""
    print("\n--- B. VMIN1 (pyserial, VMIN=1, single read(6)) ---")
    pkt = ping_packet(sid)
    ok = 0
    for i in range(1, attempts + 1):
        ser = serial.Serial(port, baudrate=baud, timeout=0.1)
        set_vmin(ser, 1)
        vmin, vtime = get_vmin_vtime(ser)
        ser.reset_input_buffer()
        t0 = time.perf_counter()
        ser.write(pkt)
        raw = ser.read(PING_LEN)
        dt = (time.perf_counter() - t0) * 1000
        ser.close()
        print(f"  [{i}] VMIN={vmin} VTIME={vtime}  bytes={len(raw)}/{PING_LEN}  dt={dt:.1f}ms  raw={raw.hex(' ')}")
        if len(raw) >= 5:
            ok += 1
    print(f"  VMIN1 total: {ok}/{attempts} got >=5 bytes")
    return ok


def variant_loop(port, baud, sid, attempts):
    """C. The SDK's read pattern: VMIN=1, ser.read(1) in a loop until target."""
    print("\n--- C. LOOP (pyserial, VMIN=1, read(1) x 6 in a loop) ---")
    pkt = ping_packet(sid)
    ok = 0
    target = PING_LEN + 1  # mimics readPort's "length+1"
    for i in range(1, attempts + 1):
        ser = serial.Serial(port, baudrate=baud, timeout=0.1)
        set_vmin(ser, 1)
        vmin, vtime = get_vmin_vtime(ser)
        ser.reset_input_buffer()
        t0 = time.perf_counter()
        ser.write(pkt)
        deadline = time.time() + 0.55
        buf = bytearray()
        iters = 0
        empty_reads = 0
        while len(buf) < target and time.time() < deadline:
            iters += 1
            b = ser.read(1)
            if b:
                buf.extend(b)
            else:
                empty_reads += 1
                if empty_reads > 20:  # avoid pathological spin
                    break
        dt = (time.perf_counter() - t0) * 1000
        ser.close()
        print(f"  [{i}] VMIN={vmin} VTIME={vtime}  bytes={len(buf)}/{PING_LEN}  iters={iters}  empty={empty_reads}  dt={dt:.1f}ms  raw={bytes(buf).hex(' ')}")
        if len(buf) >= 5:
            ok += 1
    print(f"  LOOP total: {ok}/{attempts} got >=5 bytes")
    return ok


def variant_sdk(port, baud, sid, attempts):
    """D. The full SDK path — open PortHandler, set VMIN=1, call ping()."""
    print("\n--- D. SDK (PortHandler + sms_sts.ping) ---")
    ok = 0
    for i in range(1, attempts + 1):
        ph = PortHandler(port)
        st = sms_sts(ph)
        if not ph.openPort():
            print(f"  [{i}] openPort failed")
            continue
        ph.setBaudRate(baud)
        # Check VMIN immediately after PortHandler's setup
        before = get_vmin_vtime(ph.ser)
        set_vmin(ph.ser, 1)
        after = get_vmin_vtime(ph.ser)
        t0 = time.perf_counter()
        model, result, error = st.ping(sid)
        dt = (time.perf_counter() - t0) * 1000
        ph.closePort()
        # Re-open to recheck if pyserial resets VMIN inside ph.openPort
        print(f"  [{i}] VMIN before our set={before}  after={after}  "
              f"result={result}  model={model}  dt={dt:.1f}ms")
        if result == COMM_SUCCESS:
            ok += 1
    print(f"  SDK total: {ok}/{attempts} COMM_SUCCESS")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyAMA0")
    ap.add_argument("--baud", type=int, default=1_000_000)
    ap.add_argument("--id", type=int, default=2)
    ap.add_argument("--n", type=int, default=5,
                    help="Attempts per variant (default 5)")
    args = ap.parse_args()

    print(f"Port: {args.port}  Baud: {args.baud}  Servo: {args.id}  Attempts each: {args.n}")
    print(f"Expected ping packet: {ping_packet(args.id).hex(' ')}")

    a = variant_raw  (args.port, args.baud, args.id, args.n)
    b = variant_vmin1(args.port, args.baud, args.id, args.n)
    c = variant_loop (args.port, args.baud, args.id, args.n)
    d = variant_sdk  (args.port, args.baud, args.id, args.n)

    print("\n=== SUMMARY ===")
    print(f"  A. RAW   (VMIN=6, read(6)): {a}/{args.n}")
    print(f"  B. VMIN1 (VMIN=1, read(6)): {b}/{args.n}")
    print(f"  C. LOOP  (VMIN=1, read(1) x 6): {c}/{args.n}")
    print(f"  D. SDK   (PortHandler.ping): {d}/{args.n}")
    print()
    print("Interpretation:")
    print("  A pass, B fail → VMIN=1 breaks single-shot read")
    print("  B pass, C fail → the read(1)-loop pattern is the bug")
    print("  C pass, D fail → something in PortHandler/SDK (not the loop) breaks it")
    print("  A,B,C pass, D fail → look at clearPort/flush, double openPort, packet timeout")


if __name__ == "__main__":
    main()
