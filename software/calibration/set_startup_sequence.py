#!/usr/bin/env python3
"""
set_startup_sequence.py — Record a hand-performed motion sequence on the
leader arm, to be replayed on both arms by run_startup_sequence.py.

Torque is disabled on the leader only — move it by hand while this records
Present_Position (normalized 0–100) at a fixed rate. After a keypress, a
5-second countdown gives you time to get in position; recording then runs
for a fixed 5-second window.

Usage (from hexarm root, conda lerobot env):
  conda activate lerobot
  python software/calibration/set_startup_sequence.py

Arguments:
  --port  serial port (default: /dev/ttyACM0)

Output:
  software/config/startup_sequence.json
  {"hz": <int>, "samples": [{joint_name: normalized_value, ...}, ...]}
"""

import argparse
import json
import time
from pathlib import Path

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
RECORD_SECONDS    = 5
RECORD_HZ         = 50   # matches teleop.py's default control-loop rate

# ── Helpers ───────────────────────────────────────────────────────────────────

def build_motors(arm: str) -> dict[str, Motor]:
    id_offset = ARM_ID_OFFSET[arm]
    return {
        JOINT_NAMES[i]: Motor(
            id=i + 1 + id_offset,
            model="sts3215",
            norm_mode=MotorNormMode.RANGE_0_100,
        )
        for i in range(6)
    }


def load_calibration(arm: str) -> dict[str, MotorCalibration]:
    """Load calibration from JSON backup. Raises if file doesn't exist."""
    cal_path = CONFIG_DIR / f"calibration_{arm}.json"
    if not cal_path.exists():
        raise FileNotFoundError(
            f"No calibration file found at {cal_path}. "
            f"Run calibrate_lerobot.py --arm {arm} first."
        )
    with open(cal_path) as f:
        raw = json.load(f)
    return {name: MotorCalibration(**data) for name, data in raw.items()}

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record a startup sequence performed by hand on the leader arm")
    parser.add_argument("--port", default=DEFAULT_PORT)
    args = parser.parse_args()

    motors      = build_motors("leader")
    calibration = load_calibration("leader")
    out_path    = CONFIG_DIR / "startup_sequence.json"

    bus = FeetechMotorsBus(port=args.port, motors=motors, calibration=calibration)
    bus.connect()
    print(f"Connected to {args.port}")

    bus.disable_torque()
    print("\nTorque disabled. Get the leader arm ready to perform the startup sequence.")
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
        positions = bus.sync_read("Present_Position", normalize=True)
        samples.append({name: round(float(pos), 2) for name, pos in positions.items()})
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
