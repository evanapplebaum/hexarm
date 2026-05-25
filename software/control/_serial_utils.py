#!/usr/bin/env python3
"""
_serial_utils.py
----------------
Shared helpers for STS3215 SDK-based control scripts. Three responsibilities:

  1. VMIN fix              — set termios VMIN=1 after open so that the SDK's
                             ser.read() calls block until a byte arrives
                             instead of returning empty immediately.
  2. Port open boilerplate — wrap PortHandler + sms_sts construction, baud
                             setting, and VMIN; return (port_handler, st).
  3. Retry wrappers        — wrap ping()/ReadPos()/write1ByteTxRx() with a
                             small retry loop. Cheap insurance for any
                             residual flakiness; not currently load-bearing
                             on a healthy bus.

Background — two pyserial gotchas this file handles
---------------------------------------------------
  * pyserial's timeout=0 sets O_NONBLOCK on the fd, which makes ser.read()
    return immediately regardless of VMIN. port_handler.setupPort() now
    opens with timeout=0.1 to avoid this; see port_handler.py.

  * pyserial's default VMIN=0 also lets ser.read(n) return short reads (or
    0 bytes) when bytes haven't arrived yet. Setting VMIN=1 via termios
    after open fixes this for the SDK's read-one-byte-at-a-time pattern.

History
-------
A previous version of this module + a custom resync parser in
port_handler.readPort() were built around the theory that the PL011 was
dropping the leading 0xFF of responses to a UART framing error at the bus
turnaround. That theory was wrong — the real cause was a serial console
(console=serial0,115200 in cmdline.txt) and serial-getty@ttyAMA0.service
contesting /dev/ttyAMA0 with our scripts. Once those were disabled, clean
6/6 responses came back consistently and the resync parser was removed
(it had also been silently breaking multi-transaction SDK calls like
ping() by stealing the leading byte of the second transaction's response).

See docs/debugging/servo-comms-debug-log.md Phase 5 for the full story.

USAGE:
    from _serial_utils import (
        open_sdk_port, ping_with_retry,
        read_pos_with_retry, write_byte_with_retry,
    )

    port_handler, st = open_sdk_port("/dev/ttyAMA0", 1_000_000)
    ok, model = ping_with_retry(st, servo_id=1)
    pos, ok   = read_pos_with_retry(st, servo_id=1)
    ok, _     = write_byte_with_retry(st, servo_id=1, addr=40, value=0)
"""

import os
import sys
import termios

# scservo_sdk lives in software/ — one level up from software/control/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scservo_sdk import PortHandler, sms_sts, COMM_SUCCESS  # noqa: E402


# Default retry budget. One extra attempt is enough in practice to clear the
# 0/6 case — the bus has settled by the second try. Keep low so genuinely
# absent servos still fail fast.
DEFAULT_MAX_RETRIES = 2


# ---------------------------------------------------------------------------
# Low-level termios helper
# ---------------------------------------------------------------------------

def set_vmin(ser, vmin: int = 1, vtime: int = 0) -> None:
    """Set VMIN/VTIME on the underlying serial fd via termios.

    Call AFTER opening the port. pyserial's default VMIN=0 makes read(n)
    return immediately even when no data has arrived; setting VMIN=1 makes
    read(1) block until at least one byte is available, which is what the
    deadline loop in port_handler.readPort() expects.

    VMIN > 0 only works if O_NONBLOCK is clear on the fd — port_handler now
    opens with timeout=0.1 to ensure this.
    """
    fd = ser.fileno()
    attrs = termios.tcgetattr(fd)
    attrs[6][termios.VMIN] = vmin
    attrs[6][termios.VTIME] = vtime
    termios.tcsetattr(fd, termios.TCSANOW, attrs)


# ---------------------------------------------------------------------------
# Port lifecycle
# ---------------------------------------------------------------------------

def open_sdk_port(port: str, baud: int):
    """Open a serial port for SDK use. Returns (port_handler, st).

    On failure prints a diagnostic and raises SystemExit — callers are
    expected to be scripts, not library code.

    The function applies all of the workarounds the SDK needs to talk to an
    STS3215 reliably on a Pi via the Waveshare board:
      * opens via PortHandler (which uses timeout=0.1 internally so VMIN works)
      * sets requested baud
      * sets VMIN=1 on the fd

    Note on the open path: PortHandler.openPort() internally calls
    setBaudRate(self.baudrate) where self.baudrate is the constructor default.
    Setting port_handler.baudrate BEFORE openPort avoids a redundant
    close/reopen cycle.
    """
    port_handler = PortHandler(port)
    port_handler.baudrate = baud  # consumed by openPort → setBaudRate → setupPort
    st = sms_sts(port_handler)

    if not port_handler.openPort():
        print(f"ERROR: Could not open port {port} at {baud} baud.")
        print("  Check: board powered (12V barrel)? Mode switch set correctly?")
        raise SystemExit(1)

    # Must be after setupPort() — VMIN=0 is pyserial's default and would
    # otherwise let ser.read(1) return immediately with 0 bytes.
    set_vmin(port_handler.ser, vmin=1)

    return port_handler, st


# ---------------------------------------------------------------------------
# Retry wrappers
# ---------------------------------------------------------------------------

def ping_with_retry(st, servo_id: int, max_retries: int = DEFAULT_MAX_RETRIES):
    """Ping a servo, retrying on transient comm errors.

    Returns (ok: bool, model_number: int). On failure model_number is 0.

    The SDK's ping() internally does TWO transactions — the ping itself,
    then a read of the model-number register at address 3. Either one
    failing returns a non-COMM_SUCCESS result here. On a healthy bus
    (console removed, getty disabled), this normally succeeds on the
    first try in sub-millisecond time. The retry is cheap insurance
    against any rare transient.
    """
    last_result = None
    for attempt in range(max_retries + 1):
        model, result, _error = st.ping(servo_id)
        if result == COMM_SUCCESS:
            return True, model
        last_result = result
    return False, 0


def read_pos_with_retry(st, servo_id: int, max_retries: int = DEFAULT_MAX_RETRIES):
    """Read present position, retrying on transient comm errors.

    Returns (pos: int, ok: bool). On failure pos is 0.
    """
    for attempt in range(max_retries + 1):
        pos, result, _error = st.ReadPos(servo_id)
        if result == COMM_SUCCESS:
            return pos, True
    return 0, False


def write_byte_with_retry(st, servo_id: int, addr: int, value: int,
                          max_retries: int = DEFAULT_MAX_RETRIES):
    """Write a single byte to a register, retrying on transient comm errors.

    Returns (ok: bool, result_code). Useful for SRAM/EPROM writes that
    expect a status packet back — those acks go through the same RX path
    as ping responses and can hit the same transient errors.

    Caller is responsible for unlocking EPROM beforehand if writing to one
    of the EPROM registers (registers 0–13). Do not use with broadcast
    ID (0xFE) — broadcast writes don't reply, so every "retry" would fail
    after a full timeout. Use st.write1ByteTxRx(0xFE, ...) directly for
    broadcast.
    """
    last_result = None
    for attempt in range(max_retries + 1):
        result, _error = st.write1ByteTxRx(servo_id, addr, value)
        if result == COMM_SUCCESS:
            return True, result
        last_result = result
    return False, last_result
