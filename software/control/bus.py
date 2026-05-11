# bus.py
# Bus connection, setup, and diagnostic helpers for hexarm.
# Import this module — do not run directly.

from lerobot.motors.feetech import FeetechMotorsBus
from config import (
    LEADER_MOTORS, FOLLOWER_MOTORS,
    LEADER_PORT, FOLLOWER_PORT,
)


def connect_buses() -> tuple[FeetechMotorsBus, FeetechMotorsBus]:
    """Open serial connections to both arms. Returns (leader_bus, follower_bus)."""
    leader_bus = FeetechMotorsBus(port=LEADER_PORT, motors=LEADER_MOTORS)
    follower_bus = FeetechMotorsBus(port=FOLLOWER_PORT, motors=FOLLOWER_MOTORS)

    leader_bus.connect()
    follower_bus.connect()

    print(f"Leader  bus connected  → {LEADER_PORT}")
    print(f"Follower bus connected → {FOLLOWER_PORT}")

    return leader_bus, follower_bus


def disconnect_buses(leader_bus: FeetechMotorsBus, follower_bus: FeetechMotorsBus) -> None:
    """Close both serial connections cleanly."""
    leader_bus.disconnect()
    follower_bus.disconnect()
    print("Both buses disconnected.")


def ping_all(bus: FeetechMotorsBus, label: str = "bus") -> bool:
    """
    Attempt to read Present_Position from every motor on the bus.
    Prints which motors respond and which don't.
    Returns True if all motors responded.
    """
    all_ok = True
    for name in bus.motors:
        try:
            bus.read("Present_Position", [name])
            print(f"  [{label}] {name} ✓")
        except Exception as e:
            print(f"  [{label}] {name} ✗  ({e})")
            all_ok = False
    return all_ok


def setup_leader(bus: FeetechMotorsBus) -> None:
    """
    Put leader arm into passive mode — torque disabled so the user can
    move it freely. Servos still stream position data over the bus.
    """
    bus.write("Torque_Enable", [0] * len(bus.motors))
    print("Leader torque disabled (passive mode).")


def setup_follower(bus: FeetechMotorsBus) -> None:
    """
    Put follower arm into active mode — torque enabled so it drives
    to whatever goal position is commanded.
    """
    bus.write("Torque_Enable", [1] * len(bus.motors))
    print("Follower torque enabled (active mode).")
