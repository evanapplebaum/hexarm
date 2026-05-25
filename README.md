# Hexarm

A custom 6-DOF leader-follower robotic arm system based on the open-source [SO-100](https://github.com/TheRobotStudio/SO-ARM100) design. Built for hands-on experience in mechanical design, embedded systems, and robot teleoperation — with imitation learning via the [LeRobot](https://github.com/huggingface/lerobot) framework as the end goal.

> **Status:** 🔧 In active development — servo communication and per-joint calibration working end-to-end (2026-05-25). Teleoperation control loop is next.

---

## Overview

| Property | Value |
|---|---|
| Configuration | Leader-follower (2 arms) |
| Degrees of Freedom | 6 per arm (5 + gripper) |
| Actuators | FEETECH STS3215 (6× per arm, 12 total) |
| Servo Driver | Waveshare Bus Servo Adapter (A) — half-duplex TTL, USB or UART host |
| Compute | Raspberry Pi Zero 2W (Ubuntu 24.04 server) |
| Bus interface | PL011 hardware UART on `/dev/ttyAMA0` at 1 Mbps |
| Framework | [LeRobot](https://github.com/huggingface/lerobot) 0.5.2 (target) |
| CAD Tool | Onshape |
| Reach | TBD |
| Payload | TBD |

---

## Demo

<!-- Add a GIF or photo here once the arm is built -->
<!-- ![Hexarm demo](docs/images/demo.gif) -->

*Photos and video coming soon.*

---

## Repository Structure

```
hexarm/
├── cad/            # Mechanical design files and exports
├── firmware/       # Microcontroller code (servo drivers, control loops)
├── software/       # PC-side kinematics and teleoperation control
├── electronics/    # Schematics and bill of materials
├── docs/           # Technical documentation and design decisions
└── simulation/     # URDF and simulation models
```

---

## Documentation

- [Kinematics — DH Parameters & Forward/Inverse Kinematics](docs/kinematics.md)
- [System Architecture](docs/architecture.md) *(coming soon)*
- [Hardware Assembly Guide](docs/hardware-setup.md) *(coming soon)*
- [Servo Protocol — STS3215](docs/servo-protocol.md) *(coming soon)*
- [Control Loop Design](docs/control-loop.md) *(coming soon)*

### Design Decisions (ADRs)
- [ADR-001 — Controller Selection](docs/decisions/adr-001-controller.md) *(coming soon)*
- [ADR-002 — Servo Communication Topology](docs/decisions/adr-002-servo-comms.md) *(coming soon)*

---

## Getting Started

### Requirements

- Raspberry Pi Zero 2W running Ubuntu Server 24.04 (aarch64)
- Waveshare Bus Servo Adapter (A) (×2 once both arms are wired)
- 12× FEETECH STS3215 servos
- 12 V DC supply for the servo bus

### Software Setup

```bash
# Clone the repo
git clone https://github.com/evanapplebaum/hexarm.git
cd hexarm

# Set up Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install pyserial readchar

# On the Pi only — free PL011 from Bluetooth and disable the serial console.
# See docs/context.md "Compute — Raspberry Pi Zero 2W" for the full procedure.

# Verify communication with a connected servo:
python3 software/control/raw_ping.py --id 1     # raw pyserial diagnostic
python3 software/control/ping_one.py --id 1     # via the scservo_sdk path
```

See [docs/context.md](docs/context.md) for the full hardware/software handoff document and [docs/debugging/servo-comms-debug-log.md](docs/debugging/servo-comms-debug-log.md) for a deep dive into the comms bring-up.

---

## Setup Status

| Task | Status |
|---|---|
| Pi Zero 2W flashed with Ubuntu 24.04 | ✅ Done |
| PL011 UART configured (disable-bt, console removed) | ✅ Done |
| Waveshare Bus Servo Adapter (A) wired in UART-Servo mode | ✅ Done |
| Servo communication verified (raw pyserial + scservo_sdk) | ✅ Done |
| Per-servo configuration tool (`setup_servo.py`) | ✅ Done |
| Joint-limit calibration tool (`calibrate.py`) | ✅ Done |
| Servo 2 calibrated end-to-end | ✅ Done |
| Remaining 11 servos wired + calibrated | ⏳ In progress |
| Second arm — port strategy (Pi Zero 2W has one UART) | ⏳ Open question |
| Teleoperation loop (`teleop.py`) | ⏳ Todo |
| Dataset recording | ⏳ Todo |
| Policy training | ⏳ Todo |

---

## Roadmap

### M1 — CAD Complete
- [ ] CAD — individual part design
- [ ] CAD — full assembly
- [ ] Docs — hardware assembly guide

### M2 — Electronics & BOM
- [ ] Electronics — servo power budget
- [ ] Electronics — wiring schematic
- [ ] Electronics — bill of materials
- [ ] ADR — controller selection
- [ ] ADR — servo communication topology

### M3 — Firmware: Servo Control
- [ ] Firmware — STS3215 driver (UART register read/write)
- [ ] Firmware — position control with joint limits
- [ ] Firmware — multi-servo synchronization
- [ ] Firmware — calibration routine
- [ ] Docs — servo protocol reference

### M4 — Software: Kinematics
- [ ] Software — forward kinematics (DH-based)
- [ ] Software — inverse kinematics (geometric + wrist decoupling)
- [ ] Software — joint limit enforcement
- [ ] URDF — model creation and RViz validation

### M5 — Physical Build & Integration
- [x] Compute — Pi 5 provisioned and networked
- [x] Software — LeRobot 0.5.2 installed and verified
- [ ] Build — print and source all parts
- [ ] Build — assemble both arms
- [ ] Build — wire electronics and assign servo IDs
- [ ] Integration — end-to-end teleoperation test
- [ ] Docs — control loop design

### M6 — Teleoperation & Imitation Learning
- [ ] Software — leader-follower control loop (LeRobot)
- [ ] Software — safety limits and emergency stop
- [ ] Data — record demonstration dataset
- [ ] Training — train ACT or diffusion policy
- [ ] Deploy — run policy on hardware
- [ ] Demo — record demo video / GIF

---

## License

MIT License — see [LICENSE](LICENSE)
