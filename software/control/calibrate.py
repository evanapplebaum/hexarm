import json
from bus import connect_buses, disconnect_buses, setup_leader, ping_all

LIMITS_FILE = "../../config/limits.json"

def main():
    leader, _ = connect_buses()

    ping_all(leader, "leader")
    setup_leader(leader)

    limits = {}
    joints = list(leader.motors.keys())

    for joint in joints:
        print(f"\nJoint: {joint}")
        input("Move to LOWER limit, then press Enter...")
        lower = leader.read("Present_Position", [joint])[joint]

        input("Move to UPPER limit, then press Enter...")
        upper = leader.read("Present_Position", [joint])[joint]

        limits[joint] = {"min": lower, "max": upper}

    with open(LIMITS_FILE, "w") as f:
        json.dump(limits, f, indent=4)

    disconnect_buses(leader, _)
    print(f"Limits saved to {LIMITS_FILE}")

if __name__ == "__main__":
    main()
