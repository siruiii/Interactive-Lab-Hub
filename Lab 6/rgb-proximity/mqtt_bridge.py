# mqtt_bridge.py — raw-first, inactive=0

import json
import time
from threading import Lock
from typing import Dict

import paho.mqtt.client as mqtt

DEFAULTS = {
    "near_cm": 5,
    "far_cm": 80,
    "invert": False,
    "stale_after_seconds": 5.0,
    "mqtt_base_topic": "rgb/proximity",
    "channels": {},  # map: pi_id -> "R"/"G"/"B"
}

def clamp_byte(v):
    try:
        v = int(v)
    except Exception:
        return None
    return max(0, min(255, v))

class RGBState:
    def __init__(self, cfg, sio):
        self.cfg = {**DEFAULTS, **cfg}
        self.sio = sio
        self.lock = Lock()

        # current RGB to show on UI
        self.channel_values = {"R": 0, "G": 0, "B": 0}

        # latest per-pi 0..255 value & last-seen time
        self.pi_latest_v: Dict[str, int] = {}
        self.pi_last_seen: Dict[str, float] = {}

        # pi_id -> channel map
        self.pi_to_channel = {}
        for pi_id, ch in (self.cfg.get("channels") or {}).items():
            ch = str(ch).upper()
            if ch in ("R", "G", "B"):
                self.pi_to_channel[str(pi_id)] = ch

    def _cm_to_255(self, cm: float) -> int:
        near_cm = float(self.cfg.get("near_cm", DEFAULTS["near_cm"]))
        far_cm = float(self.cfg.get("far_cm", DEFAULTS["far_cm"]))
        cm = max(min(cm, far_cm), near_cm)
        t = 1.0 - (cm - near_cm) / max(far_cm - near_cm, 1e-6)  # near→1, far→0
        val = int(round(255 * t))
        if bool(self.cfg.get("invert", DEFAULTS["invert"])):
            val = 255 - val
        return max(0, min(255, val))

    def _recompute_channels(self):
        now = time.time()
        stale_after = float(self.cfg.get("stale_after_seconds", DEFAULTS["stale_after_seconds"]))

        # start at zeros; inactive Pis will remain 0
        out = {"R": 0, "G": 0, "B": 0}
        active = {}

        for pi_id, channel in self.pi_to_channel.items():
            last_seen = self.pi_last_seen.get(pi_id, 0.0)
            is_active = (now - last_seen) <= stale_after
            active[pi_id] = is_active
            if is_active and pi_id in self.pi_latest_v:
                out[channel] = self.pi_latest_v[pi_id]

        self.channel_values = out
        rgb = {"r": out["R"], "g": out["G"], "b": out["B"]}
        self.sio.emit("rgb_update", {"rgb": rgb, "active": active})

    def handle_payload(self, pi_id: str, data: dict):
        # prefer raw if available
        v = None
        if "proximity_raw" in data:
            v = clamp_byte(data["proximity_raw"])
        elif "proximity_cm" in data:
            try:
                cm = float(data["proximity_cm"])
                v = self._cm_to_255(cm)
            except Exception:
                v = None

        if v is None:
            return

        with self.lock:
            self.pi_last_seen[pi_id] = time.time()
            self.pi_latest_v[pi_id] = v
            self._recompute_channels()

    def get_current_snapshot(self):
        with self.lock:
            stale_after = float(self.cfg.get("stale_after_seconds", DEFAULTS["stale_after_seconds"]))
            now = time.time()
            # build active map and RGB exactly like _recompute_channels
            out = {"R": 0, "G": 0, "B": 0}
            active = {}
            for pi_id, channel in self.pi_to_channel.items():
                is_active = (now - self.pi_last_seen.get(pi_id, 0.0)) <= stale_after
                active[pi_id] = is_active
                if is_active and pi_id in self.pi_latest_v:
                    out[channel] = self.pi_latest_v[pi_id]

            rgb = {"r": out["R"], "g": out["G"], "b": out["B"]}
            return {"rgb": rgb, "active": active}

class MQTTBridge:
    def __init__(self, cfg, rgb_state: RGBState):
        self.cfg = {**DEFAULTS, **cfg}
        self.rgb_state = rgb_state
        self.client = mqtt.Client()

        user = (self.cfg.get("mqtt_username") or "").strip()
        pw = (self.cfg.get("mqtt_password") or "").strip()
        if user:
            self.client.username_pw_set(user, pw)

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = lambda c, u, rc: (
            print(f"[MQTT] Unexpected disconnect rc={rc}; auto-reconnect") if rc != 0 else None
        )

    def _on_connect(self, client, userdata, flags, rc):
        base = str(self.cfg.get("mqtt_base_topic", DEFAULTS["mqtt_base_topic"])).rstrip("/")
        topic = f"{base}/+"
        client.subscribe(topic, qos=0)
        print(f"[MQTT] Connected rc={rc}, subscribed to {topic}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode("utf-8", errors="ignore")
            data = json.loads(payload) if payload.strip().startswith("{") else {}
        except Exception as e:
            print(f"[MQTT] Bad message on {msg.topic}: {e}")
            return

        # topic format: <base>/<pi_id>
        try:
            pi_id = msg.topic.split("/", 2)[-1]
        except Exception:
            return

        self.rgb_state.handle_payload(pi_id, data)

    def start(self):
        host = self.cfg.get("mqtt_host", "localhost")
        port = int(self.cfg.get("mqtt_port", 1883))
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        try:
            self.client.connect_async(host, port, keepalive=30)
        except Exception as e:
            print(f"[MQTT] connect_async failed immediately: {e}")
        self.client.loop_start()

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()
