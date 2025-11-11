
"""
Pi Proximity Client
-------------------
Reads APDS9960 proximity and sends values to the RGB Proximity Server via WebSocket (Socket.IO).

Usage:
  python pi_client.py --server http://<SERVER_IP>:5000 --channel R
Options:
  --server URL       Server base (default http://localhost:5000)
  --mac XX:..        Override MAC address string (otherwise auto-detected best-effort)
  --channel R|G|B    Optional: pre-claim a color channel
  --interval 0.05    Seconds between samples (default 0.1)
"""
import argparse
import time
import socket
import uuid

import socketio  # pip install "python-socketio[client]"

def get_mac_string(override=None):
    if override:
        return override.lower()
    # Best-effort MAC string
    mac_num = uuid.getnode()
    mac_str = ':'.join(f"{(mac_num >> ele) & 0xff:02x}" for ele in range(40, -1, -8))
    return mac_str

def read_proximity():
    # Try real sensor first; else fall back to a synthetic value for dev
    try:
        import board
        from adafruit_apds9960.apds9960 import APDS9960
        i2c = board.I2C()
        apds = APDS9960(i2c)
        apds.enable_proximity = True
        val = apds.proximity  # 0..255
        return int(val)
    except Exception:
        # Dev mode: triangle wave 0..255
        t = time.time() % 2.0
        ramp = (t/2.0)*510
        val = int(ramp if ramp <= 255 else 510 - ramp)
        return val

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', default='http://localhost:5000')
    parser.add_argument('--mac')
    parser.add_argument('--channel', choices=['R','G','B'])
    parser.add_argument('--interval', type=float, default=0.1)
    args = parser.parse_args()

    mac = get_mac_string(args.mac)
    sio = socketio.Client()

    @sio.event
    def connect():
        print('Connected to server')
        if args.channel:
            sio.emit('identify', {'mac': mac, 'channel': args.channel})

    @sio.event
    def disconnect():
        print('Disconnected from server')

    sio.connect(args.server, transports=['websocket', 'polling'])

    try:
        while True:
            val = read_proximity()
            sio.emit('proximity', {'mac': mac, 'value': int(val)})
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        sio.disconnect()

if __name__ == '__main__':
    main()
