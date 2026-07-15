# hexarm → Robot Dog — Forward Planning

> **Status:** Planning only, as of 2026-07-14. No dog-specific build has started — chassis, legs, gait control, and firmware are all unscoped. The one concrete action taken so far is ordering hexarm's wrist + overhead cameras (2026-07-14) with an eye toward reusing them as this project's front stereo pair; see below. This document exists to capture decisions made *before* the build starts, specifically so hardware bought now for hexarm is chosen with dog-reuse in mind rather than being re-bought later.

---

## Concept

A future quadruped robot dog project that reuses core hardware from hexarm rather than starting from zero:
- **Servos:** FEETECH STS3215 (same units currently on the arms)
- **Compute:** Jetson Orin Nano Super (same unit currently running hexarm teleop)

No CAD, firmware, or gait-control work has started. This doc tracks decisions made ahead of that, driven by the fact that camera purchases for hexarm's arm (wrist + overhead) are happening now (2026-07) and should double as the dog's front perception hardware later rather than being purpose-bought twice.

---

## Autonomy goal (decided 2026-07-14)

Target: **fully autonomous navigation** — the dog plans its own path and avoids obstacles in multiple directions without being steered, as opposed to pure teleop-with-FPV or simple forward-only obstacle avoidance. Treated as the end-state goal / stretch target, not necessarily the v1 milestone — camera and compute planning below is scoped for this target so hardware bought now doesn't block it later.

