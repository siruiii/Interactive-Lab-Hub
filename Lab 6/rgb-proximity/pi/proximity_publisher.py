import argparse
import json
import math
import time
import paho.mqtt.client as mqtt

def mqtt_connect(host, port):
    client = mqtt.Client()
    # Auto-retry if broker isn?t up yet
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.connect_async(host, port, keepalive=30)
    client.loop_start()
    return client

def publish_loop(pi_id: str, host: str, port: int, base_topic: str, mode: str,
                 trig_pin: int, echo_pin: int, debug: bool, hz: float):
    topic = f"{base_topic.rstrip('/')}/{pi_id}"
    client = mqtt_connect(host, port)
    print(f"[{pi_id}] publishing to {topic} on {host}:{port} (mode={mode})")

    period = 1.0 / max(1e-6, hz)
    t0 = time.time()

    sensor = None
    if mode == "hcsr04":
        from gpiozero import DistanceSensor
        # max_distance=1.0 (meters) ? ~100 cm. Tune if your space is larger.
        sensor = DistanceSensor(echo=echo_pin, trigger=trig_pin, max_distance=1.5)

        # give the sensor a moment to settle
        time.sleep(0.2)

    try:
        while True:
            if mode == "mock":
                t = time.time() - t0
                cm = 42.5 + 37.5 * math.sin(t * 0.5)  # ~5..80 cm
            else:
                # gpiozero returns meters; convert to cm
                meters = sensor.distance
                # handle occasional spurious spikes by clamping
                cm = max(2.0, min(200.0, round(meters * 100.0, 2)))

            payload = {"pi_id": pi_id, "proximity_cm": round(cm, 2)}
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
    ap.add_argument("--mode", choices=["mock", "hcsr04"], default="mock",
                    help="mock = simulated sine wave; hcsr04 = real sensor")
    ap.add_argument("--trig", type=int, default=17, help="BCM trigger pin (hcsr04)")
    ap.add_argument("--echo", type=int, default=18, help="BCM echo pin (hcsr04)")
    ap.add_argument("--hz", type=float, default=10.0, help="publish rate")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()
    publish_loop(args.pi_id, args.host, args.port, args.base_topic,
                 args.mode, args.trig, args.echo, args.debug, args.hz)
