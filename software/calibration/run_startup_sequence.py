#!/usr/bin/env python3
"""
run_startup_sequence.py — Move both arms to neutral, replay the recorded
startup sequence on both arms simultaneously, then carefully return both
arms to neutral.

The sequence is recorded on the leader only (set_startup_sequence.py) but
replayed identically on both arms — the same normalized values sent to
follower_* and leader_* — the shared-pose invariant record_neutral.py and
go_neutral.py already rely on for physically identical, drive_mode=0 arms.

Playback itself is an open-loop sync_write per recorded sample at the
recorded rate (no velocity/acceleration limiting — same as teleop.py's
control loop, since consecutive samples are already close together at
recording rate). The neutral moves before and after the sequence go
through go_neutral(), which IS velocity/acceleration-limited — that's the
"careful" part.

Can be used standalone or imported by other scripts (e.g. teleop.py):

  Standalone:
    conda activate lerobot
    python software/calibration/run_startup_sequence.py
    python software/calibration/run_startup_sequence.py --velocity 150 --acceleration 25

  Imported:
    from software.calibration.run_startup_sequence import run_startup_sequence
    run_startup_sequence(bus, neutral, sequence)

Arguments (standalone):
  --velocity      max joint speed in counts/s for the neutral moves before
                  and after the sequence (default: 100 ≈ 8.8°/s)
  --acceleration  ramp rate in counts/s² for the neutral moves (default: 20)
  --port          serial port (default: /dev/ttyACM0)

Prerequisites:
  - Both arms calibrated       (software/config/calibration_*.json)
  - Neutral pose captured      (software/config/neutral.json)
  - Startup sequence recorded  (software/config/startup_sequence.json,
    via set_startup_sequence.py)
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Add repo root (hexarm/) to path — NOT software/, which would shadow the
# pip-installed scservo_sdk with our local copy and break LeRobot imports.
# Needed here (unlike most calibration/ scripts) because this module is
# imported by teleop.py as well as run standalone.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from software.calibration.go_neutral import go_neutral  # noqa: E402

from lerobot.motors.feetech import FeetechMotorsBus
from lerobot.motors.motors_bus import Motor, MotorCalibration, MotorNormMode

# ── Constants ─────────────────────────────────────────────────────────────────

JOINT_NAMES   = ["shoulder_pan", "shoulder_lift", "elbow_flex",
                 "wrist_flex", "wrist_roll", "gripper"]
ARM_ID_OFFSET = {"follower": 0, "leader": 6}
DEFAULT_PORT  = "/dev/ttyACM0"
CONFIG_DIR    = Path("software/config")

DEFAULT_VELOCITY     = 100   # counts/s  ≈ 8.8°/s — matches go_neutral.py
DEFAULT_ACCELERATION = 20    # counts/s² — matches go_neutral.py

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing config file: {path}")
    with open(path) as f:
        return json.load(f)


def build_motors(arm: str, names: list[str], prefix: str = "") -> dict[str, Motor]:
    id_offset = ARM_ID_OFFSET[arm]
    return {
        f"{prefix}{name}": Motor(
            id=JOINT_NAMES.index(name) + 1 + id_offset,
            model="sts3215",
            norm_mode=MotorNormMode.RANGE_0_100,
        )
        for name in names
    }


def safe_enable_torque(bus: FeetechMotorsBus) -> None:
    """Write Goal_Position = Present_Position before enabling torque.
    Prevents servos from snapping to a stale goal on enable."""
    positions = bus.sync_read("Present_Position", normalize=False)
    for name, pos in positions.items():
        bus.write("Goal_Position", name, int(float(pos)), normalize=False)
    bus.enable_torque()


def play_sequence(bus: FeetechMotorsBus, sequence: dict) -> None:
    """Replay a recorded leader-arm trajectory onto both arms simultaneously."""
    hz      = sequence["hz"]
    samples = sequence["samples"]
    period  = 1 / hz
    print(f"Playing startup sequence — {len(samples)} samples at {hz} Hz "
          f"(~{len(samples) / hz:.1f}s)...")

    for sample in samples:
        t0 = time.monotonic()
        goals = {}
        for joint, value in sample.items():
            goals[f"follower_{joint}"] = value
            goals[f"leader_{joint}"]   = value
        bus.sync_write("Goal_Position", goals, normalize=True)
        elapsed = time.monotonic() - t0
        time.sleep(max(0.0, period - elapsed))

    print("Startup sequence playback done.")

# ── Orchestration ─────────────────────────────────────────────────────────────

def run_startup_sequence(
    bus: FeetechMotorsBus,
    neutral: dict[str, float],
    sequence: dict,
    velocity: int = DEFAULT_VELOCITY,
    acceleration: int = DEFAULT_ACCELERATION,
) -> None:
    """Neutral -> play the recorded sequence on both arms -> back to neutral."""
    print("Moving both arms to neutral before startup sequence...")
    go_neutral(bus, neutral, velocity=velocity, acceleration=acceleration)

    play_sequence(bus, sequence)

    print("Startup sequence complete — carefully returning to neutral...")
    go_neutral(bus, neutral, velocity=velocity, acceleration=acceleration)

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Move both arms to neutral, play the recorded startup sequence, then return to neutral")
    parser.add_argument("--velocity",     type=int, default=DEFAULT_VELOCITY,
                        help=f"Max speed in counts/s for the neutral moves (default: {DEFAULT_VELOCITY} ≈ 8.8°/s)")
    parser.add_argument("--acceleration", type=int, default=DEFAULT_ACCELERATION,
                        help=f"Ramp rate in counts/s² for the neutral moves (default: {DEFAULT_ACCELERATION})")
    parser.add_argument("--port",         default=DEFAULT_PORT)
    args = parser.parse_args()

    neutral_data  = load_json(CONFIG_DIR / "neutral.json")
    sequence_data = load_json(CONFIG_DIR / "startup_sequence.json")

    motors: dict[str, Motor] = {}
    calibration: dict[str, MotorCalibration] = {}
    neutral: dict[str, float] = {}

    for arm in ("follower", "leader"):
        cal_data = load_json(CONFIG_DIR / f"calibration_{arm}.json")
        active_joints = [n for n in JOINT_NAMES if n in cal_data and n in neutral_data]
        skipped = [n for n in JOINT_NAMES if n not in active_joints]
        if skipped:
            print(f"Skipping {arm} joints with missing calibration or neutral: {skipped}")

        prefix = f"{arm}_"
        calibration.update({f"{prefix}{n}": MotorCalibration(**cal_data[n]) for n in active_joints})
        neutral.update({f"{prefix}{n}": float(neutral_data[n]) for n in active_joints})
        motors.update(build_motors(arm, active_joints, prefix=prefix))

    if not neutral:
        raise RuntimeError("No joints to move — run calibrate_lerobot.py and record_neutral.py first.")

    bus = FeetechMotorsBus(port=args.port, motors=motors, calibration=calibration)
    bus.connect()
    print(f"Connected to {args.port}  ({len(motors)} motor(s))")

    safe_enable_torque(bus)
    run_startup_sequence(bus, neutral, sequence_data,
                          velocity=args.velocity, acceleration=args.acceleration)

    bus.disconnect(disable_torque=False)
    print("Torque left enabled — run torque_off.py if you want it disabled.")


if __name__ == "__main__":
    main()
