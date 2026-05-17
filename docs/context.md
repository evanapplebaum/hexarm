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
- **Status:** Not yet set up — being reflashed
- **Planned OS:** Ubuntu 24.04 Server
- **Connection to driver boards:** UART GPIO pins (one board per arm)
- Previously had Pi-hole installed; needs to be reflashed before use

### Vision (planned)
- Wrist-mounted camera and/or overhead workspace camera
- Hardware TBD

---

## Repository Structure

```
hexarm/
├── docs/
│   ├── context.md              ← this file
│   └── ...
├── software/
│   ├── control/                ← host-side Python scripts
│   │   ├── ping_one.py         ← first-contact servo ping (CLI: --port, --id, --baud)
│   │   ├── raw_ping.py         ← raw serial diagnostic (bypasses SDK entirely)
│   │   ├── baud_scan.py        ← scans all baud rates × IDs 1–20 for any response
│   │   ├── calibrate.py
│   │   ├── teleop.py
│   │   └── ...
│   ├── scservo_sdk/            ← Feetech official SDK (copied from ftservo/FTServo_Python)
│   │   ├── protocol_packet_handler.py  ← packet framing/parsing (UNMODIFIED — see debug notes)
│   │   ├── sms_sts.py          ← STS/SMS series class (correct for STS3215)
│   │   ├── port_handler.py
│   │   └── ...
│   ├── STServo_Python/         ← Waveshare's official SDK distribution
│   │   ├── requirements.txt    ← only dependency: pyserial==3.5
│   │   └── stservo-env/        ← Windows venv from Waveshare tutorial (not usable on Mac)
│   │       ├── STservo_sdk/    ← Waveshare's SDK (sts.py instead of sms_sts.py)
│   │       └── sms_sts/        ← official example scripts (ping.py, read.py, etc.)
│   ├── kinematics/
│   ├── arduino/
│   └── config/
│       └── limits.json
├── .venv/                      ← Mac Python 3.12 venv (at hexarm root)
└── ...
```

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
- `scservo_sdk` — Feetech's original SDK; uses class `sms_sts` for STS/SMS servos
- `STservo_sdk` — Waveshare's renamed version; uses class `sts` (functionally identical)
- "SCServo" is Feetech's brand name for the whole ecosystem, not a specific protocol
- Both have been tested — both produce identical (failing) results in current debug

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

## Active Blocker: Servo Communication Not Working

**Status as of 2026-05-17:** Cannot establish serial communication with servos from Mac.

### What has been confirmed working:
- Serial port opens successfully at `/dev/cu.usbmodem5B141112771`
- Servos are powered: red LED lit, warm to touch, 12V confirmed between VCC and GND on JST
- Board power: 12V into barrel jack, USB-C into Mac
- Physical connections: 3-wire JST into Bus1/Bus2 ports, verified wiring
- Board mode: USB-Servo (confirmed)

### What has been tried (all failing):
- `ping_one.py` (scservo_sdk) → "There is no status packet" for all IDs
- Official Waveshare `sms_sts/ping.py` example → same result
- `raw_ping.py` (pure pyserial, no SDK) → "No bytes received"
- All supported baud rates: 9600 / 19200 / 38400 / 57600 / 115200 / 250000 / 500000 / 1000000
- IDs 1–20 at every baud rate (`baud_scan.py`)
- Broadcast torque enable (0xFE) → no physical servo movement
- Broadcast position command → no movement
- Both `/dev/tty.*` and `/dev/cu.*` port prefixes

### What was ruled out:
- **Echo fix** (wrong): we added a `ser.read(total_packet_length)` after `writePort()` in
  `protocol_packet_handler.py` thinking the board echoed TX bytes. It doesn't — the board
  handles half-duplex in hardware. The fix was consuming the servo's response. **Reverted.**
  Current `scservo_sdk/protocol_packet_handler.py` is stock (no echo fix).
- **Wrong SDK class:** `sms_sts` is correct for STS3215 (not `scscl`)
- **tty vs cu:** switching to `cu` prefix made no difference

### Most likely remaining causes:
1. **Data line not passing from board to servo bus** (power/GND confirmed, but DATA might not be switching properly in USB mode)
2. **Servo bricked or in error state** (red LED is normal-on for STS3215, but worth verifying with a second servo)
3. **Mac-specific USB CDC driver issue** silently dropping writes

### Immediate next step:
**Test with SCServo Debug on Windows (Bootcamp)**
- Waveshare provides SCServo Debug tool on their wiki
- Pass USB device through to Bootcamp, install CH340 driver if needed
- Scan at 1 Mbps, IDs 1–20
- If it works in Windows → Mac driver/port issue
- If it also fails → hardware (data line between board and servo)

---

## Setup Status

| Task | Status |
|---|---|
| LeRobot 0.5.2 installed (Pi) | ✅ Done |
| Mac venv created (Python 3.12) | ✅ Done |
| pyserial installed in Mac venv | ✅ Done |
| scservo_sdk copied into software/ | ✅ Done |
| STServo_Python (Waveshare SDK) added to software/ | ✅ Done |
| ping_one.py, raw_ping.py, baud_scan.py created | ✅ Done |
| LeRobot installed in Mac venv | ❌ Not possible (Intel Mac, torch 2.7+) |
| Mac → board → servo communication working | ❌ **Blocked — see above** |
| Pi Zero 2W setup (Ubuntu 24.04) | ⏳ Todo |
| Driver board connected to Pi | ⏳ Todo |
| Servo IDs assigned (1–6 leader, 7–12 follower) | ⏳ Blocked by comms |
| Bus communication test (ping all 12 servos) | ⏳ Blocked |
| LeRobot arm config file | ⏳ Todo |
| First teleoperation test | ⏳ Todo |
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

---

*Last updated: 2026-05-17*
