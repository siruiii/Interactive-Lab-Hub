# SPDX-FileCopyrightText: 2025
# SPDX-License-Identifier: MIT
"""Music player controlled by APDS9960 proximity sensor (low-pass) and rotary encoder (pitch)."""


import time
import board
import numpy as np
import sounddevice as sd
import soundfile as sf
from scipy import signal
import threading
from adafruit_apds9960.apds9960 import APDS9960
from adafruit_seesaw import seesaw, rotaryio, digitalio


# ==============================
# Hardware init
# ==============================
i2c = board.I2C()


# APDS9960 proximity sensor
apds = APDS9960(i2c)
apds.enable_proximity = True


# Rotary encoder (Seesaw)
ss = seesaw.Seesaw(i2c, addr=0x36)
seesaw_product = (ss.get_version() >> 16) & 0xFFFF
print("Found seesaw product {}".format(seesaw_product))
if seesaw_product != 4991:
    print("Warning: Expected product 4991")


# Encoder button
ss.pin_mode(24, ss.INPUT_PULLUP)
button = digitalio.DigitalIO(ss, 24)
button_held = False


# Encoder
encoder = rotaryio.IncrementalEncoder(ss)


# ==============================
# Music files
# ==============================
MUSIC_FOLDER = "music"
MUSIC_FILES = ["1.mp3", "2.mp3", "3.mp3"]
current_song_index = 0


# ==============================
# Control ranges
# ==============================
PROXIMITY_MIN = 0
PROXIMITY_MAX = 255


# Low-pass cutoff mapping (Hz): far = bright, close = muffled
LPF_CUTOFF_MIN = 300.0    # very muffled (hand close, prox=255)
LPF_CUTOFF_MAX = 8000.0   # bright (hand far, prox=0)
LPF_SMOOTH_ALPHA = 0.25   # smoothing for cutoff updates (0..1], higher = snappier


PITCH_MIN = 0.5
PITCH_MAX = 2.0
PITCH_CENTER = 1.0


# ==============================
# Audio state
# ==============================
current_audio = None
current_samplerate = 0
playback_position = 0
current_pitch = 1.0


# Low-pass filter state (Butterworth, order 2)
filter_b = None
filter_a = None
filter_zi = None
target_cutoff = 4000.0  # start mid-ish
smoothed_cutoff = target_cutoff


audio_lock = threading.Lock()
is_playing = False
stream = None


# ==============================
# Helpers
# ==============================
def load_song(index):
    """Load a song file into mono float32."""
    global current_audio, current_samplerate, playback_position


    filepath = f"{MUSIC_FOLDER}/{MUSIC_FILES[index]}"
    print("Loading:", filepath)
    try:
        audio_data, samplerate = sf.read(filepath, dtype="float32")


        # Convert to mono if stereo
        if audio_data.ndim > 1:
            audio_data = np.mean(audio_data, axis=1)


        with audio_lock:
            current_audio = audio_data
            current_samplerate = samplerate
            playback_position = 0


        # Recompute filter for this samplerate
        _recompute_filter_coeffs(smoothed_cutoff, samplerate)


        return True
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return False




def map_value(x, in_min, in_max, out_min, out_max):
    """Clamp-map x from [in_min,in_max] to [out_min,out_max]."""
    x = max(in_min, min(in_max, x))
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min




def calculate_pitch(encoder_pos, initial_pos):
    """
    Pitch based on encoder relative to initial.
    CCW from initial -> lower pitch down to 0.5
    CW from initial  -> higher pitch up to 2.0
    """
    relative = encoder_pos - initial_pos
    if relative <= 0:
        return map_value(relative, -50, 0, PITCH_MIN, PITCH_CENTER)
    else:
        return map_value(relative, 0, 50, PITCH_CENTER, PITCH_MAX)




def calculate_lpf_cutoff(proximity):
    """
    Map proximity to low-pass cutoff.
    - prox = 255 (close) -> LPF_CUTOFF_MIN (muffled)
    - prox = 0   (far)   -> LPF_CUTOFF_MAX (bright)
    """
    # Inverse mapping: higher proximity -> lower cutoff
    t = map_value(proximity, PROXIMITY_MIN, PROXIMITY_MAX, 0.0, 1.0)
    inv = 1.0 - t
    return LPF_CUTOFF_MIN + inv * (LPF_CUTOFF_MAX - LPF_CUTOFF_MIN)




def _recompute_filter_coeffs(cutoff_hz, samplerate):
    """
    Build a new 2nd-order Butterworth low-pass at `cutoff_hz`.
    Sets globals filter_b, filter_a, filter_zi.
    """
    global filter_b, filter_a, filter_zi


    # Clamp cutoff to a safe range relative to Nyquist
    nyq = max(1.0, samplerate / 2.0)
    cutoff = max(10.0, min(cutoff_hz, nyq * 0.95))


    # 2nd-order Butterworth low-pass
    b, a = signal.butter(2, cutoff, btype="low", fs=samplerate)


    filter_b = b
    filter_a = a


    # Initialize zi to steady-state for minimal click: yi ≈ x0 * sum(b - a[1:])
    # Use lfilter_zi and scale by first sample later inside the callback.
    filter_zi = signal.lfilter_zi(b, a)




