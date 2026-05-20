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
│   │   ├── bus.py                      ← LeRobot FeetechMotorsBus connection helpers (Pi only)
│   │   ├── config.py                   ← motor IDs, port assignments, joint names
│   │   ├── calibrate.py                ← joint limit calibration (move to min/max, saves JSON)
│   │   └── teleop.py
│   ├── scservo_sdk/                    ← Feetech official SDK (NOT a pip package — local copy)
│   │   ├── protocol_packet_handler.py  ← packet framing/parsing (keep UNMODIFIED — see debug notes)
│   │   ├── sms_sts.py                  ← STS/SMS series class (correct for STS3215)
│   │   ├── port_handler.py
│   │   └── ...
│   ├── STServo_Python/                 ← Waveshare's official SDK distribution
│   │   ├── requirements.txt            ← only dependency: pyserial==3.5
│   │   └── stservo-env/               ← Windows venv (not usable on Mac/Pi)
│   │       ├── STservo_sdk/            ← Waveshare's SDK (sts.py instead of sms_sts.py)
│   │       └── sms_sts/               ← official example scripts (ping.py, read.py, etc.)
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
- `scservo_sdk` — Feetech's original SDK; uses class `sms_sts` for STS/SMS servos
- `STservo_sdk` — Waveshare's renamed version; uses class `sts` (functionally identical)
- "SCServo" is Feetech's brand name for the whole ecosystem, not a specific protocol

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

**Status as of 2026-05-19:** Servo communication confirmed working over Pi UART → Waveshare board → STS3215.

### Root cause
**Wrong UART wiring.** The Waveshare Bus Servo Adapter (A) in UART-Servo mode uses **straight-through wiring** (TX→TX, RX→RX), NOT the standard crossed wiring (TX→RX, RX→TX). The board labels its UART pins from the host's perspective — the board's TX pin means "connect your TX here," not "this pin transmits." This is counterintuitive and underdocumented.

### Confirmed working configuration
- **Host:** Raspberry Pi Zero 2W
- **Interface:** Hardware UART `/dev/ttyAMA0` (PL011, GPIO 14/15)
- **Wiring:** Pi TX (GPIO 14) → Board TX, Pi RX (GPIO 15) → Board RX, GND → GND
- **Board mode switch:** UART-Servo
- **Board power:** 12V barrel jack only (no USB needed in UART-Servo mode)
- **Baud rate:** 1,000,000 bps (factory default)
- **Servo ID:** 1 (factory default)
- **Test:** `baud_scan.py` → `*** GOT RESPONSE from ID 1: FC` at 1Mbps ✅

### What was tried before finding the root cause
- Mac USB → Waveshare board (USB-Servo mode) → all baud rates, IDs 1–20: no response
- Arduino UART → servo directly and through board: no response (Arduino also has 1Mbps inaccuracy)
- Pi UART → Waveshare board (UART-Servo mode) with crossed wiring: no response
- Suspected: broken board, dead servo, wrong baud, wrong SDK, Mac driver issues, USB CDC bug
- All red herrings — root cause was wiring alone

### Key lesson
**Always verify board-specific UART pin labeling convention before assuming standard crossing.** See `docs/debugging/servo-comms-debug-log.md` for the full debugging narrative.

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
| Mac → board → servo communication working | ⚠️ Not yet tested (USB-Servo mode) |
| Pi → board → servo communication working | ✅ Done (2026-05-19) |
| Pi Zero 2W setup (Ubuntu 24.04) | ✅ Done |
| Pi UART configured (ttyAMA0) | ✅ Done |
| Driver board connected to Pi | ✅ Done |
| Servo IDs assigned (1–6 leader, 7–12 follower) | ⏳ Next up |
| Bus communication test (ping all 12 servos) | ⏳ Next up |
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

---

### Waveshare Bus Servo Adapter (A) — Critical Wiring Note

**UART-Servo mode wiring is straight-through, NOT crossed:**
- Pi TX → Board TX
- Pi RX → Board RX
- GND → GND

This is the opposite of standard UART convention. The board labels its UART pins from the host's perspective. See `docs/debugging/servo-comms-debug-log.md`.

*Last updated: 2026-05-19*
