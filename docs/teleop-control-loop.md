# Teleop Control-Loop Design

Covers `software/control/teleop.py`'s steady-state loop and the startup
sequence around it. `record_dataset.py` runs the identical tick (see below)
with dataset-recording added on top — this doc is the shared reference for
both.

Related: [ADR 0002 — single-bus servo topology](adr/0002-single-bus-servo-topology.md)
for why one bus carries both arms at all.

## Architecture

One `FeetechMotorsBus` holds all 12 motors, named `follower_<joint>` /
`leader_<joint>` (`build_bus()`). Both arms share calibration-driven
normalization (`MotorNormMode.RANGE_0_100`), so a leader position and its
mirrored follower position are directly comparable numbers — no separate
coordinate transform between the two arms.

## Startup sequence (before the loop starts)

1. **Both arms torque-enabled**, via `safe_enable_torque()` — reads each
   motor's *current* position and writes it as `Goal_Position` before
   calling `enable_torque()`. Skipping this snaps the servo to whatever
   stale goal was left from a previous run the instant torque engages.
2. **Neutral → recorded startup sequence → neutral**, on both arms
   simultaneously, via `run_startup_sequence.py`. Both arms are driven to
   the identical normalized `neutral.json` values (see ADR 0002) so the
   follower doesn't jump when leader torque drops in the next step.
3. **Leader torque disabled** (`bus.disable_torque(motors=LEADER_NAMES)`) —
   operator moves it freely from here. Follower stays torque-enabled.

## The tick (`run_teleop()`)

```python
period = 1.0 / hz
while True:
    t0 = time.monotonic()

    leader_pos = bus.sync_read("Present_Position", motors=LEADER_NAMES, normalize=True)
    follower_goals = {f"follower_{j}": leader_pos[f"leader_{j}"] for j in JOINT_NAMES}
    bus.sync_write("Goal_Position", follower_goals, normalize=True)

    elapsed = time.monotonic() - t0
    time.sleep(max(0.0, period - elapsed))
```

- **One `sync_read` + one `sync_write` per tick**, each a single bus
  transaction covering all 6 joints of the relevant arm — not 6 individual
  reads/writes. This is the throughput reason a single shared bus is
  workable at all at 50 Hz.
- **1:1 normalized mapping**, leader → follower, no offset or scaling.
  Direction differences between physically-mirrored joints are absorbed by
  `drive_mode` in each motor's calibration, not by loop logic.
- **Drift-corrected timing**: `t0` is captured at the top of the loop, and
  the sleep is `period - elapsed`, not a flat `time.sleep(period)` — so a
  slow tick (a retried packet, a scheduler hiccup) shortens the next sleep
  instead of compounding a growing lag. `elapsed` clamped to ≥0 in case a
  tick ever takes *longer* than `period`.
- Default rate is 50 Hz (`DEFAULT_HZ`), overridable via `--hz`.

## Shutdown

`Ctrl-C` is caught around `run_teleop()`; the `finally` block disables
torque on all motors and disconnects the bus regardless of how the loop
exited — so an interrupted session never leaves a motor holding torque
against nothing watching it.

## Where `record_dataset.py` diverges

`record_episode()` in `record_dataset.py` runs the same
`sync_read(leader)` → `sync_write(follower)` → `sync_read(follower)` shape
per tick, plus:

- reads both cameras (`cam.read_latest()`) and resizes each frame to the
  dataset's recorded resolution,
- calls `dataset.add_frame()` with the combined observation/action dict
  every tick,
- polls for a single raw-terminal keypress (ENTER/`r`/`q`) each iteration
  instead of running unconditionally forever.

It does *not* use LeRobot's own `lerobot-record` — see
[ADR 0002](adr/0002-single-bus-servo-topology.md) for why the single-bus
layout rules that out, and `record_dataset.py`'s module docstring for the
full reasoning including the keyboard-input substitution.
