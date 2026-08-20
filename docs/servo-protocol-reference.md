# STS3215 Servo Protocol Reference

Practical reference for the FEETECH STS3215 half-duplex TTL serial protocol,
as actually exercised by this project. For the complete register map beyond
what's covered here, see the vendor sources in `docs/component_specs/`:
`ST3215 Communication Manual.pdf`, `ST3215-general-manual.pdf`,
`sts3215_memory_table.xlsx`, `Servo-bus-schematic.pdf`.

Most code in this repo talks to servos through LeRobot's `FeetechMotorsBus`
(named fields like `"Present_Position"`, `"Goal_Position"`), not raw
register addresses — this doc is for the raw-protocol layer underneath that
abstraction (`software/scservo_sdk/`, `software/low-lvl-setup/*.py`), and
for understanding what the abstraction is actually doing on the wire.

## Packet framing

```
0xFF 0xFF | ID | LEN | INST | PARAMS... | CHECKSUM
```

- `CHECKSUM = ~(ID + LEN + INST + PARAMS) & 0xFF`
- `LEN` = number of bytes *after* the LEN field itself (`INST` + `PARAMS` +
  `CHECKSUM`)
- Broadcast ID = `0xFE` (254) — servo acts but sends no reply. Used for
  `SYNC_WRITE`.

## Key instructions

| Instruction | Code | Notes |
|---|---|---|
| PING | 0x01 | Servo responds with a status packet — reports model number `777` for STS3215. Cheapest health check available. |
| READ | 0x02 | Read N bytes starting at an address |
| WRITE | 0x03 | Write bytes starting at an address |
| SYNC_WRITE | 0x83 | Broadcast write to multiple servos in one transaction — this is what `bus.sync_write()` uses under the hood, and why a 6-joint goal update costs one bus transaction, not six |

## Key register addresses confirmed in use

| Register | Address | Notes |
|---|---|---|
| ID | 5 | EPROM — requires lock/unlock before writing |
| BAUD_RATE | 6 | EPROM — `0` = 1 Mbps (factory default), `1` = 500K, etc. |
| TORQUE_ENABLE | 40 | SRAM — `1` = enabled |
| GOAL_POSITION_L/H | 42–43 | SRAM — 0–4095 raw range |
| PRESENT_POSITION_L/H | 56–57 | SRAM — read-only |

Everything else this project touches (`Homing_Offset`, `Min/Max_Position_Limit`,
`Maximum_Velocity_Limit`, `Acceleration`) is written through LeRobot's
`FeetechMotorsBus.write()`/`.read()` by field name — see the full memory
table in `sts3215_memory_table.xlsx` for their raw addresses if working below
that abstraction.

## Hardware-verified behavior (the parts no datasheet page will tell you)

- **Wiring is straight-through, not crossed.** The Waveshare Bus Servo
  Adapter labels its pins from the host's perspective: TX→TX, RX→RX. This
  is the opposite of the usual UART cross-wiring convention and was the
  root cause of an initial "no response at all" failure — full chronology
  in `docs/debugging/servo-comms-debug-log.md`.
- **A serial console on the servo UART silently eats bytes.** If comms are
  flaky in a way that looks like framing errors, check
  `systemctl is-enabled serial-getty@<port>` (or `/proc/cmdline` for a
  kernel console) before suspecting the protocol layer. This bit twice —
  once on the Pi, reconfirmed as a risk on the Jetson.
- **`readPort()` should stay stock.** A custom resync layer was added at
  one point to work around what looked like intermittent framing errors; it
  was based on a self-consistent but wrong theory (the real cause was the
  serial-console byte-stealing above) and was reverted. Any retry/error
  recovery belongs in `software/low-lvl-setup/_serial_utils.py`
  (`ping_with_retry`, etc.), not in the packet-parsing layer.
- **`timeout=0.1`, not `timeout=0`, when opening the port.**
  `timeout=0` sets `O_NONBLOCK` on the fd, which makes `ser.read()` return
  immediately regardless of the VMIN termios setting — this silently
  breaks every SDK read. `port_handler.py`'s one deliberate deviation from
  upstream is opening with `timeout=0.1` so `_serial_utils.set_vmin(ser,
  vmin=1)` can actually take effect.
- **`Present_Position` already has the homing offset applied in hardware,
  even with `normalize=False`.** The servo computes
  `Present_Position = (raw_encoder − Homing_Offset) mod 4096` internally
  and reports the wrapped 0–4095 result — there's no way to read the
  "pre-offset" raw encoder value directly. This mod-4096 wrapping requires
  Phase register bit 4 (`0x10`) to be cleared, which LeRobot's
  `configure_motors()` does for `sts3215`. This was the key insight behind
  fixing the encoder wrap-around calibration bug (`docs/context.md`,
  "Encoder Wrap-Around" section) — the earlier assumption that
  `normalize=False` reads were offset-independent was wrong.
- **`num_retry` defaults to 0** on `bus.read()`/`bus.write()` — a single
  dropped status packet raises `ConnectionError` and crashes an unattended
  script. Pass `num_retry=3` (or similar) on any call in a script meant to
  run without a human watching it; LeRobot's own internal cleanup code
  (`disable_torque()`) uses `num_retry=5` for the same reason.
- **A servo in position mode keeps driving toward `Goal_Position` under
  torque** even after a host-side polling loop has given up and timed out.
  Sustained contact with an obstruction (not a momentary spike) is what
  trips the servo's own overcurrent (`OverEle`) protection fault, which
  auto-disables its torque — a stalled/timed-out script on the host side
  does not, by itself, stop the servo from pushing.
