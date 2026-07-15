# Handoff: LeRobot Calibration — Encoder Wrap-Around

**Date:** 2026-05-31  
**For:** Claude Opus  
**Project:** hexarm — leader/follower robotic arm (SO-100 design, STS3215 servos)  
**Repo:** github.com/evanapplebaum/hexarm  
**Context file:** `docs/context.md` (read this for full project background)

---

## What We're Trying to Do

Calibrate both arms using LeRobot's `FeetechMotorsBus` so that:
1. Joint positions are expressed in normalized values (0–100%) rather than raw encoder counts
2. The same normalized value on both arms corresponds to the same physical angle
3. A "neutral pose" can be defined and both arms moved there before teleoperation begins

---

## Hardware

- **Servos:** FEETECH STS3215 — 12-bit absolute magnetic encoder, 0–4095 counts per revolution
- **Bus:** Both arms on one serial bus (`/dev/ttyACM0`), one Waveshare Bus Servo Adapter (A)
- **IDs:** Follower arm = 1–6, Leader arm = 7–12
- **Compute:** Jetson Orin Nano Super, conda env `lerobot` at `/data/miniconda3/envs/lerobot/`
- **LeRobot:** installed at `/data/lerobot` via `pip install -e ".[feetech]"`

---

## The Problem: Encoder Wrap-Around

### What it is

The STS3215 uses a 12-bit absolute magnetic encoder. Its value counts 0→4095 over one full rotation, then wraps back to 0. If a joint's physical travel range (defined by PLA mechanical stops) happens to straddle the 0↔4095 boundary, the encoder reading jumps from 4095→0 mid-motion.

### Confirmed on leader arm shoulder_lift (ID=8)

Physical stops measured with a streaming read script:
- **Stop A:** raw 1855  
- **Stop B:** raw 202  
- **Motion direction:** Going UP from 1855 → 2000 → 3000 → 4095 → 0 → 202  
- **Physical span:** (4096 − 1855) + 202 = **2443 counts ≈ 214°**

The encoder physically traverses the 0/4095 boundary during normal joint motion.

### Suspected on wrist_flex (ID=10)

Physical stops: raw 2448 and 3970. During calibration run, recorded min=0, max=4095. Not yet confirmed with streaming diagnostic (shoulder_lift was confirmed; wrist_flex not tested yet).

### Clean joints (no wrap)

| Joint | ID | Stop A | Stop B | Span |
|---|---|---|---|---|
| shoulder_pan | 7 | 944 | 3337 | 2393 counts (~210°) |
| elbow_flex | 9 | 831 | 3149 | 2318 counts (~203°) |

---

## What We've Tried and Why It Doesn't Work

### Attempt 1: `set_half_turn_homings` then `record_ranges_of_motion`

`set_half_turn_homings()` reads current position, computes `homing_offset = 2047 - present_pos`, writes it to servo EPROM.

For shoulder_lift, center of physical travel (in the wrap path) is at raw ~3076:
- `homing_offset = 2047 - 3076 = -1029`
- Stop A (raw 1855): homed = 1855 + (−1029) = **826** ✓
- Stop B (raw 202): homed = 202 + (−1029) = **−827** ✗

`write_calibration` then tries to write range_min = −827 to the servo's `Min_Position_Limit` EPROM register, which is unsigned → `ValueError: Negative values are not allowed: -827`.

### Attempt 2: Clear homing offsets, per-joint sweep

Updated `calibrate_lerobot.py` to:
1. Write `Homing_Offset = 0` to all motors (clear stale EPROM offsets from previous runs)
2. Sweep each joint individually (to avoid gravity swinging unsupported joints)
3. Record raw min/max
4. Compute `homing_offset = 2047 - raw_mid`
5. Write homing offset and derive homed limits

This correctly handles non-wrapping joints. For wrapping joints, the same negative-value problem occurs.

### Root issue

A single linear homing offset cannot simultaneously keep both physical stops within [0, 4095] when the encoder traverses the 0/4095 boundary between them. Any offset that centers the "wrap path" will make one stop negative in homed coordinates.

---

## LeRobot API (confirmed signatures, 2026-05-31)

