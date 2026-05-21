#!/usr/bin/env python3
"""
_serial_utils.py
----------------
Shared helpers for STS3215 SDK-based control scripts.

Centralises three concerns that every SDK-using script needs to get right:

  1. VMIN fix              — set termios VMIN=1 so SDK read(1) calls block
                             until at least one byte arrives.
  2. Port open boilerplate — open PortHandler, set baud, apply VMIN, return
                             (port_handler, st) pair.
  3. Retry wrappers        — wrap ping()/ReadPos() with a small retry loop
                             to absorb the 0/6 framing-error case at bus
                             turnaround.

Background
----------
The Waveshare bus servo board is half-duplex. At the TX→RX turnaround the
servo's line driver takes time to charge the bus back to idle-high (RC rise
time). During that window the PL011 UART samples what looks like a start bit
on a low line and reads a framing-errored byte. The Linux tty layer under its
default IGNPAR setting silently discards that byte.

There are two failure modes:

  * 5/6 bytes received — first 0xFF of the response header is dropped.
    Recovered inside port_handler.readPort() via the resync parser
    (reconstructs the missing 0xFF and validates checksum).

  * 0/6 bytes received — outgoing instruction itself was corrupted; servo
    never replies. Recovered by retrying — on the second attempt the line
    driver is "warm" and the transient is smaller. This is what the retry
    wrappers in this file are for.

Two more pyserial gotchas this file handles:

  * pyserial's timeout=0 sets O_NONBLOCK, which makes read() return
    immediately regardless of VMIN. port_handler.setupPort() now opens with
    timeout=0.1 so VMIN is respected; see port_handler.py for the change.

  * Default VMIN=0 VTIME=0 still lets read() return 0 bytes when nothing
    has arrived. Setting VMIN=1 fixes this for the read-one-byte-at-a-time
    loop inside port_handler.readPort().

See docs/debugging/servo-comms-debug-log.md for the full investigation and
raw_ping.py for the SDK-bypassing ground-truth implementation.

USAGE:
    from _serial_utils import open_sdk_port, ping_with_retry, read_pos_with_retry

    port_handler, st = open_sdk_port("/dev/ttyAMA0", 1_000_000)
    ok, model = ping_with_retry(st, servo_id=1)
    pos, ok   = read_pos_with_retry(st, servo_id=1)
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
      * opens via PortHandler (which now uses timeout=0.1 internally)
      * sets requested baud
      * sets VMIN=1 on the fd
    """
    port_handler = PortHandler(port)
    st = sms_sts(port_handler)

    if not port_handler.openPort():
        print(f"ERROR: Could not open port {port}.")
        print("  Check: board powered (12V barrel)? Mode switch set correctly?")
        raise SystemExit(1)

    if not port_handler.setBaudRate(baud):
        print(f"ERROR: Could not set baud rate {baud}.")
        port_handler.closePort()
        raise SystemExit(1)

    # Must be after the final setupPort() call — setBaudRate reopens the fd.
    set_vmin(port_handler.ser, vmin=1)

    return port_handler, st


# ---------------------------------------------------------------------------
# Retry wrappers
# ---------------------------------------------------------------------------

def ping_with_retry(st, servo_id: int, max_retries: int = DEFAULT_MAX_RETRIES):
    """Ping a servo, retrying on framing errors.

    Returns (ok: bool, model_number: int). On failure model_number is 0.

    Note: the SDK's ping() internally does TWO transactions — the ping
    itself, then a read of the model-number register. Either one can hit a
    framing error. The retry here covers the case where one of them returns
    0/6 bytes; the resync parser in port_handler covers the 5/6 case
    transparently.
    """
    last_result = None
    for attempt in range(max_retries + 1):
        model, result, _error = st.ping(servo_id)
        if result == COMM_SUCCESS:
            return True, model
        last_result = result
    return False, 0


def read_pos_with_retry(st, servo_id: int, max_retries: int = DEFAULT_MAX_RETRIES):
    """Read present position, retrying on framing errors.

    Returns (pos: int, ok: bool). On failure pos is 0.
    """
    for attempt in range(max_retries + 1):
        pos, result, _error = st.ReadPos(servo_id)
        if result == COMM_SUCCESS:
            return pos, True
    return 0, False


def write_byte_with_retry(st, servo_id: int, addr: int, value: int,
                          max_retries: int = DEFAULT_MAX_RETRIES):
    """Write a single byte to a register, retrying on framing errors.

    Returns (ok: bool, result_code). Useful for SRAM/EPROM writes that
    expect a status packet back — those acks are subject to the same
    turnaround framing error as ping responses.

    Caller is responsible for unlocking EPROM beforehand if writing to one
    of the EPROM registers.
    """
    last_result = None
    for attempt in range(max_retries + 1):
        result, _error = st.write1ByteTxRx(servo_id, addr, value)
        if result == COMM_SUCCESS:
            return True, result
        last_result = result
    return False, last_result
