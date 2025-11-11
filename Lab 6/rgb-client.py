#!/usr/bin/env python3
"""
RGB Proximity Client (Socket.IO)
- Reads APDS9960 proximity (0..255)
- Sends to server as:  {"mac": "...", "value": 0-255}
- Optionally claims a channel on connect: {"mac": "...", "channel": "R|G|B"}


Usage:
  python rgb-client.py --server http://<SERVER_IP>:5000 --channel R
"""


import argparse
import time
import uuid
import socketio  # pip install "python-socketio[client]" websocket-client requests


def get_mac_string(override=None):
    if override:
        return override.lower()
    mac_num = uuid.getnode()
    return ':'.join(f"{(mac_num >> i) & 0xff:02x}" for i in range(40, -1, -8))


def read_proximity():
    """Return 0..255 from APDS9960 if available, else a smooth test wave."""
    try:
        import board
        from adafruit_apds9960.apds9960 import APDS9960
        i2c = board.I2C()
        apds = APDS9960(i2c)
        apds.enable_proximity = True
        return int(apds.proximity)
    except Exception:
        # Dev fallback: triangle wave 0..255
        t = time.time() % 2.0
        ramp = (t/2.0)*510
        return int(ramp if ramp <= 255 else 510 - ramp)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--server", default="http://localhost:5000")
    p.add_argument("--mac")
    p.add_argument("--channel", choices=["R","G","B"])
    p.add_argument("--interval", type=float, default=0.1)
    p.add_argument("--polling-only", action="store_true",
                   help="Force HTTP long-polling (no websockets)")
    args = p.parse_args()


    mac = get_mac_string(args.mac)


    # Set logger=True briefly if you need to debug namespaces/transports
    sio = socketio.Client()


    @sio.event
    def connect():
        print("Connected to", args.server)
        if args.channel:
            sio.emit("identify", {"mac": mac, "channel": args.channel})


    @sio.event
    def disconnect():
        print("Disconnected")


    transports = ["polling"] if args.polling_only else ["websocket", "polling"]
    sio.connect(args.server, transports=transports)  # default namespace "/"


    try:
        while True:
            val = max(0, min(255, int(read_proximity())))
            sio.emit("proximity", {"mac": mac, "value": val})  # default namespace
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        sio.disconnect()


if __name__ == "__main__":
    main()






