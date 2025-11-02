import os
import math
import time
import threading

import cv2
import numpy as np

# --- Optional audio output (sounddevice required) ---
try:
    import sounddevice as sd
    HAVE_SD = True
except Exception:
    HAVE_SD = False

# --- Decode MP3 (pydub + ffmpeg required) ---
try:
    from pydub import AudioSegment
    HAVE_PYDUB = True
except Exception:
    HAVE_PYDUB = False

# --- MediaPipe Hands ---
import mediapipe as mp
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_styles = mp.solutions.drawing_styles

# =============================
# Config
# =============================
SAMPLE_RATE = 48000
GAIN = 0.9
LPF_INIT = 4000.0
LPF_MIN, LPF_MAX = 80.0, 9000.0

PLAYBACK_MIN, PLAYBACK_MAX = 0.5, 1.5

SMOOTH_MS = 50.0
HUD_SMOOTH = 0.2

MUSIC_FILE = "music.mp3"

calib = {
    "Left":  {"y_min": 1.0, "y_max": 0.0},
    "Right": {"y_min": 1.0, "y_max": 0.0},
}
CALIB_DECAY = 0.002  # lets the range relax slowly over time

# =============================
# Simple 4-pole Low-Pass filter
# =============================
class FourPoleLPF:
    def __init__(self, sr):
        self.sr = sr
        self.z = [0.0, 0.0, 0.0, 0.0]
        self.set_cutoff(LPF_INIT)

    def set_cutoff(self, fc):
        fc = max(20.0, min(fc, 0.45 * self.sr))
        x = math.exp(-2.0 * math.pi * fc / self.sr)
        self.a = (1.0 - x)
        self.b = x

    def process(self, x):
        y = np.empty_like(x)
        a = self.a
        b = self.b
        z = self.z
        for i in range(x.shape[0]):
            z[0] = a * x[i] + b * z[0]
            z[1] = a * z[0] + b * z[1]
            z[2] = a * z[1] + b * z[2]
            z[3] = a * z[2] + b * z[3]
            y[i] = z[3]
        return y

# =============================
# Shared state for audio callback
# =============================
class SharedParams:
    def __init__(self):
        self.lock = threading.Lock()
        self.playback_rate = 1.0
        self.cutoff = LPF_INIT
        self._playback_rate_s = 1.0
        self._cutoff_s = LPF_INIT
        self._last_update = time.time()
        self.running = True
        self.muted = False

params = SharedParams()

# =============================
# Utility mapping
# =============================
def clamp01(x): return max(0.0, min(1.0, x))
def lerp(a,b,t): return a + (b-a)*t
def norm_to_range(v_norm, lo, hi): return lerp(lo, hi, clamp01(v_norm))
def y_to_param(y_norm): return clamp01(1.0 - y_norm)  # top=1

def clamp01(x): return max(0.0, min(1.0, x))

def y_to_param_adaptive(label, y_tip):
    # Update running min/max
    c = calib[label]
    # small decay so range doesn?t lock-in forever
    c["y_min"] = max(0.0, c["y_min"] + CALIB_DECAY)
    c["y_max"] = min(1.0, c["y_max"] - CALIB_DECAY)
    c["y_min"] = min(c["y_min"], y_tip)
    c["y_max"] = max(c["y_max"], y_tip)

    # Map fingertip to 0..1 using the observed range,
    # then invert so top=1, bottom=0
    lo, hi = c["y_min"], c["y_max"]
    if hi - lo < 1e-3:  # avoid divide-by-zero at startup
        return 0.5
    v = (y_tip - lo) / (hi - lo)    # 0 at min (highest), 1 at max (lowest)
    return clamp01(1.0 - v)

# =============================
# Music Player (resampling + LPF)
# =============================
class MusicPlayer:
    def __init__(self, sr=SAMPLE_RATE, music_path=MUSIC_FILE):
        self.sr = sr
        self.pos = 0.0
        self.lpf = FourPoleLPF(sr)

        if not HAVE_PYDUB:
            raise RuntimeError("pydub not installed. Install with: pip install pydub  (requires ffmpeg)")

        if not os.path.exists(music_path):
            raise FileNotFoundError(f'Could not find "{music_path}" in the current folder: {os.getcwd()}')

        seg = AudioSegment.from_file(music_path)
        seg = seg.set_channels(1).set_frame_rate(sr)
        arr = np.array(seg.get_array_of_samples()).astype(np.float32)
        if seg.sample_width == 1:
            arr = (arr - 128.0) / 128.0
        elif seg.sample_width == 2:
            arr /= 32768.0
        elif seg.sample_width == 3:
            arr /= 2**23
        elif seg.sample_width == 4:
            arr /= 2**31
        else:
            maxv = max(1.0, np.max(np.abs(arr)))
            arr /= maxv
        self.buffer = arr
        self.length = len(self.buffer)

    def block(self, frames):
        now = time.time()
        dt = now - params._last_update
        params._last_update = now
        tau = max(0.001, SMOOTH_MS / 1000.0)
        alpha = 1.0 - math.exp(-dt / tau)

        with params.lock:
            params._playback_rate_s += alpha * (params.playback_rate - params._playback_rate_s)
            params._cutoff_s += alpha * (params.cutoff - params._cutoff_s)
            rate = 0.0 if params.muted else params._playback_rate_s
            cutoff = max(10.0, params._cutoff_s)

        self.lpf.set_cutoff(cutoff)

        idx = self.pos + rate * np.arange(frames, dtype=np.float64)
        idx_mod = np.mod(idx, self.length - 1)
        i0 = np.floor(idx_mod).astype(np.int64)
        frac = idx_mod - i0
        i1 = i0 + 1
        buf = self.buffer
        out = (1.0 - frac) * buf[i0] + frac * buf[i1]
        out = out.astype(np.float32)

        if frames > 0:
            self.pos = (idx[-1] + rate) % (self.length - 1)

        out = self.lpf.process(out) * GAIN
        return out

