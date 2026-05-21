# hexarm — Project Context

> **Purpose:** Full handoff document for AI sessions (Claude Cowork, Claude.ai, etc.).
> A fresh session reading this file should be able to pick up immediately with zero catch-up questions.
> Update this file at the end of every significant work session.

---

## Project Overview

**hexarm** is a custom 6-DOF serial robotic arm built by Evan Applebaum, based on the SO-100/SO-101 open-source design by TheRobotStudio. Goal: leader–follower teleoperation system with imitation learning via Hugging Face LeRobot.

GitHub: `github.com/evanapplebaum/hexarm`

---

## Hardware

### Arm Structure
- **Design basis:** SO-100 (open-source, 3D-printed frame)
- **Configuration:** Leader arm + follower arm (6 DOF each)
- **Actuators:** 12 × FEETECH STS3215 smart servos (6 per arm)

### Servos — FEETECH STS3215
- **Control:** Half-duplex TTL serial bus (NOT PWM)
- **Encoder:** 12-bit absolute magnetic — no homing needed on boot
- **Feedback:** Position, temperature, voltage, current, load — all readable over bus
- **Supply voltage:** 6–12.6V (running at ~12V in current test setup)
- **Torque:** 19.5 kg·cm @ 7.4V
- **Baud rate:** Factory default = **1,000,000 bps**
- **Factory default ID:** 1 (all servos ship as ID=1)
- **Target IDs:** Leader arm 1–6, follower arm 7–12 (not yet assigned)
- All servos daisy-chained on one bus per arm, addressed by unique ID
- **Status LED:** Red LED on = powered and alive; this has been confirmed in testing

### Servo Driver Boards — Waveshare Bus Servo Adapter (A) (×2)
- **2 boards total — one per arm**
- Sold under "UeeKKoo" brand on Amazon but arrived in Waveshare boxes;
  Amazon listing links to the official Waveshare wiki → treat as Waveshare Bus Servo Adapter (A)
- **Waveshare wiki:** https://www.waveshare.com/wiki/Bus_Servo_Adapter_(A)
- Handles half-duplex bus direction switching in hardware (host sees full-duplex serial)
- **Two host interfaces:**
  - **USB (CH340 chip):** appears on Mac as `/dev/cu.usbmodem*` — use `cu` prefix, NOT `tty`
  - **UART GPIO pins:** for Raspberry Pi connection (no USB needed)
- **Physical mode switch** on board: set to USB-Servo for Mac testing, UART-Servo for Pi
- **Power:** separate DC barrel jack for servo bus power (12V); USB only powers CH340 logic
- Compatible with ST/SC series Feetech servos including STS3215
- **Official Python SDK:** STservo_sdk (see software section)

### Compute — Raspberry Pi Zero 2W
- **Status:** ✅ SSHable — UART setup in progress (2026-05-19)
- **OS:** Ubuntu 24.04 Server (fresh flash via Raspberry Pi Imager)
- **Network:** WiFi on "Apples" home network — IP `192.168.86.121`
- **SSH:** `ssh ekapi@eka-pi02w.local` or `ssh ekapi@192.168.86.121`
- **Connection to driver boards:** UART GPIO pins (one board per arm)
- **UART setup:** PL011 hardware UART freed from Bluetooth via `dtoverlay=disable-bt` + `enable_uart=1` in `/boot/firmware/config.txt` — exposes `/dev/ttyAMA0` on GPIO 14 (TX) and GPIO 15 (RX)
  - Pi Zero 2W has two UARTs: PL011 (hardware, clock-independent, reliable at 1Mbps) and mini-UART (CPU-clock-dependent, unreliable at high baud). PL011 is assigned to Bluetooth by default; disable-bt overlay frees it.
- **Wiring to Waveshare board (UART-Servo mode):** Pi GPIO14/TX → Board RX, Pi GPIO15/RX → Board TX, Pi GND → Board GND
- **Known dirty config:** `dtoverlay=dwc2,dr_mode=peripheral` and `modules-load=dwc2,g_ether` still in boot config from USB gadget mode attempts — harmless but should be cleaned up

### Vision (planned)
- Wrist-mounted camera and/or overhead workspace camera
- Hardware TBD

