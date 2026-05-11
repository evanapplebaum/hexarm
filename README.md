# Hexarm

A custom 6-DOF leader-follower robotic arm system based on the open-source [SO-100](https://github.com/TheRobotStudio/SO-ARM100) design. Built for hands-on experience in mechanical design, embedded systems, and robot teleoperation — with imitation learning via the [LeRobot](https://github.com/huggingface/lerobot) framework as the end goal.

> **Status:** 🔧 In development — compute and software stack ready, awaiting hardware

---

## Overview

| Property | Value |
|---|---|
| Configuration | Leader-follower (2 arms) |
| Degrees of Freedom | 6 per arm (5 + gripper) |
| Actuators | FEETECH STS3215 (6× per arm, 12 total) |
| Servo Driver | Waveshare Serial Bus Servo Driver (USB → TTL) |
| Compute | Raspberry Pi 5 |
| Framework | [LeRobot](https://github.com/huggingface/lerobot) 0.5.2 |
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

- Raspberry Pi 5 running Ubuntu Server 24.04 (aarch64)
- Waveshare Serial Bus Servo Driver
- 12× FEETECH STS3215 servos

### Software Setup

```bash
# Clone the repo
git clone https://github.com/evanapplebaum/hexarm.git
cd hexarm

# SSH into the Pi
ssh ekapi@eka-pi5.local

# Activate the LeRobot environment
source ~/lerobot-env/bin/activate
```

*Full setup guide coming once hardware integration is complete.*

---

## Setup Status

| Task | Status |
|---|---|
| Pi 5 flashed with Ubuntu 24.04 | ✅ Done |
| System updated | ✅ Done |
| LeRobot 0.5.2 installed | ✅ Done |
| Feetech motor drivers verified | ✅ Done |
| Waveshare board connected | ⏳ Awaiting hardware |
| Servo IDs assigned (1–6 per arm) | ⏳ Awaiting hardware |
| Bus communication test (ping 12 servos) | ⏳ Awaiting hardware |
| LeRobot arm config file | ⏳ Todo |
| First teleoperation test | ⏳ Todo |
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
