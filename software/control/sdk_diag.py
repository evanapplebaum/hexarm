#!/usr/bin/env python3
"""
sdk_diag.py
-----------
Diagnostic to isolate where the STS3215 comm path is broken on the Pi.

After the first round of testing showed ALL variants (including a verbatim
copy of raw_ping.py) returning 0 bytes even though raw_ping.py worked
moments earlier, the goal shifted: instead of testing read patterns, we now
test BUS STATE — does rapid open/close break it, does a write-after-open
delay help, does an inter-attempt gap help.

Variants (run in order, each repeated N times):
  A. RAW    — verbatim raw_ping.py pattern, fresh open per attempt
  B. VMIN1  — same, but VMIN=1 instead of 6
  C. LOOP   — VMIN=1, ser.read(1) × 6 in a loop (the SDK's read pattern)
  D. SDK    — full PortHandler + sms_sts.ping() stack
  E. WARM   — open ONCE, then ping N times in a row inside that one open

Use --gap to add a delay (ms) between attempts within each variant. raw_ping
had implicit pacing from print() / Python startup; the diag has none, which
may matter if the bus needs settling time between transactions.

Usage on the Pi:
  python3 software/control/sdk_diag.py --id 2                  # back-to-back
  python3 software/control/sdk_diag.py --id 2 --gap 200        # 200ms between attempts
  python3 software/control/sdk_diag.py --id 2 --gap 50 --n 10
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


def _sleep_gap(gap_ms):
    if gap_ms > 0:
        time.sleep(gap_ms / 1000.0)


def variant_raw(port, baud, sid, attempts, gap_ms):
    """A. Mirrors raw_ping.py exactly. Fresh open per attempt."""
    print(f"\n--- A. RAW (VMIN=6, read(6), reopen each attempt, gap={gap_ms}ms) ---")
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
        if len(raw) >= 5:
            ok += 1
        _sleep_gap(gap_ms)
    print(f"  RAW total: {ok}/{attempts} got >=5 bytes")
    return ok


def variant_vmin1(port, baud, sid, attempts, gap_ms):
    """B. Like RAW but VMIN=1, single read(6)."""
    print(f"\n--- B. VMIN1 (VMIN=1, read(6), reopen each attempt, gap={gap_ms}ms) ---")
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
        _sleep_gap(gap_ms)
    print(f"  VMIN1 total: {ok}/{attempts} got >=5 bytes")
    return ok


def variant_loop(port, baud, sid, attempts, gap_ms):
    """C. The SDK's read pattern: VMIN=1, ser.read(1) loop."""
    print(f"\n--- C. LOOP (VMIN=1, read(1) x 6 loop, reopen each attempt, gap={gap_ms}ms) ---")
    pkt = ping_packet(sid)
    ok = 0
    target = PING_LEN + 1
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
                if empty_reads > 20:
                    break
        dt = (time.perf_counter() - t0) * 1000
        ser.close()
        print(f"  [{i}] VMIN={vmin} VTIME={vtime}  bytes={len(buf)}/{PING_LEN}  iters={iters}  empty={empty_reads}  dt={dt:.1f}ms  raw={bytes(buf).hex(' ')}")
        if len(buf) >= 5:
            ok += 1
        _sleep_gap(gap_ms)
    print(f"  LOOP total: {ok}/{attempts} got >=5 bytes")
    return ok


def variant_sdk(port, baud, sid, attempts, gap_ms):
    """D. Full SDK path — PortHandler + sms_sts.ping()."""
    print(f"\n--- D. SDK (PortHandler + sms_sts.ping, reopen each attempt, gap={gap_ms}ms) ---")
    ok = 0
    for i in range(1, attempts + 1):
        ph = PortHandler(port)
        ph.baudrate = baud
        st = sms_sts(ph)
        if not ph.openPort():
            print(f"  [{i}] openPort failed")
            continue
        before = get_vmin_vtime(ph.ser)
        set_vmin(ph.ser, 1)
        after = get_vmin_vtime(ph.ser)
        t0 = time.perf_counter()
        model, result, error = st.ping(sid)
        dt = (time.perf_counter() - t0) * 1000
        ph.closePort()
        print(f"  [{i}] VMIN before={before} after={after}  result={result}  model={model}  dt={dt:.1f}ms")
        if result == COMM_SUCCESS:
            ok += 1
        _sleep_gap(gap_ms)
    print(f"  SDK total: {ok}/{attempts} COMM_SUCCESS")
    return ok