---

## Repository Structure

```
hexarm/
├── docs/
│   ├── context.md                      ← this file (AI handoff doc)
│   ├── kinematics.md                   ← kinematics notes and derivations
│   ├── images/
│   └── documentation/                  ← datasheets and manuals
│       ├── ST3215 Communication Manual.pdf
│       ├── ST3215-general-manual.pdf
│       ├── Servo-bus-schematic.pdf
│       └── sts3215_memory_table.xlsx
├── cad/
│   ├── assembly/
│   ├── exports/
│   ├── parts/
│   └── renders/
├── electronics/
│   ├── bom/
│   └── schematics/
│       └── Raspberry Pi 5 Pinout.png   ← NOTE: outdated, project uses Pi Zero 2W
├── firmware/
│   ├── tools/
│   │   └── set_baud_115200/
│   │       └── set_baud_115200.ino     ← Arduino one-shot: changes servo baud 1Mbps→115200
│   ├── lib/
│   └── src/
├── scripts/
│   └── setup-github.sh
├── simulation/
│   └── urdf/
├── software/
│   ├── control/                        ← host-side Python scripts (run from repo root)
│   │   ├── ping_one.py                 ← ping a single servo (CLI: --port, --id, --baud)
│   │   ├── raw_ping.py                 ← raw pyserial diagnostic, bypasses SDK entirely
│   │   ├── baud_scan.py                ← scans all baud rates × IDs 1–20 for any response
│   │   ├── setup_servo.py              ← flash ID, return delay, baud rate to one servo at a time
│   │   ├── ping_stress.py              ← stress-ping a servo N times, logs results to CSV
│   │   ├── config.py                   ← motor IDs, port assignments (needs rewrite — Pi 5 refs)
│   │   └── read_register.py            ← read arbitrary EPROM/SRAM register (needs VMIN fix)
│   ├── scservo_sdk/                    ← Feetech official SDK (NOT a pip package — local copy)
│   │   ├── protocol_packet_handler.py  ← packet framing/parsing (keep UNMODIFIED — see debug notes)
│   │   ├── sms_sts.py                  ← STS/SMS series class (correct for STS3215)
│   │   ├── port_handler.py
│   │   └── ...
│   ├── STServo_Python/                 ← DELETED (Windows venv, redundant with scservo_sdk/)
│   ├── arduino/
│   │   ├── ping_servo/
│   │   │   └── ping_servo.ino          ← Arduino ping sketch (half-duplex, 1kΩ resistor wiring)
│   │   ├── ping_servo_uno/
│   │   │   └── ping_servo_uno.ino      ← Uno variant
│   │   └── st3215-src/                 ← Feetech Arduino library source (SCServo)
│   │       ├── SCServo/                ← Library with SMS_STS, SCSCL classes + examples
│   │       └── ST Servo/               ← Alternative library variant
│   ├── kinematics/
│   ├── utils/
│   └── config/
│       └── limits.json                 ← joint travel limits (populated by calibrate.py)
├── .venv/                              ← Python venv (recreate per platform — NOT cross-platform)
└── .gitignore
```

### Important config.py Notes
- `config.py` currently has port assignments written for **Pi 5** (`/dev/ttyAMA0` and `/dev/ttyAMA3` on GPIO 4/5)
- **Pi Zero 2W only has one exposed hardware UART** (ttyAMA0 on GPIO 14/15 after disable-bt)
- Second arm port strategy for Pi Zero 2W is TBD — options: USB adapter, or software UART
- The 1kΩ resistor half-duplex wiring comment in config.py applies to **direct** Pi→servo wiring; the Waveshare board handles this internally

---

## Software Stack

```
LeRobot policy / teleop loop        (Pi only — not usable on Intel Mac)
        ↓
FeetechMotorsBus                    (register map abstraction)
        ↓
scservo_sdk / pyserial              (raw packet framing over UART)
        ↓
USB/UART → Waveshare board → servo bus
```

