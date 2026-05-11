import time
from bus import connect_buses, disconnect_buses, ping_all, setup_leader, setup_follower

def main():
    leader, follower = connect_buses()

    ping_all(leader, "leader")
    ping_all(follower, "follower")

    setup_leader(leader)
    setup_follower(follower)

    try:
        while True:
            pos = leader.read("Present_Position")
            follower.write("Goal_Position", pos)
            time.sleep(1/50)  # 50 Hz

    except KeyboardInterrupt:
        print("Stopping...")

    finally:
        disconnect_buses(leader, follower)

if __name__ == "__main__":
    main()