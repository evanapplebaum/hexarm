# Hexarm

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)

A custom anthropomorphic 6-DOF leader-follower robotic arm system roughly based on the open-source [SO-100](https://github.com/TheRobotStudio/SO-ARM100) design. Built for hands-on experience in mechanical design, embedded systems, and robot teleoperation, with imitation learning via the [LeRobot](https://github.com/huggingface/lerobot) framework.

> **Status:** ✅ Core pipeline complete. Both arms were built, calibrated, and made to teleoperate end-to-end. An ACT policy trained on a 50-episode pick-and-place dataset was run autonomously on the physical follower arm via a dead-man's-switch-gated control loop. Full session-by-session history lives in [docs/context.md](docs/context.md).

---

## Demo

<p align="center">
  <img src="media/videos/autonomous.gif" width="520" alt="ACT policy running autonomously on the follower arm">
</p>

**Autonomous policy.** An ACT policy trained on 50 teleoperated demonstrations, running
on the follower arm with no human input: approach, grasp, transport, release. Clip is
1.25× real time.

<p align="center">
  <img src="media/videos/teleop.gif" width="260" alt="Teleoperation: leader arm driven by hand, follower mirroring">
</p>

**Teleoperation.** The leader arm (bottom) is backdriven by hand; the follower (top)
mirrors it at 50 Hz over a single half-duplex servo bus. This is how the training
demonstrations were recorded.

---

## Overview

| Property | Value |
|---|---|
| Configuration | Leader-follower (2 arms) |
| Degrees of Freedom | 6 per arm (5 + gripper) |
| Actuators | FEETECH STS3215 (6× per arm, 12 total) |
| Servo Driver | Waveshare Bus Servo Adapter (A) — half-duplex TTL, USB host |
| Compute | NVIDIA Jetson Orin Nano Super (JetPack 7.2, Ubuntu 24.04) |
| Bus interface | USB CDC-ACM on `/dev/ttyACM0` at 1 Mbps |
| Bus topology | Single bus — both arms (follower IDs 1–6, leader IDs 7–12) |
| Framework | [LeRobot](https://github.com/huggingface/lerobot) (`feetech` extra, editable install) |
| CAD Tool | [Onshape](https://cad.onshape.com) (public) |
| Reach | 433 mm |
| Payload | 1.2 kg @ worst case scenario (maximum reach) |

---

### CAD

| Leader | Follower |
|---|---|
| ![Leader arm CAD assembly](cad/renders/leader_arm.png) | ![Follower arm CAD assembly](cad/renders/follower_arm.png) |

*CAD renders (Onshape, 2026-08-09) of the finished leader and follower arm assemblies.*

### Hardware Photos

<table>
<tr>
<td align="center"><img src="media/pictures/full-scene.jpg" width="200"><br>Full workspace scene</td>
<td align="center"><img src="media/pictures/both-standing.jpg" width="200"><br>Both arms</td>
<td align="center"><img src="media/pictures/closeup-sideview.jpg" width="200"><br>Side view close-up</td>
<td align="center"><img src="media/pictures/leader-closeup.jpg" width="200"><br>Leader close-up</td>
</tr>
<tr>
<td align="center"><img src="media/pictures/leader-claw-closeup.jpg" width="200"><br>Leader claw close-up</td>
<td align="center"><img src="media/pictures/follower-isometric.jpg" width="200"><br>Follower isometric</td>
<td align="center"><img src="media/pictures/follower-sideview.jpg" width="200"><br>Follower side view</td>
<td align="center"><img src="media/pictures/follower-front-close.jpg" width="200"><br>Follower front close-up</td>
</tr>
<tr>
<td align="center"><img src="media/pictures/follower-top-side.jpg" width="200"><br>Follower top/side view</td>
<td align="center"><img src="media/pictures/follower-underview.jpg" width="200"><br>Follower underside</td>
<td align="center"><img src="media/pictures/follower-full-extended.jpg" width="200"><br>Follower fully extended</td>
<td align="center"><img src="media/pictures/follower-horizontal-extended.jpg" width="200"><br>Follower horizontal reach</td>
</tr>
<tr>
<td align="center"><img src="media/pictures/follower-joints-closeup.jpg" width="200"><br>Follower joints close-up</td>
<td align="center"><img src="media/pictures/follower-closeup-camera.jpg" width="200"><br>Follower wrist camera close-up</td>
</tr>
</table>

*Real hardware photos (2026-08-21) of the finished leader and follower arms.*

---

## Repository Structure

```
hexarm/
├── cad/            # Mechanical design files and exports (Onshape)
├── media/          # Hardware photos of robots & workspace (media/pictures/)
├── software/       # Control, calibration, and low-level setup scripts
└── docs/           # Technical documentation and debugging logs
```

Key entry points inside `software/`:

```
software/
├── control/teleop.py            # leader-follower teleoperation loop (working)
├── control/record_dataset.py    # records teleoperated demos into a LeRobotDataset
├── control/run_policy.py        # runs a trained checkpoint on the physical follower arm
├── calibration/                 # LeRobot-based calibration + arm control
├── vision/camera_preview.py     # headless MJPEG live-view tool for camera positioning
└── low-lvl-setup/               # raw SDK diagnostics and one-time setup tools
```

---

## Documentation

- [Hardware Assembly Guide — fastener reference, build order, workspace setup](docs/hardware-assembly-guide.md)
- [Teleop Control Loop — 50 Hz `sync_read` → `sync_write` design reference](docs/teleop-control-loop.md)
- [Servo Protocol Reference — STS3215 packet protocol + hardware-verified gotchas](docs/servo-protocol-reference.md)
- [Project Context — full hardware/software handoff](docs/context.md)
- [Postmortems — consolidated incident log (symptom → root cause → fix → lesson)](docs/debugging/postmortems.md)
- [Servo Comms Bring-Up — full UART/SDK debugging chronology](docs/debugging/servo-comms-debug-log.md)
- [CAD Assembly (Onshape, public)](https://cad.onshape.com/documents/0670dbd7fb06bb7c9bf9782d/w/e043c38067500e43503b5676/e/e17080d119308b27c44a0ee6) — full parametric model, leader and follower arms modeled separately
- ADR — [0001: compute platform selection](docs/adr/0001-compute-platform-selection.md) (Pi Zero 2W → Jetson Orin Nano Super), [0002: single-bus servo topology](docs/adr/0002-single-bus-servo-topology.md) (vs. LeRobot's two-bus default)

---

## Getting Started

### Hardware

- NVIDIA Jetson Orin Nano Super (JetPack 7.2, Ubuntu 24.04 / aarch64)
- 1× Waveshare Bus Servo Adapter (A) — set to USB-Servo mode
- 12× FEETECH STS3215 servos (both arms daisy-chained on one bus)
- 12 V DC supply for the servo bus (via the board's barrel jack) - minimum 5A
- 19 V DC supply for Jetson Orin Nano Super (comes with the Dev Kit)

### Physical Hookup / Power

| Adapter | Output | Powers | Connector |
|---|---|---|---|
| Jetson power supply | 19V, 2.37A max | Jetson Orin Nano Super | Jetson's barrel jack |
| Servo bus power supply | 12V, 5A max | Servo bus (both arms) | Waveshare board's barrel jack |


Full connection sequence:

1. Daisy-chain both arms' servo JST connectors into the **one** Waveshare Bus Servo Adapter (A) that's in use - 2 JST ports on the adapter; one per arm.
2. Confirm the board's physical mode switch is set to **USB-Servo**. 
3. Plug the 12V/5A adapter into the Waveshare board's barrel jack (servo bus power).
4. Plug the 19V/2.37A adapter into the Jetson's barrel jack (compute power).
5. Connect the Waveshare board to the Jetson via USB.
6. Power on the Jetson and SSH in (ssh username@hostname.local).

### Software Setup (Jetson)

```bash
# Clone the repo
git clone https://github.com/evanapplebaum/hexarm.git
cd hexarm

# Raw SDK diagnostics only need pyserial — use the hexarm .venv
# Note that these 'low-level' scripts were created to modify servo registers or isolate issues while debugging hardware.
# Also note that ALL STS3215 SERVOES SHIP WITH ID = 1. Attempts to ping 2 servoes with the same ID at the same time will fail (both servoes will attempt to respond simultaneously --> jumbled data)

source .venv/bin/activate
python software/low-lvl-setup/ping_one.py --id 1     # via the scservo_sdk path
python software/low-lvl-setup/raw_ping.py --id 1     # raw pyserial diagnostic
deactivate

# Anything importing LeRobot (teleop, calibration, recording) uses the
# separate lerobot-env venv (Python 3.12+, CUDA-linked torch build)
# — see requirements.txt for exact pinned versions and the Jetson-specific
# install steps (custom torch wheel + a small local LeRobot patch)
source /data/lerobot-env/bin/activate

# Run leader-follower teleoperation:
python software/control/teleop.py
```

> **Note:** LeRobot is not installable on Intel Mac (no x86_64 torch build). For Mac-side
> diagnostics, a lightweight `pyserial`-only venv drives the same `low-lvl-setup` scripts
> over the board's USB port (`/dev/cu.usbmodem*`). See [docs/context.md](docs/context.md)
> for the full per-platform setup and the servo bus bring-up procedure.

---

## Setup Status

| Task | Status |
|---|---|
| Jetson Orin Nano Super flashed (JetPack 7.2) + SSH | ✅ Done |
| Servo bus over USB (`/dev/ttyACM0`, CDC-ACM) | ✅ Done |
| Servo communication verified (raw pyserial + scservo_sdk) | ✅ Done |
| LeRobot installed on Jetson (`pip install -e ".[feetech]"`) | ✅ Done |
| Servo IDs assigned — follower 1–6, leader 7–12, single bus | ✅ Done |
| All 12 servos responding on one bus | ✅ Done |
| Per-joint calibration (both arms) | ✅ Done — clean re-calibration complete (2026-07-27); follower re-calibrated again (2026-08-03) after a broken joint was reprinted and reassembled |
| Leader-follower teleoperation (`teleop.py`) | ✅ Done (2026-06-03) |
| Encoder wrap-around fix — code rewrite | ✅ Done (2026-06-02) |
| Angle limits flashed to servo EPROM | ✅ Done (2026-07-27) |
| Cameras (wrist + overhead, 2× Arducam OV9782 global shutter) | ✅ Done — overhead mounted & locked (2026-07-31), wrist mount reprinted, installed, and placement confirmed (2026-08-05) |
| Dataset recording | ✅ Done — `hexarm/pick_and_place_v2` (2026-08-10, 50 episodes, verified + visually reviewed); superseded by `hexarm/pick_and_place_v3` (2026-08-20, 50 episodes re-recorded with wider claw opening + higher drop-off arc, see postmortem #10) |
| Policy training | ✅ Done — v2: 25,000-step ACT run (2026-08-14), best of 5 via direct eval, L1 loss 0.1742→0.0942, monotonic, no overfitting. v3: 30,000-step ACT run on the re-recorded dataset (completed 2026-08-21, ~12h07m), best checkpoint confirmed via the same direct-eval method — see `docs/context.md` session 15 log. |
| Run trained policy on hardware | ✅ Done (2026-08-21) — v3's checkpoint run on the physical follower arm via `software/control/run_policy.py` (dead-man's-switch gated, mirrors `go_neutral.py --diagnostic`); postmortem #10's margin issues confirmed fixed. |

---

## Roadmap

### M1 — CAD Complete
- [x] CAD — individual part design
- [x] CAD — full assembly
- [x] Docs — hardware assembly guide

### M2 — Platform & Architecture Decisions
- [x] ADR — compute platform selection
- [x] ADR — single-bus servo topology

### M3 — Firmware & Low-Level Comms
- [x] Servo communication over UART/USB (register read/write)
- [x] Per-servo configuration tool (ID, baud, return delay)
- [x] Joint-limit calibration tool
- [x] Docs — servo protocol reference

### M4 — Physical Build & Integration
- [x] Compute — Jetson Orin Nano Super provisioned and networked
- [x] Software — LeRobot installed and verified
- [x] Build — print and source all parts
- [x] Build — assemble both arms
- [x] Integration — servo IDs assigned, both arms on one bus

### M5 — Teleoperation & Imitation Learning
- [x] Software — leader-follower control loop (LeRobot)
- [x] Data — record demonstration dataset (2026-08-10, 50 episodes)
- [x] Training — train ACT or diffusion policy
- [x] Deploy — run policy on hardware (v3, 2026-08-21 — postmortem #10 margins confirmed fixed)
- [x] Demo — hardware photos in README (2026-08-21; video skipped by choice — recordings ran too long)

---

## License

MIT License — see [LICENSE](LICENSE)