### scservo_sdk vs STservo_sdk
Both SDKs are from Feetech/Waveshare and use identical packet protocols for STS3215:
- `scservo_sdk` — Feetech's original SDK; uses class `sms_sts` for STS/SMS servos; **this is the one in use**
- `STservo_sdk` — Waveshare's renamed version; uses class `sts` (functionally identical); **deleted from repo** (Windows venv, redundant)
- "SCServo" is Feetech's brand name for the whole ecosystem, not a specific protocol
- `port_handler.py` has been modified with a resync parser in `readPort()` — do NOT replace with stock version

### Mac Development Environment
- **Venv:** `hexarm/.venv` (Python 3.12)
- **Activate:** `source .venv/bin/activate` (from hexarm root, every new session)
- **Installed packages:** pyserial 3.5
- **LeRobot:** NOT installable on Intel Mac — torch 2.7+ has no x86_64 macOS build
- **Serial port:** `/dev/cu.usbmodem5B141112771` (confirmed working port name)
  - IMPORTANT: use `cu` prefix, NOT `tty` — `tty` blocks waiting for carrier detect
  - Port shows as `usbmodem` (USB CDC) not `usbserial` (CH340 with driver)
- **SDK in use:** `scservo_sdk` (in `software/scservo_sdk/`, imported via `sys.path.insert`)

### LeRobot (Pi — future)
- Version: 0.5.2
- Feetech driver: `lerobot.motors.feetech.feetech.FeetechMotorsBus`
- Python 3.12 required (numba constraint: >=3.9, <3.13)
- Venv on Pi: `source ~/lerobot-env/bin/activate`

---

## STS3215 Protocol Reference

Packet format: `0xFF 0xFF | ID | LEN | INST | PARAMS... | CHECKSUM`
- Checksum = `~(ID + LEN + INST + PARAMS) & 0xFF`
- LEN = number of bytes after LEN field (INST + PARAMS + CHECKSUM)

Key instructions:
| Instruction | Code | Notes |
|---|---|---|
| PING | 0x01 | Servo responds with status packet |
| READ | 0x02 | Read N bytes from address |
| WRITE | 0x03 | Write to address |
| SYNC_WRITE | 0x83 | Broadcast write to multiple servos |

Key register addresses (sms_sts / STS3215):
| Register | Address | Notes |
|---|---|---|
| ID | 5 | EPROM — requires lock/unlock |
| BAUD_RATE | 6 | EPROM — 0=1Mbps, 1=500K, etc. |
| TORQUE_ENABLE | 40 | SRAM — 1=enabled |
| GOAL_POSITION_L/H | 42–43 | SRAM — 0–4095 range |
| PRESENT_POSITION_L/H | 56–57 | SRAM — read only |

Broadcast ID = 0xFE (254) — no response expected, servo acts but does not reply.

---

## Servo Communication — RESOLVED ✅

**Status as of 2026-05-20:** All 12 servos responding. Two separate issues encountered and resolved.

### Issue 1: No response at all (resolved 2026-05-19)
**Root cause: Wrong UART wiring.** The Waveshare Bus Servo Adapter (A) uses **straight-through wiring** (TX→TX, RX→RX), NOT the standard crossed wiring. The board labels its pins from the host's perspective — counterintuitive and underdocumented. See `docs/debugging/servo-comms-debug-log.md` Phases 1–3.

### Issue 2: Intermittent responses — 0/5/6 bytes, never 1–4 (resolved 2026-05-20)
**Root cause: UART framing error from line-driver turn-on transient.**

At the TX→RX bus turnaround, the servo's line driver takes time to charge the bus back to idle-high (RC rise time: τ = R_driver × C_bus). During this rise, the PL011 UART samples what looks like a valid start bit (line still low), then reads garbage data bits — a **framing error**. The Linux tty layer, under its default `IGNPAR` setting, **silently discards** the framing-errored byte with no warning to userspace.

Because only the **first byte** of the response is at the turnaround boundary (all subsequent bytes arrive cleanly and contiguously), the only possible byte counts are 0, 5, or 6. Counts of 1–4 are physically impossible under this failure mode — and empirically, none were observed across hundreds of pings.

The 0/6 case: the framing error hits the **outgoing ping's** first byte, corrupting it — the servo rejects the whole packet and sends no response at all.

