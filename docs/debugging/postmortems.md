# Postmortems

Consolidated log of hardware/software incidents encountered while building hexarm — each one root-caused, not just patched. Full blow-by-blow chronology for incidents 1–2 lives in [`servo-comms-debug-log.md`](servo-comms-debug-log.md); incident 3's original handoff doc lives at `docs/context mds/lerobot-calibration-wrap-around.md`.

---

## 1. No Servo Communication At All

**Dates:** ~2026-05-17 to 2026-05-19 (~3 days) · **Severity:** Blocking

**Symptom:** Zero response from any STS3215 servo, on any host (Mac, Arduino, Raspberry Pi), any interface (USB, UART), any baud rate (9600–1,000,000). Servos powered on (red LED lit) but never replied to a ping, and never physically stiffened in response to a broadcast torque-enable.

**Investigation:** Systematically isolated the hardware path — tested across three different hosts and two different Waveshare boards and STS3215 units, ruling out a single bad component. Bypassed the SDK entirely with a raw pyserial ping to remove software as a variable. Every combination failed identically, which pointed at something common to all setups rather than any one host/interface.

**Root cause:** The Waveshare Bus Servo Adapter (A) labels its UART pins from the *host's* perspective, not the device's. Standard UART convention crosses TX↔RX between two devices; this board's silkscreen means "connect the host's TX wire to the pin labeled TX," i.e. straight-through wiring (TX→TX, RX→RX). Every wiring attempt had used the standard crossed convention.

**Fix:** Rewire straight-through (TX→TX, RX→RX, GND→GND) per the corrected understanding.

**Lesson:** Verify a third-party board's pin-labeling convention before assuming standard UART crossing. A broadcast command (ID 0xFE, no response expected) is a cheap way to test "is the data line reaching the bus at all" without needing to know a servo's ID first.

---

## 2. Intermittent Ping Failures — Two Stacked Root Causes

**Dates:** 2026-05-20 to 2026-05-25 · **Severity:** Blocking (masked as "mostly working")

**Symptom:** After incident 1's fix, pings succeeded only 15–40% of the time. Byte counts were always exactly 0/6 or 5/6 — never 1, 2, 3, or 4.

