# Hexarm — Hardware Assembly Guide

This covers fastening the printed/CAD parts to the servos, and the physical
workspace setup around the finished arms. It does not re-derive part
geometry or link-by-link fit — for that, the [Onshape assembly
(public)](https://cad.onshape.com/documents/0670dbd7fb06bb7c9bf9782d/w/e043c38067500e43503b5676/e/e17080d119308b27c44a0ee6)
is the primary reference and is detailed enough to build from directly
(leader and follower are modeled as two separate assemblies in that doc).
This guide is for the things that aren't obvious just from looking at the
CAD: which fastener goes where, build order, and — most importantly — the
physical setup constraints that affect data collection and training later.

---

## 3D Printing

All printed parts (links, bases, camera mounts, claw) were printed on a
Bambu Lab P1S with budget/generic PLA, using Bambu Studio's **Strength**
preset rather than the default profile — the extra wall/infill it adds was
worth the print-time cost given how much these parts flex and bend under
load in practice (see [postmortem #6](debugging/postmortems.md), base
tipping, and [postmortem #7](debugging/postmortems.md), servo-mount joints
bending). Printing has to happen before anything below — have a full set of
both arms' parts on hand (`cad/exports/leader/` and `cad/exports/follower/`)
before starting assembly.

---

## Before You Start

- **Assign each servo's ID before mounting it into the arm.**
  `software/low-lvl-setup/setup_servo.py` requires exactly one servo on the
  bus at a time (all servos ship at factory default ID `1` and will collide
  if powered up together) — far easier to do this with a servo sitting
  loose on the bench than after it's daisy-chained into a fully built arm.
  Target IDs: follower `1`–`6`, leader `7`–`12` (see [ADR
  0002](adr/0002-single-bus-servo-topology.md)).
- Have both STEP export sets open or printed for reference:
  `cad/exports/leader/` and `cad/exports/follower/`.

### Tools

- Phillips (crosshead) screwdriver. Exact bit size isn't critical,
  just make sure it seats fully in the screw head before applying torque,
  the M2 heads are small enough to strip if it's not fully seated.
- No thread-locker is used on any of these fasteners by choice; screws
  have held securely without loosening under the arm's motion, and
  thread-locker would make dissassembly more difficult.

---

## Fasteners (per servo)

Each STS3215 servo ships with 5× M3 and 4× M2 screws.

| Fastener | Qty per servo | Connects | Notes |
|---|---|---|---|
| M3 | 5 | The two metal horn plates on either end of the servo | One plate keys onto the output driveshaft (drives the joint); the opposite plate spins freely and is purely a support/idler bearing for the far side of the servo — don't confuse the two, only one side is driven. |
| M2 | 4 | Servo body → the printed link supporting it | Mounts the servo itself into the arm's link structure. |

---

## Assembly Order

1. Configure each servo's ID (and return delay, if not already set) one at
   a time on the bench — see [Before You Start](#before-you-start).
2. For each servo: bolt on the two M3 horn/idler plates first, then mount
   the servo body into its supporting link with the 4× M2s.
3. Build up each arm link-by-link per the Onshape assembly view. Leader and
   follower differ (leader: `base`, `crank`, `link1`–`4`, `wheel`;
   follower: `base`, `link1`–`5`, `claw`, `pinion`, top/bottom rack) — work
   from the matching arm's assembly, not the other one.
4. Repeat for the second arm.

---

## Workspace Setup — Critical for Data Collection

This matters as much as the mechanical assembly itself. After training begins,
if the captured scene changes, the trained policy may fail unpredictably.

- **Clamp/screw both arm bases securely to a table** (a foldable table is fine; 
  that's what's in use here). A free-standing base isn't enough: the arm's
  own motion generates a tipping moment that an unclamped base can't
  resist on its own, and a base that shifts throws off every joint's
  calibrated position. This is exactly the failure in [postmortem
  #6](debugging/postmortems.md) — the fix there was making the base
  clamp to the table rather than relying on its own footprint/mass.
- **Position the two arms so neither can physically reach the other** (or
  the operator) at full extension. Don't just eyeball the spacing — after
  clamping, power up each arm in `go_neutral.py --diagnostic` mode
  (hold-to-move, releases instantly) and sweep it out to its joint limits
  by hand to confirm the real reachable envelope before trusting the
  layout.
- **Once cameras are mounted and calibration/recording begins, treat the
  entire workspace as fixed** — table position, arm bases, camera mounts,
  and background. A trained policy has zero experience with a scene it
  wasn't recorded against; moving anything (even something that seems
  incidental, like an object left in frame) can degrade or break policy
  performance in ways that look nothing like a hardware fault. See the
  camera-placement research in [docs/context.md](context.md)'s Vision
  section for the related constraint on keeping the camera pose itself
  fixed.

---

## First Power-On

For a freshly assembled arm, do the first torque-on with
`go_neutral.py --diagnostic` rather than a script that drives straight to a
stored goal position. A newly mounted servo horn has no guarantee it was
seated at the exact position the software expects — a full-speed move to
an assumed neutral pose on the very first power-up could be a large,
unexpected motion. Hold-to-move lets you confirm each joint's direction and
range by hand before trusting it to move on its own.

---

## Next Steps

Once both arms are mechanically assembled and IDs are confirmed on the bus,
per-joint calibration (`software/calibration/calibrate_lerobot.py`) and
neutral-pose capture (`record_neutral.py`) come next — see
[docs/context.md](context.md) for that procedure.
