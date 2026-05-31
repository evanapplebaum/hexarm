import os
import sys
import json
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scservo_sdk import (
    PortHandler, sms_sts, COMM_SUCCESS,
    SMS_STS_MIN_ANGLE_LIMIT_L, SMS_STS_MAX_ANGLE_LIMIT_L,
)

LIMITS_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "limits.json")

DEFAULT_PORT = "/dev/ttyACM0"
DEFAULT_BAUD = 1_000_000


def main():
    parser = argparse.ArgumentParser(description="Flash min/max angle limits from limits.json to servo EPROM.")
    parser.add_argument("--port", default=DEFAULT_PORT, help="Serial port (default: /dev/ttyACM0)")
    parser.add_argument("--baud", default=DEFAULT_BAUD, type=int, help="Baud rate (default: 1000000)")
    args = parser.parse_args()

    with open(LIMITS_FILE) as f:
        limits = json.load(f)

    port_handler = PortHandler(args.port)
    if not port_handler.openPort():
        print(f"Failed to open port {args.port}")
        return
    port_handler.setBaudRate(args.baud)
    servo = sms_sts(port_handler)

    print(f"Flashing angle limits for IDs: {list(limits.keys())}\n")

    for id_str, vals in limits.items():
        servo_id = int(id_str)

        # limits.json records in movement order — sort so EPROM min < max
        lo = min(vals["min"], vals["max"])
        hi = max(vals["min"], vals["max"])

        print(f"[ID {servo_id}]  min={lo}  max={hi}", end="  →  ")

        servo.unLockEprom(servo_id)
        r1, _ = servo.write2ByteTxRx(servo_id, SMS_STS_MIN_ANGLE_LIMIT_L, lo)
        r2, _ = servo.write2ByteTxRx(servo_id, SMS_STS_MAX_ANGLE_LIMIT_L, hi)
        servo.LockEprom(servo_id)

        if r1 == COMM_SUCCESS and r2 == COMM_SUCCESS:
            print("OK")
        else:
            print(f"FAILED (min result={r1}, max result={r2}) — not connected?")

    port_handler.closePort()


if __name__ == "__main__":
    main()
