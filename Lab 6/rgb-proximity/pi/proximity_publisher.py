import argparse
import json
import math
import time
import paho.mqtt.client as mqtt

def publish_loop(pi_id: str, host: str, port: int, base_topic: str):
    topic = f"{base_topic.rstrip('/')}/{pi_id}"
    client = mqtt.Client()
    client.connect(host, port, keepalive=30)
    client.loop_start()
    print(f"[{pi_id}] publishing to {topic} on {host}:{port}")

    t0 = time.time()
    try:
        while True:
            # -------- MOCK MODE (default) --------
            t = time.time() - t0
            # oscillate between ~5 and ~80 cm
            cm = 42.5 + 37.5 * math.sin(t * 0.5)
            cm = round(cm, 2)

            # -------- HC-SR04 EXAMPLE (uncomment to use) --------
            # from gpiozero import DistanceSensor
            # sensor = DistanceSensor(echo=18, trigger=17, max_distance=1.0) # 1.0 m
            # cm = round(sensor.distance * 100.0, 2)
            # ------------------------------------

            payload = {"pi_id": pi_id, "proximity_cm": cm}
            client.publish(topic, json.dumps(payload), qos=0, retain=False)
            time.sleep(0.1)  # 10 Hz
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pi-id", required=True, help="must match a key in [channels] of config.toml (e.g., pi_red)")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--base-topic", default="rgb/proximity")
    args = ap.parse_args()
    publish_loop(args.pi_id, args.host, args.port, args.base_topic)
