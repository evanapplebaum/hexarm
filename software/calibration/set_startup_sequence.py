#!/usr/bin/env python3
"""
set_startup_sequence.py — Record a hand-performed motion sequence on the
leader arm, to be replayed on both arms by run_startup_sequence.py.

Both arms are driven to the shared neutral pose first — the same starting
point run_startup_sequence.py's playback begins from, so the recorded
trajectory doesn't jump on replay. Torque is then disabled on the leader
only (the follower stays enabled, holding neutral); move the leader by hand
while this records its Present_Position (normalized 0–100) at a fixed rate.
After a keypress, a 5-second countdown gives you time to get in position;
recording then runs for a fixed 5-second window.

Usage (from hexarm root, conda lerobot env):
  conda activate lerobot
  python software/calibration/set_startup_sequence.py

Arguments:
  --port  serial port (default: /dev/ttyACM0)

Prerequisites:
  - Both arms calibrated  (software/config/calibration_*.json)
  - Neutral pose captured (software/config/neutral.json, via record_neutral.py)

Output:
  software/config/startup_sequence.json
  {"hz": <int>, "samples": [{joint_name: normalized_value, ...}, ...]}
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Add repo root (hexarm/) to path — NOT software/, which would shadow the
# pip-installed scservo_sdk with our local copy and break LeRobot imports.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from software.calibration.go_neutral import at_neutral, go_neutral, safe_enable_torque  # noqa: E402

from lerobot.motors.feetech import FeetechMotorsBus
from lerobot.motors.motors_bus import Motor, MotorCalibration, MotorNormMode

# ── Constants ─────────────────────────────────────────────────────────────────

JOINT_NAMES = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]

ARM_ID_OFFSET = {"follower": 0, "leader": 6}
DEFAULT_PORT  = "/dev/ttyACM0"
CONFIG_DIR    = Path("software/config")

COUNTDOWN_SECONDS = 5
RECORD_SECONDS    = 10
RECORD_HZ         = 50   # matches teleop.py's default control-loop rate

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

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record a startup sequence performed by hand on the leader arm")
    parser.add_argument("--port", default=DEFAULT_PORT)
    args = parser.parse_args()

    neutral_data = load_json(CONFIG_DIR / "neutral.json")
    out_path     = CONFIG_DIR / "startup_sequence.json"

    # Build both arms on one bus — same prefixed-motor-name convention as
    # go_neutral.py/run_startup_sequence.py — so we can drive both to neutral
    # before recording, then selectively drop torque on the leader only.
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

    leader_motors = [name for name in motors if name.startswith("leader_")]

    bus = FeetechMotorsBus(port=args.port, motors=motors, calibration=calibration)
    bus.connect()
    print(f"Connected to {args.port}  ({len(motors)} motor(s))")

    safe_enable_torque(bus)
    if at_neutral(bus, neutral):
        print("Both arms already at neutral — skipping the move.")
    else:
        print("Moving both arms to neutral before recording...")
        go_neutral(bus, neutral)

    bus.disable_torque(leader_motors)
    print("\nTorque disabled on the leader only (follower holds neutral). "
          "Move the leader by hand to perform the startup sequence.")
    input("Press Enter to begin the countdown...\n")

    for remaining in range(COUNTDOWN_SECONDS, 0, -1):
        print(f"  Recording starts in {remaining}...")
        time.sleep(1)

    print(">>> RECORDING NOW <<<")

    period = 1 / RECORD_HZ
    samples: list[dict[str, float]] = []
    t_start = time.monotonic()
    while time.monotonic() - t_start < RECORD_SECONDS:
        t0 = time.monotonic()
        positions = bus.sync_read("Present_Position", leader_motors, normalize=True)
        samples.append({
            name.removeprefix("leader_"): round(float(pos), 2)
            for name, pos in positions.items()
        })
        elapsed = time.monotonic() - t0
        time.sleep(max(0.0, period - elapsed))

    print(f"Recording done — {len(samples)} samples over {RECORD_SECONDS}s (~{RECORD_HZ} Hz).")

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"hz": RECORD_HZ, "samples": samples}, f, indent=2)
    print(f"Saved to {out_path}")

    bus.disconnect()


if __name__ == "__main__":
    main()
