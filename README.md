# Hexarm

A custom 6-DOF leader-follower robotic arm system based on the open-source [SO-100](https://github.com/TheRobotStudio/SO-ARM100) design. Built for hands-on experience in mechanical design, embedded systems, and robot teleoperation — with imitation learning via the [LeRobot](https://github.com/huggingface/lerobot) framework as the end goal.

> **Status:** 🔧 In active development — leader-follower **teleoperation working end-to-end** (2026-06-03). Both arms run on a single servo bus at 50 Hz. Calibration refinement and dataset recording are next.

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
└── low-lvl-setup/               # raw SDK diagnostics and one-time setup tools
```

---

## Documentation

- [Kinematics — DH Parameters & Forward/Inverse Kinematics](docs/kinematics.md)
- [Project Context — full hardware/software handoff](docs/context.md)
- [Servo Comms Bring-Up — UART/SDK debugging chronology](docs/debugging/servo-comms-debug-log.md)
- [Encoder Wrap-Around — LeRobot calibration handoff](docs/handoffs/lerobot-calibration-wrap-around.md)

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
| Per-joint calibration (both arms) | ✅ Working (clean re-cal pending) |
| Leader-follower teleoperation (`teleop.py`) | ✅ Done (2026-06-03) |
| Encoder wrap-around fix — code rewrite | ⏳ In progress |
| Angle limits flashed to servo EPROM | ⏳ Todo |
| Dataset recording | ⏳ Todo |
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
