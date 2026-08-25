"""
torque_off.py — Disable torque on one or more STS3215 servos.

Usage (from hexarm root):
  python software/control/torque_off.py --all
"""

import os
import sys
import argparse
import readchar

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scservo_sdk import PortHandler, sms_sts, COMM_SUCCESS, SMS_STS_TORQUE_ENABLE

DEFAULT_PORT = "/dev/ttyACM0"
DEFAULT_BAUD = 1_000_000


def collect_ids():
    """Interactively collect servo IDs via readchar. SPACE to finish."""
    print("\nEnter servo IDs to disable torque on. ENTER to confirm each, SPACE when done.")
    id_list = []
    done = False
    while not done:
        print(f"\n  IDs so far: {id_list}  |  Enter next ID: ", end="", flush=True)
        current_input = ""
        while True:
            char = readchar.readkey()
            if char.isdigit():
                current_input += char
                print(char, end="", flush=True)
            elif char == readchar.key.SPACE:
                done = True
                break
            elif char == readchar.key.ENTER:
                if current_input:
                    id_list.append(int(current_input))
                break
    return id_list


def main():
    parser = argparse.ArgumentParser(description="Disable torque on one or more STS3215 servos.")
    parser.add_argument("--port", default=DEFAULT_PORT, help="Serial port (default: /dev/ttyACM0)")
    parser.add_argument("--baud", default=DEFAULT_BAUD, type=int, help="Baud rate (default: 1000000)")
    parser.add_argument("--all", action="store_true",
                        help="Disable torque on all 12 servos (IDs 1-12) without prompting")
    args = parser.parse_args()

    if args.all:
        id_list = list(range(1, 13))
    else:
        id_list = collect_ids()
        if not id_list:
            print("No IDs entered. Exiting.")
            return
    print(f"\nDisabling torque on IDs: {id_list}")

    port_handler = PortHandler(args.port)
    if not port_handler.openPort():
        print(f"Failed to open port {args.port}")
        return
    port_handler.setBaudRate(args.baud)
    servo = sms_sts(port_handler)

    for servo_id in id_list:
        result, error = servo.write1ByteTxRx(servo_id, SMS_STS_TORQUE_ENABLE, 0)
        if result != COMM_SUCCESS:
            print(f"[ID {servo_id}] TorqueDisable failed (result={result}, error={error})")
        else:
            print(f"[ID {servo_id}] Torque disabled.")

    port_handler.closePort()


if __name__ == "__main__":
    main()
