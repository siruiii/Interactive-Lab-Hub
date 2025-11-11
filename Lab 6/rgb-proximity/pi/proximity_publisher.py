import argparse
import json
import math
import time
import paho.mqtt.client as mqtt

def mqtt_connect(host, port):
    client = mqtt.Client()
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.connect_async(host, port, keepalive=30)
    client.loop_start()
    return client

def map_raw_to_cm(raw, near_cm, far_cm):
    # APDS9960: raw 0..255 where ~255 is NEAR, 0 is FAR.
    raw = max(0, min(255, int(raw)))
    span = max(1e-6, (far_cm - near_cm))
    # invert: 255 -> near_cm, 0 -> far_cm
    cm = far_cm - (raw / 255.0) * (span)
    return round(cm, 2)

def publish_loop(pi_id: str, host: str, port: int, base_topic: str,
                 mode: str, trig_pin: int, echo_pin: int, hz: float,
                 near_cm: float, far_cm: float, debug: bool):
    topic = f"{base_topic.rstrip('/')}/{pi_id}"
    client = mqtt_connect(host, port)
    print(f"[{pi_id}] publishing to {topic} on {host}:{port} (mode={mode})")

    period = 1.0 / max(1e-6, hz)
    sensor = None

    if mode == "hcsr04":
        from gpiozero import DistanceSensor
        sensor = DistanceSensor(echo=echo_pin, trigger=trig_pin, max_distance=1.5)
        time.sleep(0.2)

    elif mode == "apds9960":
        import board
        from adafruit_apds9960.apds9960 import APDS9960
        i2c = board.I2C()
        sensor = APDS9960(i2c)
        sensor.enable_proximity = True
        time.sleep(0.1)

    t0 = time.time()
    try:
        while True:
            if mode == "mock":
                t = time.time() - t0
                cm = 42.5 + 37.5 * math.sin(t * 0.5)  # ~5..80cm demo
                payload = {"pi_id": pi_id, "proximity_cm": round(cm, 2)}

            elif mode == "hcsr04":
                meters = sensor.distance
                cm = max(2.0, min(200.0, round(meters * 100.0, 2)))
                payload = {"pi_id": pi_id, "proximity_cm": cm}

            else:  # apds9960
                raw = int(sensor.proximity)        # 0..255 (near≈255)
                cm  = map_raw_to_cm(raw, near_cm, far_cm)
                payload = {
                    "pi_id": pi_id,
                    "proximity_raw": raw,           # helpful for debugging
                    "proximity_cm": cm              # server expects this
                }

            client.publish(topic, json.dumps(payload), qos=0, retain=False)
            if debug:
                print(f"[{pi_id}] {payload}")
            time.sleep(period)
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pi-id", required=True, help="ID that server maps in [channels]")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--base-topic", default="rgb/proximity")
    ap.add_argument("--mode", choices=["mock", "hcsr04", "apds9960"], default="mock")
    ap.add_argument("--trig", type=int, default=17, help="BCM trigger pin (hcsr04)")
    ap.add_argument("--echo", type=int, default=18, help="BCM echo pin (hcsr04)")
    ap.add_argument("--hz", type=float, default=10.0, help="publish rate")
    ap.add_argument("--near-cm", type=float, default=5.0, help="APDS9960 map: raw255 -> near_cm")
    ap.add_argument("--far-cm", type=float, default=80.0, help="APDS9960 map: raw0 -> far_cm")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    publish_loop(
        args.pi_id, args.host, args.port, args.base_topic,
        args.mode, args.trig, args.echo, args.hz,
        args.near_cm, args.far_cm, args.debug
    )
