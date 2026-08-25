# ADR 0002 — Single-Bus Servo Topology (vs. LeRobot's Two-Bus Default)

**Status:** Accepted (confirmed working 2026-06-03)

## Context

LeRobot's built-in leader-follower examples assume one port per arm: a
`Teleoperator` (leader) and a `Robot` (follower) are constructed as two
independent objects, each normally opening its own serial port. hexarm has
one Waveshare Bus Servo Adapter (A) in active use — a second board is on
hand but not wired in.

Two ways to reconcile that with LeRobot's two-bus assumption:

1. Wire in the second board, run two ports, and match LeRobot's default
   layout exactly.
2. Daisy-chain both arms' servos onto the one bus already in use, and give
   every servo a unique ID across both arms instead of reusing IDs 1–6 on
   each port.

## Decision

Single bus. All 12 servos (6 per arm) are daisy-chained onto the one
Waveshare board, addressed by ID: follower 1–6, leader 7–12, both reachable
over one `/dev/ttyACM0`. Confirmed working end-to-end 2026-06-03.

Every custom control script (`teleop.py`, `record_dataset.py`, `go_neutral.py`,
etc.) constructs a single `FeetechMotorsBus` containing all 12 motors, with
motor names prefixed `follower_<joint>` / `leader_<joint>` to avoid collisions
in the shared dict — see `build_bus()` in `teleop.py` and `record_dataset.py`.

## Consequences

- **`lerobot-record` and friends don't work unmodified.** They construct
  Robot and Teleoperator as two independent objects that each expect to own
  a port; sharing one physical port between two independent bus instances
  isn't safe. This is why hexarm has its own `record_dataset.py` instead of
  using LeRobot's stock recording CLI — see that script's docstring for the
  full reasoning, including why its keyboard control also had to be
  reimplemented (LeRobot's `pynput`-based keyboard handling needs a
  display/event backend that doesn't exist over headless SSH; hexarm reuses
  the raw-termios reading pattern from `go_neutral.py --diagnostic` instead).
- **One shared neutral pose, not two.** Because both arms are physically
  identical (with respect to joint limits), driving both to the *same* normalized values
  keeps them aligned — this is what `record_neutral.py`/`go_neutral.py`
  rely on (capture the follower's pose once; apply it to both arms). Two
  independently hand-posed neutrals were never perfectly identical and caused the
  follower to snap the instant leader torque dropped at teleop startup —
  fixed 2026-08-01, see `docs/context.md`'s Neutral Pose Unification section.
- **Every `sync_read`/`sync_write` transaction now moves data for both arms
  in one call.** `teleop.py`'s control loop reads all 6 leader joints and
  writes all 6 follower goals as two bus transactions per tick, not four —
  see [teleop-control-loop.md](../teleop-control-loop.md).
- **A single dropped packet on the shared bus can affect either arm.**
  `num_retry=3` was added across `go_neutral.py`, `teleop.py`,
  `calibrate_lerobot.py`, `monitor_joints.py`, and `run_startup_sequence.py`
  after an unretried write crashed a session on one missed byte
  (2026-08-10) — a single-bus design makes bus-level reliability shared
  infrastructure for both arms at once, not an isolated per-arm concern.
