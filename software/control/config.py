# config.py
# Motor configuration for hexarm leader-follower system.
# Servo IDs must be assigned physically (via servo programmer) before first use.
# Port names use Pi 5 hardware UARTs — enable in /boot/firmware/config.txt:
#   UART0 is on by default → /dev/ttyAMA0  (GPIO 14 TX, GPIO 15 RX)
#   dtoverlay=uart3        → /dev/ttyAMA3  (GPIO 4  TX, GPIO 5  RX)
# Both buses use the 1k-resistor half-duplex wiring (TX → 1kΩ → data line ← RX).

from lerobot.motors.feetech import FeetechMotorsBus

# ---------------------------------------------------------------------------
# Joint definitions — order matches physical chain: base → tip
# Motors defined as (id, model) tuples.
# Leader IDs 1–6, Follower IDs 7–12
# ---------------------------------------------------------------------------

LEADER_MOTORS = {
    "shoulder_pan":   (1,  "sts3215"),
    "shoulder_raise": (2,  "sts3215"),
    "elbow_adduct":   (3,  "sts3215"),
    "wrist_adduct":   (4,  "sts3215"),
    "wrist_rotate":   (5,  "sts3215"),
    "claw":           (6,  "sts3215"),
}

FOLLOWER_MOTORS = {
    "shoulder_pan":   (7,  "sts3215"),
    "shoulder_raise": (8,  "sts3215"),
    "elbow_adduct":   (9,  "sts3215"),
    "wrist_adduct":   (10, "sts3215"),
    "wrist_rotate":   (11, "sts3215"),
    "claw":           (12, "sts3215"),
}

# ---------------------------------------------------------------------------
# Serial port assignments — Pi 5 hardware UARTs
# Confirm available ports with: ls /dev/ttyAMA* after enabling overlays.
# Leader   → UART0: GPIO 14 (TX), GPIO 15 (RX) → /dev/ttyAMA0  (default, no overlay needed)
# Follower → UART3: GPIO 4  (TX), GPIO 5  (RX) → /dev/ttyAMA3  (requires dtoverlay=uart3)
# ---------------------------------------------------------------------------

LEADER_PORT   = "/dev/ttyAMA0"
FOLLOWER_PORT = "/dev/ttyAMA3"
