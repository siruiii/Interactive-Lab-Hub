import json
import time
from threading import Lock
from typing import Dict, Optional

import paho.mqtt.client as mqtt

class RGBState:
    def __init__(self, cfg, sio):
        self.cfg = cfg
        self.sio = sio
        self.lock = Lock()
        # Track last reading for each channel and last-seen timestamps per pi_id
        self.channel_values = {"R": cfg["fallback_R"], "G": cfg["fallback_G"], "B": cfg["fallback_B"]}
        self.pi_last_seen: Dict[str, float] = {}
        self.pi_latest_cm: Dict[str, float] = {}

        # Build pi_id -> channel map from cfg['channels']
        self.pi_to_channel = {}
        for pi_id, ch in cfg["channels"].items():
            ch = ch.upper()
            if ch not in ("R", "G", "B"):
                raise ValueError(f"Invalid channel '{ch}' for {pi_id}. Must be R/G/B.")
            self.pi_to_channel[pi_id] = ch

    def _cm_to_255(self, cm: float) -> int:
        near_cm = float(self.cfg["near_cm"])
        far_cm = float(self.cfg["far_cm"])
        cm = max(min(cm, far_cm), near_cm)
        # Normalize: near => 1.0, far => 0.0
        t = 1.0 - (cm - near_cm) / max(far_cm - near_cm, 1e-6)
        val = int(round(255 * t))
        if self.cfg.get("invert", False):
            val = 255 - val
        return max(0, min(255, val))

    def _recompute_channels(self):
        """Compute R/G/B with fallbacks for any missing/stale pi."""
        now = time.time()
        stale_after = float(self.cfg["stale_after_seconds"])

        # Start with fallbacks
        out = {
            "R": self.cfg["fallback_R"],
            "G": self.cfg["fallback_G"],
            "B": self.cfg["fallback_B"],
        }

        active = {}
        # For each known pi -> channel, if fresh, convert cm -> 0..255
        for pi_id, channel in self.pi_to_channel.items():
            last_seen = self.pi_last_seen.get(pi_id, 0.0)
            is_active = (now - last_seen) <= stale_after
            active[pi_id] = is_active
            if is_active:
                cm = self.pi_latest_cm.get(pi_id)
                if cm is not None:
                    out[channel] = self._cm_to_255(cm)

        self.channel_values = out
        # Also compute combined color
        rgb = {"r": out["R"], "g": out["G"], "b": out["B"]}
        # Broadcast to web clients
        self.sio.emit("rgb_update", {"rgb": rgb, "active": active})

    def handle_proximity(self, pi_id: str, proximity_cm: float):
        with self.lock:
            self.pi_last_seen[pi_id] = time.time()
            self.pi_latest_cm[pi_id] = proximity_cm
            self._recompute_channels()

    def get_current_snapshot(self):
        with self.lock:
            rgb = {"r": self.channel_values["R"], "g": self.channel_values["G"], "b": self.channel_values["B"]}
            active = {pi: (time.time() - self.pi_last_seen.get(pi, 0.0) <= float(self.cfg["stale_after_seconds"]))
                      for pi in self.pi_to_channel.keys()}
            return {"rgb": rgb, "active": active}

class MQTTBridge:
    def __init__(self, cfg, rgb_state: RGBState):
        self.cfg = cfg
        self.rgb_state = rgb_state
        self.client = mqtt.Client()
        user = (self.cfg.get("mqtt_username") or "").strip()
        pw = (self.cfg.get("mqtt_password") or "").strip()
        if user:
            self.client.username_pw_set(user, pw)

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        base = self.cfg["mqtt_base_topic"].rstrip("/")
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

        # Expect topic: <base>/<pi_id>
        try:
            base = self.cfg["mqtt_base_topic"].rstrip("/")
            pi_id = msg.topic.split("/", 2)[-1]  # after base/
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
        self.client.connect(self.cfg["mqtt_host"], int(self.cfg["mqtt_port"]), keepalive=30)
        self.client.loop_start()

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()
