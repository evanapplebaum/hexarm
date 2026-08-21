# Hexarm

A custom anthropomorphic 6-DOF leader-follower robotic arm system roughly based on the open-source [SO-100](https://github.com/TheRobotStudio/SO-ARM100) design. Built for hands-on experience in mechanical design, embedded systems, and robot teleoperation — with imitation learning via the [LeRobot](https://github.com/huggingface/lerobot) framework.

> **Status:** 🔧 In active development. Both arms are built, calibrated, and teleoperating end-to-end. A first ACT policy (25,000 steps) ran successfully on the physical follower arm, but with tight real-world margins — the claw sometimes grazed the block on pick, and the drop-off motion passed close over the bowl's lip (see [postmortem #10](docs/debugging/postmortems.md#10-first-hardware-policy-run--claw-grazing-the-block-near-clipping-the-bowl-lip)). A new 50-episode dataset was recorded with wider claw opening and a higher drop-off arc, and a second policy (30,000 steps) has been trained on it; running it on hardware to confirm the fix is next. Full session-by-session history lives in [docs/context.md](docs/context.md).

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
| CAD Tool | [Onshape](https://cad.onshape.com/documents/0670dbd7fb06bb7c9bf9782d/w/e043c38067500e43503b5676/e/e17080d119308b27c44a0ee6) (public) |
| Reach | TBD |
| Payload | TBD |

---

## Demo

| Leader | Follower |
|---|---|
| ![Leader arm CAD assembly](cad/renders/leader_arm.png) | ![Follower arm CAD assembly](cad/renders/follower_arm.png) |

*CAD renders (Onshape, 2026-08-09) of the finished leader and follower arm assemblies. Real hardware photos and teleop video coming soon.*

---

## Repository Structure

```
hexarm/
├── cad/            # Mechanical design files and exports (Onshape)
├── software/       # Control, calibration, and low-level setup scripts
├── electronics/    # Schematics and bill of materials
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

**Still needed** (blocked on physical build details only Evan has — see Roadmap M2):

- Electronics — wiring schematic, bill of materials, servo power budget

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
5. Connect the Waveshare board to the Jetson via USB.
6. Power on the Jetson and SSH in (ssh username@hostname.local).

### Software Setup (Jetson)

```bash
# Clone the repo
git clone https://github.com/evanapplebaum/hexarm.git
cd hexarm

# Raw SDK diagnostics only need pyserial — use the hexarm .venv
source .venv/bin/activate
python software/low-lvl-setup/ping_one.py --id 1     # via the scservo_sdk path
python software/low-lvl-setup/raw_ping.py --id 1     # raw pyserial diagnostic
deactivate

# Anything importing LeRobot (teleop, calibration, recording) uses the
# separate lerobot-env venv (Python 3.12+, CUDA-linked torch build)
source /data/lerobot-env/bin/activate

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
| Cameras (wrist + overhead, 2× Arducam OV9782 global shutter) | ✅ Done — overhead mounted & locked (2026-07-31), wrist mount reprinted, installed, and placement confirmed (2026-08-05) |
| Dataset recording | ✅ Done — `hexarm/pick_and_place_v2` (2026-08-10, 50 episodes, verified + visually reviewed); superseded by `hexarm/pick_and_place_v3` (2026-08-20, 50 episodes re-recorded with wider claw opening + higher drop-off arc, see postmortem #10) |
| Policy training | ✅ Done — v2: 25,000-step ACT run (2026-08-14), best of 5 via direct eval, L1 loss 0.1742→0.0942, monotonic, no overfitting. v3: 30,000-step ACT run on the re-recorded dataset (completed 2026-08-21, ~12h07m), best checkpoint confirmed via the same direct-eval method — see `docs/context.md` session 15 log. |
| Run trained policy on hardware | 🔶 In progress — v2's checkpoint **was** run on the physical follower arm via `software/control/run_policy.py` (dead-man's-switch gated, mirrors `go_neutral.py --diagnostic`) and completed the task, but with tight margins flagged in postmortem #10. v3 was trained to address it; running v3 on hardware to confirm is next. |

---

## Roadmap

### M1 — CAD Complete
- [x] CAD — individual part design
- [x] CAD — full assembly
- [x] Docs — hardware assembly guide

### M2 — Electronics & BOM
- [ ] Electronics — servo power budget
- [ ] Electronics — wiring schematic
- [ ] Electronics — bill of materials
- [x] ADR — compute platform selection
- [x] ADR — single-bus servo topology

### M3 — Firmware & Low-Level Comms
- [x] Servo communication over UART/USB (register read/write)
- [x] Per-servo configuration tool (ID, baud, return delay)
- [x] Joint-limit calibration tool
- [x] Docs — servo protocol reference

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
- [x] Data — record demonstration dataset (2026-08-10, 50 episodes)
- [x] Training — train ACT or diffusion policy
- [ ] Deploy — run policy on hardware (v2 run and worked, but see postmortem #10; v3 retrained to fix, not yet re-verified)
- [ ] Demo — record demo video / GIF

---

## License

MIT License — see [LICENSE](LICENSE)
