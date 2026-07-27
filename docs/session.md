# Session Guide (personal)

> Fast-path notes for Evan, not AI handoff. For the deep technical reference (hardware specs, protocol details, calibration internals, collaboration style) see [`context.md`](context.md). For past incidents see [`debugging/postmortems.md`](debugging/postmortems.md).

---

## 1. General Setup

### Wiring / power — do this first, safely

**Two adapters. Do not cross them** — the Jetson's 19V adapter will fry the servo board (rated 12V).

| Adapter | Output | Goes to |
|---|---|---|
| Jetson power supply | 19V, 2.37A | Jetson's barrel jack |
| Servo bus power supply | 12V, 5A | Waveshare board's barrel jack |

Connection order:
1. Daisy-chain both arms' servo JST connectors into the one active Waveshare Bus Servo Adapter (A). (A second board is a spare, not wired in.)
2. Confirm the board's physical mode switch is set to **USB-Servo**.
3. Plug in the 12V/5A adapter (servo bus).
4. Plug in the 19V/2.37A adapter (Jetson).
5. Connect the Waveshare board to the Jetson via USB — enumerates as `/dev/ttyACM0`.
6. Power on the Jetson, then SSH in.

### SSH in

```bash
ssh evan0h@eka-orin.local
```

Workspace is `/data` — `cd /data` once you're in. The NVMe SSD is mounted there and holds everything: the `hexarm` repo, the `lerobot` repo, and the `lerobot` conda env.

- mDNS (`eka-orin.local`) can lag — a direct IP is faster/more reliable if you have it.
- If SSH complains `REMOTE HOST IDENTIFICATION HAS CHANGED` (happens after a reflash): `ssh-keygen -R eka-orin.local`, then retry.

### Python environments — which one, and why

Two separate environments, for two separate jobs.

| | conda activate `lerobot` | hexarm `.venv` |
|---|---|---|
| Location | `/data/miniconda3/envs/lerobot` | `/data/hexarm/.venv` |
| Activate | `conda activate lerobot` | `source .venv/bin/activate` (from hexarm root) |
| Use for | anything importing `lerobot` — `teleop.py`, `software/calibration/*` | raw SDK diagnostics that don't touch LeRobot — `software/low-lvl-setup/*` (ping, baud scan, etc.) |
| Why it's separate | LeRobot needs Python 3.12+ and a CUDA-linked torch build (cu126) — a heavy, GPU-specific dependency tree that has no business polluting anything else. Installed editable (`pip install -e ".[feetech]"`) from the `/data/lerobot` checkout. | These scripts only need `pyserial`. No reason to drag in torch/LeRobot for a ping test. A matching venv exists on the Mac side too, where LeRobot can't even install (no x86_64 torch build) — the venv is what makes those diagnostic scripts portable across machines. |

Rule of thumb: script imports `lerobot` → conda. Script only talks raw serial → venv.

### Quick sanity check after powering up

```bash
cd /data/hexarm
conda activate lerobot
python software/low-lvl-setup/ping_one.py --id 1     # bus is alive?
python software/control/teleop.py             # run teleop
```

### Known footguns (see postmortems.md for full writeups)

- Waveshare board wiring is **straight-through** (TX→TX, RX→RX), not crossed — opposite of standard UART convention.
- A serial console/getty on the servo UART silently eats bytes. If comms flake out, check `systemctl is-enabled serial-getty@<port>` before anything else.
- On Mac, use `/dev/cu.usbmodem*`, not `/dev/tty.*` — `tty` blocks waiting for carrier detect.
- Adding `software/` to `sys.path` shadows the pip-installed `scservo_sdk`. Add the repo root instead.

---

## 2. Where We Left Off

*Last updated: 2026-07-27*

