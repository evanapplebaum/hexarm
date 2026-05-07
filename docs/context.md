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

### Servo Driver Board — Waveshare Serial Bus Servo Driver
- Bridges USB (host) → TTL half-duplex serial (servos)
- Handles bus direction switching and power distribution
- Appears as `/dev/ttyUSB0` (or similar) on the host

### Compute — Raspberry Pi 5
- **Hostname:** `eka-pi5`
- **User:** `ekapi`
- **OS:** Ubuntu Server 24.04.4 LTS (64-bit, aarch64)
- **Network:** Home guest WiFi (SSH confirmed working)
- **IP:** 192.168.86.123 (DHCP — may change)
- SSH access: `ssh ekapi@eka-pi5.local`

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

## Key Technical Notes

### Half-Duplex Bus Timing
The STS3215 uses half-duplex UART. TX and RX share one wire — the driver board switches a direction pin between transmit and receive. Sequence per transaction:
1. Host drives bus → sends command packet
2. Host releases bus (switches to RX)
3. Addressed servo replies
4. Servo releases bus

Timing between host releasing and servo replying is critical. All other servos see the packet but ignore it (addressed by ID).

### Servo IDs
Each servo needs a unique ID (1–6 per arm) programmed via the Waveshare board before LeRobot can address them. This is a required first step when hardware arrives.

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

- [ ] Confirm ROS2 integration plan (standalone LeRobot vs. ROS2 nodes)
- [ ] Decide on camera hardware
- [ ] Assign servo IDs when Waveshare board arrives
- [ ] Write/configure LeRobot arm config file for hexarm (based on SO-100 config)
- [ ] First end-to-end teleoperation test

---

*Last updated: May 2026*
