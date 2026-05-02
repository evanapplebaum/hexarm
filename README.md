# Hexarm

A custom 5-DOF leader-follower robotic arm system built from scratch using ST3215 servo motors. Hexarm is an independent design inspired by the open-source [SO-100](https://github.com/TheRobotStudio/SO-ARM100), aimed at gaining hands-on experience in mechanical design, kinematics, embedded systems, and robot teleoperation.

> **Status:** 🔧 In development — CAD phase

---

## Overview

| Property | Value |
|---|---|
| Configuration | Leader-follower (2 arms) |
| Degrees of Freedom | 5 + 1 gripper per arm |
| Actuation | ST3215 servo motor (6× per arm) |
| Reach | TBD |
| Payload | TBD |
| CAD Tool | Onshape |
| Controller | TBD |

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
- [Servo Protocol — ST3215](docs/servo-protocol.md) *(coming soon)*
- [Control Loop Design](docs/control-loop.md) *(coming soon)*

### Design Decisions (ADRs)
- [ADR-001 — Controller Selection](docs/decisions/adr-001-controller.md) *(coming soon)*
- [ADR-002 — Servo Communication Topology](docs/decisions/adr-002-servo-comms.md) *(coming soon)*

---

## Getting Started

*(Fill in once firmware/software is ready)*

```bash
# Clone the repo
git clone https://github.com/evanapplebaum/hexarm.git
cd hexarm
```

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
- [ ] Firmware — ST3215 driver (UART register read/write)
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
- [ ] Build — print and source all parts
- [ ] Build — assemble both arms
- [ ] Build — wire electronics
- [ ] Integration — end-to-end position control test
- [ ] Docs — control loop design

### M6 — Teleoperation Demo
- [ ] Software — leader-follower control loop
- [ ] Software — safety limits and emergency stop
- [ ] Demo — record demo video / GIF

---

## License

MIT License — see [LICENSE](LICENSE)