audio_stream = None
player = None

def audio_callback(outdata, frames, time_info, status):
    if status:
        pass
    if not params.running or player is None:
        outdata[:] = 0
        return
    block = player.block(frames)
    outdata[:, 0] = block

def start_audio():
    global audio_stream, player
    if not HAVE_SD:
        print("sounddevice not found. Audio disabled. Install with: pip install sounddevice")
        return
    player = MusicPlayer(SAMPLE_RATE, MUSIC_FILE)
    audio_stream = sd.OutputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype='float32',
        callback=audio_callback,
        blocksize=0,
        latency='low'
    )
    audio_stream.start()

def stop_audio():
    global audio_stream
    if audio_stream is not None:
        audio_stream.stop()
        audio_stream.close()
        audio_stream = None

# =============================
# HUD state
# =============================
hud_rate = 1.0
hud_cutoff = LPF_INIT

# =============================
# UI helpers
# =============================
BG_COLOR = (200, 220, 200)   # sage-ish (B, G, R)
FG_DARK  = (20, 20, 20)
FG_MID   = (60, 60, 60)
WHITE    = (245, 245, 245)
ACCENT   = (0, 0, 0)

def draw_centered_text(img, text, center, scale, color, thickness=2):
    (w, h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
    x = int(center[0] - w/2)
    y = int(center[1] + h/2)
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)

