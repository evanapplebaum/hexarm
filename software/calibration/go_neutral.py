#!/usr/bin/env python3
"""
go_neutral.py — Move both arms to the shared neutral pose.

Loads the single normalized neutral pose captured by record_neutral.py
(software/config/neutral.json) and drives BOTH arms to those exact same
normalized values, simultaneously, in one sync_write. Using one shared pose
instead of two separately-captured per-arm poses is what keeps the leader
and follower physically aligned at teleop startup — see record_neutral.py's
docstring for why that matters.

Sets Maximum_Velocity_Limit and Acceleration on each joint, commands
Goal_Position for all joints simultaneously, then polls Present_Position
until all joints are within ±1.0 of their targets (normalized 0–100).

Can be used standalone or imported by other scripts (e.g. teleop.py):

  Standalone:
    conda activate lerobot
    python software/calibration/go_neutral.py
    python software/calibration/go_neutral.py --velocity 200 --acceleration 30

  Imported:
    from software.calibration.go_neutral import go_neutral
    go_neutral(bus, neutral, velocity=100, acceleration=20)

Arguments (standalone):
  --velocity      max joint speed in counts/s (default: 100 ≈ 8.8°/s)
  --acceleration  ramp rate in counts/s² (default: 20)
  --port          serial port (default: /dev/ttyACM0)
  --diagnostic    dead-man's-switch mode: the arms only move while SPACE is
                   held down; releasing it freezes them in place immediately.
                   Press 'q' to abort (also freezes in place). Useful for
                   stepping a suspect move through by hand instead of letting
                   it run open-loop to completion.

Always moves both arms simultaneously on one bus (one sync_write for all
12 joints), the same prefixed-motor-name approach teleop.py uses.

Torque is left ENABLED on exit (standalone mode only — the importable
go_neutral() function never touches torque either way). Run torque_off.py
separately if you want it disabled afterward.
"""

import argparse
import json
import select
import sys
import termios
import time
import tty
from pathlib import Path

from lerobot.motors.feetech import FeetechMotorsBus
from lerobot.motors.motors_bus import Motor, MotorCalibration, MotorNormMode

# ── Constants ─────────────────────────────────────────────────────────────────

JOINT_NAMES   = ["shoulder_pan", "shoulder_lift", "elbow_flex",
                 "wrist_flex", "wrist_roll", "gripper"]
ARM_ID_OFFSET = {"follower": 0, "leader": 6}
DEFAULT_PORT  = "/dev/ttyACM0"
CONFIG_DIR    = Path("software/config")

DEFAULT_VELOCITY     = 50   # counts/s  ≈ 8.8°/s
DEFAULT_ACCELERATION = 10    # counts/s²
POSITION_TOLERANCE   = 1.0   # normalized units (0–100 scale)
POLL_HZ              = 50

# No key-up event exists over a raw SSH terminal, so "held" is inferred from
# your OS's keyboard auto-repeat: as long as another space arrives within this
# window, treat the key as still down. Too short and normal repeat gaps read
# as "released"; too long and releasing space doesn't freeze the arm promptly.
SPACE_HOLD_WINDOW = 0.2  # seconds

# ── Helpers ───────────────────────────────────────────────────────────────────

def _read_available_key() -> str | None:
    """Non-blocking single-char read from stdin; None if nothing waiting."""
    if select.select([sys.stdin], [], [], 0)[0]:
        return sys.stdin.read(1)
    return None


class _RawTerminal:
    """Puts stdin in raw mode (no echo/line-buffering) for the diagnostic loop."""

    def __enter__(self):
        self._fd = sys.stdin.fileno()
        self._old = termios.tcgetattr(self._fd)
        tty.setraw(self._fd)
        return self

    def __exit__(self, *exc_info):
        termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old)


def at_neutral(bus: FeetechMotorsBus, neutral: dict[str, float],
               tolerance: float = POSITION_TOLERANCE) -> bool:
    """True if every joint in `neutral` is already within `tolerance` of its target."""
    positions = bus.sync_read("Present_Position", normalize=True)
    return all(abs(float(positions[n]) - target) <= tolerance for n, target in neutral.items())


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