**Fix implemented in `scservo_sdk/port_handler.py` and `control/raw_ping.py`:**
1. **Resync parser** — reads `length+1` bytes; finds `FF FF` header. If only a lone `FF` is found (first 0xFF dropped by tty layer), prepends a synthetic 0xFF to reconstruct the packet. Checksum `~(ID+LEN+ERR)&0xFF` confirms integrity.
2. **Retry on empty response** (MAX_RETRIES=2 in `raw_ping.py`) — the 0/6 case resolves on retry because the line driver is "warm" from the first transmission; the RC capacitance is already partially charged and the transient is smaller on subsequent attempts.

**What was ruled out:**
- Return delay (reg 7): doesn't help — the transient is physically tied to the first byte regardless of the silence period before it.
- Baud rate reduction to 250kbps: doesn't help — the RC time constant is set by hardware, independent of bit timing.

**VMIN/VTIME note:** pyserial sets `VMIN=0 VTIME=0` on port open, which persists after `close()`. With VMIN=0, `read(n)` returns immediately with 0 bytes if nothing has arrived yet, making missed responses look identical to an empty buffer. Fix: call `termios.tcsetattr()` to set `VMIN=n` after opening the port. See `raw_ping.py:set_vmin()`.

### Confirmed working configuration
- **Host:** Raspberry Pi Zero 2W
- **Interface:** Hardware UART `/dev/ttyAMA0` (PL011, GPIO 14/15)
- **Wiring:** Pi TX (GPIO 14) → Board TX, Pi RX (GPIO 15) → Board RX, GND → GND
- **Board mode switch:** UART-Servo
- **Board power:** 12V barrel jack only
- **Baud rate:** 1,000,000 bps
- **All 12 servos responding:** IDs 1–12 ✅

See `docs/debugging/servo-comms-debug-log.md` for the full narrative.

---

## Setup Status

| Task | Status |
|---|---|
| LeRobot 0.5.2 installed (Pi) | ✅ Done |
| Mac venv created (Python 3.12) | ✅ Done |
| pyserial installed in Mac venv | ✅ Done |
| scservo_sdk copied into software/ | ✅ Done |
| ping_one.py, raw_ping.py, baud_scan.py, setup_servo.py created | ✅ Done |
| Framing error resync parser in port_handler.py + raw_ping.py | ✅ Done (2026-05-20) |
| LeRobot installed in Mac venv | ❌ Not possible (Intel Mac, torch 2.7+) |
| Mac → board → servo communication working | ⚠️ Not yet tested (USB-Servo mode) |
| Pi → board → servo communication working | ✅ Done (2026-05-19) |
| Pi Zero 2W setup (Ubuntu 24.04) | ✅ Done |
| Pi UART configured (ttyAMA0) | ✅ Done |
| Driver board connected to Pi | ✅ Done |
| Servo IDs assigned (1–6 leader, 7–12 follower) | ✅ Done (2026-05-20) |
| Bus communication test (ping all 12 servos) | ✅ Done (2026-05-20) |
| config.py rewrite (remove LeRobot, update for Pi Zero 2W) | ⏳ Todo |
| read_register.py VMIN fix | ⏳ Todo |
| Second arm port strategy for Pi Zero 2W | ⏳ Todo |
| Joint limit calibration (calibrate.py) | ⏳ Next up |
| First teleoperation test (teleop.py from scratch) | ⏳ Todo |
| Dataset recording | ⏳ Todo |
| Policy training | ⏳ Todo |

---

## Key Technical Notes

### Half-Duplex Direction Switching
STS3215 uses half-duplex UART — TX and RX share one wire on the servo side. The Waveshare board handles direction switching internally. The host sends normal full-duplex serial; the board drives the bus on TX and listens on RX. There is NO echo of TX bytes back to the host's RX buffer (confirmed by comparing with official SDK, which has no echo-consuming code).

### tty vs cu on macOS
On macOS, each USB serial device appears twice: `/dev/tty.*` and `/dev/cu.*`.
- `tty` waits for carrier detect — designed for incoming connections (modems receiving calls)
- `cu` (call-up) initiates connections — correct for outbound serial communication
- Always use `/dev/cu.usbmodem*` for this board on Mac.

### Pi UART Configuration Commands

