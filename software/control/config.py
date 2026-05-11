# config.py
# Motor configuration for hexarm leader-follower system.
# Servo IDs must be assigned physically (via servo programmer) before first use.
# Port names use Pi 5 hardware UARTs — enable in /boot/firmware/config.txt:
#   UART0 is on by default → /dev/ttyAMA0  (GPIO 14 TX, GPIO 15 RX)
#   dtoverlay=uart3        → /dev/ttyAMA3  (GPIO 4  TX, GPIO 5  RX)
# Both buses use the 1k-resistor half-duplex wiring (TX → 1kΩ → data line ← RX).

from lerobot.motors.feetech.feetech import FeetechMotorsBus, Motor

# ---------------------------------------------------------------------------
# Joint definitions — order matches physical chain: base → tip
# Leader IDs 1–6, Follower IDs 7–12
# ---------------------------------------------------------------------------

LEADER_MOTORS = {
    "shoulder_pan":   Motor(id=1,  model="sts3215"),
    "shoulder_raise": Motor(id=2,  model="sts3215"),
    "elbow_adduct":   Motor(id=3,  model="sts3215"),
    "wrist_adduct":   Motor(id=4,  model="sts3215"),
    "wrist_rotate":   Motor(id=5,  model="sts3215"),
    "claw":           Motor(id=6,  model="sts3215"),
}

FOLLOWER_MOTORS = {
    "shoulder_pan":   Motor(id=7,  model="sts3215"),
    "shoulder_raise": Motor(id=8,  model="sts3215"),
    "elbow_adduct":   Motor(id=9,  model="sts3215"),
    "wrist_adduct":   Motor(id=10, model="sts3215"),
    "wrist_rotate":   Motor(id=11, model="sts3215"),
    "claw":           Motor(id=12, model="sts3215"),
}

# ---------------------------------------------------------------------------
# Serial port assignments — Pi 5 hardware UARTs
# Confirm available ports with: ls /dev/ttyAMA* after enabling overlays.
# Leader   → UART0: GPIO 14 (TX), GPIO 15 (RX) → /dev/ttyAMA0  (default, no overlay needed)
# Follower → UART3: GPIO 4  (TX), GPIO 5  (RX) → /dev/ttyAMA3  (requires dtoverlay=uart3)
# ---------------------------------------------------------------------------

LEADER_PORT   = "/dev/ttyAMA0"
FOLLOWER_PORT = "/dev/ttyAMA3"
