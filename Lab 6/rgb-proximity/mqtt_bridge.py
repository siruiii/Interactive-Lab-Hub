import json
import time
from threading import Lock
from typing import Dict

import paho.mqtt.client as mqtt

DEFAULTS = {
    "fallback_R": 0,
    "fallback_G": 0,
    "fallback_B": 0,
    "near_cm": 5,
    "far_cm": 80,
    "invert": False,
    "stale_after_seconds": 5.0,
    "mqtt_base_topic": "rgb/proximity",
    "channels": {},  # user should map pi_id -> R/G/B here
}

class RGBState:
    def __init__(self, cfg, sio):
        self.cfg = {**DEFAULTS, **cfg}  # merge defaults
        self.sio = sio
        self.lock = Lock()

        self.fallbacks = {
            "R": int(self.cfg.get("fallback_R", DEFAULTS["fallback_R"])),
            "G": int(self.cfg.get("fallback_G", DEFAULTS["fallback_G"])),
            "B": int(self.cfg.get("fallback_B", DEFAULTS["fallback_B"])),
        }

        self.channel_values = {"R": self.fallbacks["R"], "G": self.fallbacks["G"], "B": self.fallbacks["B"]}
        self.pi_last_seen: Dict[str, float] = {}
        self.pi_latest_cm: Dict[str, float] = {}

        # Build pi_id -> channel map; accept lower/upper case for channels
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

        out = {"R": self.fallbacks["R"], "G": self.fallbacks["G"], "B": self.fallbacks["B"]}
        active = {}

        for pi_id, channel in self.pi_to_channel.items():
            last_seen = self.pi_last_seen.get(pi_id, 0.0)
            is_active = (now - last_seen) <= stale_after
            active[pi_id] = is_active
            if is_active:
                cm = self.pi_latest_cm.get(pi_id)
                if cm is not None:
                    out[channel] = self._cm_to_255(cm)

        self.channel_values = out
        rgb = {"r": out["R"], "g": out["G"], "b": out["B"]}
        self.sio.emit("rgb_update", {"rgb": rgb, "active": active})

    def handle_proximity(self, pi_id: str, proximity_cm: float):
        with self.lock:
            self.pi_last_seen[pi_id] = time.time()
            self.pi_latest_cm[pi_id] = proximity_cm
            self._recompute_channels()

    def get_current_snapshot(self):
        with self.lock:
            stale_after = float(self.cfg.get("stale_after_seconds", DEFAULTS["stale_after_seconds"]))
            rgb = {"r": self.channel_values["R"], "g": self.channel_values["G"], "b": self.channel_values["B"]}
            active = {pi: (time.time() - self.pi_last_seen.get(pi, 0.0) <= stale_after)
                      for pi in self.pi_to_channel.keys()}
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

    def _on_connect(self, client, userdata, flags, rc):
        base = str(self.cfg.get("mqtt_base_topic", DEFAULTS["mqtt_base_topic"])).rstrip("/")
        topic = f"{base}/+"
        client.subscribe(topic, qos=0)
        print(f"[MQTT] Connected rc={rc}, subscribed to {topic}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode("utf-8", errors="ignore")
            data = json.loads(payload) if payload.strip().startswith("{") else {"proximity_cm": float(payload)}
        except Exception as e:
            print(f"[MQTT] Bad message on {msg.topic}: {e}")
            return

        try:
            base = str(self.cfg.get("mqtt_base_topic", DEFAULTS["mqtt_base_topic"])).rstrip("/")
            pi_id = msg.topic.split("/", 2)[-1]
        except Exception:
            return

        prox = None
        if "proximity_cm" in data:
            try:
                prox = float(data["proximity_cm"])
            except Exception:
                pass

        if prox is not None:
            self.rgb_state.handle_proximity(pi_id, prox)

    def start(self):
        host = self.cfg.get("mqtt_host", "localhost")
        port = int(self.cfg.get("mqtt_port", 1883))
        self.client.connect(host, port, keepalive=30)
        self.client.loop_start()

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()