```bash
# Append a line to /boot/firmware/config.txt (Pi's boot config, read at startup):
echo "dtoverlay=disable-bt" | sudo tee -a /boot/firmware/config.txt
# echo "..." — print the string to stdout
# sudo tee -a <file> — tee reads stdin and writes to both stdout AND the file;
#   -a means append (don't overwrite); sudo needed because /boot/firmware/ is root-owned.
#   Piping to "sudo tee" is the correct pattern when you need root to write a file,
#   since "sudo echo ... >> file" doesn't work (the >> redirect runs as the current user).

echo "enable_uart=1" | sudo tee -a /boot/firmware/config.txt

# Verify a specific setting in config.txt:
grep "dwc2" /Volumes/system-boot/config.txt
# grep — search for a pattern in a file; prints matching lines.
# Use -n flag to show line numbers: grep -n "pattern" file

# Check which UART devices exist:
ls /dev/ttyAMA* /dev/ttyS*
# /dev/ttyAMA0 = PL011 hardware UART (want this for servos)
# /dev/ttyS0   = mini-UART (CPU-clock-dependent, unreliable at 1Mbps)

# Check active kernel boot parameters (read-only, reflects what actually booted):
cat /proc/cmdline
```

### Pi SSH Quick Reference

```bash
ssh ekapi@eka-pi02w.local     # mDNS hostname (may be slow to resolve)
ssh ekapi@192.168.86.121      # direct IP (faster, more reliable)

# If SSH fails with "REMOTE HOST IDENTIFICATION HAS CHANGED" (happens after reflash):
ssh-keygen -R eka-pi02w.local  # removes stale host key from ~/.ssh/known_hosts
# Then retry ssh normally.
```

### scservo_sdk Import Path
`ping_one.py` and other scripts in `software/control/` use:
```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scservo_sdk import PortHandler, sms_sts, COMM_SUCCESS
```
This resolves to `software/scservo_sdk/`. Run scripts from hexarm root or from `software/control/`.

---

## Concepts Covered (Learning Log)

- SO-100 hardware architecture and design tradeoffs
- FEETECH STS3215 servo internals (encoder, bus protocol, packet framing)
- Half-duplex UART — direction control, timing, bus arbitration, echo problem
- STS3215 packet format — header, ID, length, instruction, checksum
- scservo_sdk architecture — 4 layers (def → port_handler → protocol_packet_handler → sms_sts)
- Python venv — isolation model, activation, per-session requirement
- macOS serial ports — tty vs cu distinction, usbmodem vs usbserial
- LeRobot imitation learning pipeline (teleoperation → record → train → deploy)
- Forward kinematics and DH parameters
- Jacobian matrix — physical meaning, column interpretation
- Singularities — rank deficiency, physical causes
- Pseudoinverse (J⁺) and null space
- Device Tree and overlays — how Linux embedded systems describe hardware at boot
- Pi UART architecture — PL011 vs mini-UART, why PL011 is required for 1Mbps servo comms
- Raspberry Pi SSH setup — mDNS, host key management, direct IP fallback
- UART framing errors — what "corrupting a start bit" means on a µs scale (RC transient, PL011 error flag)
- Linux tty IGNPAR — silent byte discard on framing errors, no userspace notification
- VMIN/VTIME POSIX terminal settings — how they control read() blocking, pyserial persistence bug
- Resync parser design — using checksum as integrity check to recover from a dropped header byte
- RC charging analogy for line-driver turn-on transient — τ=RC, capacitance sources, retry warm-up effect
- STS3215 EPROM write workflow — unLockEprom → write → LockEprom, broadcast --force mode
- Baud rate register (reg 6) and BAUD_MAP — value encoding, power-cycle requirement
- Return delay register (reg 7) — what it does (silence before response) and what it doesn't fix (framing errors)
- git rm vs rm — staging deletions for git, using git add -A to recover after rm

---

### Waveshare Bus Servo Adapter (A) — Critical Wiring Note

**UART-Servo mode wiring is straight-through, NOT crossed:**
- Pi TX → Board TX
- Pi RX → Board RX
- GND → GND

This is the opposite of standard UART convention. The board labels its UART pins from the host's perspective. See `docs/debugging/servo-comms-debug-log.md`.

*Last updated: 2026-05-20*
