""" 
teleop.py
Author: Evan Applebaum
-------------
USECASE:
Allows user to set joint limits of a robotic arm (or similar device) one servo at
a time.

SETUP: 
Connect all servos to a single serial bus, and connect that bus to a servo driver module.
Many different setups are possible. In this case, we have Rasp pi 02w --GND TX RX--> Driver --> Power supply

USAGE:
Run from command line, specifying --id, --port, --baud as needed. Example:
python software/control/teleop.py --id 1 --baud 1000000

"""



import time
import serial
import argparse # for parsing command line arguments
import sys # for sys.exit() and sys.path manipulation

# Adds location of scservo_sdk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Define all of the parameters to pass into this file: --id, --port, and --baud. Also have 
# defaults for each

# set defaults
DEFAULT_ID = 1
DEFAULT_BAUD = 1000000
DEFAULT_PORT  = "/dev/ttyACM0"

# setup parser args
parser = argparse.ArgumentParser(
    prog="teleop.py",
    description="Teleop for setting joint limits of a robotic arm one servo at a time.",
    epilog="Example usage: python software/control/teleop.py --id 1 --baud 1000000 --port /dev/tty/AMA0")

parser.add_argument("--id", default = DEFAULT_ID, type = int)
parser.add_argument("--baud", default = DEFAULT_BAUD, type = int)
parser.add_argument("--port", default = DEFAULT_PORT)
args=parser.parse_args()

sys.path