def draw_meter(img, x, y_top, y_bot, width, norm_value):
    # background
    cv2.rectangle(img, (x, y_top), (x+width, y_bot), WHITE, -1, cv2.LINE_AA)
    # fill from bottom
    h = y_bot - y_top
    filled = int(h * clamp01(norm_value))
    cv2.rectangle(img, (x, y_bot - filled), (x+width, y_bot), ACCENT, -1, cv2.LINE_AA)
    # ticks
    cv2.putText(img, "100%", (x-10, y_top-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, FG_MID, 2, cv2.LINE_AA)
    cv2.putText(img, "0%",   (x, y_bot+35),    cv2.FONT_HERSHEY_SIMPLEX, 0.8, FG_MID, 2, cv2.LINE_AA)

def draw_ui(canvas, left_v, right_v, num_hands, rate, cutoff, have_sd, have_pydub, fps):
    H, W = canvas.shape[:2]

    # center help card
    card_w, card_h = int(W*0.45), 110
    card_x = (W - card_w) // 2
    card_y = 40
    cv2.rectangle(canvas, (card_x, card_y), (card_x+card_w, card_y+card_h), (235,240,235), -1, cv2.LINE_AA)
    draw_centered_text(canvas, "How to Use", (W//2, card_y+35), 1.0, FG_DARK, 2)
    draw_centered_text(canvas, "Left Hand: pinch to control playback rate", (W//2, card_y+70), 0.6, FG_MID, 1)
    draw_centered_text(canvas, "Right Hand: pinch to control low-pass cutoff", (W//2, card_y+95), 0.6, FG_MID, 1)

    # meters
    bar_top, bar_bot = 120, H-110
    bar_w = 40
    left_x = 120
    right_x = W - 120 - bar_w
    draw_meter(canvas, left_x, bar_top, bar_bot, bar_w, left_v)
    draw_meter(canvas, right_x, bar_top, bar_bot, bar_w, right_v)

    # left labels
    draw_centered_text(canvas, "Left Hand", (left_x+bar_w+200, H//2 - 40), 1.0, FG_MID, 2)
    draw_centered_text(canvas, f"{int(round(left_v*100))}%", (left_x+bar_w+200, H//2+10), 2.2, ACCENT, 6)
    draw_centered_text(canvas, "Playback Rate", (left_x+bar_w+200, H//2+60), 0.9, FG_DARK, 2)

    # right labels
    draw_centered_text(canvas, "Right Hand", (right_x-200, H//2 - 40), 1.0, FG_MID, 2)
    draw_centered_text(canvas, f"{int(round(right_v*100))}%", (right_x-200, H//2+10), 2.2, ACCENT, 6)
    draw_centered_text(canvas, "Low Pass Filter", (right_x-200, H//2+60), 0.9, FG_DARK, 2)

    # bottom status line
    # cv2.putText(canvas, f"Playback Rate: {rate:0.2f}x", (20, H-65), cv2.FONT_HERSHEY_SIMPLEX, 0.9, FG_DARK, 2, cv2.LINE_AA)
    # cv2.putText(canvas, f"LPF Cutoff (Hz): {cutoff:6.1f}", (20, H-25), cv2.FONT_HERSHEY_SIMPLEX, 0.9, FG_DARK, 2, cv2.LINE_AA)

    if not have_sd:
        cv2.putText(canvas, "Audio OFF (install 'sounddevice')", (W-400, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 120, 255), 2, cv2.LINE_AA)
    if not have_pydub:
        cv2.putText(canvas, "MP3 decode OFF (install 'pydub' + ffmpeg)", (W-520, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 120, 255), 2, cv2.LINE_AA)

    cv2.putText(canvas, f"FPS: {int(fps)}", (W-140, H-20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (80, 80, 80), 2, cv2.LINE_AA)
    # if num_hands < 2:s
        # draw_centered_text(canvas, "Show BOTH hands (Left=Rate, Right=LPF)!", (W//2, 95), 0.9, (0, 0, 255), 2)

# =============================
# Main (vision + control)
# =============================
def main():
    global hud_rate, hud_cutoff

    print("=" * 60)
    print('Two-Hand DJ: LEFT hand = Playback Rate (Pitch), RIGHT hand = Low-Pass Cutoff')
    print(' - Raise LEFT hand to speed up / pitch up; lower to slow/pitch down')
    print(' - Raise RIGHT hand to open the filter (brighter)')
    print(' - Put "music.mp3" in the SAME folder as this script')
    print(" - Press 'm' to mute/unmute audio, 'q' to quit")
    print("=" * 60)

    try:
        start_audio()
    except Exception as e:
        print(f"[Audio Start Error] {e}")

    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        model_complexity=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    pTime = 0.0
    fps = 0.0

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            # We still use the camera for tracking, but we WON'T display it.
            frame = cv2.flip(frame, 1)
            img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(img_rgb)

            left_y = None
            right_y = None
            num_hands = 0

            if results.multi_hand_landmarks:
                for hand_lms, handed in zip(results.multi_hand_landmarks, results.multi_handedness):
                    label = handed.classification[0].label  # "Left"/"Right"
                    y_tip = hand_lms.landmark[8].y          # index fingertip

                    v = y_to_param_adaptive(label, y_tip)   # 0..1 with full usable travel

                    if label == "Left":
                        params.playback_rate = norm_to_range(v, PLAYBACK_MIN, PLAYBACK_MAX)
                    else:
                        params.cutoff = norm_to_range(v, LPF_MIN, LPF_MAX)


            # Map to parameters
            with params.lock:
                if left_y is not None:
                    v = y_to_param(left_y)
                    params.playback_rate = norm_to_range(v, PLAYBACK_MIN, PLAYBACK_MAX)
                if right_y is not None:
                    v = y_to_param(right_y)
                    params.cutoff = norm_to_range(v, LPF_MIN, LPF_MAX)

                # HUD smoothing
                hud_rate += HUD_SMOOTH * (params.playback_rate - hud_rate)
                hud_cutoff += HUD_SMOOTH * (params.cutoff - hud_cutoff)

            # Build a fresh canvas (no camera image)
            H, W = 720, 1280
            canvas = np.full((H, W, 3), BG_COLOR, dtype=np.uint8)

            # UI (meters + labels)
            left_v = clamp01((hud_rate - PLAYBACK_MIN) / (PLAYBACK_MAX - PLAYBACK_MIN))
            right_v = clamp01((hud_cutoff - LPF_MIN) / (LPF_MAX - LPF_MIN))
            draw_ui(canvas, left_v, right_v, num_hands, hud_rate, hud_cutoff, HAVE_SD, HAVE_PYDUB, fps)

            # Draw only the hand skeletons on top of the UI
            if results.multi_hand_landmarks:
                for hand_lms, handed in zip(results.multi_hand_landmarks, results.multi_handedness):
                    color = (255, 0, 255) if handed.classification[0].label == "Left" else (0, 255, 255)
                    mp_drawing.draw_landmarks(
                        canvas,
                        hand_lms,
                        mp_hands.HAND_CONNECTIONS,
                        mp_drawing.DrawingSpec(color=color, thickness=2, circle_radius=3),
                        mp_drawing.DrawingSpec(color=color, thickness=2),
                    )

            # FPS calc
            cTime = time.time()
            fps = 1.0 / (cTime - pTime) if (cTime - pTime) > 0 else fps
            pTime = cTime

            cv2.imshow("Two-Hand DJ: music.mp3 Controller", canvas)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('m'):
                with params.lock:
                    params.muted = not params.muted

    finally:
        params.running = False
        stop_audio()
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
