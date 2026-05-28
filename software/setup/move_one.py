



import os # talks to ubuntu
import argparse
import sys # talks to python
import readchar

# scsservo_sdk lives a level up from software/setup - lines 10 and 11 prepend that path so python looks in right place
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# sms_sts contains protocol_packet_handler (defines how to speak ST3215 serial)

from scservo_sdk import PortHandler, sms_sts, COMM_SUCCESS
# Path to limits file — relative to this script's location
LIMITS_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "limits.json")

# --- defaults ---
DEFAULT_PORT  = "/dev/ttyACM0"   # Jetson USB — override with --port /dev/cu.usbmodem* for Mac
DEFAULT_ID    = 1
DEFAULT_BAUD  = 1000000  # factory default for STS3215

"""
PUT SERVO LIMITS IN?

{ specific af
Position reg are in sram (see sms_sts) - posL = 56, posH = 57
Low byte: up to 1111 1111
High byte: up to 0000 1111
bitshift low << 8(?), bwAND? probs
}



READ CURRENT POSITION FROM SERVOES




OVERWRITE THE DESIRED POSITION REGISTER FOR EACH SERVO






ENABLE TORQUE
"""
def main():
    # parse input parameters
    parser = argparse.ArgumentParser(description="Ping a single STS3215 servo.")
    parser.add_argument("--port",  default=DEFAULT_PORT,  help="Serial port")
    parser.add_argument("--baud",  default=DEFAULT_BAUD,  type=int, help="Baud rate")
    args = parser.parse_args()

    print("\nEnter ID of servo you want to control. Press enter to confirm entry, esc when done entering")
    id_list = []
    done = False
    while not done:
        print("\nEnter ID: ")
        current_input = ""
        while True:
            char = readchar.readkey()
            print(repr(char))
            print(char, end="", flush=True)
            if char.isdigit():
                current_input += char
            elif char == readchar.key.ESC:
                done = True
                print(f"{done}")
                break
            elif char == readchar.key.ENTER:
                break
                
        




    # open_sdk_port returns tuple
    # port_handler gives access to serial port 
    # st is sms_sts object - access to WritePosEx, etc.
    print(f"Opening port {args.port} at {args.baud} baud...")
    port_handler, st = open_sdk_port(args.port, args.baud)

    print(f"Pinging servo ID {args.id}...")
    ok, model_number = ping_with_retry(st, args.id)


# when running ex. python3 move_one.py, python sets __name__ == __main__.
# this below code makes sure that only the main file runs and not other imported files
if __name__ == "__main__":
    main()