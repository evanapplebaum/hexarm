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

*Last updated: 2026-08-01*

### Current state
- **Git note (2026-07-31, still unresolved 2026-08-01):** local `.git/objects` currently has 6 empty/corrupt loose objects — `git status`, `git log`, etc. error out. `git verify-pack` on the packfile is clean and the reflog shows history through commit `48f9eaa5...` (merge, 2026-07-27), so packed history and all working-tree files look intact — reads like an interrupted `git add` from the tail end of the 2026-07-27 session, not real data loss. **Still not fixed** — re-confirmed broken 2026-08-01, same object (`ddf24cd3...`). See Open threads below before trying to commit anything (this session's script changes are currently uncommitted for this reason).
- Teleoperation is working end-to-end (both arms, single bus, 50Hz) — startup sequence changed 2026-08-01, see below.
- **Neutral-pose bug fixed (2026-08-01):** the follower used to snap to the leader's position the instant leader torque dropped at teleop startup. Cause: `neutral_follower.json` and `neutral_leader.json` were two independently hand-posed captures, never bit-identical. Fix: `record_neutral.py`/`go_neutral.py` lost their `--arm` flags — `record_neutral.py` now always poses the follower only and writes one shared `neutral.json`; `go_neutral.py` now always drives both arms to that one file. `teleop.py` updated to match. **Old `neutral_follower.json`/`neutral_leader.json` are stale — `neutral.json` needs to be captured fresh via `record_neutral.py` before `go_neutral.py` or `teleop.py` will run.** Full writeup in `docs/context.md`'s "Neutral pose unification" section.
- **New: startup sequence feature (2026-08-01).** `set_startup_sequence.py` records a hand-performed leader-arm motion (Enter → 5s countdown → 5s recording @ 50Hz) to `startup_sequence.json`; `run_startup_sequence.py` replays it on both arms between two `go_neutral()` calls (neutral → sequence → neutral). `teleop.py`'s startup now calls this instead of a bare `go_neutral()`. **`startup_sequence.json` doesn't exist yet — `teleop.py` will raise `FileNotFoundError` until `set_startup_sequence.py` is run at least once.**
- **Done 2026-07-27:** clean re-calibration of both arms with the fixed flow, and angle limits flashed to servo EPROM. Both were the last blockers before camera integration/dataset recording.
- **`calibrate_lerobot.py` UX simplified (2026-08-01):** per-joint flow went from 3 Enter presses to 2 — the redundant prompt in front of `record_ranges_of_motion()` was removed (that function already blocks on its own Enter internally, so it never needed a second prompt to "start").
- **Cameras arrived and connected (2026-07-31):** both Arducam OV9782 boards enumerate fine over USB — overhead is `/dev/video0`, wrist is `/dev/video2` (each camera also exposes a second, metadata-only node — `/dev/video1`/`/dev/video3` — not used).
- **Overhead camera mounted and locked (2026-07-31):** positioned against the target geometry using a new live MJPEG preview tool, `software/vision/camera_preview.py` (headless stdlib `http.server` + cv2; serves each requested `/dev/videoN` at `http://<jetson-ip>:8080/videoN`, so you can nudge a camera and see which browser tab moves — useful since both cameras report identical USB serials and can't be told apart from udev alone). Confirmed good — **do not move it again**, collection and deployment pose must match.
- **Wrist camera mount — reprinted and installed (2026-08-01), placement not yet re-verified.** The redesigned mount (built around the real 70°(H) FOV) is printed and fitted, replacing the first print that placed the camera too far from the jaws and aimed too level (background-dominated framing). The follow-up check via `camera_preview.py` + a close-focus check was started this session but got sidetracked into the calibration/neutral-pose work above before actually running the tool — **first thing to pick up next session.** Good candidate for a `postmortems.md` #6 entry once it's fully resolved (mirrors the modular-CAD note on #5: designing a mount without accounting for FOV/working-distance first cost a reprint).
- Two open claw/gripper issues, both tracked in `postmortems.md`, likely to converge into one redesign:
  - **#4** (started 2026-07-15): leader-side claw hard to actuate by hand in limp mode — force breaks PLA parts.
  - **#5** (started 2026-07-27): follower-side claw jaw too small — drops grasped objects. Evan is designing a new claw as a **union of modular sub-parts** rather than one monolithic body, partly as a deliberate experiment in whether modular CAD actually saves iteration time (see `context.md` Concepts Covered log).

### Camera placement research (2026-07-27)

Researched where the overhead camera should go, using LeRobot's own docs/blog plus general imitation-learning camera-setup practice (ALOHA-style dual-arm rigs). Key takeaways to apply when mounting:

- **The leader arm must not appear in frame.** This is an explicit LeRobot dataset-quality rule ("Leader arm should not appear" — HF's "what makes a good dataset" post) and is a real constraint here specifically because both arms share one workspace. The overhead camera's position *and* field of view need to be chosen so it frames only the follower's workspace — may mean offsetting it toward the follower's side rather than centering it over the whole table, or narrowing the FOV, not just placing it dead-center overhead.
- **Mount it rigid and fixed.** No shake, and don't reposition it between recording sessions — these policies learn from raw pixel observations tied to a specific camera pose, so a camera that moves between data collection and eval is a known failure mode.
- **Cover the full reachable/placement workspace**, high/wide enough to see everywhere an object could be grasped or placed, angled rather than a strict straight-down nadir shot so the gripper isn't constantly self-occluded directly under the camera.
- **Pair with the wrist camera intentionally**, not redundantly: wrist cam gives a close-up, occlusion-robust grasp view; overhead gives global spatial context of object position relative to the arm. This wrist+top combo is LeRobot's own standard example config (`cameras={"wrist": ..., "top": ...}`).
- Matches the existing plan in `context.md`'s Vision section ("mid-distance rack" for the overhead unit) — this just adds the *why* and the leader-exclusion constraint that should drive exact positioning once the cameras are in hand.
- Sources: [LeRobot Imitation Learning docs](https://huggingface.co/docs/lerobot/il_robots) (camera config examples, "keep cameras fixed" / visibility guidance), [LeRobot Datasets blog post](https://huggingface.co/blog/lerobot-datasets) ("what makes a good dataset" — leader-arm-out-of-frame rule, two-camera recommendation, steady/stable-lighting guidance), general ALOHA/dual-arm teleop camera-design background via web search.
- **Addendum (2026-07-31):** the wrist mount's first fit ran into a version of exactly the pitfall this research was trying to head off — the mount standoff distance wasn't designed around the lens's actual 70°(H) FOV, so the first print ended up too far from the jaws and captured mostly background instead of the grasp zone. Confirms the FOV-driven placement math mattered as much for the wrist cam as it did for the overhead tower, just easier to get wrong on a fixed-geometry mount than on a tower you can eyeball live.

### Next steps (unclaimed as of last session)
- [ ] Resolve local git corruption (see Current state above) before the next commit — this session's script changes are still uncommitted because of it
- [ ] Re-check wrist camera placement/aim via live preview (`software/vision/camera_preview.py`, mount is now printed and installed) and check focus at the actual close working distance
- [ ] Wire both cameras into LeRobot camera config once wrist mount is locked
- [ ] Re-capture `neutral.json` via `record_neutral.py` (old `neutral_follower.json`/`neutral_leader.json` are stale now — see Current state above)
- [ ] Record a startup sequence via `set_startup_sequence.py` — `teleop.py` will fail with `FileNotFoundError` until `startup_sequence.json` exists
- [ ] Continue claw redesign (postmortems #4 + #5) — see each entry's TODO list
- [ ] Disable Jetson GUI (headless, reclaim ~800MB RAM)
- [ ] Verify serial console is off on the servo UART on the Jetson
- [ ] Start dataset recording → policy training

### Open threads / questions to pick up
- Git corruption fix not yet decided — options are on the table (see chat), waiting on Evan's call before anything in `.git/` gets touched.
- Once wrist mount placement is re-verified, worth a `postmortems.md` #6 entry on the FOV-blind-mount-design lesson if it feels like it cleared the leverage bar.

---

*Update this section at the end of each session (or ask Claude to do it) — commit alongside whatever code changed.*
