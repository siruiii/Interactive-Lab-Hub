#!/usr/bin/env python3
import os, sys, json, queue, threading, time
import numpy as np
import sounddevice as sd
from vosk import Model, KaldiRecognizer
from PIL import Image, ImageDraw
import board, digitalio, adafruit_rgb_display.st7789 as st7789


# ---------------- Display (same pattern as clock.py) ----------------
cs_pin = digitalio.DigitalInOut(board.D5)
dc_pin = digitalio.DigitalInOut(board.D25)
reset_pin = None
BAUDRATE = 64_000_000


spi = board.SPI()
disp = st7789.ST7789(
    spi,
    cs=cs_pin,
    dc=dc_pin,
    rst=reset_pin,
    baudrate=BAUDRATE,
    width=135,
    height=240,
    x_offset=53,
    y_offset=40,
)


# Landscape like your clock: swap width/height then use rotation=90 to draw
height = disp.width
width  = disp.height
rotation = 90


backlight = digitalio.DigitalInOut(board.D22)
backlight.switch_to_output(); backlight.value = True


def clear_display(color=(0,0,0)):
    disp.image(Image.new("RGB", (width, height), color), rotation)


def show_image(path):
    """Open, rotate 180°, resize, and draw an image onto the ST7789."""
    print("show_image() path:", path)
    try:
        img = Image.open(path).convert("RGB")
        # Rotate all images by 180 degrees as requested
        img = img.rotate(180, expand=False)
        img = img.resize((width, height))
        disp.image(img, rotation)
        print("show_image() success")
    except Exception as e:
        print("show_image() ERROR:", repr(e))
        # Visible placeholder with error text
        img = Image.new("RGB", (width, height), (20,20,20))
        ImageDraw.Draw(img).text((10,10), "ERROR\n"+str(e), fill=(255,255,255))
        disp.image(img, rotation)


clear_display()


# ---------------- Vosk (like test_microphone.py) ----------------
audio_q = queue.Queue()
detected_ready = threading.Event()


try:
    SAMPLE_RATE = int(sd.query_devices(None, "input")["default_samplerate"])
except Exception:
    SAMPLE_RATE = 16000
print("Using SAMPLE_RATE:", SAMPLE_RATE)


try:
    model = Model(lang="en-us")
except Exception as e:
    print("Could not load Vosk model:", e); sys.exit(1)


# Keep [unk] in grammar so noise isn't forced into "ready"
recognizer = KaldiRecognizer(model, SAMPLE_RATE, '["ready", "[unk]"]')


SILENCE_RMS_THRESHOLD = 800   # raise if still too sensitive
CONF_THRESHOLD = 0.80         # confidence gate for the word "ready"


def audio_callback(indata, frames, time_info, status):
    if status: print("AUDIO STATUS:", status, file=sys.stderr)
    audio_q.put(bytes(indata))


def has_ready_with_conf(res_dict, min_conf=0.0):
    # Prefer wordlist confidence
    for w in res_dict.get("result", []):
        if w.get("word","").lower() == "ready":
            conf = float(w.get("conf", w.get("confidence", 0.0)))
            if conf >= min_conf:
                return True
    # Fallback: allow text like "[unk] ready" by stripping [unk]
    txt = res_dict.get("text","").strip().lower().replace("[unk]","").strip()
    return (txt == "ready")


def listen_for_ready():
    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=8192,
                           dtype="int16", channels=1, callback=audio_callback):
        print("Listening for final 'ready' ...")
        while not detected_ready.is_set():
            data = audio_q.get()
            # silence gate to reduce garbage finals
            rms = np.sqrt(np.mean(np.frombuffer(data, dtype=np.int16).astype(np.float64)**2))
            if rms < SILENCE_RMS_THRESHOLD:
                continue
            if recognizer.AcceptWaveform(data):
                res = json.loads(recognizer.Result())
                print("Final:", repr(res.get("text","")))
                if has_ready_with_conf(res, min_conf=CONF_THRESHOLD):
                    print("Detected 'ready' with sufficient confidence.")
                    detected_ready.set()
            else:
                pass  # ignore partials entirely


# ---------------- Main ----------------
if __name__ == "__main__":
    UI_DIR    = "UI"
    START_IMG = os.path.join(UI_DIR, "Start.png")
    NEXT_IMG  = os.path.join(UI_DIR, "1.png")


    print("CWD:", os.getcwd())
    print("START_IMG exists:", os.path.exists(START_IMG), "->", os.path.abspath(START_IMG))
    print("NEXT_IMG  exists:", os.path.exists(NEXT_IMG),  "->", os.path.abspath(NEXT_IMG))


    try:
        show_image(START_IMG)
        print("Displayed Start.png")


        t = threading.Thread(target=listen_for_ready, daemon=True)
        t.start()


        while not detected_ready.is_set():
            time.sleep(0.05)


        # Directly switch to 1.png (no red flash)
        show_image(NEXT_IMG)
        print("Displayed 1.png")


        while True:
            time.sleep(1)


    except KeyboardInterrupt:
        print("Exiting (KeyboardInterrupt).")
    finally:
        clear_display((0,0,0))
        backlight.value = False






