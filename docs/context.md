# hexarm — Project Context

> **Purpose:** Full handoff document for AI sessions (Claude Cowork, Claude.ai, etc.).
> A fresh session reading this file should be able to pick up immediately with zero catch-up questions.
> Update this file at the end of every significant work session.

---

## AI Collaboration Style

This document is read by Claude at the start of every session. Follow these rules when working with Evan on this project:

**Coding sessions — Claude writes, Evan directs.**
Evan is comfortable with the codebase and syntax. Claude writes all code directly — no Socratic guiding on implementation details.
- Write complete, correct code when asked. Don't make Evan do it himself.
- Exception: when Evan explicitly says "teach me" or the goal is conceptual learning — then switch to Socratic mode.

**General teaching style:**
- One question at a time.
- Ask before explaining — let him try first.
- Tie everything back to physical meaning and real hardware behavior.

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

### Compute — Jetson Orin Nano Super
- **Status:** ✅ SSHable as of 2026-05-26
- **OS:** JetPack 6.2 (Ubuntu 22.04-based, with CUDA, cuDNN, TensorRT)
- **Hostname:** `eka-orin`
- **Username:** `evan0h`
- **Network:** WiFi — IP TBD (use mDNS `eka-orin.local` for now)
- **SSH:** `ssh evan0h@eka-orin.local` — VS Code Remote SSH confirmed working
- **Display note:** Carrier board has DisplayPort only (no HDMI). Passive HDMI↔DP cable does NOT work — requires an active DisplayPort → HDMI adapter for initial GUI setup.
- **Post-setup plan:** Disable GUI after oem-config to reclaim ~800MB RAM; operate permanently headless
- **Connection to driver boards:** USB (USB-Servo mode on Waveshare board) — confirmed working 2026-05-26
- **Serial port:** `/dev/ttyACM0` — board enumerates via `cdc_acm` driver (not `ch341`/`ttyUSB0` as expected). The CH343 chip on the board presents as a CDC ACM device on Jetson/Linux.
- **dialout group:** `sudo usermod -aG dialout evan0h` — done. Note: VS Code Remote SSH caches group memberships and may not reflect changes after reconnect. Use `newgrp dialout` as workaround, or `pkill -f vscode-server` then reconnect for a clean session.
- **Python venv:** `/home/evan0h/evdev/hexarm/.venv` (Python 3.10), pyserial installed. Activate: `source .venv/bin/activate` from hexarm root.

### Compute — Raspberry Pi Zero 2W (retired — kept for UART debugging reference)
- **Status:** Was active compute; replaced by Jetson Orin Nano Super (2026-05-26)
- **OS:** Ubuntu 24.04 Server
- **Network:** WiFi "Apples" — IP `192.168.86.121`
- **SSH:** `ssh ekapi@eka-pi02w.local` or `ssh ekapi@192.168.86.121`
- **UART setup:** PL011 freed from Bluetooth via `dtoverlay=disable-bt` + `enable_uart=1` → `/dev/ttyAMA0` on GPIO 14/15
  - Pi Zero 2W: PL011 = hardware UART (reliable at 1Mbps); mini-UART = CPU-clock-dependent (unreliable). PL011 assigned to BT by default; overlay frees it.