```python
from lerobot.motors.feetech import FeetechMotorsBus
from lerobot.motors.motors_bus import Motor, MotorCalibration, MotorNormMode

# Constructor
FeetechMotorsBus(port: str, motors: dict[str, Motor],
                 calibration: dict[str, MotorCalibration] | None = None,
                 protocol_version: int = 0)

# Motor
Motor(id: int, model: str, norm_mode: MotorNormMode,
      motor_type_str: str | None = None, recv_id: int | None = None)

# MotorCalibration
MotorCalibration(id: int, drive_mode: int, homing_offset: int,
                 range_min: int, range_max: int)

# MotorNormMode
MotorNormMode.RANGE_0_100     # 0–100%
MotorNormMode.RANGE_M100_100  # –100 to +100
MotorNormMode.DEGREES

# Key methods
bus.connect() / bus.disconnect()
bus.enable_torque(motors=None) / bus.disable_torque(motors=None)
bus.read(data_name, motor, *, normalize=True) -> Value
bus.write(data_name, motor, value, *, normalize=True)
bus.sync_read(data_name, motors=None, *, normalize=True) -> dict[str, Value]
bus.sync_write(data_name, values, *, normalize=True)
bus.set_half_turn_homings(motors=None) -> dict[NameOrID, Value]
bus.record_ranges_of_motion(motors=None, display_values=True) -> tuple[dict, dict]
bus.write_calibration(calibration_dict, cache=True)  # writes Homing_Offset + Min/Max_Position_Limit to EPROM
bus.read_calibration() -> dict[str, MotorCalibration]
bus.apply_drive_mode(motors=None)  # exists — signature unknown
```

**Unverified:** Whether `normalize=False` returns raw encoder values or homing-offset-adjusted values. Empirically it appears to return raw (since wrist_flex showed POS=1180, not ~2047 after homing was set).

**Available but unused:** `bus.apply_drive_mode()`, `bus.broadcast_ping()`, `bus.scan_port()`, `bus.setup_motor()`

---

## Current State of calibrate_lerobot.py

Located at `software/control/calibrate_lerobot.py`. Implements:
- Clear stale homing offsets (Step 1)
- Per-joint sweep via `record_ranges_of_motion(motors=[name])` (Step 2)
- Compute `homing_offset = 2047 - raw_mid`, write to EPROM (Step 3)
- Derive homed limits = raw_limits + homing_offset (Step 4)
- `write_calibration` + JSON backup (Steps 5–6)

**Works correctly for non-wrapping joints.** Fails for wrapping joints at Step 4/5 when homed limit is negative.

---

## Questions for Opus

1. **How does LeRobot's reference SO-100 calibration handle wrap-around joints?** The SO-100 is the exact hardware this project is based on. Does the reference implementation assume no wrap-around (i.e., correct servo mounting), or does it have explicit handling for it? Check `/data/lerobot/` on the Jetson — there may be SO-100-specific calibration scripts or documentation.

2. **What does `drive_mode` actually do for Feetech/STS3215 servos?** Does it flip the encoder direction? If `drive_mode=1` reverses the encoder, then the wrap-around joint's range would be represented as the "short path" (1653 counts, ~145°, no wrap) rather than the "long path" (2443 counts, ~214°, wraps). Is this a valid approach? What physical angle range would be lost?

3. **Is there a way to configure calibration so that `range_min` can be negative** (purely in software, not written to EPROM)? The `write_calibration` call both writes to EPROM AND caches in `self.calibration`. Could we set calibration in memory only (no EPROM write) and use it for normalization? What does `write_calibration(cache=False)` do vs `cache=True`?

4. **Is the correct fix to physically remount the servo?** If so, what encoder position should the servo be in relative to the joint link to guarantee no wrap-around for a joint with ~214° travel? (The encoder boundary must be outside the 214° travel arc.)

5. **Verify wrist_flex (ID=10) wrap-around.** Run the streaming diagnostic on wrist_flex with stops at raw 2448 and 3970 — does it traverse the boundary?

---

## Diagnostic Command

```bash
# SSH into Jetson first:
ssh evan0h@eka-orin.local
conda activate lerobot
cd ~/evdev/hexarm

# Stream position of any motor
python -c "
from lerobot.motors.feetech import FeetechMotorsBus
from lerobot.motors.motors_bus import Motor, MotorNormMode
import time
bus = FeetechMotorsBus(port='/dev/ttyACM0', motors={
    'joint': Motor(id=8, model='sts3215', norm_mode=MotorNormMode.RANGE_0_100),  # change id as needed
})
bus.connect(); bus.disable_torque()
while True:
    v = bus.read('Present_Position', 'joint', normalize=False)
    print(f'\r  {int(v):4d}', end='', flush=True)
    time.sleep(0.05)
"
```

---

## What We Do NOT Need

- A re-explanation of what calibration is or why it's needed
- Suggestions to switch to a different servo library
- The full LeRobot training pipeline — today's goal is calibration only

---

## Desired Output

A working `calibrate_lerobot.py` (or corrections to the existing one) that correctly calibrates both wrapping and non-wrapping joints, producing valid `MotorCalibration` objects that LeRobot can use for normalization.
