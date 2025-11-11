import os
import json
import threading
from pathlib import Path

from flask import Flask, send_from_directory, jsonify
from flask_socketio import SocketIO
import tomli  # use tomllib on Python 3.11+

from mqtt_bridge import MQTTBridge, RGBState

DEFAULTS = {
    "mqtt_host": "localhost",
    "mqtt_port": 1883,
    "mqtt_base_topic": "rgb/proximity",
    "channels": {},
    "fallback_R": 0, "fallback_G": 0, "fallback_B": 0,
    "near_cm": 5, "far_cm": 80, "invert": False,
    "stale_after_seconds": 5.0,
}

def load_config():
    cfg_path = Path("config.toml")
    if not cfg_path.exists():
        cfg_path = Path("config.example.toml")
    if cfg_path.exists():
        with cfg_path.open("rb") as f:
            user_cfg = tomli.load(f)
    else:
        user_cfg = {}
    return {**DEFAULTS, **user_cfg}


cfg = load_config()
rgb_state = RGBState(cfg, socketio)
mqtt = MQTTBridge(cfg, rgb_state)
mqtt.start()

@app.route("/")
def index():
    return send_from_directory("web", "index.html")

@app.route("/index.css")
def css():
    return send_from_directory("web", "index.css")

@app.route("/api/snapshot")
def snapshot():
    return jsonify(rgb_state.get_current_snapshot())

@socketio.on("connect")
def on_connect():
    # push initial state to the new client
    socketio.emit("rgb_update", rgb_state.get_current_snapshot())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    print(f"Serving on http://localhost:{port}")
    socketio.run(app, host="0.0.0.0", port=port)