- **Serial console removed (2026-05-25):** Default Ubuntu image puts `console=serial0,115200` in `/boot/firmware/cmdline.txt` and enables `serial-getty@ttyAMA0.service` — either alone holds the port and eats bytes, silently breaking servo comms. Both removed. This same issue is likely to appear on the Jetson.
- **Wiring to Waveshare board (UART-Servo mode):** Pi GPIO14/TX → Board TX, Pi GPIO15/RX → Board RX, GND → GND (straight-through, NOT crossed)

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
│   ├── debugging/
│   │   └── servo-comms-debug-log.md    ← full chronology of UART/SDK debugging (Phases 1–5); read before touching servo comms
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
│   │   ├── _serial_utils.py            ← shared SDK helpers: open_sdk_port, retry wrappers (use these in new scripts)
│   │   ├── ping_one.py                 ← ping a single servo (CLI: --port, --id, --baud)
│   │   ├── raw_ping.py                 ← raw pyserial diagnostic, bypasses SDK entirely
│   │   ├── baud_scan.py                ← scans all baud rates × IDs 1–20 for any response
│   │   ├── setup_servo.py              ← flash ID, return delay, baud rate to one servo at a time
│   │   ├── ping_stress.py              ← stress-ping a servo N times, logs results to CSV
│   │   ├── sdk_diag.py                 ← diagnostic — runs 5 read patterns, isolates SDK vs raw-path bugs
│   │   ├── calibrate.py                ← interactive MIN/MAX/MID joint-limit calibration → config/limits.json
│   │   ├── teleop.py                   ← STUB ONLY — currently has unfixed `os` import bug, no SDK calls yet
│   │   ├── config.py                   ← motor IDs, port assignments (needs rewrite — Pi 5 refs)
│   │   └── read_register.py            ← read arbitrary EPROM/SRAM register (raw pyserial, doesn't need VMIN fix)
│   ├── scservo_sdk/                    ← Feetech official SDK (NOT a pip package — local copy)
│   │   ├── protocol_packet_handler.py  ← packet framing/parsing — UNMODIFIED, keep upstream
│   │   ├── sms_sts.py                  ← STS/SMS series class (correct for STS3215)
│   │   ├── port_handler.py             ← stock readPort; only edit is timeout=0.1 (so VMIN works)
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
LeRobot policy / teleop loop        (Jetson — ARM64 + CUDA, torch works; NOT usable on Intel Mac)
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
- `port_handler.py` has one minimal change vs. upstream — `setupPort()` opens pyserial with `timeout=0.1` instead of `timeout=0`. The `timeout=0` default sets `O_NONBLOCK` on the fd, which makes `ser.read()` return immediately regardless of VMIN, breaking all SDK reads. `timeout=0.1` removes `O_NONBLOCK` and lets the VMIN=1 termios setting (applied in `_serial_utils.open_sdk_port`) actually take effect.
- `readPort()` is stock — a previous custom resync layer was reverted on 2026-05-25 (see Phase 5 of `docs/debugging/servo-comms-debug-log.md`). Any per-call retry/error-recovery now lives in `software/control/_serial_utils.py`.

### Mac Development Environment
- **Venv:** `hexarm/.venv` (Python 3.12)
- **Activate:** `source .venv/bin/activate` (from hexarm root, every new session)
- **Installed packages:** pyserial 3.5
- **LeRobot:** NOT installable on Intel Mac — torch 2.7+ has no x86_64 macOS build
- **Serial port:** `/dev/cu.usbmodem5B141112771` (confirmed working port name)
  - IMPORTANT: use `cu` prefix, NOT `tty` — `tty` blocks waiting for carrier detect
  - Port shows as `usbmodem` (USB CDC) not `usbserial` (CH340 with driver)
- **SDK in use:** `scservo_sdk` (in `software/scservo_sdk/`, imported via `sys.path.insert`)

### LeRobot (Jetson — target platform)
- Version: 0.5.2
- Feetech driver: `lerobot.motors.feetech.feetech.FeetechMotorsBus`
- Python 3.12 required (numba constraint: >=3.9, <3.13)
- ARM64 + CUDA on Jetson → torch 2.7+ installs normally (unlike Intel Mac)
- Venv on Jetson: TBD (was `source ~/lerobot-env/bin/activate` on Pi)

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

**Status as of 2026-05-25:** End-to-end SDK path working. `calibrate.py` runs to completion. Three distinct issues encountered and resolved across multiple sessions.

### Issue 1: No response at all (resolved 2026-05-19)
**Root cause: Wrong UART wiring.** The Waveshare Bus Servo Adapter (A) uses **straight-through wiring** (TX→TX, RX→RX), NOT the standard crossed wiring. The board labels its pins from the host's perspective — counterintuitive and underdocumented. See `docs/debugging/servo-comms-debug-log.md` Phases 1–3.

### Issue 2: Intermittent responses — superseded by Issue 3 (originally "resolved" 2026-05-20)
The Phase 4 investigation diagnosed an intermittent 0/5/6-byte response pattern as a UART framing error at the half-duplex bus turnaround, and added a custom resync parser to `port_handler.readPort()`. That diagnosis turned out to be wrong — the real cause was Issue 3 below. The Phase 4 narrative is preserved in `docs/debugging/servo-comms-debug-log.md` as a cautionary record of how a self-consistent but incorrect theory can survive without falsification testing.

### Issue 3: Serial console + SDK byte-stealing (resolved 2026-05-25)
**Root causes (two stacked):**

**(a) Serial console on `/dev/ttyAMA0`.** The default Ubuntu 24.04 image for Pi Zero 2W ships with `console=serial0,115200` in `/boot/firmware/cmdline.txt` AND `serial-getty@ttyAMA0.service` enabled. Either alone holds the PL011 UART at 115200 baud at the kernel level, consumes incoming bytes before pyserial can read them, and writes login-prompt characters out the TX line. This invisibly corrupted every UART transaction on the project for weeks; the previously-observed "framing error" pattern was getty interference, not a real RC transient.

**(b) Custom `readPort()` stealing bytes from multi-transaction SDK calls.** The Phase 4 resync layer in `port_handler.readPort()` read `length+1` bytes from the kernel into a local buffer, then sliced and returned only `length`. For single-transaction SDK calls (like `ReadPos`), this was harmless. For `ping()` — which internally does two transactions (PING, then a READ of the model-number register at address 3) — the extra byte from the first read was the *first byte of the second response*, and dropping it caused the second transaction to time out short with `COMM_RX_CORRUPT`.

**Fixes:**
- Remove `console=serial0,115200` from `/boot/firmware/cmdline.txt`, leave `console=tty1`.
- `sudo systemctl disable --now serial-getty@ttyAMA0.service serial-getty@serial0.service`
- Reboot.
- Revert `port_handler.readPort()` to upstream SDK (`return self.ser.read(length)`).
- Retry and error recovery now live in `software/control/_serial_utils.py` wrappers (`ping_with_retry`, `read_pos_with_retry`, `write_byte_with_retry`) — the correct scope.

**Two supporting fixes that survived from the wrong diagnosis (still required):**
- `port_handler.setupPort()` opens pyserial with `timeout=0.1` (not `timeout=0`). The `timeout=0` default sets `O_NONBLOCK` on the fd, which makes `ser.read()` return 0 bytes immediately regardless of VMIN.
- `_serial_utils.set_vmin(ser, vmin=1)` sets termios `VMIN=1` after open so that `ser.read(1)` calls inside the SDK actually block until a byte arrives.

**Quick verification the Pi UART is healthy for servo use:**

```bash
cat /proc/cmdline | grep -o "console=[^ ]*"        # should show only:  console=tty1
systemctl is-enabled serial-getty@ttyAMA0.service  # should output:     disabled
stty -F /dev/ttyAMA0 -a | head -1                  # should NOT be stuck at 115200
python3 software/control/raw_ping.py --id 2        # should return clean 6/6 bytes
```

### Confirmed working configuration (2026-05-25)
- **Host:** Raspberry Pi Zero 2W (Ubuntu 24.04 server)
- **Interface:** Hardware UART `/dev/ttyAMA0` (PL011, GPIO 14/15)
- **Wiring:** Pi TX (GPIO 14) → Board TX, Pi RX (GPIO 15) → Board RX, GND → GND
- **Board mode switch:** UART-Servo
- **Board power:** 12V barrel jack only
- **Baud rate:** 1,000,000 bps
- **Console on ttyAMA0:** DISABLED (cmdline.txt + serial-getty)
- **SDK readPort:** stock upstream + `timeout=0.1` setup + `VMIN=1` via `_serial_utils.open_sdk_port`
- **Verified end-to-end:** `raw_ping.py`, `ping_one.py`, `sdk_diag.py` (all 5 variants 5/5), `calibrate.py`
- **STS3215 reports model number 777** (returned from `ping()`)

See `docs/debugging/servo-comms-debug-log.md` Phase 5 for the actual root cause and full chronology.

---

## Setup Status

| Task | Status |
|---|---|
| **Compute** | |
| Jetson Orin Nano Super — JetPack 6.2 flash | ⚠️ In progress (2026-05-26, Balena Etcher) |
| Jetson — oem-config first-boot wizard | ⏳ Todo |
| Jetson — SSH access configured | ⏳ Todo |
| Jetson — GUI disabled (headless mode) | ⏳ Todo |
| Jetson — UART device nodes confirmed for servo chains | ⏳ Todo |
| Jetson — serial console verified off UART used for servos | ⏳ Todo |
| **Software** | |
| Mac venv created (Python 3.12) | ✅ Done |
| pyserial installed in Mac venv | ✅ Done |
| scservo_sdk copied into software/ | ✅ Done |
| ping_one.py, raw_ping.py, baud_scan.py, setup_servo.py created | ✅ Done |
| _serial_utils.py (shared SDK helpers + retry wrappers) | ✅ Done (2026-05-25) |
| sdk_diag.py (read-pattern diagnostic) | ✅ Done (2026-05-25) |
| port_handler.py reverted to upstream readPort | ✅ Done (2026-05-25) |
| LeRobot 0.5.2 installed (Jetson) | ⏳ Todo |
| LeRobot installed in Mac venv | ❌ Not possible (Intel Mac, torch 2.7+) |
| **Hardware / Servos** | |
| Mac → board → servo communication working | ⚠️ Not yet tested (USB-Servo mode) |
| Jetson → board → servo communication working | ✅ Done (2026-05-26, USB, /dev/ttyACM0) |
| Driver board UART wiring to Jetson | ✅ Done (USB-Servo mode, ttyACM0 via cdc_acm driver) |
| Servo IDs assigned (1–6 leader, 7–12 follower) | ⚠️ Only servo 2 currently on bus; reassign others when wired |
| Bus communication test (ping all servos) | ⚠️ Only ID 2 verified end-to-end (2026-05-25, on Pi) |
| SDK path (ping_one, calibrate) working on Jetson | ✅ Done (2026-05-26, sdk_diag 5/5, ping_one confirmed) |
| Joint limit calibration for all 12 servos | ⏳ Todo (wire remaining servos first) |
| **Application** | |
| config.py rewrite (Jetson ports, remove Pi 5 / Pi Zero 2W refs) | ⏳ Todo |
| move_one.py — ping + ReadPos working for multiple IDs | ✅ In progress (2026-05-28) — move logic not yet written |
| teleop.py (currently stub with `os` import bug) | ⏳ Todo — full implementation |
| .gitignore for CSV stress-test artifacts | ⏳ Todo |
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

### Jetson SSH Quick Reference

```bash
ssh evan0h@eka-orin.local    # mDNS hostname
ssh evan0h@<jetson-ip>       # direct IP (faster, more reliable — IP TBD)

# If SSH fails with "REMOTE HOST IDENTIFICATION HAS CHANGED" (happens after reflash):
ssh-keygen -R eka-orin.local  # removes stale host key from ~/.ssh/known_hosts
# Then retry ssh normally.
```

### Pi SSH Quick Reference (retired — kept for reference)

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
- `O_NONBLOCK` override of VMIN — why `pyserial(timeout=0)` defeats termios VMIN settings, and how `timeout=0.1` fixes it
- Linux serial console + `serial-getty@ttyAMA0.service` — how a console on the same UART silently breaks user-space communication (eats RX bytes, writes prompt to TX, holds baud at 115200). Always check `cat /proc/cmdline` and `systemctl is-enabled serial-getty@ttyAMA0.service` before anything else when a Pi UART misbehaves.
- Pi GPIO TX↔RX loopback testing — cheapest UART sanity check, falsifies all higher-level theories at once
- Falsifying experiments vs. self-consistent theory — Phase 4's framing-error story matched every symptom but was wrong; the loopback test collapsed it in one command
- Resync parser design — using checksum as integrity check to recover from a dropped header byte (the Phase 4 implementation; not currently in use)
- The byte-stealing pitfall — reading N+1 bytes and returning N silently steals data from the next read; breaks multi-transaction SDK calls like `ping()` (which does PING + read-model)
- STS3215 model number reported via `ping()` = **777**
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

### move_one.py — current state (2026-05-28)

- Located at `software/setup/move_one.py`
- Uses raw `scservo_sdk` directly (no `_serial_utils` wrapper) — Evan's deliberate choice to learn from first principles
- Currently: collects servo IDs interactively via readchar, opens port, pings each servo, reads and prints current position
- ESC detection: uses `'\x1b' in char` — SSH on Orin eats the first ESC press, second comes through as `'\x1b\x1b'`
- **Not yet implemented:** torque enable, WritePosEx move command, home position logic
- Home positions captured 2026-05-28, stored in `software/config/home.json` (IDs 1–6, leader arm)

*Last updated: 2026-05-28*
