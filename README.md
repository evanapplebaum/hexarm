# Hexarm

A custom 6-DOF leader-follower robotic arm system based on the open-source [SO-100](https://github.com/TheRobotStudio/SO-ARM100) design. Built for hands-on experience in mechanical design, embedded systems, and robot teleoperation — with imitation learning via the [LeRobot](https://github.com/huggingface/lerobot) framework as the end goal.

> **Status:** 🔧 In active development — leader-follower **teleoperation working end-to-end** (2026-06-03), calibration and angle limits finalized (2026-07-27). A broken follower joint was reprinted, reassembled, and re-calibrated (2026-08-03); the startup sequence now moves both arms to neutral before recording, plays back a 10s recorded motion, and returns to neutral, with a hold-to-move diagnostic mode for safe testing — confirmed working end-to-end (2026-08-03). Cameras are in hand and connected — the overhead camera is mounted and locked, the wrist camera's reprinted mount is installed but placement isn't re-verified yet (2026-08-01). Dataset recording starts next.

---

## Overview

| Property | Value |
|---|---|
| Configuration | Leader-follower (2 arms) |
| Degrees of Freedom | 6 per arm (5 + gripper) |
| Actuators | FEETECH STS3215 (6× per arm, 12 total) |
| Servo Driver | Waveshare Bus Servo Adapter (A) — half-duplex TTL, USB host |
| Compute | NVIDIA Jetson Orin Nano Super (JetPack 6.2, Ubuntu 22.04) |
| Bus interface | USB CDC-ACM on `/dev/ttyACM0` at 1 Mbps |
| Bus topology | Single bus — both arms (follower IDs 1–6, leader IDs 7–12) |
| Framework | [LeRobot](https://github.com/huggingface/lerobot) (`feetech` extra, editable install) |
| CAD Tool | Onshape |
| Reach | TBD |
| Payload | TBD |

---

## Demo

<!-- Add a GIF or photo here once the arm is built -->
<!-- ![Hexarm demo](docs/images/demo.gif) -->

*Photos and teleop video coming soon.*

---

## Repository Structure

```
hexarm/
├── cad/            # Mechanical design files and exports (Onshape)
├── firmware/       # Arduino tools (one-shot servo config sketches)
├── software/       # Control, calibration, and low-level setup scripts
├── electronics/    # Schematics and bill of materials
├── docs/           # Technical documentation and debugging logs
└── simulation/     # URDF and simulation models
```

Key entry points inside `software/`:

```
software/
├── control/teleop.py            # leader-follower teleoperation loop (working)
├── calibration/                 # LeRobot-based calibration + arm control
├── vision/camera_preview.py     # headless MJPEG live-view tool for camera positioning
└── low-lvl-setup/               # raw SDK diagnostics and one-time setup tools
```

---

## Documentation

- [Session Guide — personal setup checklist + where-we-left-off log](docs/session.md)
- [Kinematics — DH Parameters & Forward/Inverse Kinematics](docs/kinematics.md)
- [Project Context — full hardware/software handoff](docs/context.md)
- [Postmortems — consolidated incident log (symptom → root cause → fix → lesson)](docs/debugging/postmortems.md)
- [Servo Comms Bring-Up — full UART/SDK debugging chronology](docs/debugging/servo-comms-debug-log.md)
- [Robot Dog — forward planning (hardware reuse, camera architecture)](docs/robotdogplan.md)

**Planned** (to be written as the project's notes get consolidated):

- ADR — compute platform selection (Pi Zero 2W → Jetson Orin Nano Super)
- ADR — single-bus servo topology (vs. LeRobot's two-bus default)
- Teleop control-loop design doc (50 Hz `sync_read` → `sync_write` mapping)

---

## Getting Started

### Hardware

- NVIDIA Jetson Orin Nano Super (JetPack 6.2, Ubuntu 22.04 / aarch64)
- 1× Waveshare Bus Servo Adapter (A) — set to USB-Servo mode
- 12× FEETECH STS3215 servos (both arms daisy-chained on one bus)
- 12 V DC supply for the servo bus (via the board's barrel jack)

### Physical Hookup / Power

There are **two separate power adapters** — both plug into standard AC wall sockets, but they are **not interchangeable**:

| Adapter | Output | Powers | Connector |
|---|---|---|---|
| Jetson power supply | 19V, 2.37A max | Jetson Orin Nano Super | Jetson's barrel jack |
| Servo bus power supply | 12V, 5A max | Servo bus (both arms) | Waveshare board's barrel jack |

> **⚠️ Do not cross these.** Plugging the Jetson's 19V adapter into the Waveshare board's barrel jack will fry it (it's only rated for 12V). Double-check which brick you're holding before plugging in.

Full connection sequence:

1. Daisy-chain both arms' servo JST connectors into the **one** Waveshare Bus Servo Adapter (A) that's in use (the second board on hand is a spare — not wired in for the current single-bus setup).
2. Confirm the board's physical mode switch is set to **USB-Servo**.
3. Plug the 12V/5A adapter into the Waveshare board's barrel jack (servo bus power).
4. Plug the 19V/2.37A adapter into the Jetson's barrel jack (compute power).
5. Connect the Waveshare board to the Jetson via USB — it enumerates as `/dev/ttyACM0`.
6. Power on the Jetson and SSH in (`ssh evan0h@eka-orin.local`).

### Software Setup (Jetson)

```bash
# Clone the repo
git clone https://github.com/evanapplebaum/hexarm.git
cd hexarm

# LeRobot runs in a conda env (Python 3.12 required)
conda activate lerobot

# Verify communication with a connected servo:
python software/low-lvl-setup/raw_ping.py --id 1     # raw pyserial diagnostic
python software/low-lvl-setup/ping_one.py --id 1     # via the scservo_sdk path

# Run leader-follower teleoperation:
python software/control/teleop.py --hz 50
```

> **Note:** LeRobot is not installable on Intel Mac (no x86_64 torch build). For Mac-side
> diagnostics, a lightweight `pyserial`-only venv drives the same `low-lvl-setup` scripts
> over the board's USB port (`/dev/cu.usbmodem*`). See [docs/context.md](docs/context.md)
> for the full per-platform setup and the servo bus bring-up procedure.

---

## Setup Status

| Task | Status |
|---|---|
| Jetson Orin Nano Super flashed (JetPack 6.2) + SSH | ✅ Done |
| Servo bus over USB (`/dev/ttyACM0`, CDC-ACM) | ✅ Done |
| Servo communication verified (raw pyserial + scservo_sdk) | ✅ Done |
| LeRobot installed on Jetson (`pip install -e ".[feetech]"`) | ✅ Done |
| Servo IDs assigned — follower 1–6, leader 7–12, single bus | ✅ Done |
| All 12 servos responding on one bus | ✅ Done |
| Per-joint calibration (both arms) | ✅ Done — clean re-calibration complete (2026-07-27); follower re-calibrated again (2026-08-03) after a broken joint was reprinted and reassembled |
| Leader-follower teleoperation (`teleop.py`) | ✅ Done (2026-06-03) |
| Encoder wrap-around fix — code rewrite | ✅ Done (2026-06-02) |
| Angle limits flashed to servo EPROM | ✅ Done (2026-07-27) |
| Cameras (wrist + overhead, 2× Arducam OV9782 global shutter) | 🔧 In hand and connected — overhead mounted & locked (2026-07-31), wrist mount reprinted & installed but placement not yet re-verified (2026-08-01) |
| Dataset recording | 🔧 Starting next |
| Policy training | ⏳ Todo |

---

## Roadmap

### M1 — CAD Complete
- [x] CAD — individual part design
- [ ] CAD — full assembly
- [ ] Docs — hardware assembly guide

### M2 — Electronics & BOM
- [ ] Electronics — servo power budget
- [ ] Electronics — wiring schematic
- [ ] Electronics — bill of materials
- [ ] ADR — compute platform selection
- [ ] ADR — single-bus servo topology

### M3 — Firmware & Low-Level Comms
- [x] Servo communication over UART/USB (register read/write)
- [x] Per-servo configuration tool (ID, baud, return delay)
- [x] Joint-limit calibration tool
- [ ] Docs — servo protocol reference

### M4 — Software: Kinematics
- [ ] Software — forward kinematics (DH-based)
- [ ] Software — inverse kinematics (geometric + wrist decoupling)
- [ ] Software — joint limit enforcement
- [ ] URDF — model creation and RViz validation

### M5 — Physical Build & Integration
- [x] Compute — Jetson Orin Nano Super provisioned and networked
- [x] Software — LeRobot installed and verified
- [x] Build — print and source all parts
- [x] Build — assemble both arms
- [x] Integration — servo IDs assigned, both arms on one bus

### M6 — Teleoperation & Imitation Learning
- [x] Software — leader-follower control loop (LeRobot)
- [ ] Software — safety limits and emergency stop
- [ ] Data — record demonstration dataset
- [ ] Training — train ACT or diffusion policy
- [ ] Deploy — run policy on hardware
- [ ] Demo — record demo video / GIF

---

## License

MIT License — see [LICENSE](LICENSE)
