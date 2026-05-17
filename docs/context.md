# hexarm — Project Context

> This file is the source of truth for project context across AI sessions (Claude.ai, Cowork, etc.).
> Update it as the project evolves.

---

## Project Overview

**hexarm** is a custom 6-DOF serial robotic arm built by Evan Applebaum, based on the SO-100/SO-101 open-source design by TheRobotStudio. The goal is to develop a leader–follower teleoperation system with imitation learning capabilities using the Hugging Face LeRobot framework.

The project lives at: `github.com/evanapplebaum/hexarm`

---

## Hardware

### Arm Structure
- **Design basis:** SO-100 (open-source, 3D printed frame)
- **Configuration:** Leader arm + follower arm (6 DOF each)
- **Frame material:** 3D printed (PLA+/PETG)

### Actuators — FEETECH STS3215 Smart Servos
- 12 total: 6 per arm
- **Control:** Half-duplex TTL serial bus (NOT PWM)
- **Encoder:** 12-bit absolute magnetic — no homing needed on boot
- **Feedback:** Position, temperature, voltage, current, load — all readable over bus
- **Supply voltage:** 7.4V (SO-100 spec)
- **Torque:** 19.5 kg·cm @ 7.4V
- **Modes:** Servo mode (position) or motor mode (continuous rotation)
- All servos daisy-chained on one bus, addressed by unique ID

### Servo Driver Board — UeeKKoo Serial Bus Servo Driver (×2)
- **2 boards total — one per arm** (leader bus and follower bus are fully independent)
- Integrates servo power supply and half-duplex bus direction control
- **Dual host interfaces:** USB (appears as `/dev/ttyUSB0` or `/dev/tty.usbserial-XXXX`) and UART GPIO pins — either works
- Supports ST/SC series servos; explicitly compatible with ST3215
- Addresses up to 253 servos per bus
- USB interface allows direct control from Mac or Pi without a separate USB-UART adapter

### Compute — Raspberry Pi Zero 2W
- **OS:** to be confirmed
- **Network:** to be confirmed
- **Connection to driver boards:** Each UeeKKoo board connects via USB → Pi sees them as `/dev/ttyUSB0` and `/dev/ttyUSB1` (or similar)
  - USB avoids Pi 02W UART count constraints entirely
  - Alternatively: boards expose GPIO UART pins if USB is unavailable

### Vision (planned)
- Wrist-mounted (eye-in-hand) camera and/or overhead workspace camera
- UVC-compatible (Intel RealSense D405/D435 or standard webcam)

---

## Software Stack

### LeRobot (Hugging Face) — Primary Framework
- **Version installed:** 0.5.2
- **Install location:** `~/lerobot/` on Pi
- **Virtual environment:** `lerobot-env` (activate with `source ~/lerobot-env/bin/activate`)
- **Feetech driver path (v0.5.x):** `lerobot.motors.feetech.feetech.FeetechMotorsBus`
- Handles teleoperation, dataset recording, policy training (ACT, diffusion), and policy deployment

### Intended Workflow
```
Teleoperate (leader → follower)
    ↓
Record demonstrations (joint states + camera frames)
    ↓
Train policy (ACT or diffusion policy)
    ↓
Deploy on hardware
```

### ROS2 (optional / future)
- ROS2 Jazzy targets Ubuntu 24.04 — compatible with current Pi setup
- Potential use: motion planning via MoveIt2, integration with autonomous delivery robot
- Decision pending: LeRobot standalone vs. wrapped in ROS2 nodes

---

## Setup Status

| Task | Status |
|---|---|
| LeRobot 0.5.2 installed | ✅ Done |
| Feetech motor drivers verified | ✅ Done |
| Pi Zero 2W setup | ⏳ Todo |
| Driver board connected to Pi | ⏳ Awaiting hardware |
| config.py updated for Pi 02W UART ports | ⏳ Todo |
| Servo IDs assigned (1–6 leader, 7–12 follower) | ⏳ Awaiting hardware |
| Bus communication test (ping 12 servos) | ⏳ Awaiting hardware |
| LeRobot arm config file | ⏳ Todo |
| First teleoperation test | ⏳ Todo |
| Dataset recording | ⏳ Todo |
| Policy training | ⏳ Todo |

---

## Key Technical Notes

### Half-Duplex Bus Timing
The STS3215 uses half-duplex UART — TX and RX share one physical wire on the servo side. The UeeKKoo driver board handles bus direction switching internally; the host just uses a standard full-duplex serial interface (USB or UART). Sequence per transaction:
1. Host sends command packet → board drives bus
2. Board switches to receive
3. Addressed servo replies
4. Servo releases bus

All other servos on the bus see every packet but ignore ones not addressed to their ID. Timing between the board releasing and the servo replying is handled by the board's direction-switching circuit.

### Servo IDs
Each servo needs a unique ID programmed before LeRobot can address them. Current plan: leader IDs 1–6, follower IDs 7–12. IDs are stored in EPROM (requires unlock/lock sequence to write). This is a required first step when hardware arrives — can be done via the ST3215 driver board + a script using `scservo_sdk` or a short Arduino sketch.

### LeRobot Virtual Environment
Always activate before running anything:
```bash
source ~/lerobot-env/bin/activate
```

---

## Concepts Covered (Learning Log)

- SO-100 hardware architecture and design tradeoffs
- FEETECH STS3215 servo internals (encoder, bus protocol, packet framing)
- Half-duplex UART — direction control, timing, bus arbitration
- Forward kinematics and DH parameters
- Jacobian matrix — physical meaning, column interpretation
- Singularities — rank deficiency, physical causes, configuration dependence
- Pseudoinverse (J⁺) and null space
- Impedance/compliance control
- Gravity compensation
- LeRobot imitation learning pipeline (teleoperation → record → train → deploy)

---

## Open Questions / Next Steps

- [ ] Set up Pi Zero 2W (OS, networking, LeRobot install)
- [ ] Confirm second UART availability on Pi 02W (mini-UART vs overlay vs USB adapter)
- [ ] Update config.py with correct Pi 02W UART port paths
- [ ] Assign servo IDs when driver board arrives
- [ ] Write/configure LeRobot arm config file for hexarm (based on SO-100 config)
- [ ] First end-to-end teleoperation test
- [ ] Confirm ROS2 integration plan (standalone LeRobot vs. ROS2 nodes)
- [ ] Decide on camera hardware

---

*Last updated: May 16, 2026*
