# hexarm — Project Context

> **Purpose:** Full handoff document for AI sessions (Claude Cowork, Claude.ai, etc.).
> A fresh session reading this file should be able to pick up immediately with zero catch-up questions.
> Update this file at the end of every significant work session.

---

## AI Collaboration Style

This document is read by Claude at the start of every session. Follow these rules when working with Evan on this project:

**Coding sessions — triage by whether the code carries a model.**
The deciding question for any piece of code: *"Would a robotics interviewer ask Evan to explain this on a whiteboard?"*
- **Model-bearing code** (physics, math, control logic — homing offsets, mod-4096 reasoning, IK, teleop mapping): **Evan writes it first**, predict-first (he writes the expected output/value before running), *then* Claude red-teams it. Generation before feedback. Do NOT hand Evan the answer on this code the first time — the act of deriving it IS the education.
- **Glue code** (argparse, JSON I/O, per-joint loops, file paths, plotting): Claude writes it; Evan reads and checks he can predict the output. The "quiz me, then you write" flow is correct here.
- **Earned boilerplate** (patterns Evan has already internalized): full Claude, minimal review.
- The rule: Evan earns the delegation. He may hand a task to Claude once he can *predict its output and verify it*. If he can't predict it yet, doing it by hand is the learning, not inefficiency.
- Exception: when Evan explicitly says "teach me" or the goal is conceptual learning — then switch to Socratic mode regardless of bucket.

**General teaching style:**
- One question at a time.
- Ask before explaining — let him try first.
- Tie everything back to physical meaning and real hardware behavior.

---

## Learning Approach (methodology — agreed 2026-06-01)

How Evan is approaching learning robotics, decided in a long discussion. This governs how to pace and structure work, not just how to write code.

**Goal & timeline.** Evan is 22, targeting a solid robotics job. The current proof is **for recruiters** → favor breadth-with-polish and one or two deep, defensible subsystems.  The hexarm project is the portfolio centerpiece.

**Core principle — optimize prediction-error density, not speed.** Learning is driven by prediction error (the gap between expected and actual is the signal that updates the model and tags memory). Fast-vs-slow is the wrong axis; both fail the same way when no error loop is closed (passive reading = high load, no signal; cargo-culting = working demo, no model). The danger of AI isn't that it writes syntax — it's that it skips the prediction-error loop and leaves you fluent-feeling but model-empty.

**Why robotics fits this.** Physical bugs (oscillation, current limits, the encoder seam) live in reality, can't be hand-waved, and AI can't see the hardware — so debugging forces a real causal model. This is protection against the fluency illusion.