**Investigation (first pass — wrong):** Built a stress-test harness (`ping_stress.py`) that logged hundreds of ping attempts to CSV. The "never 1–4 bytes, only ever the first byte missing" pattern was a strong, self-consistent signal: it matched a UART framing-error theory (the half-duplex bus driver's RC turnaround time causing the first response byte to be misread as garbage while the line is still charging). Built a fix around that theory — a resync parser that over-reads by one byte to recover a dropped header — plus retry logic. This appeared to work.

**Investigation (second pass — real cause):** The "fix" from pass one caused a *new* regression: SDK calls that do multiple reads per call (like `ping()`, which does a PING + a follow-up model-number read) started failing with `COMM_RX_CORRUPT`, consistently, even after reboots and reseated connectors. A loopback test — jumpering the Pi's own TX to its own RX and trying to read back what was written — failed to echo anything. That falsified the framing-error theory outright: if the Pi couldn't hear its own transmitted bytes, the Waveshare board and servo bus were never the problem. `dmesg` and `stty -F /dev/ttyAMA0` then showed the port pinned at 115200 despite the code requesting 1,000,000 baud.

**Root cause:** A kernel serial console + `serial-getty@ttyAMA0.service` were still attached to the same UART used for the servo bus. The getty silently consumed incoming bytes before pyserial could read them, wrote login-prompt characters onto the TX line, and held the port at its console baud rate at the kernel level. This explained every symptom from pass one — the "always missing byte 1" pattern was the getty grabbing bytes non-deterministically, and "retry helps" was coincidence, not RC warm-up. On top of that, pass one's resync-parser "fix" turned out to have its own bug: reading `length+1` bytes to recover a dropped header silently stole a byte that `ping()`'s second, chained read still needed — a second, independent bug hiding behind the first.

**Fix:** Removed `console=ttyAMA0` from the kernel command line and disabled `serial-getty@ttyAMA0.service` (or, more simply, `raspi-config` → Serial Port → login shell **No**, hardware **Yes**). Reverted `port_handler.readPort()` to the stock upstream SDK implementation; moved retry/recovery logic to an outer wrapper (`_serial_utils.py`) instead of patching SDK internals.

**Lesson:** A theory that explains every observed symptom can still be wrong — the fix is a falsifying experiment, not more confirming evidence. The loopback test collapsed the whole framing-error narrative in one command. `stty` reporting a baud rate you never set is a red flag that something else owns the port; `dmesg | grep -iE "uart|serial|tty"` should be one of the first checks, not the last. Monkey-patches to shared SDK internals need to be audited across *every* call site, not just the one under test — a fix for a single-transaction read broke a multi-transaction one.

---

## 3. Encoder Wrap-Around — Negative Calibration Values

**Dates:** 2026-05-31 to 2026-06-02 · **Severity:** Blocking (calibration crash)

**Symptom:** LeRobot calibration crashed with `ValueError: Negative values are not allowed: -827` for certain joints, but not others.

**Investigation:** Streamed raw encoder positions per joint while manually sweeping each one to its physical stops. Found that some joints' physical travel arc straddles the STS3215's 12-bit encoder rollover (4095→0), while others don't. The servo's homing math (`homing_offset = 2047 − raw_mid`) worked fine for non-wrapping joints but produced a negative homed position for one stop on wrapping joints — and `write_calibration` rejects negative values for the unsigned `Min_Position_Limit` EPROM register.

**Root cause:** `Present_Position` is actually `(raw_encoder − Homing_Offset) mod 4096` — the encoder's reporting *seam* (where the value jumps 4095↔0) is not fixed to the magnet's physical zero; it sits wherever `raw = Homing_Offset`. Homing at the arc's endpoint (rather than its center) placed that seam *inside* the joint's traveled range, so one physical stop legitimately needed to report a negative position — which the unsigned EPROM field can't hold. The `-827` error was a symptom of a bad homing choice, not evidence that negative ranges are unsupported in general.

**Fix:** Home at the arc's *midpoint* instead of an endpoint. This throws the seam exactly 2048 counts away from center — the middle of the joint's *untraveled* ("dead") gap — so any travel range under 360° never crosses it. Rewrote `calibrate_lerobot.py` around the library's own primitives in the correct order: `configure_motors()` (clears the Phase register bit so position reporting is clean single-turn mod-4096) → `set_half_turn_homings()` (homes at the measured center) → `record_ranges_of_motion()` (now records a clean, contiguous, all-positive range).

**Lesson:** SO-100/LeRobot doesn't special-case wrap-around joints — it *avoids* the seam entirely via home-at-center, so no negative EPROM write is ever needed for a physically valid joint. Understanding the seam as something that *moves* with the chosen homing offset (rather than being fixed to the magnet) was the key insight that made the fix obvious in hindsight.

---

## 4. Leader Gripper — Manual Actuation Force Breaking PLA Parts

**Dates:** started 2026-07-15 · **Severity:** In progress · **Status:** 🚧 Open

**Symptom:** During teleoperation, the leader arm's gripper servo runs torque-disabled ("limp" mode) so Evan can manipulate the claw by hand. Rotating the gripper bars by hand under limp mode takes surprisingly high force — likely the servo's internal gearbox drag rather than anything gripper-specific — and PLA gripper parts aren't strong enough to take it comfortably.

**Investigation so far:**
- **Attempt 1 — thick squeeze bars:** printed two thicker bars to squeeze directly. Functional but awkward to hold while simultaneously operating the other 5 joints one-handed.
- **Attempt 2 — finger-hole attachments (current):** printed two finger-hole mounts that attach to the existing gripper bars, intended to give a more natural grip while leaving fingers free for the other joints. Problems:
  - The mounts flex/bend under load and go out of alignment with the claw's linear guide, which introduces friction that adds even more resistance to an already-stiff motion.
  - The finger mounts sit at a distance from the bar's pivot, creating a long lever arm — the torque this generates at the attachment point is close to snapping the PLA outright.

**Root cause:** Not yet finalized — likely a combination of (a) underestimating the servo's limp-mode resistance torque when sizing the mechanism, and (b) the finger-mount attachment geometry creating a lever arm that multiplies hand force into more torque/bending stress at the joint than the direct-squeeze bars ever saw.

**Fix:** TBD — Evan is actively iterating on this.

**Lesson:** TBD once resolved.

**TODO:**
- [ ] Characterize the actual limp-mode resistance torque (measure, don't guess) to size any new mechanism correctly
- [ ] Shorten the lever arm between the hand-contact point and the bar pivot, or reinforce that joint (e.g. brass insert, thicker wall, different infill orientation)
- [ ] Consider a stiffer/tougher material for just the finger-mount part (PETG/nylon) if PLA is fundamentally undersized here, rather than redesigning geometry further
- [ ] Re-check claw guide alignment tolerance — the friction problem may be solvable independently of the strength problem

---

## 5. Claw Too Small — Dropping Grasped Objects

**Dates:** started 2026-07-27 · **Severity:** In progress · **Status:** 🚧 Open

**Symptom:** The follower claw's jaw opening/contact geometry is undersized for the objects being grasped during teleop — grip doesn't fully secure the object, and it slips or drops mid-manipulation.

**Investigation so far:** Evan is designing a new claw from scratch rather than patching the current one. Related to (but a separate symptom from) postmortem #4 — both point at the same gripper assembly needing a redesign, #4 on the leader side (hand-actuation force breaking PLA) and this one on the grasping side (jaw too small to hold objects reliably).

**Root cause:** TBD — likely the original claw geometry was sized against the SO-100 reference design/early test objects rather than the actual range of objects intended for this project's dataset.

**Fix:** TBD — new claw in progress.

**Lesson (in progress, not yet settled):** Evan is deliberately building the new claw as a **union of smaller, modular sub-parts** rather than one monolithic printed body, specifically to test whether this is actually faster to iterate on — a failed sub-part gets reprinted/redesigned alone instead of forcing a full-part redo. Still calibrating how much time this saves in practice; see the "Modular vs. monolithic CAD design" entry in `context.md`'s Concepts Covered log once there's a real before/after comparison to write down.

**TODO:**
- [ ] Nail down the target object set (size/weight range) the claw needs to reliably hold, so the new design is sized against real requirements instead of guesswork
- [ ] Decide how the modular sub-parts union together (fasteners? printed snap-fit? glued?) and whether that joint becomes its own weak point
- [ ] Once printed, cross-check against postmortem #4 — a wider/reshaped jaw may also change the hand-actuation force problem (for better or worse)

---

## 6. Arm Base Instability — Bending/Tipping Under Load

**Dates:** during CAD/build assembly, resolved by 2026-08-09 · **Severity:** Blocking (assembly) · **Status:** ✅ Resolved

**Symptom:** The free-standing arm base bent and the arm tipped/fell over during assembly and testing.

**Investigation:** The base had been sized to support the arm's static weight while sitting still, not the tipping moment generated once the arm moves — the shoulder/base joint applies a lever-arm load that a free-standing footprint has to resist entirely through its own stiffness and mass.

**Root cause:** Static support and dynamic tip-resistance are different requirements — a base wide/heavy enough to hold the arm upright at rest can still flex or tip once the arm swings its weight around, because that introduces a moment the base's footprint alone wasn't sized against.

**Fix:** Made the base clampable to the table (rather than relying on the base's own footprint and mass for stability), converting the table itself into part of the base's effective support.

**Lesson:** For a free-standing multi-DOF arm, size (or mount) the base against the worst-case *tipping moment* the arm's motion can generate, not just its static resting weight. A clamp/fixture to an external rigid surface is a simpler fix than iterating base geometry/mass if the application allows a fixed mounting point.

---

## 7. Servo-Mount Joint Bending — PLA Screw Points Undersized

**Dates:** during CAD/build assembly, resolved by 2026-08-09 · **Severity:** Moderate · **Status:** ✅ Resolved

**Symptom:** Printed links bent under load specifically at the joints, at the point where the PLA part screws into the servo horn — other, unattached regions of the same links were fine.

**Investigation:** The bending was localized to the fastener bosses at each servo attachment, not distributed along the link, pointing at the screw point itself rather than the part's general cross-section as the weak spot.

**Root cause:** The screw-in boss where a link bolts to a servo horn is a stress concentration — a smaller, thinner feature than the rest of the link, carrying the full joint load through a small attachment area. Sizing wall thickness for the link overall didn't account for this local feature needing its own margin.

**Fix:** Thickened the links specifically at the servo screw-in points (not a uniform thickness increase across the whole part).

**Lesson:** Fastener attachment points on a printed part are a distinct sizing problem from the part's general wall thickness — treat them as their own local stress concentration and reinforce there directly, rather than assuming a part that's strong everywhere else is automatically strong at its mounting holes too.

---

## 8. Phantom Episodes — Silent Data Loss From a Resolution Mismatch on `--resume`

**Dates:** 2026-08-10 · **Severity:** High (unrecoverable data loss) · **Status:** ✅ Resolved

**Symptom:** After a `record_dataset.py --resume` session that appeared to complete normally (no errors, no crash), `meta/info.json` reported `total_episodes=5` / `total_frames=3447`, but the actual per-episode data — `data/chunk-000/file-000.parquet`, the video files, and `meta/episodes/...parquet` — only ever had 3 real episodes / 2268 frames. Two full episodes' worth of counters existed with no data behind them.

**Investigation:** Confirmed via direct inspection that `info.json`'s totals didn't match row counts in the actual parquet/video files, then cross-checked file mtimes: `info.json` had been touched at 15:28:40, but the real data files' last-touched time was 14:45:55 — matching only the original recording session, not the later `--resume` session that supposedly added 2 more episodes. That pinned the corruption to something in the resume path specifically, not the original recording.

**Root cause:** Earlier the same session, `record_dataset.py` had been changed to downscale newly-recorded frames to 640×400 (for faster video encoding — see the video-encode speed investigation) via unconditional `RECORD_WIDTH`/`RECORD_HEIGHT` constants. That change only accounted for *new* datasets. `hexarm/pick_and_place` had already been created earlier at the camera's native 1280×800, so its on-disk schema (`dataset.features[...]["shape"]`) was permanently locked at 1280×800. Resuming it with the new code wrote 640×400 frames into an 1280×800-schema dataset. LeRobot's dataset writer advances its internal episode counter *before* the shape-mismatched image/video data actually fails to merge — so the failure was silent from the operator's side: no exception, no warning, just counters that quietly went wrong. By the time this was discovered, the raw per-tick frames for both phantom episodes had already been cleaned up as part of the (apparently successful) save flow, so the underlying recordings were gone — not just mislabeled.

**Fix:** Replaced the unconditional `RECORD_WIDTH`/`RECORD_HEIGHT` constants in the recording tick loop with a `record_sizes` dict derived dynamically from the dataset's *own* declared feature shape right after `create()`/`resume()` (`dataset.features[f"observation.images.{name}"]["shape"]`), so recording always matches whatever resolution that specific dataset is actually locked at — 1280×800 for an old dataset, 640×400 for a freshly-created one — instead of assuming one fixed resolution applies everywhere. `meta/info.json`'s counters were hand-repaired back to the true state (5→3 episodes, 3447→2268 frames), and the orphaned frame directories for the two phantom episodes were deleted. Going forward, datasets that need the faster resolution are created fresh under a new `repo_id` (e.g. `pick_and_place_v2`) rather than resized in place — resolution is schema-locked for the lifetime of a dataset, there's no in-place "upgrade."

**Lesson:** Any per-recording constant that a script assumes applies globally (resolution, feature shape, etc.) needs to be checked against the specific artifact being *resumed*, not just the artifact being *created* — `create()` and `resume()` are not symmetric, and a fix validated against "start fresh" doesn't automatically hold for "continue existing." Also: a library that advances a counter before validating the data behind it turns a hard failure into a silent one — when writing anything that resembles "reserve a slot, then fill it," validate before incrementing, not after, or a downstream failure corrupts bookkeeping instead of raising.

---

## 9. Jetson Hard-Freezes During Local ACT Training — RAM Exhaustion With No Swap

**Dates:** 2026-08-11 to 2026-08-13 · **Severity:** Blocking (required a physical power cycle both times) · **Status:** ✅ Resolved

**Symptom:** The Jetson hard-froze twice while running `lerobot-train`'s local ACT benchmark (`--steps=300` smoke test against `hexarm/pick_and_place_v2`) — SSH dead, no console response, requiring a physical power cycle both times. Neither crash left a kernel panic, an OOM-killer log line, or any graceful-shutdown trace; the system journal simply stopped mid-boot with nothing further.

**Investigation:** The first crash (2026-08-11, 16:53:23) happened mid-conversation with Claude Code, but the actual crashing command wasn't in that session's own tool-call history — it had been run manually in a separate terminal and only pasted back as output. Recovering the literal command meant grepping the raw Claude Code session JSONL transcripts under `~/.claude/projects/` and cross-referencing timestamps. `journalctl -b -1` on that first crash showed the last kernel message before the log went dark was `nvme nvme0: I/O tag 464 (41d0) QID 1 timeout, completion polled` — pointing at NVMe power delivery as the likely trigger, especially combined with the board's factory-default 25W `nvpmodel` mode. That theory drove a first mitigation attempt, but wasn't confirmed before a second, deliberate repro was set up: `tegrastats` logging and the training command's own stdout both redirected to the **eMMC root** (`/home`, not `/data`) at high resolution, specifically so telemetry would survive even if the NVMe browned out again. The second crash reproduced in the same command's first-step warmup window, but the surviving telemetry told a different story: RAM at 7280–7292MB of the board's 7486MB total (97–98% full) with **swap at 0B**, CPU/GPU utilization near-idle for ~28 seconds (stuck, not computing), then both `tegrastats` and the system journal going silent together — no NVMe timeout this time. That ruled out power delivery as the primary mechanism (the first crash's NVMe timeout was real but a downstream symptom, not the root cause) and pointed at memory exhaustion instead.

**Root cause:** The board has 7.3GB of usable unified CPU/GPU memory and zero swap configured. During the dataloader's prefetch warmup (`prefetch_factor=4`, decoding camera video frames into batches ahead of the training loop) on top of the baseline RAM already held by the desktop GUI session (gdm/gnome-shell/PackageKit — this is a full Ubuntu desktop image, not headless), the board hit close to 100% memory utilization with nowhere to go. `systemd-oomd` — the userspace OOM killer that should have stepped in first — was silently disabled the whole time: its unit requires `/proc/pressure/memory`, which this kernel doesn't expose, so the condition check failed and it never armed. With no swap and no working OOM protection, the kernel had no graceful way out of the pressure spike and hard-locked instead of killing the offending process.

**Fix:** Installed `zram-tools` for compressed-RAM swap (chosen over a disk-backed swapfile specifically to avoid adding NVMe/eMMC I/O load at the exact moment the system is already under stress). The package's default config failed outright — `ALGO` defaults to `lz4`, which this Tegra kernel's zram driver doesn't support (`cat /sys/block/zram0/comp_algorithm` only lists `lzo`, `lzo-rle`, `zstd`) — fixed with `ALGO=zstd` in `/etc/default/zramswap`. Its other default, a flat `SIZE=256` (MiB), was also far too small against a multi-GB spike; fixed with `PERCENT=50` instead (~3.7GB — `PERCENT` overrides `SIZE`). Verified by re-running the identical 300-step benchmark with telemetry watching again: RAM hit the same ~97% ceiling, but this time zram absorbed ~1.4GB into swap at peak instead of the kernel hitting a wall — training pushed through the same warmup window that killed it twice before, completed all 300 steps (loss 28.07 → 3.00, confirming real learning, not just non-crashing), and the checkpoint saved cleanly to disk.

**Lesson:** A crash that leaves nothing behind — no panic, no OOM-kill message, no core dump — doesn't mean there's nothing to find; it means the evidence has to be captured *during* a live reproduction, written somewhere that survives the failure mode under test (eMMC root, not the drive suspected of failing). The first crash's NVMe timeout was a real, reproducible-looking signature that still pointed at the wrong root cause — only a second, instrumented repro separated symptom from mechanism. Separately: on an 8GB unified-memory board, swap isn't optional for GPU training workloads, and `systemd-oomd`'s silent dependency on `/proc/pressure/memory` (present on many kernels, absent on this one) means "the OOM killer will handle it" isn't a safe assumption without checking first.

**Note (unrelated, worth recording):** after a successful run, `lerobot-train` now throws `AttributeError: module 'torch.distributed' has no attribute 'is_initialized'` during `accelerate`'s teardown (`accelerator.end_training()`), causing a non-zero exit code even though training and checkpointing both complete successfully first. Likely `torch.distributed` support stripped from this Jetson build of `torch` (2.12.0). Harmless for interactive use; would need a fix if this ever gets wired into an automated/scripted pipeline that checks exit codes.

---

## 10. First Hardware Policy Run — Claw Grazing the Block, Near-Clipping the Bowl Lip

**Dates:** exact date not logged — between the v2 checkpoint being confirmed best-of-5 (2026-08-14) and the v3 re-recording (2026-08-20) · **Severity:** High (near-miss, no actual damage) · **Status:** ✅ Resolved — v3 verified on hardware 2026-08-21

**Symptom:** First physical run of the trained policy (`act_pick_and_place_v2`, 25,000-step checkpoint, via `run_policy.py`'s dead-man's-switch mode) completed the pick-and-place task successfully, but with thin real-world margins in two places: (1) during the pick, the claw would sometimes graze the block while closing around it — if contact had been harder, it risked breaking the claw (PLA, already flagged as fragile in postmortems #4 and #5); (2) during the place, the trajectory toward the bowl would often pass just over the bowl's top lip, with little clearance to spare.

**Investigation:** Caught by eye during the run itself, under the dead-man's-switch (SPACE held in short bursts, per the script's own guidance) — not by any automated check. Notably, nothing in the policy's offline eval numbers predicted this: L1 loss was 0.0942 at 25k, monotonically decreasing across all 5 checkpoints with no sign of overfitting (see the 2026-08-14 session log). That number measures how faithfully the policy reproduces the *demonstrated* trajectories, not how much clearance those trajectories leave from real-world contact — a policy can nail its training objective and still have no margin for error.

**Root cause:** The policy faithfully reproduced what was demonstrated in `pick_and_place_v2` — and those demonstrations themselves had tight margins: the leader-arm claw wasn't opened much wider than the block during approach, and the drop-off motion passed close over the bowl's rim by habit, not by design. Imitation learning has no built-in notion of "safety margin" beyond what's in the data; a policy trained on close-but-successful demonstrations reproduces those same close calls every time, minus the human reflexes that would normally catch a bad attempt.

**Fix:** Re-recorded a new 50-episode dataset, `hexarm/pick_and_place_v3` (2026-08-20), demonstrating the same task with two deliberate changes: opening the claw wider by default before closing on the block, and going deliberately higher over the bowl's lip during the drop-off. Retrained ACT from scratch on the new dataset — 30,000 steps (up from 25,000), all other hyperparameters unchanged (chunk_size/n_action_steps/kl_weight identical to the v2 run). Training completed 2026-08-21 04:56; see the session log for checkpoint eval results.

**Lesson:** An imitation-learning policy is only as cautious as its demonstrations. Offline loss confirms the policy learned the demonstrated behavior faithfully — it says nothing about whether that behavior had adequate real-world margin. When the hardware being controlled is fragile (this project's PLA claw, already an open concern per postmortems #4/#5) or the workspace has hard edges, demonstrate with margins deliberately wider than a human teleoperator would think necessary. The policy will reproduce your habits, including your close calls, on every attempt rather than just the one where you got lucky.

**Verification (2026-08-21):** Ran the v3 checkpoint on hardware via `run_policy.py` (dead-man's-switch, SPACE held in bursts) — 3 successful pick-and-place completions. Both margins confirmed improved: claw clearance around the block on pick and clearance over the bowl's lip on drop-off were both noticeably wider, no grazing or near-clipping observed across the 3 runs. Separately, some runs failed to pick up the block at all due to camera-coverage blind spots (a different failure mode, not a margin/clearance issue) — noted as a known limitation, not being pursued further (no additional training planned).

**TODO:** none — closed.

---

*Have a new issue in progress? Add a new `## N. Title` section above using the same template — even a partially-solved entry (Symptom + Investigation so far) is useful; fill in Root Cause / Fix / Lesson once resolved.*