# ==============================
# Audio callback
# ==============================
def audio_callback(outdata, frames, time_info, status):
    """
    Produce exactly `frames` samples.
    - Pitch via resampling (tempo side-effect is expected).
    - Proximity low-pass filter applied AFTER pitch, at output rate.
    - Advance playback_position by the amount of SOURCE audio read.
    """
    import math
    global playback_position, filter_zi


    if status:
        print("Audio status:", status)


    with audio_lock:
        if current_audio is None or not is_playing:
            outdata.fill(0)
            return


        # Guards
        p = float(current_pitch)
        p = max(p, 1e-6)


        # Approximate how many source samples are needed to yield `frames`
        # after pitch resampling (no speed control anymore).
        needed_input = int(math.ceil(frames * p)) + 8  # small headroom


        # Pull from source with loop wrap
        start_pos = playback_position
        end_pos = start_pos + needed_input
        n = len(current_audio)


        if end_pos <= n:
            chunk = current_audio[start_pos:end_pos]
            new_playback_pos = end_pos
        else:
            tail = current_audio[start_pos:]
            head = current_audio[: end_pos - n]
            chunk = np.concatenate([tail, head])
            new_playback_pos = end_pos - n


        # Apply pitch (resample). This changes sample count; we compensate by input sizing.
        if p != 1.0:
            new_len = max(1, int(len(chunk) / p))
            chunk = signal.resample(chunk, new_len)


        # Fit exactly `frames` samples (before filtering)
        if len(chunk) < frames:
            chunk = np.pad(chunk, (0, frames - len(chunk)))
        elif len(chunk) > frames:
            chunk = chunk[:frames]


        # Apply low-pass filter (proximity-controlled)
        if filter_b is not None and filter_a is not None:
            # Prepare zi scaled to first sample to reduce transient
            if filter_zi is None or filter_zi.shape[0] != max(len(filter_a), len(filter_b)) - 1:
                # Re-init if shape doesn't match (rare)
                zi = signal.lfilter_zi(filter_b, filter_a) * (chunk[0] if len(chunk) else 0.0)
            else:
                zi = filter_zi * (chunk[0] if len(chunk) else 0.0)


            chunk, zi = signal.lfilter(filter_b, filter_a, chunk, zi=zi)
            filter_zi = zi  # persist state


        # Commit source advancement
        playback_position = new_playback_pos


        # Output mono
        outdata[:, 0] = chunk




def start_playback():
    """Start audio playback."""
    global stream, is_playing


    if current_audio is None:
        return


    is_playing = True
    stream = sd.OutputStream(
        samplerate=current_samplerate,
        channels=1,
        callback=audio_callback,
        blocksize=2048,
    )
    stream.start()




def stop_playback():
    """Stop audio playback."""
    global stream, is_playing


    is_playing = False
    if stream:
        stream.stop()
        stream.close()
        stream = None


# ==============================
# Boot: load first track & start
# ==============================
if load_song(current_song_index):
    print("Successfully loaded:", MUSIC_FILES[current_song_index])
    time.sleep(0.5)
    start_playback()
    print("Playback started!")
else:
    print("ERROR: Could not load initial song!")


print("\nMusic Player Ready!")
print("=" * 50)
print("Proximity: controls LOW-PASS FILTER cutoff")
print("  255 (hand very close) = muffled (300 Hz)")
print("  0   (far/nothing)     = bright  (8 kHz)")
print("Rotary: controls PITCH")
print("  Initial position = 1.00x (normal pitch)")
print("  CCW = lower (to 0.5x), CW = higher (to 2.0x)")
print("Button: next song")
print("=" * 50)


# ==============================
# Main loop
# ==============================
last_update_time = time.monotonic()
UPDATE_INTERVAL = 0.05  # control update cadence
last_print_time = time.monotonic()
PRINT_INTERVAL = 0.3


try:
    # Calibrate initial values
    print("Calibrating initial values...")
    time.sleep(0.5)
    initial_proximity = apds.proximity
    initial_encoder_pos = -encoder.position


    print(f"Initial proximity: {initial_proximity}")
    print(f"Initial encoder: {initial_encoder_pos}")
    print("Starting main loop...\n")


    while True:
        now = time.monotonic()


        # Read sensors
        proximity_value = apds.proximity
        position = -encoder.position


        # Button: next song on press
        if not button.value and not button_held:
            button_held = True
            stop_playback()
            current_song_index = (current_song_index + 1) % len(MUSIC_FILES)
            if load_song(current_song_index):
                print("\nNow playing:", MUSIC_FILES[current_song_index])
                start_playback()


        if button.value and button_held:
            button_held = False


        # Update params
        if now - last_update_time >= UPDATE_INTERVAL:
            last_update_time = now


            # Rotary -> pitch
            new_pitch = calculate_pitch(position, initial_encoder_pos)


            # Proximity -> LPF cutoff (with smoothing)
            new_target_cutoff = calculate_lpf_cutoff(proximity_value)
            # simple one-pole smoothing toward target
            smoothed_cutoff = (1.0 - LPF_SMOOTH_ALPHA) * smoothed_cutoff + LPF_SMOOTH_ALPHA * new_target_cutoff


            with audio_lock:
                current_pitch = new_pitch
                # Update filter coefficients if samplerate available
                if current_samplerate > 0:
                    _recompute_filter_coeffs(smoothed_cutoff, current_samplerate)


            if now - last_print_time >= PRINT_INTERVAL:
                last_print_time = now
                rel = position - initial_encoder_pos
                if rel < -2:
                    pitch_dir = "LOWER"
                elif rel > 2:
                    pitch_dir = "HIGHER"
                else:
                    pitch_dir = "NORMAL"


                print(
                    "Prox: {:3d} | LPF: {:>6.0f} Hz | Enc: {:+4d} | Pitch: {:.2f}x ({})".format(
                        proximity_value, smoothed_cutoff, position, new_pitch, pitch_dir
                    )
                )


        time.sleep(0.02)


except KeyboardInterrupt:
    print("\nStopping music player...")
    stop_playback()
    print("Goodbye!")