**The operating loop (spiral / summit-then-backtrack):**
1. Build the whole pipeline fast, top-down (cargo-culting OK) → this is the map / advance organizer. *(Currently pass 1.)*
2. Log friction — every spot where reality surprised him.
3. Rank by leverage (blocks progress? recurs? core to understanding key concepts?).
4. Deep-dive the top item to first principles, **predict-first**. Only deep-dive what *bit* you — surprise + relevance is what the hippocampus prioritizes. (Calibration broke → he now owns encoders/mod-4096/sign-magnitude/normalization. He correctly did NOT deep-dive USB framing or tqdm — they didn't bite.)
5. Consolidate by writing it up (issue → ADR/doc). The writing IS the retrieval-practice learning step, not overhead. (This unifies the project's documentation/sprint goals with the learning method.)
6. Re-spiral.

**Friction log.** Evan keeps this in his Notes app (chosen for speed). It doubles as interview-prep ("tell me about a hard bug"). Per-entry fields: **Surprise** (the prediction error, logged when it fires), Guess, Reality, **Leverage** (HIGH/MED/LOW — the backtrack trigger), Status. NOT kept as a markdown file in-repo per Evan's choice 2026-06-01.

**Code-writing policy:** see the triage rule in AI Collaboration Style above (model-bearing → Evan writes first predict-first; glue → Claude writes). The deciding question is "would an interviewer make me whiteboard this?"

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
- **Target IDs:** Follower arm 1–6, leader arm 7–12
- All servos daisy-chained on one bus per arm, addressed by unique ID
- **Status LED:** Red LED on = powered and alive; this has been confirmed in testing. Blinking red - fault (usually overcurrent from physical blockage)

### Servo Driver Boards — Waveshare Bus Servo Adapter (A) (×2)
- **2 boards total — one per arm**
- Sold under "UeeKKoo" brand on Amazon but arrived in Waveshare boxes;
  Amazon listing links to the official Waveshare wiki → treat as Waveshare Bus Servo Adapter (A)
- **Waveshare wiki:** https://www.waveshare.com/wiki/Bus_Servo_Adapter_(A)
- Handles half-duplex bus direction switching in hardware (host sees full-duplex serial)
- **Two host interfaces:**
  - **USB (CH340 chip):** appears on Mac as `/dev/cu.usbmodem*` — use `cu` prefix, NOT `tty`
  - **UART GPIO pins:** for Raspberry Pi connection (no USB needed)
- **Physical mode switch** on board: set to USB-Servo for Mac testing, UART-Servo for Pi, USB-Servo for Jetson (current and final platform)
- **Power:** separate DC barrel jack for servo bus power (12V); 
- Compatible with ST/SC series Feetech servos including STS3215
- **Official Python SDK:** STservo_sdk (see software section)

### Compute — Jetson Orin Nano Super
- **Status:** ✅ SSHable as of 2026-05-26
- **OS:** JetPack 6.2 (Ubuntu 22.04-based, with CUDA, cuDNN, TensorRT)
- **Hostname:** `eka-orin`
- **Username:** `evan0h`
- **Network:** WiFi — IP TBD (use mDNS `eka-orin.local` for now)
- **SSH:** `ssh evan0h@eka-orin.local` — VS Code Remote SSH confirmed working
- **Display note:** Carrier board has DisplayPort only (no HDMI). Using DP -> HDMI on rare occasions a monitor is needed to be connected directly to the Jetson
- **Post-setup plan:** Disable GUI after oem-config to reclaim ~800MB RAM; operate permanently headless
- **Connection to driver boards:** USB (USB-Servo mode on Waveshare board) — confirmed working 2026-05-26
- **Serial port:** `/dev/ttyACM0` — board enumerates via `cdc_acm` driver (not `ch341`/`ttyUSB0` as expected). The CH343 chip on the board presents as a CDC ACM device on Jetson/Linux.
- **dialout group:** `sudo usermod -aG dialout evan0h` — done. Note: VS Code Remote SSH caches group memberships and may not reflect changes after reconnect. Use `newgrp dialout` as workaround, or `pkill -f vscode-server` then reconnect for a clean session.
- **Python venv:** `/home/evan0h/evdev/hexarm/.venv` (Python 3.10), pyserial installed. Activate: `source .venv/bin/activate` from hexarm root.

### Compute — Raspberry Pi Zero 2W (retired — kept for UART debugging reference)
- **Status:** Was active compute; replaced by Jetson Orin Nano Super (2026-05-26)
- **OS:** Ubuntu 24.04 Server
- **SSH:** `ssh ekapi@eka-pi02w.local`
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
│   ├── control/                        ← application-level scripts (run from repo root, conda lerobot)
│   │   └── teleop.py                   ← leader-follower teleoperation; single bus, 12 motors; ✅ working (2026-06-03)
│   ├── calibration/                    ← LeRobot-based calibration and arm control scripts
│   │   ├── calibrate_lerobot.py        ← per-joint LeRobot calibration (--arm leader|follower); needs rewrite (see Encoder Wrap-Around)
│   │   ├── go_neutral.py               ← move arm(s) to captured neutral pose; importable by other scripts
│   │   ├── record_neutral.py           ← capture current pose as neutral_<arm>.json
│   │   ├── keyboard_follower.py        ← keyboard control of follower arm (normalize=False); ✅ works
│   │   └── monitor_joints.py           ← live joint position display
│   ├── low-lvl-setup/                  ← raw SDK diagnostics and one-time setup tools
│   │   ├── _serial_utils.py            ← shared SDK helpers: open_sdk_port, retry wrappers (use these in new scripts)
│   │   ├── ping_one.py                 ← ping a single servo (CLI: --port, --id, --baud)
│   │   ├── raw_ping.py                 ← raw pyserial diagnostic, bypasses SDK entirely
│   │   ├── baud_scan.py                ← scans all baud rates × IDs 1–20 for any response
│   │   ├── setup_servo.py              ← flash ID, return delay, baud rate to one servo at a time
│   │   ├── ping_stress.py              ← stress-ping a servo N times, logs results to CSV
│   │   ├── sdk_diag.py                 ← diagnostic — runs 5 read patterns, isolates SDK vs raw-path bugs
│   │   ├── calibrate.py                ← interactive MIN/MAX/MID joint-limit calibration → config/limits.json
│   │   ├── move_one.py                 ← ping, ReadPos, torque enable, move to home.json position
│   │   ├── torque_off.py               ← interactive torque disable
│   │   ├── flash_angle_limits.py       ← write limits.json angle limits to servo EPROM
│   │   ├── read_register.py            ← read arbitrary EPROM/SRAM register (raw pyserial)
│   │   ├── config.py                   ← motor IDs, port assignments (needs rewrite — Pi 5 refs)
│   │   └── teleop.py                   ← DEPRECATED stub — ignore, superseded by software/control/teleop.py
│   ├── scservo_sdk/                    ← Feetech official SDK (NOT a pip package — local copy)
│   │   ├── protocol_packet_handler.py  ← packet framing/parsing — UNMODIFIED, keep upstream
│   │   ├── sms_sts.py                  ← STS/SMS series class (correct for STS3215)
│   │   ├── port_handler.py             ← stock readPort; only edit is timeout=0.1 (so VMIN works)
│   │   └── ...
│   ├── arduino/
│   │   ├── ping_servo/
│   │   │   └── ping_servo.ino          ← Arduino ping sketch (half-duplex, 1kΩ resistor wiring) - USED AS DIY SERVO DRIVER
│   │   ├── ping_servo_uno/
│   │   │   └── ping_servo_uno.ino      ← Uno variant
│   │   └── st3215-src/                 ← Feetech Arduino library source (SCServo)
│   │       ├── SCServo/                ← Library with SMS_STS, SCSCL classes + examples
│   │       └── ST Servo/               ← Alternative library variant
│   ├── kinematics/
│   ├── utils/
│   └── config/
│       ├── limits.json                 ← joint travel limits (populated by calibrate.py, leader arm)
│       ├── home.json                   ← raw encoder home positions for move_one.py (IDs 1–6)
│       ├── calibration_follower.json   ← LeRobot calibration — follower arm (IDs 1–6); ✅ working
│       ├── calibration_leader.json     ← LeRobot calibration — leader arm (IDs 7–12); ✅ working
│       ├── neutral_follower.json       ← captured neutral pose, normalized 0–100 (follower)
│       └── neutral_leader.json         ← captured neutral pose, normalized 0–100 (leader)
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
- Feetech driver: `lerobot.motors.feetech.feetech.FeetechMotorsBus`
- Python 3.12 required (LeRobot main branch requires >=3.12)
- **Conda env:** `lerobot` (Python 3.12) at `/data/miniconda3/envs/lerobot/` — activate: `conda activate lerobot`
- **PyTorch:** installed from PyPI cu126 index (`https://download.pytorch.org/whl/cu126`) — torch 2.x, CUDA 12.6 compatible
- **Repo:** cloned at `/data/lerobot`, installed with `pip install -e ".[feetech]"` — ✅ confirmed working 2026-05-31
- **NVMe SSD:** 512GB mounted at `/data` — all LeRobot data, conda env, and repo live here
- **Servo ID convention (UPDATED):** Both arms on ONE bus (/dev/ttyACM0), one driver board. Follower IDs 1–6, leader IDs 7–12. LeRobot's two-bus assumption does NOT apply.
- **Scripts live in hexarm repo** (`software/control/`), import from lerobot conda env. Run from hexarm root with `conda activate lerobot`.

### FeetechMotorsBus API (confirmed 2026-05-31)
```python
from lerobot.motors.feetech import FeetechMotorsBus
from lerobot.motors.motors_bus import Motor, MotorCalibration, MotorNormMode

# Construction
bus = FeetechMotorsBus(
    port="/dev/ttyACM0",
    motors={"shoulder_pan": Motor(id=1, model="sts3215", norm_mode=MotorNormMode.RANGE_0_100), ...},
    calibration=None,   # optional: dict[str, MotorCalibration]
    protocol_version=0  # 0 = Feetech, 1 = Dynamixel
)

# Key methods
bus.connect() / bus.disconnect()
bus.enable_torque(motors=None)   # None = all motors
bus.disable_torque(motors=None)
bus.read(data_name, motor, *, normalize=True, num_retry=0) -> Value         # single motor
bus.write(data_name, motor, value, *, normalize=True, num_retry=0)          # single motor
bus.sync_read(data_name, motors=None, *, normalize=True) -> dict[str, Value]
bus.sync_write(data_name, values, *, normalize=True)
bus.set_half_turn_homings(motors=None) -> dict[NameOrID, Value]  # resets cal, reads pos, writes Homing_Offset = 2047 - present_pos
bus.record_ranges_of_motion(motors=None, display_values=True) -> tuple[dict, dict]  # (mins, maxes); waits for Enter
bus.write_calibration(calibration_dict, cache=True)  # writes Homing_Offset + Min/Max_Position_Limit to EPROM
bus.read_calibration() -> dict[str, MotorCalibration]

# MotorCalibration
MotorCalibration(id, drive_mode, homing_offset, range_min, range_max)

# MotorNormMode options
MotorNormMode.RANGE_0_100    # 0–100%
MotorNormMode.RANGE_M100_100 # –100 to +100
MotorNormMode.DEGREES        # actual degrees
```

**IMPORTANT — normalize=False behaviour (CORRECTED 2026-06-01):** The earlier belief that "homing offset doesn't affect `normalize=False` reads" was WRONG. The STS3215 applies the homing offset *in hardware*: `Present_Position = (raw_encoder − Homing_Offset) mod 4096`, reported in 0–4095. So `normalize=False` reads DO reflect the offset, and the result is always wrapped into the single-turn range. This mod-4096 behaviour requires the Phase register bit 4 (0x10) to be cleared — `bus.configure_motors()` does this for sts3215. See the Encoder Wrap-Around section for why this is the whole key to calibration.

**IMPORTANT — safe torque enable:** Always write `Goal_Position = Present_Position` for all motors before calling `enable_torque()`. Otherwise servos snap to stale goal from a previous run. See `safe_enable_torque()` helper in `calibrate_lerobot.py`.

**IMPORTANT — stale EPROM offsets:** `write_calibration` and `set_half_turn_homings` write to servo EPROM. A crashed calibration run leaves stale homing offsets in hardware. Always clear with `bus.write("Homing_Offset", name, 0, normalize=False)` before starting a new calibration.

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
| Jetson Orin Nano Super — JetPack 6.2 flash | ✅ Done (2026-05-26) |
| Jetson — oem-config first-boot wizard | ✅ Done |
| Jetson — SSH access configured | ✅ Done (`ssh evan0h@eka-orin.local`) |
| Jetson — GUI disabled (headless mode) | ⏳ Todo |
| Jetson — UART device nodes confirmed for servo chains | ✅ Done (/dev/ttyACM0 via cdc_acm) |
| Jetson — serial console verified off UART used for servos | ⏳ Todo |
| NVMe SSD (512GB) mounted at /data | ✅ Done (2026-05-28, ext4, fstab entry added) |
| **Software** | |
| Mac venv created (Python 3.12) | ✅ Done |
| pyserial installed in Mac venv | ✅ Done |
| scservo_sdk copied into software/ | ✅ Done |
| ping_one.py, raw_ping.py, baud_scan.py, setup_servo.py created | ✅ Done |
| _serial_utils.py (shared SDK helpers + retry wrappers) | ✅ Done (2026-05-25) |
| sdk_diag.py (read-pattern diagnostic) | ✅ Done (2026-05-25) |
| port_handler.py reverted to upstream readPort | ✅ Done (2026-05-25) |
| LeRobot conda env (Python 3.12) on Jetson | ✅ Done (2026-05-28, /data/miniconda3/envs/lerobot) |
| PyTorch installed (cu126, Jetson) | ✅ Done (2026-05-28, from download.pytorch.org/whl/cu126) |
| LeRobot pip install -e ".[feetech]" | ✅ Done (2026-05-31) |
| LeRobot installed in Mac venv | ❌ Not possible (Intel Mac) |
| **Hardware / Servos** | |
| Mac → board → servo communication working | ⚠️ Not yet tested (USB-Servo mode) |
| Jetson → board → servo communication working | ✅ Done (2026-05-26, USB, /dev/ttyACM0) |
| Driver board UART wiring to Jetson | ✅ Done (USB-Servo mode, ttyACM0 via cdc_acm driver) |
| Servo IDs assigned — follower 1–6, leader 7–12, single bus | ✅ Done — both arms on /dev/ttyACM0; see LeRobot section for ID convention |
| Bus communication test (all 12 servos) | ✅ Done (2026-06-03, both arms responding, teleop confirmed) |
| SDK path (ping_one, calibrate) working on Jetson | ✅ Done (2026-05-26, sdk_diag 5/5, ping_one confirmed) |
| Angle limits flashed to servo EPROM | ⏳ Todo |
| **Application** | |
| config.py rewrite (Jetson ports, remove Pi 5 / Pi Zero 2W refs) | ⏳ Todo |
| move_one.py — ping, ReadPos, torque enable, home move | ✅ Done (2026-05-28) |
| torque_off.py — interactive torque disable | ✅ Done (2026-05-28) |
| flash_angle_limits.py — write limits.json to servo EPROM | ✅ Done (2026-05-28) |
| keyboard_follower.py — LeRobot keyboard control of follower arm | ✅ Done (2026-05-31) |
| calibrate_lerobot.py — per-joint LeRobot calibration, both arms | ⚠️ Calibration data working in practice; script needs rewrite (hand-rolls offset math, never calls configure_motors()). Fix designed 2026-06-01 (see Encoder Wrap-Around section) |
| LeRobot calibration — encoder wrap-around fix | ✅ Solved conceptually (2026-06-01); ⏳ code rewrite pending |
| go_neutral.py — move arm(s) to neutral; importable | ✅ Done — both arms working (2026-06-03) |
| record_neutral.py — capture normalized neutral pose | ✅ Done — neutral_follower.json and neutral_leader.json captured |
| teleop.py — leader-follower teleoperation | ✅ Done (2026-06-03, software/control/teleop.py) |
| First teleoperation test | ✅ Done (2026-06-03, confirmed working perfectly) |
| .gitignore for CSV stress-test artifacts | ⏳ Todo |
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
ssh ekapi@[redacted]     # direct IP (faster, more reliable)

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
- STS3215 single-turn position reporting — `Present_Position = (raw − Homing_Offset) mod 4096`; Phase register bit 4 (0x10) must be cleared (via `configure_motors()`) to enable it
- Encoder seam relocation — the 4095↔0 jump is NOT fixed to the magnet zero; it sits where `raw = Homing_Offset`, so choosing the offset moves the seam
- Home-at-center calibration — homing at the arc midpoint parks the seam 2048 counts away, i.e. in the center of the dead gap, so travel < 360° never crosses it (this is how LeRobot/SO-100 "handle" wrap joints — by avoidance, not special-casing)
- LeRobot `drive_mode` — software sign-flip applied after normalization (leader/follower direction agreement); does NOT affect encoder, offset, or seam
- LeRobot calibration internals — `_normalize`/`_unnormalize` only read range_min/max (no sign constraint); only `_serialize_data` rejects negative values, and only for the unsigned Min/Max_Position_Limit EPROM registers
- Sign-magnitude encoding — Homing_Offset uses bit 11 as sign (per Feetech tables), so negative offsets ARE writable to EPROM; position limits are unsigned
- STS3215 EPROM write workflow — unLockEprom → write → LockEprom, broadcast --force mode
- Baud rate register (reg 6) and BAUD_MAP — value encoding, power-cycle requirement
- Return delay register (reg 7) — what it does (silence before response) and what it doesn't fix (framing errors)
- git rm vs rm — staging deletions for git, using git add -A to recover after rm
- Python sys.path shadowing — adding a directory to sys.path exposes ALL its subdirectories as importable packages; adding `software/` shadows the pip-installed `scservo_sdk` with the local copy, breaking LeRobot. Always add the repo root, not a mid-tree directory.
- LeRobot teleop loop design — single FeetechMotorsBus for both arms on one port; prefix motor names (follower_/leader_) to avoid collisions; 1:1 normalized mapping works when arms are physically identical with drive_mode=0
- STS3215 Acceleration register — value 0 means no limit (like Maximum_Velocity_Limit); go_neutral must reset both to 0 on exit or downstream scripts inherit slow ramp rates

---

### Waveshare Bus Servo Adapter (A) — Critical Wiring Note

**UART-Servo mode wiring is straight-through, NOT crossed:**
- Pi TX → Board TX
- Pi RX → Board RX
- GND → GND

This is the opposite of standard UART convention. The board labels its UART pins from the host's perspective. See `docs/debugging/servo-comms-debug-log.md`.

---

## Encoder Wrap-Around — RESOLVED ✅

**Discovered 2026-05-31. Root cause understood and solution designed 2026-06-01.** Some joints have their physical travel range crossing the STS3215 encoder's 0↔4095 boundary. The absolute magnetic encoder is 12-bit (0–4095 per revolution). If the servo is mounted such that the physical joint stops straddle this boundary, raw encoder readings jump from 4095→0 mid-motion.

### The key insight (2026-06-01)

The STS3215 reports `Present_Position = (raw_encoder − Homing_Offset) mod 4096`, always in 0–4095 (requires Phase bit 4 cleared, done by `configure_motors()`). The consequence: the encoder *seam* (where present jumps 4095↔0) is NOT fixed to the magnet's zero — it sits at the shaft angle where `raw = Homing_Offset`. **Choosing the homing offset moves the seam.**

So the problem isn't "tolerate a wrap" — it's "park the seam in the joint's dead gap (the untraveled arc) so the travel never crosses it." And LeRobot's home-at-center procedure does this automatically: homing at the arc center throws the seam exactly 2048 counts away, which is the center of the opposite (dead) gap. As long as travel < 360°, the gap is non-zero and the seam lands safely inside it.

Worked example — shoulder_lift (ID 8), stops raw 1855 and 202:
- Travel arc = (202 − 1855) mod 4096 = 2443 counts ≈ 215°. Dead gap = 1653 counts ≈ 145°.
- Mid-arc raw ≈ 3076 → `Homing_Offset = 3076 − 2047 = 1029`. Seam at raw=1029, which is the center of the dead gap (202–1855). ✓
- Reported present after homing: stop A (1855) → 826, center (3076) → 2047, stop B (202) → 3269. **Both limits positive, contiguous, ~215° span. No negative EPROM write.**

The `−827` from the original failure only appeared because the OLD script computed `raw + offset` in plain Python **without the mod 4096** that the servo actually applies. The negative write was a symptom, not the disease.

### The correct calibration flow (per joint)

1. `bus.configure_motors()` once up front — clears the Phase bit so present-position reporting is single-turn mod-4096. **The old script never called this** — that was a real latent bug.
2. Hand-move the joint to the **middle** of its travel.
3. `bus.set_half_turn_homings([name])` — resets cal, reads present, writes `Homing_Offset`; the *servo* applies it.
4. `bus.record_ranges_of_motion([name])` — now records present in the continuous homed frame → clean positive range, seam parked in the dead gap.
5. `bus.write_calibration(...)`.

Keep the per-joint loop (prevents unsupported joints swinging under gravity). Just split each joint into "move to middle → Enter" then "sweep both stops → Enter."

### Answers to the three handoff questions

1. **How does SO-100 handle wrap joints?** It doesn't special-case them — it *avoids* the seam via single-turn mod-4096 reporting (Phase bit) + home-at-center (seam → dead gap). No negative range_min in normal use.
2. **Does `drive_mode=1` fix it?** No. `drive_mode` is only a software sign-flip applied *after* normalization (`100 - norm if drive_mode`) so leader/follower agree on direction. It never touches the encoder, offset, or seam. It cannot reroute the joint onto the short path — the joint physically occupies the 215° arc.
3. **Negative `range_min` in software only?** Not needed if you home correctly (you get 826–3269). But it IS valid in principle: `_normalize`/`_unnormalize` only read range_min/range_max and never require ≥0. Only `_serialize_data` rejects negatives, and only when writing the *unsigned* Min/Max_Position_Limit EPROM registers. (Homing_Offset itself is fine negative — sign-magnitude, bit 11.) So a true-negative range = keep range in JSON, skip the EPROM limit write.

### Historical (superseded) framing of the failure

**Discovered 2026-05-31.** Some joints have their physical travel range crossing the STS3215 encoder's 0↔4095 boundary.

### Confirmed affected joints (leader arm, 2026-05-31)

| Joint | ID | Stop A (raw) | Stop B (raw) | Wraps? | Notes |
|---|---|---|---|---|---|
| shoulder_pan | 7 | 944 | 3337 | No ✅ | Clean range |
| shoulder_lift | 8 | 1855 | 202 | **Yes ⚠️** | Goes UP: 1855→4095→0→202; span ~214° |
| elbow_flex | 9 | 831 | 3149 | No ✅ | Clean range |
| wrist_flex | 10 | 2448 | 3970 | Unknown | Suspect yes — showed 0–4095 in calibration run |

Diagnostic command used to confirm:
```bash
python -c "
from lerobot.motors.feetech import FeetechMotorsBus
from lerobot.motors.motors_bus import Motor, MotorNormMode
import time
bus = FeetechMotorsBus(port='/dev/ttyACM0', motors={
    'shoulder_lift': Motor(id=8, model='sts3215', norm_mode=MotorNormMode.RANGE_0_100),
})
bus.connect(); bus.disable_torque()
while True:
    v = bus.read('Present_Position', 'shoulder_lift', normalize=False)
    print(f'\r  {int(v):4d}', end='', flush=True)
    time.sleep(0.05)
"
```

### Why `record_ranges_of_motion` fails for wrap-around joints

`record_ranges_of_motion` uses simple `min()` / `max()` tracking. For a joint that traverses 1855→4095→0→202, it records min=0, max=4095 (full encoder range) — which is physically wrong.

### Why `set_half_turn_homings` doesn't fix it

`set_half_turn_homings` computes `homing_offset = 2047 - present_position` and writes it to the servo EPROM. For shoulder_lift with the center of wrap-path at raw ~3076:
- homing_offset = 2047 - 3076 = -1029
- Stop A (raw 1855): homed = 1855 + (-1029) = 826 ✓
- Stop B (raw 202): homed = 202 + (-1029) = **-827** ✗

`write_calibration` attempts to write range_min = -827 to the `Min_Position_Limit` EPROM register, which rejects negative values → `ValueError`.

### Current state of calibration files

Both `calibration_follower.json` and `calibration_leader.json` were generated with the old script, but in practice the calibration data is good enough for teleoperation — both arms are tracking correctly. A clean re-calibration using the fixed flow is still recommended before dataset recording to ensure precise normalization.

### Remaining implementation work

The physics is solved; the code is not yet rewritten. `calibrate_lerobot.py` still hand-rolls offset math (`raw + offset` without mod 4096) and never calls `configure_motors()`. Next step: rewrite it around the library primitives in the order listed above. Per the coding-triage rule, the homing/seam logic is **model-bearing → Evan writes it first, predict-first**; the argparse/JSON/loop scaffolding is glue → Claude can write it.

---

### move_one.py — current state (2026-05-28)

- Located at `software/setup/move_one.py`
- Uses raw `scservo_sdk` directly (no `_serial_utils` wrapper)
- Interactive ID collection via readchar; SPACE to finish (ESC dropped — SSH eats it)
- On startup: pings each servo, reads current position, enables torque, moves to home position from `config/home.json`
- Home speed: 500 steps/s, accel: 50 (~100 steps/s² units) — conservative startup values
- Home positions stored in `software/config/home.json` (IDs 1–6, leader arm, captured 2026-05-28)

### torque_off.py / flash_angle_limits.py (2026-05-28)
- `torque_off.py`: interactive torque disable, same ID collection as move_one.py
- `flash_angle_limits.py`: reads limits.json, writes MIN/MAX angle limits to servo EPROM for all IDs; servo needs power cycle after

### teleop.py — confirmed working (2026-06-03)

- Located at `software/control/teleop.py`
- Single `FeetechMotorsBus` on `/dev/ttyACM0` with all 12 motors (prefixed `follower_*` and `leader_*`)
- Startup: safe-enables both arms → `go_neutral` both simultaneously → disables leader torque → loop starts
- Loop: `sync_read` leader normalized positions (0–100) → 1:1 dict remap → `sync_write` to follower at 50 Hz
- Arms are physically identical (not mirrored), so `drive_mode=0` + 1:1 normalized mapping = matching poses
- No pre-running `go_neutral` needed — teleop handles its own startup sequence
- Usage: `conda activate lerobot && python software/control/teleop.py [--hz 50]`

**Import path gotcha (hit 2026-06-03):** Adding `software/` to `sys.path` to import `go_neutral` shadows the pip-installed `scservo_sdk` with the local copy in `software/scservo_sdk/`. LeRobot's `feetech.py` uses `scservo_sdk.PacketHandler` which doesn't exist in the local SDK → `AttributeError`. Fix: add the repo root (`hexarm/`) to `sys.path` instead, then import as `from software.calibration.go_neutral import go_neutral`.

### go_neutral.py — bug fix (2026-06-03)

`go_neutral` was resetting `Maximum_Velocity_Limit` to 0 after completing but **not** resetting `Acceleration`. Leaving `Acceleration = 20` on the servos caused sluggish ramp-up in the teleop loop. Fixed: both registers are now reset to 0 on completion.

*Last updated: 2026-06-03 (session 2)*
