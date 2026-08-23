# hexarm — Project Context

> **Purpose:** Full handoff document for AI sessions (Claude Cowork, Claude.ai, etc.).
> A fresh session reading this file should be able to pick up immediately with zero catch-up questions.
> Update this file at the end of every significant work session.

---

## Summary

hexarm is a custom 6-DOF leader-follower robotic arm (based on SO-100/SO-101) built for hands-on robotics learning, with imitation learning via Hugging Face LeRobot. As of 2026-08-21, the project is **functionally complete**: both arms are built, calibrated, and teleoperating end-to-end, and an ACT policy trained on a re-recorded 50-episode pick-and-place dataset (v3) runs autonomously on the physical follower arm with the margin issues from an earlier run (postmortem #10) confirmed fixed. Remaining work is portfolio polish only — see [WRAPUP.md](../WRAPUP.md) (gitignored, not in the published repo).

The bulk of this document is a chronological engineering journal — most of the narrative detail and incident history lives in [Concepts Covered (Learning Log)](#concepts-covered-learning-log), read top-to-bottom in date order. The most recent entry, [v3 run on hardware — postmortem #10 confirmed fixed, project functionally complete (2026-08-21)](#v3-run-on-hardware--postmortem-10-confirmed-fixed-project-functionally-complete-2026-08-21), is the current state of the project.

### Contents

- [AI Collaboration Style](#ai-collaboration-style)
- [Learning Approach (methodology)](#learning-approach-methodology--agreed-2026-06-01)
- [Project Overview](#project-overview)
- [Hardware](#hardware)
- [Repository Structure](#repository-structure)
- [Software Stack](#software-stack)
- [STS3215 Protocol Reference](#sts3215-protocol-reference)
- [Servo Communication — RESOLVED](#servo-communication--resolved-)
- [Setup Status](#setup-status)
- [Key Technical Notes](#key-technical-notes)
- [Concepts Covered (Learning Log)](#concepts-covered-learning-log) — the session-by-session history, chronological from here to the end of the doc

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
- **CAD:** Full assembly (both arms) finalized in Onshape (2026-08-09) — [public document](https://cad.onshape.com/documents/0670dbd7fb06bb7c9bf9782d/w/e043c38067500e43503b5676/e/e17080d119308b27c44a0ee6). Leader and follower are modeled as two separate arm assemblies within the doc, not a single mirrored/derived assembly. Two build lessons surfaced during assembly and were resolved — see `docs/debugging/postmortems.md` #6 (base stability) and #7 (servo-mount joint strength). STEP exports of both arms' custom parts added to `cad/exports/`, renders added to `cad/renders/` (both 2026-08-09) — see Repository Structure below for what's in/out.

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

### Servo Driver Board — Waveshare Bus Servo Adapter (A)
- **Current setup: ONE board carries both arms.** All 12 servos are daisy-chained on a single bus → `/dev/ttyACM0`. Follower IDs 1–6, leader IDs 7–12. A second board is on hand for a possible future two-bus split, but it is NOT in use — teleop runs single-bus (confirmed 2026-06-03).
- Sold under "UeeKKoo" brand on Amazon but arrived in Waveshare boxes;
  Amazon listing links to the official Waveshare wiki → treat as Waveshare Bus Servo Adapter (A)
- **Waveshare wiki:** https://www.waveshare.com/wiki/Bus_Servo_Adapter_(A)
- Handles half-duplex bus direction switching in hardware (host sees full-duplex serial)
- **Two host interfaces:**
  - **USB (CH340/CH343 chip):** current connection to the Jetson — enumerates as `/dev/ttyACM0` via the `cdc_acm` driver. On Mac appears as `/dev/cu.usbmodem*` — use `cu` prefix, NOT `tty`
  - **UART GPIO pins:** used during the retired Pi era (no USB needed)
- **Physical mode switch** on board: USB-Servo for the Jetson (current platform) and Mac testing; UART-Servo was used for the Pi
- **Power:** separate DC barrel jack for servo bus power (12V)
- Compatible with ST/SC series Feetech servos including STS3215
- **Official Python SDK:** scservo_sdk (see software section)

### Compute — Jetson Orin Nano Super
- **Status:** ✅ SSHable as of 2026-05-26
- **OS:** JetPack 7.2 (L4T r39.2, Ubuntu 24.04, CUDA 13.2) — reflashed 2026-08-04 from JetPack 6.2. Reason: LeRobot requires Python ≥3.12, and no cp312 CUDA torch wheel exists for JetPack 6.2 (cp310 only); cp312 CUDA torch only exists for JetPack 7.2. Reflashed via Jetson ISO (USB installer, no x86 host needed), microSD as target, NVMe (`/data`) deliberately left untouched and preserved intact. See "Jetson JP7.2 reflash" write-up below for full details.
- **Hostname:** `eka-orin`
- **Username:** `evan0h`
- **Network:** WiFi (`wlP1p1s0`) and Ethernet (`enP8p1s0` — PCIe NIC, not `eth0`) both available; Ethernet preferred for teleop/dataset transfer.
- **SSH:** `ssh evan0h@eka-orin.local` — VS Code Remote SSH confirmed working
- **Display note:** Carrier board has DisplayPort only (no HDMI). Using DP -> HDMI on rare occasions a monitor is needed to be connected directly to the Jetson
- **Post-setup plan:** Disable GUI after oem-config to reclaim ~800MB RAM; operate permanently headless
- **Connection to driver boards:** USB (USB-Servo mode on Waveshare board) — confirmed working 2026-05-26, reconfirmed post-reflash 2026-08-04
- **Serial port:** `/dev/ttyACM0` — board enumerates via the in-kernel `cdc_acm` driver (not `ch341`/`ttyUSB0` as one might expect from the CH343 chip on the board). The CH343 presents as a CDC ACM device on Jetson/Linux, so **no out-of-tree driver is needed** — this was re-verified after the JP7.2 reflash (2026-08-04): `broadcast_ping()` via LeRobot's `FeetechMotorsBus` got responses from all 12 servo IDs on `/dev/ttyACM0` with zero driver work. Stable alternative path: `/dev/serial/by-id/usb-1a86_USB_Single_Serial_<serial>-if00`.
- **dialout group:** `sudo usermod -aG dialout evan0h` — done. Note: VS Code Remote SSH caches group memberships and may not reflect changes after reconnect. Use `newgrp dialout` as workaround, or `pkill -f vscode-server` then reconnect for a clean session.
- **Python env (LeRobot):** `/data/lerobot-env` — venv on system Python 3.12 (not conda; the Jetson CUDA wheels link against system CUDA/glibc/libstdc++, and conda's bundled copies of those cause `GLIBCXX`/CUDA resolution failures). Activate: `source /data/lerobot-env/bin/activate`. Replaces the old `/data/miniconda3/envs/lerobot` conda env (left on disk, unused).
- **Python venv (raw serial diagnostics):** `/data/hexarm/.venv` — separate from the LeRobot env, only needs `pyserial`. Rule of thumb: script imports `lerobot` (`teleop.py`, `software/calibration/*`) → `/data/lerobot-env`; script only talks raw serial (`software/low-lvl-setup/*`) → `hexarm/.venv`.

### Compute — Raspberry Pi Zero 2W (RETIRED 2026-05-26 — kept as a pointer)
Replaced by the Jetson Orin Nano Super. The full Pi UART bring-up chronology — PL011 vs mini-UART, `disable-bt`, the serial-console/`getty` trap, and the straight-through Waveshare wiring — lives in [`docs/debugging/servo-comms-debug-log.md`](debugging/servo-comms-debug-log.md). **One lesson carries forward to the Jetson:** a kernel serial console or `serial-getty` sitting on the servo UART silently eats RX bytes and breaks comms — always confirm it's off on whatever port the servos use (tracked under Setup Status → "Jetson — serial console verified off").

### Vision (cameras in hand, both mounted — 2026-08-05)
- 2× Arducam OV9782 1MP Global Shutter USB Camera Board (B0385), UVC, M12 manual-focus lens, 1280×800 MJPG. Ordered 2026-07-14, arrived ~07-22. Chosen partly for reuse as the front stereo pair on a future quadruped project.
- **Lens FOV — verified 2026-07-31:** Arducam's own B0385 manual specs the lens as **70°(H)**, confirmed to be the full/total horizontal angle (standard lens-spec convention), not a half-angle. The manufacturer does NOT publish vertical or diagonal FOV. The "~47° V" figure used in earlier planning below is a derived estimate from the 1280×800 sensor aspect ratio, not a manufacturer spec — treat it as approximate where precision matters (e.g. confirming full-reach clearance).
- **Both cameras connected and enumerated.** Each UVC camera exposes 2 `/dev/videoN` nodes (capture + metadata) — overhead is `/dev/video0`, wrist is `/dev/video2`; `/dev/video1`/`/dev/video3` are the metadata-only nodes and aren't used. Confirmed via OpenCV (`cv2.VideoCapture(idx, cv2.CAP_V4L2)`) reading MJPG @ 1280×800 successfully. `v4l2-ctl` is not installed (`sudo apt install v4l-utils`, blocked by no passwordless sudo in the current session) — not needed so far since OpenCV covers format confirmation.
- **Overhead camera — mounted and confirmed good (2026-07-31).** Positioned using a live MJPEG preview tool (see `software/vision/camera_preview.py` in Repository Structure below) against the target geometry: ~50° below horizontal, ~0.38 m above table, ~0.32 m in front of workspace center, aimed at follower workspace center, slant distance ~0.5 m. Framing locked — per the collection/deployment pose-identity constraint, do not move it again without re-deriving downstream calibration.
- **Wrist camera — reprinted mount installed (2026-08-01), placement confirmed good (2026-08-05).** The redesigned mount (built around the real 70°(H) FOV, positioned close to the jaws per the close-focus placement plan, aimed down the grasp axis — see prior entry for why the first print failed) is printed, fitted, and its aim/placement verified via the live preview tool (`software/vision/camera_preview.py`) at the actual close working distance. Both cameras are now locked — no further mount changes without re-deriving downstream calibration.
- Both cameras are wired into `software/control/record_dataset.py`'s `OpenCVCamera` config for dataset recording.
- **Camera placement research (2026-07-27):** researched where the overhead camera should go using LeRobot's own docs/blog plus general imitation-learning camera-setup practice (ALOHA-style dual-arm rigs) before mounting. Key takeaways: (1) **the leader arm must not appear in frame** — an explicit LeRobot dataset-quality rule ("Leader arm should not appear" — HF's "what makes a good dataset" post), and a real constraint here specifically because both arms share one workspace; (2) **mount rigid and fixed** — no shake, never reposition between sessions, since these policies learn from raw pixel observations tied to a specific camera pose; (3) **cover the full reachable/placement workspace**, angled rather than a strict nadir shot so the gripper isn't constantly self-occluded; (4) **pair wrist + overhead intentionally, not redundantly** — wrist gives a close-up, occlusion-robust grasp view, overhead gives global spatial context; this is LeRobot's own standard example config. Sources: [LeRobot Imitation Learning docs](https://huggingface.co/docs/lerobot/il_robots), [LeRobot Datasets blog post](https://huggingface.co/blog/lerobot-datasets), general ALOHA/dual-arm teleop camera-design background.

---

## Repository Structure

```
hexarm/
├── docs/
│   ├── context.md                      ← this file (AI handoff doc)
│   ├── teleop-control-loop.md          ← teleop.py control-loop design reference
│   ├── servo-protocol-reference.md     ← STS3215 packet protocol + hardware-verified gotchas
│   ├── hardware-assembly-guide.md      ← fastener reference, build order, workspace setup
│   ├── adr/                            ← architecture decision records
│   │   ├── 0001-compute-platform-selection.md
│   │   └── 0002-single-bus-servo-topology.md
│   ├── debugging/
│   │   ├── postmortems.md              ← consolidated incident log (symptom → root cause → fix → lesson)
│   │   └── servo-comms-debug-log.md    ← full chronology of UART/SDK debugging (Phases 1–5); read before touching servo comms
│   └── component_specs/                ← datasheets and manuals
│       ├── ST3215 Communication Manual.pdf
│       ├── ST3215-general-manual.pdf
│       ├── Servo-bus-schematic.pdf
│       ├── sts3215_memory_table.xlsx
│       └── B0385_OV9782_Global_Shutter_UVC_Camera_Datasheet_19190316e78.pdf
├── media/
│   └── pictures/                       ← real hardware photos (JPG), wired into README's Demo section
├── cad/                                ← live CAD doc linked in Hardware → Arm Structure above (Onshape, cloud-hosted — no native files stored here)
│   ├── exports/                        ← STEP exports, added 2026-08-09
│   │   ├── leader/                     ← leader arm's custom-designed parts only (base, crank, link1-4, wheel)
│   │   ├── follower/                   ← follower arm's custom-designed parts only (base, claw, link1-5, pinion, racks, part18, Arducam mount)
│   │   ├── overhead camera mount/      ← overhead tower/mount custom parts
│   │   └── sts3215_servo_reference.step ← ONE copy of the vendor STS3215 servo model (same part instanced 6×/arm in Onshape; only one kept here, not 12 near-duplicates)
│   └── renders/                        ← leader_arm.png, follower_arm.png — isometric assembly screenshots, used in README Demo section (added 2026-08-09)
├── electronics/                        ← empty (schematics/ subfolder has no files); a wiring schematic + BOM were considered and dropped (2026-08-21, Evan's call — not worth it for the portfolio), not left as planned work
├── scripts/
│   └── setup-github.sh
├── outputs/train/                      ← local lerobot-train run outputs (checkpoints), gitignored
│   ├── act_benchmark_local/            ← short local benchmark run, used to size Jetson vs. cloud training time
│   └── act_pick_and_place_v2/          ← the real 25,000-step run — checkpoints/{005000,010000,015000,020000,025000,last}
├── software/
│   ├── control/                        ← application-level scripts (run from repo root, lerobot-env)
│   │   ├── teleop.py                   ← leader-follower teleoperation; single bus, 12 motors; ✅ working (2026-06-03)
│   │   ├── record_dataset.py           ← records teleoperated demos into a LeRobotDataset (both cameras + both arms); custom recorder (not `lerobot-record`) since hexarm shares one bus/port across arms; ✅ added (2026-08-03), hardened 2026-08-10: both arms return to neutral after the final episode (not just between episodes); `image_writer_threads = 4 × len(cameras)` (LeRobot's own per-camera recommendation — too few threads was silently queuing a multi-minute backlog with no console feedback); `--resume` now passes an explicit `root=HF_LEROBOT_HOME/repo_id` (required, unlike `create()`); recording resolution (`record_sizes`) is now read from the target dataset's own feature schema instead of a fixed constant — see postmortems.md #8 for the data-loss incident this fixes; full-width on-screen banner when recording starts (visible from across the room)
│   │   ├── run_policy.py               ← runs a trained checkpoint on the physical follower arm (no leader involved); dead-man's-switch gated (hold SPACE to let predicted actions reach the servos, release freezes instantly), same convention as go_neutral.py --diagnostic; ✅ written and verified (imports, checkpoint load, feature shapes) 2026-08-14, not yet run against real hardware
│   │   └── torque_off.py               ← interactive torque disable
│   ├── vision/                         ← camera positioning/dev tools (not part of the LeRobot camera config)
│   │   └── camera_preview.py           ← headless MJPEG-over-HTTP live preview (stdlib http.server + cv2); serves one stream per --indices arg at http://<jetson-ip>:8080/videoN; used to aim/lock camera mounts before recording, then torn down
│   ├── calibration/                    ← LeRobot-based calibration and arm control scripts
│   │   ├── calibrate_lerobot.py        ← per-joint LeRobot calibration (--arm leader|follower); ✅ implements the fixed wrap-around flow (see Encoder Wrap-Around); single-Enter-per-joint flow (2026-08-01)
│   │   ├── go_neutral.py               ← move BOTH arms to the shared neutral pose (config/neutral.json); no --arm flag (2026-08-01); importable by other scripts; `at_neutral()` pre-check + `--diagnostic` hold-to-move mode (2026-08-03)
│   │   ├── record_neutral.py           ← capture the follower's pose as the shared config/neutral.json used by both arms; no --arm flag (2026-08-01)
│   │   ├── set_startup_sequence.py     ← both arms to neutral (skipped if already there) → torque off on leader only → Enter → 5s countdown → 10s recording @ 50Hz → config/startup_sequence.json; ✅ new (2026-08-01), rewritten to start from neutral (2026-08-03)
│   │   ├── run_startup_sequence.py     ← neutral → play recorded sequence on both arms → neutral; importable (used by teleop.py) or standalone; ✅ new (2026-08-01)
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
│   │   └── read_register.py            ← read arbitrary EPROM/SRAM register (raw pyserial)
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
│   └── config/
│       ├── limits.json                 ← joint travel limits (populated by calibrate.py, leader arm)
│       ├── home.json                   ← raw encoder home positions for move_one.py (IDs 1–6)
│       ├── motion_profile.json         ← shared {velocity, acceleration} defaults for go_neutral.py/run_policy.py — one source of truth so tuning one file updates both
│       ├── calibration_follower.json   ← LeRobot calibration — follower arm (IDs 1–6); ✅ working
│       ├── calibration_leader.json     ← LeRobot calibration — leader arm (IDs 7–12); ✅ working
│       ├── neutral.json                ← single shared neutral pose, normalized 0–100, applied identically to BOTH arms (2026-08-01; replaces neutral_follower.json/neutral_leader.json — see Setup Status for why)
│       ├── neutral_follower.json, neutral_leader.json ← stale, unused — pre-unification per-arm captures, kept on disk but superseded by neutral.json
│       └── startup_sequence.json       ← recorded leader-arm motion (50 Hz, ~10s of samples), played on both arms at teleop startup; ✅ new (2026-08-01), extended from 5s (2026-08-03)
├── .venv/                              ← Python venv (recreate per platform — NOT cross-platform)
└── .gitignore
```

There is no `config.py` in the current tree — an earlier Pi-era config module (Pi 5 UART port assignments, direct-wiring resistor notes) was fully superseded by the `software/config/*.json` files above plus per-script `--port` CLI args, and was removed. `software/kinematics/`, `software/utils/`, and a top-level `simulation/urdf/` never got built — the FK/IK/URDF work they'd have held (formerly Roadmap M4) was dropped by Evan's decision (2026-08-21), not just deferred, so there's no plan to add them.

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

**IMPORTANT — `num_retry` defaults to 0:** `bus.read()`/`bus.write()` do not retry a dropped status packet by default — a single missed byte on the wire raises `ConnectionError` and crashes the whole script (hit 2026-08-10 mid-`safe_enable_torque()`). LeRobot's own internal cleanup code (`disable_torque()`) uses `num_retry=5` for exactly this reason. Pass `num_retry=3` (or similar) on any `bus.read`/`bus.write` call in a script meant to run unattended — applied across `go_neutral.py`, `teleop.py`, `calibrate_lerobot.py`, `monitor_joints.py`, and `run_startup_sequence.py` (2026-08-10).

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

End-to-end SDK path has worked since 2026-05-25 (on the Pi) and now runs on the Jetson over `/dev/ttyACM0`. The bring-up took three stacked root causes to untangle; the full chronology (Phases 1–5) lives in [`docs/debugging/servo-comms-debug-log.md`](debugging/servo-comms-debug-log.md). Condensed:

1. **No response — wrong wiring.** The Waveshare board uses **straight-through** wiring (TX→TX, RX→RX), not crossed; it labels pins from the host's perspective.
2. **Intermittent "framing errors" — misdiagnosis.** A custom resync parser added to `port_handler.readPort()` was based on a self-consistent but wrong theory; it was reverted. Kept in the debug log as a cautionary tale about falsification testing.
3. **The real cause — serial console + SDK byte-stealing.** A kernel serial console / `serial-getty` on the servo UART silently ate RX bytes, and the resync layer's `length+1` read stole a byte from `ping()`'s second transaction (`COMM_RX_CORRUPT`).

**Fixes that still apply on any platform (Jetson included):**
- Ensure no serial console / `getty` owns the servo port (`/proc/cmdline`, `systemctl is-enabled serial-getty@<port>`).
- `port_handler.setupPort()` opens pyserial with `timeout=0.1` (not `timeout=0`, which sets `O_NONBLOCK` and defeats VMIN).
- `_serial_utils.set_vmin(ser, vmin=1)` so `ser.read(1)` inside the SDK actually blocks.
- `readPort()` is stock upstream; retry/recovery lives in the `_serial_utils` wrappers (`ping_with_retry`, etc.) — the correct scope.

**STS3215 reports model number 777** from `ping()` — a quick health check. See debug log Phase 5 for the full root-cause analysis.

---

## Setup Status

| Task | Status |
|---|---|
| **CAD / Mechanical** | |
| CAD — individual part design | ✅ Done |
| CAD — full assembly (both arms, leader + follower) | ✅ Done (2026-08-09) — [Onshape doc](https://cad.onshape.com/documents/0670dbd7fb06bb7c9bf9782d/w/e043c38067500e43503b5676/e/e17080d119308b27c44a0ee6). STEP exports of custom parts in `cad/exports/` (2026-08-09). Renders pending. |
| Docs — hardware assembly guide | ⏳ Todo |
| **Compute** | |
| Jetson Orin Nano Super — JetPack 6.2 flash | ✅ Done (2026-05-26), superseded — see JP7.2 reflash below |
| Jetson Orin Nano Super — JetPack 7.2 reflash (R39.2, Ubuntu 24.04, CUDA 13.2) | ✅ Done (2026-08-04) — via Jetson ISO, microSD target, NVMe/`/data` preserved untouched. Reason: LeRobot needs Python ≥3.12; only JP7.2 has cp312 CUDA torch wheels for Jetson. Full write-up below. |
| Jetson — oem-config first-boot wizard | ✅ Done |
| Jetson — SSH access configured | ✅ Done (`ssh evan0h@eka-orin.local`) |
| Jetson — GUI disabled (headless mode) | ⏳ Todo |
| Jetson — UART device nodes confirmed for servo chains | ✅ Done (/dev/ttyACM0 via cdc_acm; reconfirmed post-JP7.2-reflash 2026-08-04, no driver work needed) |
| Jetson — serial console verified off UART used for servos | ⏳ Todo |
| NVMe SSD (512GB) mounted at /data | ✅ Done (2026-05-28, ext4, fstab entry added); survived JP7.2 reflash intact (2026-08-04) |
| **Software** | |
| Mac venv created (Python 3.12) | ✅ Done |
| pyserial installed in Mac venv | ✅ Done |
| scservo_sdk copied into software/ | ✅ Done |
| ping_one.py, raw_ping.py, baud_scan.py, setup_servo.py created | ✅ Done |
| _serial_utils.py (shared SDK helpers + retry wrappers) | ✅ Done (2026-05-25) |
| sdk_diag.py (read-pattern diagnostic) | ✅ Done (2026-05-25) |
| port_handler.py reverted to upstream readPort | ✅ Done (2026-05-25) |
| LeRobot conda env (Python 3.12) on Jetson | ⚠️ Superseded (2026-08-04) — replaced by `/data/lerobot-env` venv (system Python 3.12) after the JP7.2 reflash; old conda env left on disk unused |
| PyTorch installed (cu126, Jetson) | ⚠️ Superseded (2026-08-04) — replaced by torch 2.12.0 (cp312, CUDA 13.2) from Shattered217/Jetson-Orin-Wheels; `torch.cuda.is_available()` verified `True` |
| LeRobot pip install -e ".[feetech]" | ✅ Done (2026-05-31); reinstalled into `/data/lerobot-env` post-reflash (2026-08-04), lerobot 0.6.1 |
| LeRobot installed in Mac venv | ❌ Not possible (Intel Mac) |
| **Hardware / Servos** | |
| Mac → board → servo communication working | ⚠️ Not yet tested (USB-Servo mode) |
| Jetson → board → servo communication working | ✅ Done (2026-05-26, USB, /dev/ttyACM0) |
| Driver board UART wiring to Jetson | ✅ Done (USB-Servo mode, ttyACM0 via cdc_acm driver) |
| Servo IDs assigned — follower 1–6, leader 7–12, single bus | ✅ Done — both arms on /dev/ttyACM0; see LeRobot section for ID convention |
| Bus communication test (all 12 servos) | ✅ Done (2026-06-03, both arms responding, teleop confirmed) |
| SDK path (ping_one, calibrate) working on Jetson | ✅ Done (2026-05-26, sdk_diag 5/5, ping_one confirmed) |
| Angle limits flashed to servo EPROM | ✅ Done (2026-07-27) |
| Cameras — 2× Arducam OV9782 (B0385) global shutter USB, wrist + overhead | ✅ In hand, both connected (`/dev/video0` overhead, `/dev/video2` wrist). See Vision section above. |
| Local git object DB — corrupted loose objects found | ✅ Fixed (2026-08-03) — found 2026-07-31, 6 empty/corrupt loose objects (`master`'s tip commit among them). Packed history and `origin` were unaffected, so the fix was: delete the corrupt loose objects and the two local refs pointing at the corrupt commit, then `git fetch origin` to redownload it (refs already claiming to "have" a commit block fetch from resending it, so they had to go first). `git fsck --full` clean after. The 2026-08-01 session's uncommitted script changes were then committed (`60ce4ac`) and pushed. |
| **Application** | |
| config.py rewrite (Jetson ports, remove Pi 5 / Pi Zero 2W refs) | ✅ Obsolete — `config.py` was removed entirely, superseded by `software/config/*.json` + per-script `--port` CLI args (no Pi-era references remain to clean up) |
| move_one.py — ping, ReadPos, torque enable, home move | ✅ Done (2026-05-28) |
| torque_off.py — interactive torque disable | ✅ Done (2026-05-28) |
| flash_angle_limits.py — write limits.json to servo EPROM | ✅ Done (2026-05-28) |
| keyboard_follower.py — LeRobot keyboard control of follower arm | ✅ Done (2026-05-31) |
| calibrate_lerobot.py — per-joint LeRobot calibration, both arms | ✅ Done — rewritten around configure_motors()/set_half_turn_homings()/record_ranges_of_motion() (2026-06-02). Clean re-calibration with current arms completed 2026-07-27. Redundant mid-flow Enter prompt removed 2026-08-01 — now one Enter to home+start the sweep, one Enter to record and advance (see Neutral Pose Unification section). |
| LeRobot calibration — encoder wrap-around fix | ✅ Done (solved 2026-06-01, code rewritten 2026-06-02) |
| go_neutral.py — move both arms to shared neutral; importable | ✅ Done — rewritten 2026-08-01: `--arm` flag removed, always drives both arms to the one shared `neutral.json` (previously per-arm `--arm follower\|leader\|both`). Extended 2026-08-03: `at_neutral()` helper (checks whether all joints are already within tolerance without commanding motion — lets callers skip the move entirely), `--diagnostic` dead-man's-switch mode (hold SPACE to move, release freezes in place via `Goal_Position = Present_Position`, 'q' aborts — no key-up event over a raw SSH terminal, so "held" is inferred from OS keyboard auto-repeat within a 0.2s window), and the arrival-tolerance comparison fixed from strict `<` to `<=` (a joint sitting exactly on the tolerance boundary never registered as arrived, causing an apparent hang to the full timeout — see Concepts Covered). `POSITION_TOLERANCE` widened 0.5 → 1.0 normalized units. |
| record_neutral.py — capture shared neutral pose | ✅ Done — rewritten 2026-08-01: `--arm` flag removed, always hand-poses the follower only and writes the single `neutral.json` used by both arms (previously separate `neutral_follower.json`/`neutral_leader.json` captures — those two files are now stale/unused on disk) |
| set_startup_sequence.py — record leader-arm startup sequence | ✅ Done (2026-08-01, software/calibration/set_startup_sequence.py). Rewritten 2026-08-03: now builds both arms on one bus, drives both to the shared neutral first (via `at_neutral()` + `go_neutral()`, skipping the move if already close), then disables torque on the leader only — the follower stays enabled and holds neutral through recording. Recording window extended 5s → 10s. Output JSON format unchanged (unprefixed joint names), so `run_startup_sequence.py` needed no changes. |
| run_startup_sequence.py — neutral → sequence → neutral, both arms | ✅ Done (2026-08-01, software/calibration/run_startup_sequence.py); used by teleop.py startup |
| teleop.py — leader-follower teleoperation | ✅ Done (2026-06-03, software/control/teleop.py). Startup rewritten 2026-08-01 to go through run_startup_sequence.py instead of a bare go_neutral() call — see Neutral Pose Unification section below for the bug this fixes. New prerequisite: `config/startup_sequence.json` must exist (run set_startup_sequence.py first) or teleop.py raises FileNotFoundError. |
| First teleoperation test | ✅ Done (2026-06-03, confirmed working perfectly) |
| .gitignore for CSV stress-test artifacts | ✅ Done — `ping_stress_*.csv` and `software/control/*.csv` patterns present |
| camera_preview.py — headless MJPEG live-view tool for camera positioning | ✅ Done (2026-07-31, software/vision/camera_preview.py) |
| Overhead camera mounted at target geometry | ✅ Done (2026-07-31) — confirmed via live preview, framing locked |
| Wrist camera mounted at target geometry | ✅ Done (2026-08-05) — reprinted mount (designed around the real 70°(H) FOV) installed 2026-08-01, placement/aim confirmed via `camera_preview.py` |
| Cameras wired into LeRobot camera config | ✅ Done — both cameras wired in via `OpenCVCamera` in `software/control/record_dataset.py` |
| Dataset recording | ✅ Done (2026-08-10) — 50/50 episodes, `hexarm/pick_and_place_v2` (640×400 @ 30fps, ~28.3k frames), verified consistent across `info.json`/data/video/episode-metadata and visually reviewed via a generated thumbnail-grid QA page. A resolution-mismatch bug during recording cost 2 unrecoverable episodes from the original `hexarm/pick_and_place` dataset (3 valid episodes remain there, retired in favor of `_v2`) — see postmortems.md #8. |
| Policy training | ✅ Done (2026-08-14) — a local `lerobot-train` benchmark hard-froze the Jetson twice before being root-caused (RAM exhaustion, no swap) and fixed via zram (postmortems.md #9). Real 25,000-step run then completed locally overnight in ~6h12m (18:24→00:36) with zero issues — `tmux`-protected against SSH drops, verified via `uptime`/checkpoint timestamps that no reboot occurred. 5 checkpoints saved (5k/10k/15k/20k/25k). |
| Checkpoint evaluation | ✅ Done (2026-08-14) — no training-loss log survived (wandb disabled, tmux scrollback rolled past 6h of history), so wrote a standalone eval script loading each checkpoint and running 50 forward-pass-only batches against the training set. L1 loss: 0.1742 (5k) → 0.1354 (10k) → 0.1124 (15k) → 0.1067 (20k) → **0.0942 (25k)** — clean monotonic improvement, no overfitting; final checkpoint confirmed best of the 5. |
| Run trained policy on hardware | ✅ Done (2026-08-21) — v3 checkpoint run on the physical follower arm via `run_policy.py`, 3 successful pick-and-place completions. Postmortem #10's grazing/near-clipping margins confirmed fixed. Some runs still missed the pick due to camera-coverage blind spots — a known limitation, not a margin issue; no further training planned. See session-16 log entry below. |

---

## Key Technical Notes

### Half-Duplex Direction Switching
STS3215 uses half-duplex UART — TX and RX share one wire on the servo side. The Waveshare board handles direction switching internally. The host sends normal full-duplex serial; the board drives the bus on TX and listens on RX. There is NO echo of TX bytes back to the host's RX buffer (confirmed by comparing with official SDK, which has no echo-consuming code).

### tty vs cu on macOS
On macOS, each USB serial device appears twice: `/dev/tty.*` and `/dev/cu.*`.
- `tty` waits for carrier detect — designed for incoming connections (modems receiving calls)
- `cu` (call-up) initiates connections — correct for outbound serial communication
- Always use `/dev/cu.usbmodem*` for this board on Mac.

### Pi UART Configuration Commands (retired)

The Pi-era UART boot setup (`dtoverlay=disable-bt`, `enable_uart=1`, PL011 vs mini-UART, `cat /proc/cmdline`) is no longer used — the Jetson connects over USB. Commands and explanation are preserved in [`docs/debugging/servo-comms-debug-log.md`](debugging/servo-comms-debug-log.md). The one check that still matters on the Jetson: `cat /proc/cmdline` and `systemctl is-enabled serial-getty@<port>` to confirm nothing else owns the servo port.

### Jetson SSH Quick Reference

```bash
ssh evan0h@eka-orin.local    # mDNS hostname
ssh evan0h@<jetson-ip>       # direct IP (faster, more reliable — IP TBD)

# If SSH fails with "REMOTE HOST IDENTIFICATION HAS CHANGED" (happens after reflash):
ssh-keygen -R eka-orin.local  # removes stale host key from ~/.ssh/known_hosts
# Then retry ssh normally.
```

### scservo_sdk Import Path
The raw-SDK diagnostic scripts in `software/low-lvl-setup/` use:
```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scservo_sdk import PortHandler, sms_sts, COMM_SUCCESS
```
This resolves to `software/scservo_sdk/`. These scripts run standalone (not under the LeRobot conda env), so the local SDK copy is intended here. **Do NOT** use this pattern from scripts that import LeRobot — adding `software/` to `sys.path` shadows the pip-installed `scservo_sdk` (see the teleop import-path gotcha below). Run from hexarm root or from `software/low-lvl-setup/`.

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
- Modular vs. monolithic CAD design — building a part as a union of smaller, independently swappable sub-parts (vs. one single-body design) costs more upfront modeling effort but pays back heavily on iteration speed: a monolithic part requires a full redesign (or full reprint) for a single failed feature, while a modular one lets you reprint/redesign just the sub-part that failed and reuse the rest. Currently being felt directly on the claw redesign (see `docs/debugging/postmortems.md` #5) — still calibrating exactly how much time this saves in practice, not yet a settled rule.
- UVC camera device enumeration on Linux — one physical camera exposes multiple `/dev/videoN` nodes (capture + metadata); only the capture-capable node (check `ID_V4L_CAPABILITIES` via udev, or just try opening it) actually streams frames.
- Lens FOV spec ambiguity — a quoted FOV number is meaningless without knowing which axis (horizontal/vertical/diagonal) and whether it's the full/total angle or a half-angle; manufacturers often publish only one axis. Confirmed Arducam's B0385 "70°(H)" is the full horizontal angle via the manufacturer manual — the "H" already disambiguates the axis, and full-angle is the default convention unless stated otherwise.
- Two UVC cameras of the same make/model can report identical USB serial numbers — cheap OEM UVC bridge chips (this board uses one branded "Vitade AF", VID:PID 0c45:6366) often don't burn a unique serial, so distinguishing two identical cameras by udev/serial alone doesn't work; motion (nudge the camera, watch which video feed moves) is the reliable disambiguator.
- Git loose-object corruption is locally recoverable if the remote has the object — but `git fetch` won't resend a commit your local refs already claim to have, even if the on-disk object is corrupt/missing. The corrupt objects *and* any ref pointing at them have to be removed first, so the negotiation no longer thinks you already have it.
- A servo in position-control mode keeps applying torque toward `Goal_Position` on its own, independent of whatever the host script is doing — a Python polling loop timing out doesn't stop the servo from still pushing. Sustained pressure against an obstruction (not a momentary spike) is what trips overcurrent protection, and it can take most of a generous timeout window to do it.
- FEETECH status/error byte bits are distinct and independently latch-and-report: `OverEle` (bit 3, overcurrent) vs `Overload` (bit 5) are different conditions. The servo's own protection firmware can auto-disable torque on just the affected motor when one trips — independent of what the host's `Torque_Enable` writes say — which is why only one servo can end up detorqued after a stall while the rest of the bus stays enabled.
- Boundary-inclusive vs. exclusive tolerance checks matter operationally, not just in theory: a strict `<` against a threshold a real sensor value can land exactly on (not just get arbitrarily close to) causes a "hang" that's actually just a comparison that can never be satisfied — the joint isn't stuck, the check is unsatisfiable. `<=` (or widening the tolerance) fixes it.
- Terminal-based "hold key to move" (dead-man's switch) control has no true key-up event over a raw SSH terminal — unlike a GUI or direct HID access, there's no way to know a key was *released*, only that bytes stopped arriving. "Held" has to be inferred from the OS's keyboard auto-repeat cadence (treat recent-enough as still-down), which is a real constraint on responsiveness, not just an implementation detail.
- Free-standing multi-DOF arm bases have to resist the *tipping moment* the arm's own weight and motion generate, not just hold static weight — a base sized only for support flexed and let the arm tip over during assembly/testing. Fixed by clamping the base to the table rather than relying on the base's own footprint/mass for stability. See `docs/debugging/postmortems.md` #6.
- PLA screw-in mounting bosses (where a printed link bolts to a servo horn) are a stress concentration distinct from the part's general wall thickness — links that were adequately thick everywhere else still bent specifically at the servo attachment point, requiring local reinforcement there rather than a uniform thickness increase. See `docs/debugging/postmortems.md` #7.
- LeRobotDataset resolution is schema-locked for the life of the dataset — `create()` fixes each camera's recorded shape permanently; there is no in-place "upgrade." A script that assumes one global recording resolution will silently corrupt a `--resume` session on an older dataset created before that assumption existed (see `docs/debugging/postmortems.md` #8) — the safe pattern is to derive recording size from the target dataset's own declared feature shape, not a constant.
- A writer that advances a counter (episode index, in this case) *before* validating the data behind it turns what should be a hard failure into silent corruption — `meta/info.json`'s totals advanced normally while the real parquet/video data behind two of those episodes never existed. Worth checking for this "reserve-then-fill" ordering in any pipeline that separates a count/index update from the data write it's supposed to represent.
- `LeRobotDataset.create()` infers a default `root` from `HF_LEROBOT_HOME`/`repo_id`; `resume()` does not — it raises unless `root` is passed explicitly. Asymmetric defaults between two functions that otherwise feel like a matched pair are an easy thing to miss until the less-common path is actually exercised.
- LeRobot's own guidance: `image_writer_threads` should be sized *per camera* (4 threads/camera), not as one shared pool across all cameras — too few threads doesn't error, it just lets the write queue (unbounded `queue.Queue`) grow silently, so "recording feels laggy/hangs after pressing Enter" can be a threading-starvation symptom with zero exceptions to point at it.
- UVC cameras snap an unsupported requested capture resolution to the nearest supported discrete preset silently (requesting 640×400 on the Arducam OV9782 here returns 640×480 instead — same width, wrong aspect ratio) rather than erroring — always confirm the actual negotiated resolution against a live capture, don't trust the requested value, and downscale in software post-capture if the sensor doesn't natively support the target size.
- Video encode time on this Jetson's ARM cores is dominated by output resolution, not codec choice or GOP/keyframe interval — confirmed by direct benchmark (H.264 was not faster than AV1; GOP size only changed file size, not speed; halving resolution gave a measured ~3.4× speedup). A plausible-sounding hypothesis (codec choice) can still be wrong; benchmark on the actual target hardware before committing to a fix.
- Stream-copy video concatenation (ffmpeg's concat demuxer, used to merge each episode's own encoded video into one per-camera chunk file) can leave a small number of inert padding frames in the container that don't correspond to any real timestamped sample — visible via a raw frame-count decode, invisible to anything (like LeRobot) that addresses frames by timestamp rather than raw position.
- Sizing imitation-learning training by a flat step count (LeRobot's `train.steps` default of 100,000) doesn't account for dataset size — LeRobot's own hardware guide instead recommends sizing by epochs over the dataset (typically 5–10), which for a small ~50-episode dataset works out to a fraction of the flat default (~17.7k–35.4k steps here, not 100k).

---

### Waveshare Bus Servo Adapter (A) — Critical Wiring Note

**UART-Servo mode wiring is straight-through, NOT crossed:**
- Pi TX → Board TX
- Pi RX → Board RX
- GND → GND

This is the opposite of standard UART convention. The board labels its UART pins from the host's perspective. See `docs/debugging/servo-comms-debug-log.md`.

---

## Encoder Wrap-Around — RESOLVED ✅

**Discovered 2026-05-31. Root cause understood 2026-06-01; `calibrate_lerobot.py` rewritten around the fixed flow 2026-06-01/02 (commits `e63aaaa`…`493fbb7`).** Some joints have their physical travel range crossing the STS3215 encoder's 0↔4095 boundary. The absolute magnetic encoder is 12-bit (0–4095 per revolution). If the servo is mounted such that the physical joint stops straddle this boundary, raw encoder readings jump from 4095→0 mid-motion.

### The key insight (2026-06-01)

The STS3215 reports `Present_Position = (raw_encoder − Homing_Offset) mod 4096`, always in 0–4095 (requires Phase bit 4 cleared, done by `configure_motors()`). The consequence: the encoder *seam* (where present jumps 4095↔0) is NOT fixed to the magnet's zero — it sits at the shaft angle where `raw = Homing_Offset`. **Choosing the homing offset moves the seam.**

So the problem isn't "tolerate a wrap" — it's "park the seam in the joint's dead gap (the untraveled arc) so the travel never crosses it." And LeRobot's home-at-center procedure does this automatically: homing at the arc center throws the seam exactly 2048 counts away, which is the center of the opposite (dead) gap. As long as travel < 360°, the gap is non-zero and the seam lands safely inside it.

Worked example — shoulder_lift (ID 8), stops raw 1855 and 202:
- Travel arc = (202 − 1855) mod 4096 = 2443 counts ≈ 215°. Dead gap = 1653 counts ≈ 145°.
- Mid-arc raw ≈ 3076 → `Homing_Offset = 3076 − 2047 = 1029`. Seam at raw=1029, which is the center of the dead gap (202–1855). ✓
- Reported present after homing: stop A (1855) → 826, center (3076) → 2047, stop B (202) → 3269. **Both limits positive, contiguous, ~215° span. No negative EPROM write.**

The `−827` from the original failure only appeared because the OLD script computed `raw + offset` in plain Python **without the mod 4096** that the servo actually applies. The negative write was a symptom, not the disease.

### The correct calibration flow (per joint) — IMPLEMENTED in `calibrate_lerobot.py`

1. `bus.configure_motors()` once up front — clears the Phase bit so present-position reporting is single-turn mod-4096. **The old script never called this** — that was a real latent bug.
2. Hand-move the joint to the **middle** of its travel.
3. `bus.set_half_turn_homings([name])` — resets cal, reads present, writes `Homing_Offset`; the *servo* applies it.
4. `bus.record_ranges_of_motion([name])` — now records present in the continuous homed frame → clean positive range, seam parked in the dead gap.
5. `bus.write_calibration(...)`.

Keep the per-joint loop (prevents unsupported joints swinging under gravity). Just split each joint into "move to middle → Enter" then "sweep both stops → Enter."

`software/calibration/calibrate_lerobot.py` implements this flow exactly (steps 1–5, per-joint loop included) as of commit `493fbb7` (2026-06-02). It is the live, current calibration script — not a stub, not deprecated.

### Answers to the three handoff questions

1. **How does SO-100 handle wrap joints?** It doesn't special-case them — it *avoids* the seam via single-turn mod-4096 reporting (Phase bit) + home-at-center (seam → dead gap). No negative range_min in normal use.
2. **Does `drive_mode=1` fix it?** No. `drive_mode` is only a software sign-flip applied *after* normalization (`100 - norm if drive_mode`) so leader/follower agree on direction. It never touches the encoder, offset, or seam. It cannot reroute the joint onto the short path — the joint physically occupies the 215° arc.
3. **Negative `range_min` in software only?** Not needed if you home correctly (you get 826–3269). But it IS valid in principle: `_normalize`/`_unnormalize` only read range_min/range_max and never require ≥0. Only `_serialize_data` rejects negatives, and only when writing the *unsigned* Min/Max_Position_Limit EPROM registers. (Homing_Offset itself is fine negative — sign-magnitude, bit 11.) So a true-negative range = keep range in JSON, skip the EPROM limit write.

### Affected joints (leader arm, 2026-05-31)

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

> **The detailed failure analysis of the *old* approach** — why `record_ranges_of_motion` (naive `min()`/`max()`) and `set_half_turn_homings` produced the `-827` negative-EPROM-write `ValueError` — is preserved in [`docs/handoffs/lerobot-calibration-wrap-around.md`](handoffs/lerobot-calibration-wrap-around.md). The corrected understanding (the seam moves with the homing offset; home-at-center parks it in the dead gap) is in "The key insight" above; that's what supersedes it.

### Current state of calibration files

`calibration_follower.json` and `calibration_leader.json` were regenerated with the fixed flow in a clean re-calibration pass on 2026-07-27 — both arms tracking correctly, precise normalization confirmed.

### Remaining implementation work

None — both the physics and the code are done. `calibrate_lerobot.py` was rewritten around the library primitives (see above) on 2026-06-01/02, and the clean re-calibration pass with the fixed script (previously outstanding) was completed 2026-07-27.

---

### move_one.py — current state (2026-05-28)

- Located at `software/low-lvl-setup/move_one.py`
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
- Startup (updated 2026-08-01): safe-enables both arms → `run_startup_sequence` (neutral → recorded startup sequence on both arms → neutral) → disables leader torque → loop starts
- Loop: `sync_read` leader normalized positions (0–100) → 1:1 dict remap → `sync_write` to follower at 50 Hz
- Arms are physically identical (not mirrored), so `drive_mode=0` + 1:1 normalized mapping = matching poses
- No pre-running `go_neutral` needed — teleop handles its own startup sequence
- Usage: `conda activate lerobot && python software/control/teleop.py [--hz 50]`

**Import path gotcha (hit 2026-06-03):** Adding `software/` to `sys.path` to import `go_neutral` shadows the pip-installed `scservo_sdk` with the local copy in `software/scservo_sdk/`. LeRobot's `feetech.py` uses `scservo_sdk.PacketHandler` which doesn't exist in the local SDK → `AttributeError`. Fix: add the repo root (`hexarm/`) to `sys.path` instead, then import as `from software.calibration.go_neutral import go_neutral`.

### go_neutral.py — bug fix (2026-06-03)

`go_neutral` was resetting `Maximum_Velocity_Limit` to 0 after completing but **not** resetting `Acceleration`. Leaving `Acceleration = 20` on the servos caused sluggish ramp-up in the teleop loop. Fixed: both registers are now reset to 0 on completion.

### Neutral pose unification — fixes follower-snap-on-leader-release (2026-08-01)

**Bug:** at teleop startup, the follower would suddenly snap to the leader's position the instant leader torque was dropped (step 2 of the old startup sequence). Root cause: `neutral_follower.json` and `neutral_leader.json` were captured as two separate hand-poses via `record_neutral.py --arm <arm>`. Two independently hand-posed captures are never bit-identical — so each arm parked at a *slightly different* physical position during `go_neutral`, and the loop's first `sync_read` of the leader's actual position yanked the follower to match it.

**Fix:** `record_neutral.py` now always hand-poses the follower only (no `--arm` flag) and writes a single `software/config/neutral.json`. `go_neutral.py` now always drives *both* arms (no `--arm` flag) to that one shared file — identical normalized values sent to `follower_*` and `leader_*` in the same `sync_write`. Since both arms are physically identical with `drive_mode=0` (the same invariant `teleop.py`'s 1:1 leader→follower mapping already relies on), matching normalized values now means matching physical poses, so there's nothing left to snap to. `teleop.py` was updated to load the one `neutral.json` instead of the two per-arm files. The old `neutral_follower.json`/`neutral_leader.json` are left on disk but are no longer read by anything — `neutral.json` must be recaptured via `record_neutral.py` before `go_neutral.py`/`teleop.py` will run.

### Startup sequence feature (2026-08-01)

New capability, motivated by wanting a repeatable choreographed motion (e.g. a wave/wake-up gesture) at the start of every teleop session, on top of the neutral-pose fix above:

- `set_startup_sequence.py` — Enter to arm → 5s countdown (printed each second) → `>>> RECORDING NOW <<<` → records 5s of the leader's hand-performed motion at 50 Hz (torque disabled, leader only) → saves `{"hz": 50, "samples": [...]}` to `software/config/startup_sequence.json`.
- `run_startup_sequence.py` — importable `run_startup_sequence(bus, neutral, sequence)`: velocity/acceleration-limited move to neutral via `go_neutral()` → open-loop `sync_write` playback of the recorded samples onto **both** arms simultaneously (same values to `follower_*`/`leader_*`, same shared-pose invariant as above) → velocity/acceleration-limited move back to neutral via `go_neutral()` again (the "careful" return, handles arbitrary wherever-playback-left-off starting position since `go_neutral` targets an absolute pose). Also runnable standalone.
- `teleop.py`'s startup sequence is now: torque-enable both arms → `run_startup_sequence` (neutral → recorded sequence → neutral) → drop leader torque → teleop loop. New hard prerequisite: `software/config/startup_sequence.json` must exist, or `teleop.py` raises `FileNotFoundError` at startup — **run `set_startup_sequence.py` at least once before the next teleop session.**

### Jetson JP7.2 reflash — CUDA torch on Python 3.12, servo bus reconfirmed (2026-08-04)

**Why:** LeRobot requires Python ≥3.12. JetPack 6.2 (L4T r36.4.7, Ubuntu 22.04) ships Python 3.10, and no cp312 CUDA torch wheel exists for that JetPack version — only cp310. cp312 CUDA torch only exists for JetPack 7.2 (L4T r39.2, Ubuntu 24.04, CUDA 13.2). Rather than a multi-hour from-source torch build on 6.2, reflashed to 7.2 to use prebuilt cp312 wheels.

**Method:** Jetson ISO (USB installer, no x86 host PC needed). A QSPI capsule firmware update was applied first (firmware now r39-generation). Target storage was the microSD card; the NVMe (`/data`) was deliberately left untouched and mounts intact post-reflash (`nofail` in `fstab` — see Setup Status). First install attempt failed at subiquity late-commands with exit 127; root cause was no network during install (the installer image lacks `dhclient` and the interface was `state DOWN`). Second attempt, with network configured on the installer's network screen, succeeded. Note for next time: Ethernet is `enP8p1s0` (PCIe NIC), not `eth0`.

**Python environment:** `/data/lerobot-env`, a venv on system Python 3.12 — deliberately not conda, since the Jetson CUDA wheels link against system CUDA/glibc/libstdc++ and conda's bundled copies of those cause `GLIBCXX`/CUDA resolution failures on Jetson. Installed: torch 2.12.0, torchvision 0.27.0+78839c2, onnxruntime-gpu 1.28.0 (all cp312/CUDA 13.2/cuDNN 9, from the [Shattered217/Jetson-Orin-Wheels](https://github.com/Shattered217/Jetson-Orin-Wheels) `7.2.0` release), numpy 2.2.6 (downgraded by LeRobot's `<2.3.0` pin), lerobot 0.6.1 (editable install from `/data/lerobot`). `torch.cuda.is_available()` verified `True`.

LeRobot 0.6.1's `pyproject.toml` pins `torch>=2.7,<2.12.0`, which excludes the only available Jetson wheel (exactly 2.12.0) by one release — without patching, `pip install -e .` silently falls back to a generic manylinux CPU-only torch 2.11.0. Patched the bound to `<2.13.0`/`<0.28.0` (torchvision) and committed the patch, along with two pre-existing Python-3.10-compat edits from the abandoned JP6.2 attempt (harmless under 3.12, kept as-is), to a local-only branch `jetson-jp7.2-local` in `/data/lerobot` — `main` stays clean for future `git pull`, this branch is what's actually checked out and what the editable install uses.

**Servo bus — re-verified, no driver work needed:** the reflash handoff initially flagged the CH343 USB-serial bridge as a blocker (`ch341` module not found, `/sys/bus/usb-serial/` absent). Checking `journalctl -k` (readable without sudo via the `adm` group) showed the actual boot-time enumeration: `cdc_acm 1-1:1.0: ttyACM0: USB ACM device` — the CH343 chip on the Waveshare board presents as a CDC ACM device on Linux, not a vendor-specific CH34x device, so the in-kernel `cdc_acm` driver handles it with zero extra work. This matches what a prior session had already documented (see Compute — Jetson Orin Nano Super, above) but wasn't cross-referenced during the reflash. Confirmed end-to-end: `FeetechMotorsBus(port='/dev/ttyACM0', motors={}).broadcast_ping()` returned all 12 servo IDs (1–12, model 777/STS3215) after `bus.connect(handshake=False)`.

**Known follow-ups, not yet done:** Super Mode may be unavailable — NVIDIA documents a JP7.2.0 bug where installing via Jetson ISO doesn't configure the Orin Nano dev kit for Super Mode (currently on 25W, MAXN SUPER missing); expected fixed in 7.2.1. 252+ pending apt updates deliberately not applied (blanket `apt upgrade` on Tegra risks the vendor kernel).

**`torchcodec` import failure — root-caused and fixed (2026-08-05).** `pip install -e ".[feetech,dataset]"` (run to unblock `record_dataset.py`, which needs the `datasets` package) pulled in `torchcodec==0.11.1` per the aarch64 pin in `pyproject.toml`. Importing it raised `RuntimeError: Could not load libtorchcodec` — the error message's own hint ("PyTorch version not compatible with this version of TorchCodec") looked like it might confirm the torch-2.12-vs-torchcodec-0.11 mismatch flagged in the JP7.2 reflash writeup above, but `ldd` on `libtorchcodec_core6.so` (the build matching the system's installed FFmpeg 6.1.1 libs) showed it was actually a plain missing-shared-library problem, unrelated to torch: `libavdevice.so.60` and `libavfilter.so.9` weren't installed, even though sibling packages `libavutil58`/`libavformat60`/`libavcodec60`/`libswscale7`/`libswresample4` (same `7:6.1.1-3ubuntu5` build) already were. **Fix applied:** `sudo apt install libavdevice60 libavfilter9` (pulled in `libpostproc57` as a dependency, same `7:6.1.1-3ubuntu5` version as everything else already on the box — 0 upgraded, no kernel/driver risk). Verified: `from torchcodec.decoders import VideoDecoder` now imports cleanly, `torch.cuda.is_available()` still `True` at torch 2.12.0. No torch/torchcodec version mismatch ever existed — the pyproject.toml comment about "0.12 needs torch==2.12" was a red herring for this particular failure. This was a real, immediate blocker (not a defer-to-later item) because `get_safe_default_video_backend()` (`lerobot/utils/import_utils.py`) picks `torchcodec` via `importlib.util.find_spec()`, which only checks that the package is *installed*, not that it *imports successfully* — so it would have hard-crashed the first video-decode call (training, `lerobot-dataset-viz`, etc.) had it shipped unfixed.

### Dataset recording — 50 episodes, resolution/speed fix, phantom-episode incident (2026-08-10)

**Goal for the session:** record the pick-and-place demonstration dataset (target: 50 episodes) now that arms, cameras, and startup sequence were all confirmed ready as of session 11.

**Hardening before recording, driven by real failures hit early in the session:**
- Arms weren't returning to neutral after the *last* episode of a session (only between episodes) — fixed.
- A stale, empty dataset directory from an earlier crashed attempt caused `FileExistsError` on `create()` — the fix was just deleting the stale directory; not a code bug.
- Pressing ENTER to finish an episode appeared to hang for ~15s before Ctrl-C would even register. Root cause: `image_writer_threads=4` was being shared across 2 cameras instead of LeRobot's own documented recommendation of 4 threads *per camera* — the unbounded write queue was silently backlogged with zero console feedback. Fixed: `image_writer_threads = 4 * len(cameras)`.
- `bus.write()`/`bus.read()` default to `num_retry=0` — a single dropped status packet during `safe_enable_torque()` raised `ConnectionError` and crashed a whole session. Fixed with `num_retry=3` across all scripts using this pattern (see FeetechMotorsBus API section above).
- `--resume` raised `ValueError: resume() requires an explicit 'root' directory` — unlike `create()`, `resume()` has no default root inference. Fixed by passing `root=HF_LEROBOT_HOME / repo_id` explicitly.
- Added a full-width, high-contrast on-screen banner when recording starts — the monitor is several meters from the robot station, plain terminal text wasn't visible from there.

**Video encode speed investigation:** the ~2-minute wait after each episode (image-queue flush + video encode) was benchmarked directly on hardware rather than guessed at. Findings, in order of what turned out to matter: GOP/keyframe interval doesn't affect encode speed (only file size); switching codec (AV1 → H.264, even `ultrafast`) is *not* faster on this Jetson's ARM cores — the original hypothesis, disproven by direct measurement; **resolution is the dominant lever** — 1280×800 → 640×400 gave a measured ~3.4× speedup (71.5ms/frame → 21.2ms/frame). The camera doesn't support requesting 640×400 capture directly (it silently snaps to 640×480, the wrong aspect ratio) — confirmed via direct hardware test before committing to an approach — so the fix captures at native 1280×800 and downscales in software (`cv2.resize`, `INTER_AREA`) before writing.

**Phantom-episode data-loss incident — see `docs/debugging/postmortems.md` #8 for the full root-cause writeup.** Short version: the resolution fix above applied unconditionally, but `hexarm/pick_and_place` (created earlier, before the fix existed) was already schema-locked at 1280×800; resuming it with 640×400 frames silently produced 2 uncommitted "phantom" episodes — `info.json`'s counters advanced with no real data behind them, and the underlying frames were unrecoverable by the time it was caught. Root-caused via file-mtime forensics, fixed by deriving recording resolution dynamically from the target dataset's own feature schema (`dataset.features[...]["shape"]`) instead of a fixed constant, and `info.json` was hand-repaired back to the true state (3 valid episodes). Decision going forward: a dataset's resolution is fixed for its lifetime — to get the faster resolution, record into a **new** `repo_id` (`hexarm/pick_and_place_v2`) rather than resizing an existing one in place. The original `hexarm/pick_and_place` (3 valid episodes, 1280×800) was kept on disk, untouched, rather than deleted — cheap to keep, no reason to lose real data for a naming preference.

**Recording, verification, and result:** all 50 episodes recorded into `hexarm/pick_and_place_v2` (640×400 @ 30fps, ~28.3k total frames) across several sessions today. Verified structurally sound — `info.json` totals match the real data table exactly, every episode's first/last frame decodes correctly through the actual `LeRobotDataset` load path (not just file-existence checks), no orphaned/incomplete episode directories left on disk. One rabbit hole worth noting for next time: the raw video *container* reported ~136 more frames (via both `cv2`'s metadata and a real PyAV decode) than the data table's frame count — traced to inert padding from ffmpeg's stream-copy episode concatenation (each episode's own `from_timestamp`/`to_timestamp` × fps matches its real frame count exactly), not data loss; LeRobot addresses frames by timestamp, so the padding is never read during training. Built a visual QA artifact — start/mid/end thumbnail frames from both cameras for all 50 episodes — for the one thing no automated check can confirm: whether the leader arm ever creeps into the overhead camera's frame (an explicit LeRobot dataset-quality rule, see the Camera Placement Research entry in the Vision section above). Evan's call after reviewing: not worth blocking on given how few frames would be affected — fix it later if it actually shows up as a training problem, not preemptively.

**Training-time research (Jetson vs. cloud):** benchmarked real ACT policy training step time on this Jetson — built the actual policy LeRobot would train (same architecture, same input shapes as the real dataset, same batch size 8, FP32 — LeRobot's default has no mixed precision) and timed 20 real steps: **1.29s/step measured**. Cross-referenced against LeRobot's own hardware guide, which sizes training by epochs over the dataset (5–10 epochs), not a flat step count — for this dataset that's ~17.7k–35.4k steps, projecting to **~6.4–12.7 hours locally**. The same guide's own published anchor for a near-identical setup (RTX 4090, ACT, batch 8, ~50-episode dataset) is **~30–90 minutes**, and a rented RTX 4090 costs well under $1 for a full run. Decision: train in the cloud (`lerobot-train ... --job.target=a10g-large` via HF Jobs, or a rented RTX 4090) rather than tying up the Jetson — which is also the robot's control computer — for half a day per run, especially with multiple training iterations likely.

### Jetson training crash — RAM exhaustion diagnosed and fixed with zram (2026-08-13)

**Local training crashed the Jetson twice — see `docs/debugging/postmortems.md` #9 for the full root-cause writeup.** Short version: two hard freezes (no panic, no OOM-kill, physical power cycle required both times) while running `lerobot-train`'s local 300-step ACT benchmark. The first crash's last kernel log line (`nvme0: I/O tag ... timeout`) initially pointed at NVMe power delivery, but a second, instrumented repro — `tegrastats` and the training command's stdout both logged to the eMMC root instead of `/data`, specifically so telemetry would survive a repeat crash — caught the real mechanism: RAM hitting 97–98% of the board's 7.3GB unified pool with 0B swap configured, during the dataloader's prefetch warmup. `systemd-oomd` never armed to catch it (silently disabled — this kernel doesn't expose `/proc/pressure/memory`, which the service requires). Fixed with `zram-tools` (compressed-RAM swap, chosen over a disk-backed swapfile to avoid adding I/O load to the drive already suspected of instability): had to override the package's default `ALGO=lz4` to `zstd` (this Tegra kernel's zram driver doesn't support lz4 — only lzo/lzo-rle/zstd) and its default `SIZE=256` (MiB, far too small) to `PERCENT=50` (~3.7GB). Verified by re-running the identical benchmark with telemetry watching again — swap absorbed ~1.4GB at the same peak that killed the box twice before, and this time training ran clean through all 300 steps (loss 28.07 → 3.00) with a fully-saved checkpoint.

**Re-benchmarked training throughput with the fix in place:** the full 300-step run averaged ~0.87s/step at steady state (`updt_s` in the training log) after a ~40s warmup — noticeably faster than the earlier 1.29s/step estimate above (that number came from a synthetic 20-step benchmark script, not a real end-to-end `lerobot-train` run against the actual dataset/dataloader). At this pace, a full 5–10 epoch run (~17.7k–35.4k steps) projects to roughly **4.3–8.6 hours locally** — still well over the ~30–90 minutes a rented RTX 4090/HF Jobs run would take, but the crash risk that originally motivated moving to the cloud is now resolved. **Decision, updated:** run the first full training attempt locally on the Jetson rather than setting up a cloud job — it's free, the crash is fixed, and validating the full local pipeline end-to-end once is worth the wait for a first attempt. Cloud remains the better choice for faster iteration if multiple training runs are needed afterward.

### Full training run completed, checkpoints evaluated, run_policy.py written (2026-08-14)

**Training ran clean, no crash.** Launched `lerobot-train --steps=25000` (`--job_name=act_pick_and_place_v2`, `--save_freq=5000`) inside `tmux` specifically so a dropped SSH connection couldn't kill it — a different failure mode from the RAM-exhaustion freeze postmortem #9 covers, since here the Jetson itself stays healthy but a bare foreground process would still die if its parent SSH session hung up. Also left `tegrastats` logging in the background at a coarser 5s interval (vs. the 200ms used for the crash repro) to keep the file size sane over a multi-hour run. Training finished all 25,000 steps in ~6h12m (18:24:21 → 00:36), confirmed via three independent signals: `uptime` showed continuous boot time predating the run start (no reboot), the `tmux` session was never recreated, and all 5 checkpoints (`005000`/`010000`/`015000`/`020000`/`025000`, plus a `last` symlink) landed on disk with evenly-spaced timestamps matching the measured per-step pace.

**No loss-curve history survived to review after the fact** — `wandb.enable=false` was set (fully offline/local run), `lerobot-train` doesn't write its own metrics log file to disk, and `tmux`'s scrollback buffer had long since rolled past the ~250 progress lines a 6-hour run produces by the time anyone thought to check. The only usable signal left was checkpoint weights themselves. Wrote a standalone eval script (`/tmp/.../eval_checkpoints.py`, not committed — one-off) that loads each of the 5 checkpoints via `policy_cls.from_pretrained()` + `make_pre_post_processors()` and runs 50 forward-pass-only batches (`policy.forward()`, no gradient) against the training set, using `resolve_delta_timestamps()` to reconstruct the same action-chunked batch shape `lerobot-train` uses internally (a plain `DataLoader` without this produces the wrong action-tensor shape and crashes `F.l1_loss`). Result: L1 loss dropped monotonically across every checkpoint — 0.1742 (5k) → 0.1354 (10k) → 0.1124 (15k) → 0.1067 (20k) → **0.0942 (25k)** — with the final checkpoint confirmed as the best of the five, no late-run overfitting. One architectural note worth remembering: `kld_loss` comes back empty in eval mode — ACT's CVAE encoder only runs during training (it needs the real future actions to encode a "style" latent from, which isn't available at inference time), so only `l1_loss`/`loss` are meaningful post-training metrics.

**Wrote `software/control/run_policy.py` for running the policy on the physical arm — not yet run.** No existing script covered this: LeRobot's own `lerobot-record`/`lerobot-rollout`/`lerobot-eval` all require `--robot.type` to be one of a fixed list of built-in robot classes, and hexarm (like all the other custom control scripts here) isn't one of them. The new script mirrors `record_dataset.py`'s hardware wiring (`FeetechMotorsBus`, `OpenCVCamera`) but drives only the follower — no leader arm involved, since the policy replaces the human entirely — and uses LeRobot's own `predict_action()` helper (`lerobot.common.control_utils`) for the actual inference step rather than a hand-rolled version, so the tensor conversion/normalization/postprocessing exactly matches what LeRobot's built-in robot classes do. Safety approach (Evan's explicit choice over two less-cautious options): dead-man's-switch gated, identical convention to `go_neutral.py --diagnostic` — the policy's predicted action is only ever written to the servos while SPACE is held, checked fresh every tick, released freezes in place within ~33ms regardless of what was just predicted. Verified everything checkable without hardware: syntax, all LeRobot API imports resolve, the actual final checkpoint loads onto CUDA correctly, and the `action`/`observation.state` feature names (`{joint}.pos` × 6) and camera shapes (400×640×3) the script assumes were confirmed directly against the dataset's real metadata rather than guessed. Hardware I/O itself (bus/camera connect, real servo writes) is the one thing that can only be verified by actually running it.

**Next up:** `source /data/lerobot-env/bin/activate && cd /data/hexarm && python software/control/run_policy.py` — hold SPACE in short bursts first and watch what the policy tries to do before committing to longer holds.

---

### First hardware policy run (v2), grazing/near-clip found, re-recorded and retrained (v3) — logged retroactively (2026-08-21)

**v2 checkpoint was actually run on hardware.** Exact date not logged — it happened between session 14 (2026-08-14, checkpoint confirmed best-of-5 but not yet run) and the v3 dataset recording below (2026-08-20), outside a tracked Claude Code session, so there's no session-log entry for the run itself. `run_policy.py` worked as designed: dead-man's-switch gated, SPACE held in short bursts, task completed successfully. But two close calls surfaced that the offline eval numbers gave no warning of — full root-cause writeup in [`postmortems.md` #10](debugging/postmortems.md#10-first-hardware-policy-run--claw-grazing-the-block-near-clipping-the-bowl-lip): the claw would sometimes graze the block while closing on it during the pick (risking a break — PLA claw, already flagged fragile in postmortems #4/#5), and the drop-off trajectory toward the bowl often passed just over the bowl's top lip with little clearance. Both are the policy faithfully reproducing tight margins that were already present in the `pick_and_place_v2` demonstrations themselves, not a policy-quality problem — L1 loss doesn't measure real-world clearance.

**Fix — re-recorded the dataset, not just retrained on the same data.** New 50-episode dataset, `hexarm/pick_and_place_v3` (recorded 2026-08-20, 35,661 frames vs. v2's ~28.3k — same episode count, longer/more deliberate motions), demonstrating two explicit changes: opening the claw wider by default before closing on the block, and going deliberately higher over the bowl's lip on the drop-off. All ACT hyperparameters kept identical to the v2 run (chunk_size=100, n_action_steps=100, kl_weight=10.0, dropout=0.1, no image augmentation) — the only variable changed on purpose was the demonstration data itself.

**Training — completed, but with a logging gap.** Launched `lerobot-train --steps=30000` (`--job_name=act_pick_and_place_v3`, `--save_freq=5000`) 2026-08-20 16:49, finished 2026-08-21 04:56 (~12h07m — all 6 checkpoints landed on disk with clean, evenly-spaced timestamps through `030000`, `last` symlink updated, no crash). One anomaly worth flagging: `outputs/train/act_pick_and_place_v3.log`'s stdout/stderr capture stopped at ~step 5,700 (18:16, only 27 minutes in) even though training clearly kept running and checkpointing correctly for another ~10.75 hours after that — so there's no in-log record of *why* it stopped, only confirmation via checkpoint timestamps that the process itself was healthy throughout. Separately, the run's per-step pace was noticeably slower than v2's: v2 averaged ~0.89s/step (25k steps / 6h12m); v3 averaged ~1.45s/step (30k steps / 12h07m) despite the visible early progress-bar rate (~1.1 step/s ≈ 0.9s/step) looking normal — cause not diagnosed, since the same logging gap that lost the loss curve also lost any telemetry that could explain the slowdown. Next time: confirm the run is inside `tmux` with logging that's actually verified to keep flushing (v2's session explicitly used `tmux` for SSH-drop protection; unclear whether v3's was set up the same way).

**Checkpoint eval — v3 confirmed better than v2, no overfitting.** Same method as session 14 (one-off script, not committed, loads each checkpoint + runs 50 forward-pass-only batches against the training set, `resolve_delta_timestamps()` to reconstruct the action-chunked batch shape `lerobot-train` uses internally): L1 loss dropped monotonically across all 6 checkpoints — 0.1307 (5k) → 0.1064 (10k) → 0.0961 (15k) → 0.0857 (20k) → 0.0759 (25k) → **0.0738 (30k)** — final checkpoint confirmed best of 6, no late-run overfitting, and a lower final loss than v2's 0.0942 (not a strictly apples-to-apples comparison since it's a different dataset, but a reasonable signal the fit is at least as good). `run_policy.py`'s `DEFAULT_CHECKPOINT` updated to point at `outputs/train/act_pick_and_place_v3/checkpoints/last/pretrained_model`.

**Next up:** run `run_policy.py` against the physical follower arm again, this time watching specifically for whether the wider claw opening and higher drop-off arc actually fixed the two postmortem #10 behaviors — not just "probably better." Close out postmortem #10's TODO once confirmed.

---

### v3 run on hardware — postmortem #10 confirmed fixed, project functionally complete (2026-08-21)

**v3 checkpoint run on the physical follower arm via `run_policy.py`**, dead-man's-switch gated (SPACE held in bursts), same as the v2 run. 3 successful pick-and-place completions this session. Both postmortem #10 behaviors were specifically watched for and confirmed fixed: claw clearance around the block on pick and clearance over the bowl's lip on drop-off were both noticeably wider than the v2 run, with no grazing or near-clipping observed across the 3 successful runs. Postmortem #10 closed — see the Verification note added there.

**A different failure mode showed up, not related to postmortem #10.** Some runs failed to pick up the block at all — attributed to camera-coverage blind spots (the policy losing sight of the block/gripper from certain positions), not a margin/clearance problem. This is a known limitation going forward; no further training or dataset re-recording is planned, so it's being documented as-is rather than chased further.

**Status:** this closes the last functional TODO on the hardware/software side — `run_policy.py`'s v3 checkpoint is verified working end-to-end on the physical arm. Remaining project work is portfolio polish (pinning the LeRobot version, README badges, a `docs/context.md` summary/TOC — see `WRAPUP.md`) rather than anything functional. Roadmap M2's electronics items (wiring schematic/BOM/power budget), M4 (kinematics), and M6's safety-limits/e-stop item were all dropped outright (2026-08-21, Evan's call), not deferred — no further work planned on any of them. Real hardware photos (14, `media/pictures/`) were added and wired into the README Demo section the same day; the demo video was skipped by choice (recordings ran too long).

---

*Last updated: 2026-08-21 (session 16 — ran the v3 checkpoint on the physical follower arm for the first time via `run_policy.py`: 3 successful pick-and-place completions, dead-man's-switch gated. Specifically confirmed postmortem #10's two margin issues (claw grazing the block on pick, drop-off passing close over the bowl's lip) are fixed — both clearances visibly wider, no grazing/near-clipping across the 3 runs. Closed postmortem #10. A separate, unrelated failure mode surfaced — occasional missed picks from camera-coverage blind spots — documented as a known limitation with no further training planned, not a margin/quality regression. This was the last functional TODO on the project; what's left is documentation and portfolio polish, tracked in `WRAPUP.md`.)*

*Previously: 2026-08-21 (session 15 — logged, retroactively, that the v2 checkpoint had already been run on the physical follower arm: it worked, but with tight real-world margins (claw grazing the block on pick, drop-off passing close over the bowl's lip — full writeup in postmortems.md #10) that the offline eval numbers gave no warning of. Fix was a re-recorded dataset (`pick_and_place_v3`, wider claw opening + higher drop-off arc, same hyperparameters otherwise), retrained for 30,000 steps (completed 2026-08-21 04:56, ~12h07m — slower per-step than v2 for reasons not diagnosed, since the run's own log stopped capturing 27 minutes in despite training continuing correctly for another ~10.75 hours). Ran the same one-off forward-pass eval script as session 14 across all 6 v3 checkpoints: L1 loss monotonic 0.1307→0.0738, final checkpoint best of 6, no overfitting, lower final loss than v2. Updated `run_policy.py`'s default checkpoint to v3. Next up: run v3 on hardware and confirm the grazing/near-clip behavior is actually fixed.)*

*Previously: 2026-08-14 (session 14 — the real 25,000-step ACT training run completed locally overnight with zero issues (~6h12m, `tmux`-protected against SSH drops), confirmed via `uptime`/checkpoint timestamps that no crash occurred; 5 checkpoints saved. No loss-curve log survived to review (wandb off, tmux scrollback rolled past 6h of history), so wrote a standalone eval script instead — loads each checkpoint and runs 50 forward-pass-only batches against the training set. Result: L1 loss dropped monotonically across every checkpoint (0.1742→0.0942), final checkpoint confirmed best of the 5, no overfitting. Wrote `software/control/run_policy.py` to run the trained policy on the physical arm — no existing script covered this since hexarm isn't one of LeRobot's built-in `--robot.type` options; built on LeRobot's own `predict_action()` reference helper, dead-man's-switch gated (Evan's explicit choice, same convention as `go_neutral.py --diagnostic`) since this is the first time the arm would move under this policy's control. Verified everything checkable without hardware (imports, real checkpoint load, feature-name/shape assumptions) — not yet run against the physical arm. Next up: run it.)*

*Previously: 2026-08-13 (session 13 — local `lerobot-train` benchmark hard-froze the Jetson twice, no panic/OOM-kill/graceful-shutdown trace either time, requiring a physical power cycle both times; root-caused via an instrumented repro (tegrastats + training stdout logged to eMMC so telemetry would survive a repeat crash) to RAM exhaustion — the board's 7.3GB unified memory pool hitting 97–98% full during dataloader prefetch warmup with 0B swap configured and `systemd-oomd` silently disabled (no `/proc/pressure/memory` on this kernel) — full writeup in postmortems.md #9. Fixed via `zram-tools`, after two default-config failures: `ALGO=lz4` isn't supported by this kernel's zram driver (switched to `zstd`), and the default `SIZE=256` (MiB) was far too small (switched to `PERCENT=50`, ~3.7GB). Verified fixed by re-running the identical benchmark with telemetry watching again — completed all 300 steps cleanly (loss 28.07 → 3.00), checkpoint saved. Re-benchmarked real training throughput with the fix in place: ~0.87s/step steady-state, faster than session 12's synthetic-benchmark estimate — projects a full 5–10 epoch run to ~4.3–8.6h locally. Decision updated: run the first full training attempt locally rather than in the cloud, now that the crash risk is resolved. Next up: the real training run.)*

*Previously: 2026-08-10 (session 12 — dataset recording complete: all 50 target episodes recorded into `hexarm/pick_and_place_v2`, verified structurally sound and visually reviewed. Along the way: hardened `record_dataset.py` against several real failures (neutral-return timing, image-writer thread starvation, unretried servo writes, `--resume` root inference), root-caused and fixed a genuine data-loss bug — 2 unrecoverable phantom episodes from a resolution mismatch on `--resume`, full writeup in postmortems.md #8 — and benchmarked real ACT training throughput on this hardware to decide cloud vs. local training. Full details above. Next up: policy training, in the cloud.)*

*Previously: 2026-08-09 (session 11 — full CAD assembly finalized for both arms, leader and follower, in Onshape (public doc linked in Hardware → Arm Structure), closing out the M1 CAD milestone; two build issues surfaced during assembly and were resolved — a free-standing base flexed and let the arm tip over, fixed by making the base clamp to the table instead of relying on its own footprint/mass (postmortem #6); and printed links bent specifically where PLA screws into the servo horns, fixed by locally thickening the links at those screw points rather than uniformly (postmortem #7). STEP exports added to `cad/exports/` — trimmed from Onshape's raw 111MB per-part export (66 STEP+STL files, 93MB of which was the same vendor servo model duplicated 12×) down to 6.5MB by keeping STEP only for each arm's custom-designed parts plus a single shared servo reference file; STL and the redundant per-instance servo/duplicate files were dropped as they added no unique design information. Assembly renders (`leader_arm.png`, `follower_arm.png`) added to `cad/renders/` and wired into the README Demo section. Next M1 item: hardware assembly guide.)*

*Previously: 2026-08-05 (session 10 — confirmed the wrist camera's reprinted mount is correctly placed/aimed via `camera_preview.py`, closing out the last open item blocking dataset recording; both cameras locked and wired into `record_dataset.py`. First `record_dataset.py` run hit `ImportError: 'datasets' is required` — fixed via `pip install -e ".[feetech,dataset]"` in `/data/lerobot-env` (torch stayed pinned at 2.12.0, confirmed via `torch.cuda.is_available()` after). That install surfaced the previously-flagged `torchcodec` question, which turned out to be two missing system FFmpeg packages, not a torch mismatch — root-caused and fixed via `sudo apt install libavdevice60 libavfilter9`, verified working (see the `torchcodec` write-up above). Dataset recording is in progress this session.)*

*Previously: 2026-08-04 (session 9 — reflashed Jetson from JetPack 6.2 to JetPack 7.2 to get Python 3.12 + CUDA torch for LeRobot; full write-up above. Servo bus reconfirmed working end-to-end post-reflash with zero driver changes needed. Next up: dataset recording, now that both the software stack and hardware path are verified.)*

*Previously: 2026-08-03 (session 8 — fixed the local git corruption open since 2026-07-31: deleted the 6 corrupt loose objects and the local refs pointing at the corrupt commit, re-fetched from `origin` to recover it cleanly, then committed and pushed the 2026-08-01 session's pending script changes (`60ce4ac`); a broken follower joint (elbow_flex, ID 3) was reprinted and reassembled, then the follower arm was fully re-calibrated and `neutral.json` recaptured — see Setup Status; hit an `OverEle` (overcurrent) fault on that same joint during `go_neutral.py` after recalibration, apparently from a large excursion pressing into a wall (a servo in position mode keeps driving toward `Goal_Position` under torque regardless of whether the host script's polling loop has timed out, so sustained contact — not a momentary spike — trips the fault and the servo's own protection firmware auto-disables its torque; see Concepts Covered); ruled out a reversed calibration range (`record_ranges_of_motion()` does a true running `min()`/`max()`, structurally can't swap them) and gravity sag (confirmed by hand) as causes, resolved by power-cycling the servo bus, not reproduced since; extended `go_neutral.py` with an `at_neutral()` pre-check (skip the move entirely if already close enough) and a `--diagnostic` hold-to-move dead-man's-switch mode for safely testing suspect moves by hand; found and fixed a real bug in `go_neutral.py`'s arrival check — strict `<` against `POSITION_TOLERANCE` meant a joint sitting exactly on the boundary (observed: `elbow_flex` at `87.5` vs. target `87.0`, a diff of exactly `0.5`) would never register as arrived and would hang to the full timeout; changed to `<=` and widened the tolerance 0.5 → 1.0; rewrote `set_startup_sequence.py` to drive both arms to neutral first (skippable via `at_neutral()`) and disable torque on the leader only, so the recorded trajectory starts from the same pose `run_startup_sequence.py` replays it from instead of an arbitrary one; extended the recording window 5s → 10s; confirmed `run_startup_sequence.py` now runs end-to-end (neutral → recorded motion → neutral) without issue. Dataset recording is up next.)*

*Previously: 2026-08-01 (session 7 — wrist camera's reprinted mount (designed around the real 70°(H) FOV) installed, but the live-preview placement/aim re-check was started and then deferred, not completed this session; found and fixed the root cause of the follower snapping to the leader's position when leader torque dropped at teleop startup — two independently hand-posed `neutral_follower.json`/`neutral_leader.json` were never bit-identical, so `record_neutral.py`/`go_neutral.py`/`teleop.py` were rewritten around one shared `neutral.json` used identically by both arms (see Neutral Pose Unification); added a startup-sequence feature — `set_startup_sequence.py` records a hand-performed leader motion, `run_startup_sequence.py` replays it on both arms between neutral moves, wired into `teleop.py`'s startup in place of the bare `go_neutral()` call (see Startup Sequence Feature); simplified `calibrate_lerobot.py`'s per-joint flow from three Enter presses to two by removing a redundant prompt in front of `record_ranges_of_motion()`, which already blocks on its own Enter internally; confirmed the local git object database corruption noted last session is still present and unresolved)*

*Previously: 2026-07-31 (session 6 — cameras arrived and connected (`/dev/video0` overhead, `/dev/video2` wrist); built `software/vision/camera_preview.py`, a headless MJPEG live-view tool, and used it to position and lock the overhead tower against the target geometry; verified the Arducam B0385 lens FOV against the manufacturer manual (70°(H), confirmed full/total horizontal angle — vertical/diagonal not manufacturer-specified); found the wrist camera's first mount was placed too far back and aimed too level, framing mostly background instead of the grasp zone — Evan is reprinting the mount designed around the real FOV this time; also discovered the local git object database has corrupt loose objects — packed history and working tree are intact, not yet resolved)*

*Previously: 2026-07-27 (session 5 — clean re-calibration of both arms completed with the fixed flow, and angle limits flashed to servo EPROM; started redesigning the claw — old one too small, dropping objects, see `docs/debugging/postmortems.md` #5; added `docs/session.md` as a personal fast-path setup/continuity doc, separate from this AI-handoff file)*
