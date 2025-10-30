

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
# pip install pydub
try:
    from pydub import AudioSegment
    HAVE_PYDUB = True
except Exception:
    HAVE_PYDUB = False


# --- MediaPipe Hands ---
# pip install mediapipe opencv-python
import mediapipe as mp
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils




# =============================
# Config
# =============================
SAMPLE_RATE = 48000
GAIN = 0.9   # overall output gain (music is already normalized; keep < 1.0)
LPF_INIT = 4000.0
LPF_MIN, LPF_MAX = 80.0, 9000.0    # Hz mapped from RIGHT hand Y (top=high)


# Playback rate (acts like coarse pitch/time stretch by resampling)
# 1.0 = normal speed, >1.0 = faster & higher pitch, <1.0 = slower & lower pitch
PLAYBACK_MIN, PLAYBACK_MAX = 0.5, 1.5


SMOOTH_MS = 50.0     # smoothing for parameter changes (ms)
HUD_SMOOTH = 0.2


MUSIC_FILE = "music.mp3"   # expected to be in the same folder as this script




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
            # cascade of 4 one-pole filters → ~24 dB/oct
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




# =============================
# Music Player (resampling + LPF)
# =============================
class MusicPlayer:
    def __init__(self, sr=SAMPLE_RATE, music_path=MUSIC_FILE):
        self.sr = sr
        self.pos = 0.0  # fractional index into mono buffer
        self.lpf = FourPoleLPF(sr)


        if not HAVE_PYDUB:
            raise RuntimeError("pydub not installed. Install with: pip install pydub  (requires ffmpeg)")


        if not os.path.exists(music_path):
            raise FileNotFoundError(f'Could not find "{music_path}" in the current folder: {os.getcwd()}')


        seg = AudioSegment.from_file(music_path)  # requires ffmpeg
        # Convert to mono, target SR, float32 numpy [-1, 1]
        seg = seg.set_channels(1).set_frame_rate(sr)
        arr = np.array(seg.get_array_of_samples()).astype(np.float32)
        # Normalize from integer sample width
        if seg.sample_width == 1:   # 8-bit unsigned
            arr = (arr - 128.0) / 128.0
        elif seg.sample_width == 2: # 16-bit
            arr /= 32768.0
        elif seg.sample_width == 3: # 24-bit packed into int32 by pydub
            arr /= 2**23
        elif seg.sample_width == 4: # 32-bit int
            arr /= 2**31
        else:
            # fallback: ensure within [-1,1]
            maxv = max(1.0, np.max(np.abs(arr)))
            arr /= maxv
        self.buffer = arr
        self.length = len(self.buffer)


    def block(self, frames):
        # Smooth params to avoid zipper noise
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


        # Vectorized fractional resampling via linear interpolation
        # sample positions for this block
        idx = self.pos + rate * np.arange(frames, dtype=np.float64)
        # wrap (loop) gracefully
        idx_mod = np.mod(idx, self.length - 1)  # -1 so idx+1 is valid
        i0 = np.floor(idx_mod).astype(np.int64)
        frac = idx_mod - i0
        i1 = i0 + 1
        # linear interpolate
        buf = self.buffer
        out = (1.0 - frac) * buf[i0] + frac * buf[i1]
        out = out.astype(np.float32)


        # advance position
        if frames > 0:
            self.pos = (idx[-1] + rate) % (self.length - 1)


        # filter + gain
        out = self.lpf.process(out) * GAIN
        return out




audio_stream = None
player = None


def audio_callback(outdata, frames, time_info, status):
    if status:
        # print(status)
        pass
    if not params.running or player is None:
        outdata[:] = 0
        return
    block = player.block(frames)
    outdata[:, 0] = block  # mono




def start_audio():
    global audio_stream, player
    if not HAVE_SD:
        print("sounddevice not found. Audio disabled. Install with: pip install sounddevice")
        return
    # Initialize player (may raise if mp3 missing)
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


    # Start audio
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


            frame = cv2.flip(frame, 1)
            img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(img_rgb)


            left_y = None
            right_y = None
            num_hands = 0


            if results.multi_hand_landmarks:
                num_hands = len(results.multi_hand_landmarks)
                for hand_lms, handed in zip(results.multi_hand_landmarks, results.multi_handedness):
                    label = handed.classification[0].label  # "Left" or "Right" (from subject POV)
                    y_norm = hand_lms.landmark[8].y
                    if label == "Left":
                        left_y = y_norm
                    elif label == "Right":
                        right_y = y_norm


                    color = (255, 0, 255) if label == "Left" else (0, 255, 255)
                    mp_drawing.draw_landmarks(
                        frame, hand_lms, mp_hands.HAND_CONNECTIONS,
                        mp_drawing.DrawingSpec(color=color, thickness=2, circle_radius=3),
                        mp_drawing.DrawingSpec(color=color, thickness=2)
                    )
                    cv2.putText(frame, f"{label}",
                                (int(hand_lms.landmark[0].x * frame.shape[1]),
                                 int(hand_lms.landmark[0].y * frame.shape[0]) - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)


            # Map to parameters
            with params.lock:
                if left_y is not None:
                    v = y_to_param(left_y)  # 0..1 (top=1)
                    params.playback_rate = norm_to_range(v, PLAYBACK_MIN, PLAYBACK_MAX)
                if right_y is not None:
                    v = y_to_param(right_y)
                    params.cutoff = norm_to_range(v, LPF_MIN, LPF_MAX)


                # HUD smoothing
                hud_rate += HUD_SMOOTH * (params.playback_rate - hud_rate)
                hud_cutoff += HUD_SMOOTH * (params.cutoff - hud_cutoff)


            # HUD
            h, w = frame.shape[:2]
            cv2.rectangle(frame, (10, h-110), (w-10, h-10), (0, 0, 0), -1)
            cv2.putText(frame, f"HANDS: {num_hands}/2", (20, 40),
                        cv2.FONT_HERSHEY_DUPLEX, 1.0, (0, 255, 0) if num_hands == 2 else (0, 0, 255), 2)


            cv2.putText(frame, f"Playback Rate: {hud_rate:0.2f}x", (20, h-70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
            cv2.putText(frame, f"LPF Cutoff (Hz): {hud_cutoff:6.1f}", (20, h-30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)


            if not HAVE_SD:
                cv2.putText(frame, "Audio OFF (install 'sounddevice')",
                            (w-380, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
            if not HAVE_PYDUB:
                cv2.putText(frame, "MP3 decode OFF (install 'pydub' and ffmpeg)",
                            (w-540, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)


            # FPS
            cTime = time.time()
            fps = 1.0 / (cTime - pTime) if (cTime - pTime) > 0 else fps
            pTime = cTime
            cv2.putText(frame, f"FPS: {int(fps)}", (w-140, h-20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)


            if num_hands < 2:
                cv2.putText(frame, 'Show BOTH hands (Left=Rate, Right=LPF)!',
                            (int(0.15*w), 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)


            cv2.imshow("Two-Hand DJ: music.mp3 Controller", frame)


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