def go_neutral(
    bus: FeetechMotorsBus,
    neutral: dict[str, float],
    velocity: int = DEFAULT_VELOCITY,
    acceleration: int = DEFAULT_ACCELERATION,
    diagnostic: bool = False,
) -> None:
    """Move all joints to neutral positions and block until all arrive.

    Args:
        bus:          Open, torque-enabled FeetechMotorsBus.
        neutral:      Dict of {joint_name: target_normalized (0–100)}.
        velocity:     Maximum joint speed in counts/s.
        acceleration: Ramp rate in counts/s².
        diagnostic:   Dead-man's-switch mode — only advances toward neutral
                      while SPACE is held; releasing it freezes the arms in
                      place immediately. 'q' aborts (also freezes in place).
    """
    active_joints = list(neutral.keys())
    timeout = int(4096 / velocity) + 5  # generous: full range at chosen speed + 5s

    # Set motion profile on all joints
    for name in active_joints:
        bus.write("Maximum_Velocity_Limit", name, velocity,     normalize=False)
        bus.write("Acceleration",           name, acceleration, normalize=False)

    raw_term = _RawTerminal() if diagnostic else None
    held_until = 0.0
    aborted = False

    if diagnostic:
        print("DIAGNOSTIC MODE — hold SPACE to move, release to freeze in place. 'q' to abort.")
        raw_term.__enter__()
    else:
        # Fire all joints simultaneously
        bus.sync_write("Goal_Position", neutral, normalize=True)

    print(f"Moving {len(active_joints)} joints to neutral "
          f"(velocity={velocity}, accel={acceleration})...")

    t_start = time.time()
    try:
        while time.time() - t_start < timeout:
            if diagnostic:
                key = _read_available_key()
                if key == " ":
                    held_until = time.time() + SPACE_HOLD_WINDOW
                elif key == "q":
                    aborted = True
                    break

                if time.time() < held_until:
                    bus.sync_write("Goal_Position", neutral, normalize=True)
                else:
                    # Not held (or not yet pressed) — freeze exactly where we are.
                    current = bus.sync_read("Present_Position", normalize=False)
                    bus.sync_write(
                        "Goal_Position",
                        {n: int(float(current[n])) for n in active_joints},
                        normalize=False,
                    )

            positions = bus.sync_read("Present_Position", normalize=True)
            if all(abs(float(positions[n]) - neutral[n]) <= POSITION_TOLERANCE
                   for n in active_joints):
                break
            time.sleep(1 / POLL_HZ)
        else:
            # Loop completed without break — timed out
            positions = bus.sync_read("Present_Position", normalize=True)
            stalled = [n for n in active_joints
                       if abs(float(positions[n]) - neutral[n]) > POSITION_TOLERANCE]
            print(f"WARNING: timed out after {timeout}s. "
                  f"Joints not at target: {stalled}")
    finally:
        if raw_term is not None:
            raw_term.__exit__(None, None, None)

    if aborted:
        current = bus.sync_read("Present_Position", normalize=False)
        bus.sync_write(
            "Goal_Position",
            {n: int(float(current[n])) for n in active_joints},
            normalize=False,
        )
        print("Aborted by user ('q') — frozen in place.")
        return

    elapsed = time.time() - t_start

    # Restore motion profile to 0 (= no limit) so other scripts are unaffected
    for name in active_joints:
        bus.write("Maximum_Velocity_Limit", name, 0, normalize=False)
        bus.write("Acceleration",           name, 0, normalize=False)

    print(f"Done ({elapsed:.2f}s). Final positions:")
    final = bus.sync_read("Present_Position", normalize=True)
    for name in active_joints:
        print(f"  {name:<16}  {float(final[name]):.1f}  (target {neutral[name]:.1f})")

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Move both arms to the shared neutral pose")
    parser.add_argument("--velocity",     type=int, default=DEFAULT_VELOCITY,
                        help=f"Max speed in counts/s (default: {DEFAULT_VELOCITY} ≈ 8.8°/s)")
    parser.add_argument("--acceleration", type=int, default=DEFAULT_ACCELERATION,
                        help=f"Ramp rate in counts/s² (default: {DEFAULT_ACCELERATION})")
    parser.add_argument("--port",         default=DEFAULT_PORT)
    parser.add_argument("--diagnostic",   action="store_true",
                        help="Dead-man's-switch mode: hold SPACE to move, release to freeze in place")
    args = parser.parse_args()

    neutral_data = load_json(CONFIG_DIR / "neutral.json")

    motors: dict[str, Motor] = {}
    calibration: dict[str, MotorCalibration] = {}
    neutral: dict[str, float] = {}

    for arm in ("follower", "leader"):
        cal_data = load_json(CONFIG_DIR / f"calibration_{arm}.json")

        active_joints = [n for n in JOINT_NAMES if n in cal_data and n in neutral_data]
        skipped = [n for n in JOINT_NAMES if n not in active_joints]
        if skipped:
            print(f"Skipping {arm} joints with missing calibration or neutral: {skipped}")

        # Prefix motor names — both arms share one bus, so the identically-
        # named joints (e.g. "shoulder_pan") need disambiguating. Same
        # convention teleop.py uses. Both arms get the SAME neutral_data
        # values — that's what keeps them physically aligned.
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
    go_neutral(bus, neutral, velocity=args.velocity, acceleration=args.acceleration,
               diagnostic=args.diagnostic)

    # disable_torque=False: leave torque enabled on exit. FeetechMotorsBus's
    # default disconnect() disables torque, which was silently undoing the
    # whole point of moving to neutral. Run torque_off.py separately instead.
    bus.disconnect(disable_torque=False)
    print("Torque left enabled — run torque_off.py if you want it disabled.")


if __name__ == "__main__":
    main()