**Explicitly deferred for v1:** terrain-aware foot placement (vision-guided stepping on uneven/rough terrain). This is treated as a separate, much harder problem from navigation — walking stability on reasonably flat indoor floors comes from IMU + joint proprioception (the same sensing already driving hexarm's servos), not vision. No downward/chin camera is planned until rough-terrain traversal becomes an actual goal.

---

## Camera architecture

Navigation (path planning, obstacle avoidance, SLAM) is a vision problem; balance/gait is not — that split is why the camera plan is entirely about navigation coverage.

| Role | Count | Spec tier | Rationale |
|---|---|---|---|
| **Front (primary nav / stereo depth)** | 2 (matched stereo pair) | Global shutter, UVC, M12 lens — same units as hexarm's wrist + overhead cameras | Feeds path planning and visual odometry directly — needs real metric depth (via stereo triangulation) and quality matters because errors compound into bad maps/collisions. **This pair is the same physical cameras bought for the arm** (see Camera Hardware Decision below) — reused, not rebought. |
| **Left + right (hazard detection)** | 2 (1 per side) | Cheap, wide-FOV, mono, rolling shutter OK | Coarse "is something there" presence detection while turning/passing through doorways — a legged robot's body width makes it blind to side clips without this. Doesn't need depth precision, so spec bar is much lower than front. **Not yet purchased — dog-specific, no arm reuse angle.** |
| **Rear** | 1 | Same cheap tier as sides | Lets it back out of dead ends; improves SLAM loop-closure (recognizing previously-visited space from a different angle). **Not yet purchased.** |

**Total planned: 5 cameras** (4 is the bare minimum if rear is dropped, but then it can't safely reverse).

Side/rear camera model selection is deliberately deferred — no reuse constraint applies to them, so they should be picked against dog-specific hardware (final compute mounting, cable routing, chassis geometry) once that exists, not now.

---

## Camera hardware decision — front stereo pair (2026-07-14)

**✅ ORDERED 2026-07-14:** 2× **Arducam OV9782 1MP Global Shutter USB Camera Board (model B0385)** — UVC-compliant, M12 lens, manual-focus threaded mount, up to 100fps MJPEG at 1280×800 and lower resolutions. Purchased via Amazon.ca (third-party seller, ASIN `B0CLXZ29F9`) at $116.16 CAD/unit (~$232 CAD for the pair) — a real markup over Arducam's $59.99 USD direct price (~40% above straight FX conversion, typical marketplace-reseller premium on a low-volume niche item), accepted in exchange for certain pricing and no customs-brokerage-fee uncertainty vs. ordering direct from Arducam.com (which routes Canadian orders through a sales-assisted quote flow rather than instant checkout). Expected delivery 2026-07-20–22.

**Watch out for near-identical SKUs on the same product page** — Arducam sells the OV9782 sensor on several different carrier boards and it's easy to grab the wrong one:
- `OAK-D W` ($429) — full stereo depth camera unit, way more than needed
- `B0352` ($25.99) — "drop-in replacement for DepthAI OAK-D," bare MIPI-CSI module with FFC ribbon cable, **no USB output, will not work as a Jetson webcam**
- `B0385` ($59.99) — **this is the correct one** — has an actual USB cable, UVC-compliant, plug-and-play

The fast visual check: the correct listing's product photo shows a USB cable, and the title says "USB Camera Board" / "UVC Webcam Module" — not "MIPI camera module" or "for DepthAI OAK."

**Where to buy (Evan is in Canada):** Arducam.com routes international checkout through a sales-assisted "request a quote" flow rather than instant purchase — skip it. [Amazon.ca carries the same listing](https://www.amazon.ca/Arducam-Shutter-Distortion-Without-Microphones/dp/B0CLXZ29F9), confirmed in stock, normal checkout, no customs paperwork. RobotShop (Mirabel, QC) is a real Canadian Arducam distributor worth checking too, but this specific SKU wasn't confirmed in their catalog via search.

These are the same 2 units that go on hexarm now (1 wrist-mounted, 1 overhead/workspace) — see `docs/context.md` → Vision section. They migrate to the dog's front/head mount once that build starts.

### Why OV9782 over the alternatives considered

Researched before committing, to make sure nothing better was missed:

- **Arducam AR0234 (2.3MP, USB3.0, ~$70–100+)** — higher resolution and USB3 bandwidth headroom, genuinely a stronger sensor on paper. **Rejected for this dual-role purpose specifically**: its stock M12 lens has a fixed default focus range of **2m to infinity** — correct for a robot looking across a room, but useless for the wrist-camera role, which needs to focus at 5–20cm on a grasped object. Would need a separate close-focus lens purchase to work as a wrist cam, defeating the point of reusing one board across both roles.
- **Arducam's pre-bundled stereo kits** (e.g. "2.3MP USB3.0 UVC Global Shutter Dual-Camera Bundle Kit," "Sync Stereo... for NVIDIA Jetson Orin Nano/NX") — these exist and are the more "correct" industrial answer for stereo *specifically*: hardware-synchronized (µs-level) capture, which the DIY pair below doesn't get (each OV9782 board free-runs independently over USB, no shared trigger). Rejected for now because:
  - The USB3 bundle kit ships the two sensors on one fixed/adjustable-baseline bracket — built as a single stereo unit, not two independently mountable cameras. Can't be split apart to serve as the arm's wrist cam (which moves) and overhead cam (which is fixed, far away) separately.
  - The Jetson-specific "Sync Stereo" kit uses **GMSL2 over coax into a MIPI-CSI deserializer board**, not USB/UVC at all — different physical interface, dog-only (doesn't plug into the arm's USB ports as a general camera), and adds a Jetson-specific vendor driver install (a real bring-up risk given how much friction the servo bus already caused — see `docs/debugging/servo-comms-debug-log.md`).
  - **Worth revisiting as a dedicated, non-reused purchase once the dog build is actually underway**, if the free-running USB pair's lack of hardware sync turns out to hurt stereo-matching quality in practice (most likely to show up as ghosting/misalignment on fast-moving scene content). Not a concern for the arm's use case.
- **Plain single-camera UVC webcams (e.g. Logitech-class)** — ruled out earlier in the arm camera discussion: rolling shutter, autofocus that can't rack down to wrist-camera distances, no depth capability at all.

### Why the manual-focus M12 mount is what makes the reuse plan work

The wrist role (now) and the front-nav role (later, on the dog) want *opposite* focus distances — close-up for inspecting a grasped object vs. meters-out for room navigation. Rather than needing two different lens purchases, the OV9782 board's M12 lens is a threaded, focus-adjustable mount (standard for M12/S-mount optics) — rack it close and lock it now for the wrist, re-rack it far and lock it again when it's remounted on the dog's head later. One physical camera, refocused per role, not two purchases.

---

## Open questions / next steps

- [x] Confirm actual model number and lens FOV at order time — B0385 confirmed correct, 2 units ordered 2026-07-14 (see Camera Hardware Decision above).
- [ ] Cameras arrive (~2026-07-20–22) — mount 1 on the follower wrist, 1 overhead per `docs/context.md` Vision section; wire into LeRobot camera config for dataset recording.
- [ ] Side + rear camera selection — deferred until dog chassis/mounting exists.
- [ ] Compute budget check: running SLAM + obstacle detection across up to 5 simultaneous camera streams on the Orin Nano Super's GPU has not been prototyped. Plan is to validate incrementally (front pair first, add side/rear once that's solid) rather than assume it scales for free.
- [ ] Gait control / gait-and-gait-controller hardware and firmware — not scoped at all yet.
- [ ] CAD for legs/chassis — not started.

---

*Created 2026-07-14 — initial camera architecture and front-pair hardware decision, ahead of the arm camera order.*