### Current state
- Last commit: `aeb690a` (2026-07-21) — "parameterized config scripts to allow for easier calibration" (`calibrate_lerobot.py`, `go_neutral.py`, `torque_off.py`, calibration/neutral JSONs).
- **Uncommitted right now:** a docstring path fix in `record_neutral.py`, plus today's doc updates (README, context.md, postmortems.md, this file) — none committed yet.
- Teleoperation is working end-to-end (both arms, single bus, 50Hz).
- **Done today (2026-07-27):** clean re-calibration of both arms with the fixed flow, and angle limits flashed to servo EPROM. Both were the last blockers before camera integration/dataset recording.
- Cameras (2× Arducam OV9782 global shutter) were ordered 2026-07-14, expected ~07-22 — arrival not yet confirmed in the repo/session; still no camera code/integration written. See camera-placement research below before mounting.
- Two open claw/gripper issues, both tracked in `postmortems.md`, likely to converge into one redesign:
  - **#4** (started 2026-07-15): leader-side claw hard to actuate by hand in limp mode — force breaks PLA parts.
  - **#5** (started today, 2026-07-27): follower-side claw jaw too small — drops grasped objects. Evan is designing a new claw as a **union of modular sub-parts** rather than one monolithic body, partly as a deliberate experiment in whether modular CAD actually saves iteration time (see `context.md` Concepts Covered log).

### Camera placement research (2026-07-27)

Researched where the overhead camera should go, using LeRobot's own docs/blog plus general imitation-learning camera-setup practice (ALOHA-style dual-arm rigs). Key takeaways to apply when mounting:

- **The leader arm must not appear in frame.** This is an explicit LeRobot dataset-quality rule ("Leader arm should not appear" — HF's "what makes a good dataset" post) and is a real constraint here specifically because both arms share one workspace. The overhead camera's position *and* field of view need to be chosen so it frames only the follower's workspace — may mean offsetting it toward the follower's side rather than centering it over the whole table, or narrowing the FOV, not just placing it dead-center overhead.
- **Mount it rigid and fixed.** No shake, and don't reposition it between recording sessions — these policies learn from raw pixel observations tied to a specific camera pose, so a camera that moves between data collection and eval is a known failure mode.
- **Cover the full reachable/placement workspace**, high/wide enough to see everywhere an object could be grasped or placed, angled rather than a strict straight-down nadir shot so the gripper isn't constantly self-occluded directly under the camera.
- **Pair with the wrist camera intentionally**, not redundantly: wrist cam gives a close-up, occlusion-robust grasp view; overhead gives global spatial context of object position relative to the arm. This wrist+top combo is LeRobot's own standard example config (`cameras={"wrist": ..., "top": ...}`).
- Matches the existing plan in `context.md`'s Vision section ("mid-distance rack" for the overhead unit) — this just adds the *why* and the leader-exclusion constraint that should drive exact positioning once the cameras are in hand.
- Sources: [LeRobot Imitation Learning docs](https://huggingface.co/docs/lerobot/il_robots) (camera config examples, "keep cameras fixed" / visibility guidance), [LeRobot Datasets blog post](https://huggingface.co/blog/lerobot-datasets) ("what makes a good dataset" — leader-arm-out-of-frame rule, two-camera recommendation, steady/stable-lighting guidance), general ALOHA/dual-arm teleop camera-design background via web search.

### Next steps (unclaimed as of last session)
- [ ] Confirm cameras have arrived; mount overhead cam per the placement notes above (exclude leader arm from frame, fixed mount, angled not nadir) and wrist cam on the follower gripper; wire both into LeRobot camera config
- [ ] Continue claw redesign (postmortems #4 + #5) — see each entry's TODO list
- [ ] Disable Jetson GUI (headless, reclaim ~800MB RAM)
- [ ] Verify serial console is off on the servo UART on the Jetson
- [ ] Start dataset recording → policy training

### Open threads / questions to pick up
- (add anything you're mid-thought on here — this section is the first thing to check at the start of a new session)

---

*Update this section at the end of each session (or ask Claude to do it) — commit alongside whatever code changed.*
