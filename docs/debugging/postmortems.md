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

*Have a new issue in progress? Add a new `## N. Title` section above using the same template — even a partially-solved entry (Symptom + Investigation so far) is useful; fill in Root Cause / Fix / Lesson once resolved.*
