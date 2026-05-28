import os
import argparse
import sys
import json
import readchar

# scservo_sdk lives one level up from software/setup/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# sms_sts: STS/SMS series protocol class (wraps protocol_packet_handler)
# SMS_STS_TORQUE_ENABLE: register 40 (SRAM) — write 1 to enable, 0 to disable
from scservo_sdk import PortHandler, sms_sts, COMM_SUCCESS, SMS_STS_TORQUE_ENABLE

HOME_FILE   = os.path.join(os.path.dirname(__file__), "..", "config", "home.json")
LIMITS_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "limits.json")

DEFAULT_PORT = "/dev/ttyACM0"   # Jetson USB — override with --port /dev/cu.usbmodem* for Mac
DEFAULT_BAUD = 1_000_000        # STS3215 factory default

HOME_SPEED = 500    # steps/s — conservative startup speed (0 = uncontrolled max, don't use)
HOME_ACC   = 50     # units of ~100 steps/s² — gentle ramp so arm doesn't jerk on first move


def collect_ids():
    """Interactively collect servo IDs via readchar. SPACE to finish."""
    print("\nEnter servo IDs to control. ENTER to confirm each, SPACE when done.")
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
    parser = argparse.ArgumentParser(description="Ping servos, read position, then move to home.")
    parser.add_argument("--port", default=DEFAULT_PORT, help="Serial port (default: /dev/ttyACM0)")
    parser.add_argument("--baud", default=DEFAULT_BAUD, type=int, help="Baud rate (default: 1000000)")
    args = parser.parse_args()

    # --- collect IDs interactively ---
    id_list = collect_ids()
    if not id_list:
        print("No IDs entered. Exiting.")
        return
    print(f"\nControlling IDs: {id_list}")

    # --- load home positions ---
    # JSON keys are always strings; servo IDs are ints — use str(id) for lookup
    with open(HOME_FILE) as f:
        home_data = json.load(f)

    # --- open port ---
    port_handler = PortHandler(args.port)
    if not port_handler.openPort():
        print(f"Failed to open port {args.port}")
        return
    port_handler.setBaudRate(args.baud)

    # sms_sts wraps the port and exposes high-level servo commands
    servo = sms_sts(port_handler)

    # --- ping, read current position, move to home ---
    for servo_id in id_list:

        # ping confirms servo is alive and returns model number (expect 777 for STS3215)
        model_number, result, error = servo.ping(servo_id)
        if result != COMM_SUCCESS:
            print(f"[ID {servo_id}] Ping failed (result={result}, error={error}) — skipping.")
            continue
        print(f"[ID {servo_id}] Ping OK  model={model_number}")

        # read current position before enabling torque so we know where it is
        current_pos, result, error = servo.ReadPos(servo_id)
        if result != COMM_SUCCESS:
            print(f"[ID {servo_id}] ReadPos failed — skipping.")
            continue
        print(f"[ID {servo_id}] Current position: {current_pos}")

        # check home.json has an entry for this ID
        if str(servo_id) not in home_data:
            print(f"[ID {servo_id}] No home position in home.json — skipping move.")
            continue
        home_pos = home_data[str(servo_id)]

        # enable torque (write 1 to SRAM reg 40) — must be on before any position command
        result, error = servo.write1ByteTxRx(servo_id, SMS_STS_TORQUE_ENABLE, 1)
        if result != COMM_SUCCESS:
            print(f"[ID {servo_id}] TorqueEnable failed — skipping move.")
            continue

        # command move to home position at conservative speed/accel
        result, error = servo.WritePosEx(servo_id, home_pos, HOME_SPEED, HOME_ACC)
        if result != COMM_SUCCESS:
            print(f"[ID {servo_id}] WritePosEx failed (result={result}, error={error})")
        else:
            print(f"[ID {servo_id}] Moving to home: {home_pos}  (from {current_pos})")

    port_handler.closePort()


# python sets __name__ == "__main__" only when this file is run directly,
# not when it's imported — guards against accidental execution on import
if __name__ == "__main__":
    main()