def variant_warm(port, baud, sid, attempts, gap_ms):
    """E. Warm-bus: open ONCE, ping N times inside that single open.

    This isolates the question of whether the bus needs to be "warmed up"
    — raw_ping.py's retry loop reuses one open and often succeeds only on
    the 2nd attempt. If first ping fails but subsequent succeed, that's the
    bus-settling pattern.
    """
    print(f"\n--- E. WARM (VMIN=6, read(6), single open, gap={gap_ms}ms between pings) ---")
    pkt = ping_packet(sid)
    ok = 0
    ser = serial.Serial(port, baudrate=baud, timeout=0.1)
    set_vmin(ser, PING_LEN)
    try:
        for i in range(1, attempts + 1):
            ser.reset_input_buffer()
            t0 = time.perf_counter()
            ser.write(pkt)
            raw = ser.read(PING_LEN)
            dt = (time.perf_counter() - t0) * 1000
            print(f"  [{i}] bytes={len(raw)}/{PING_LEN}  dt={dt:.1f}ms  raw={raw.hex(' ')}")
            if len(raw) >= 5:
                ok += 1
            _sleep_gap(gap_ms)
    finally:
        ser.close()
    print(f"  WARM total: {ok}/{attempts} got >=5 bytes")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyAMA0")
    ap.add_argument("--baud", type=int, default=1_000_000)
    ap.add_argument("--id", type=int, default=2)
    ap.add_argument("--n", type=int, default=5,
                    help="Attempts per variant (default 5)")
    ap.add_argument("--gap", type=int, default=0,
                    help="Milliseconds between attempts (default 0)")
    ap.add_argument("--only", default=None,
                    help="Run only specific variants, e.g. --only AE")
    args = ap.parse_args()

    print(f"Port: {args.port}  Baud: {args.baud}  Servo: {args.id}  "
          f"Attempts each: {args.n}  Gap: {args.gap}ms")
    print(f"Expected ping packet: {ping_packet(args.id).hex(' ')}")

    only = args.only.upper() if args.only else "ABCDE"
    results = {}

    if "A" in only:
        results["A"] = variant_raw  (args.port, args.baud, args.id, args.n, args.gap)
    if "B" in only:
        results["B"] = variant_vmin1(args.port, args.baud, args.id, args.n, args.gap)
    if "C" in only:
        results["C"] = variant_loop (args.port, args.baud, args.id, args.n, args.gap)
    if "D" in only:
        results["D"] = variant_sdk  (args.port, args.baud, args.id, args.n, args.gap)
    if "E" in only:
        results["E"] = variant_warm (args.port, args.baud, args.id, args.n, args.gap)

    print("\n=== SUMMARY ===")
    labels = {
        "A": "RAW   (VMIN=6, read(6), reopen)",
        "B": "VMIN1 (VMIN=1, read(6), reopen)",
        "C": "LOOP  (VMIN=1, read(1)x6 loop, reopen)",
        "D": "SDK   (PortHandler.ping, reopen)",
        "E": "WARM  (single open, N pings)",
    }
    for k in "ABCDE":
        if k in results:
            print(f"  {k}. {labels[k]}: {results[k]}/{args.n}")
    print()
    print("Interpretation key:")
    print("  Nothing works at all          → power-cycle Waveshare, then re-run raw_ping.py")
    print("  E (warm) passes, A (reopen) fails → bus needs settling time between opens; add gap")
    print("  E passes only after first miss  → 'warm bus' pattern (RC transient on first packet)")
    print("  A pass, B fail                → VMIN=1 alone breaks single-shot read")
    print("  A,B pass, C fail              → read(1)-loop is fundamentally broken")
    print("  A,B,C pass, D fail            → bug is inside SDK (clearPort, packet timeout, etc.)")


if __name__ == "__main__":
    main()
