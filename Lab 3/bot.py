#!/usr/bin/env python3
"""
Integrated Twenty Questions Game with ST7789 Display
Combines voice recognition, Ollama AI, and visual feedback
"""


import os, sys, json, queue, threading, time, subprocess
import numpy as np
import sounddevice as sd
import requests
from vosk import Model, KaldiRecognizer
from PIL import Image, ImageDraw, ImageFont
import board, digitalio, adafruit_rgb_display.st7789 as st7789


# ---------------- Display Setup ----------------
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


height = disp.width
width = disp.height
rotation = 90


backlight = digitalio.DigitalInOut(board.D22)
backlight.switch_to_output()
backlight.value = True


def clear_display(color=(0,0,0)):
    disp.image(Image.new("RGB", (width, height), color), rotation)


def show_image(path):
    """Open, rotate 180°, resize, and draw an image onto the ST7789."""
    print(f"[DISPLAY] Loading image: {path}")
    try:
        img = Image.open(path).convert("RGB")
        img = img.rotate(180, expand=False)
        img = img.resize((width, height))
        disp.image(img, rotation)
        print(f"[DISPLAY] Successfully displayed: {path}")
    except Exception as e:
        print(f"[DISPLAY] ERROR loading {path}: {repr(e)}")
        img = Image.new("RGB", (width, height), (20,20,20))
        draw = ImageDraw.Draw(img)
        draw.text((10,10), f"ERROR\n{str(e)}", fill=(255,255,255))
        disp.image(img, rotation)


def show_text_on_image(img_path, text, text_color=(0,0,0)):
    """Display text overlaid on an image at the top left, rotated 180 degrees."""
    print(f"[DISPLAY] Showing text on {img_path}: {text}")
    try:
        if os.path.exists(img_path):
            img = Image.open(img_path).convert("RGB")
            img = img.rotate(180, expand=False)
            img = img.resize((width, height))
        else:
            print(f"[DISPLAY] Image not found, using black background")
            img = Image.new("RGB", (width, height), (0,0,0))
        
        draw = ImageDraw.Draw(img)
        
        # Try to load a larger font, fallback to default if not available
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
            except:
                font = ImageFont.load_default()
        
        # Word wrap the text to fit the screen
        words = text.split()
        lines = []
        current_line = ""
        max_width = width - 20  # 10px padding on each side
        
        for word in words:
            test_line = current_line + " " + word if current_line else word
            # Get actual text width using the font
            try:
                bbox = draw.textbbox((0, 0), test_line, font=font)
                text_width = bbox[2] - bbox[0]
            except:
                text_width = len(test_line) * 10  # Larger estimate for bigger font
            
            if text_width < max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        # Create a separate image for the text
        text_img = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        text_draw = ImageDraw.Draw(text_img)
        
        # Calculate starting position for top-left alignment
        line_height = 25  # Larger line height for bigger font
        y_start = 10  # 10px padding from top
        
        # Draw text lines aligned to the left
        y_offset = y_start
        for line in lines:
            x_position = 10  # 10px padding from left
            text_draw.text((x_position, y_offset), line, fill=text_color, font=font)
            y_offset += line_height
        
        # Rotate the text image 180 degrees
        text_img = text_img.rotate(180, expand=False)
        
        # Composite the rotated text onto the background image
        img.paste(text_img, (0, 0), text_img)
        
        disp.image(img, rotation)
        print(f"[DISPLAY] Successfully displayed text overlay")
    except Exception as e:
        print(f"[DISPLAY] Error showing text on image: {repr(e)}")


clear_display()


# ---------------- Ollama Configuration ----------------
OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "phi3:mini"


STARTING_PROMPT = (
    "You are a Twenty Questions bot. The user silently thinks of a PERSON."
    " The user replies only YES or NO."
    " Ask exactly ONE short, clear, speakable yes/no question per turn."
    " Never write multiple questions. Never use the word 'or'."
    " Start broad, then narrow. Keep it under 120 characters."
    " When >=90% confident, make ONE concise guess like 'I think it is [name]' (no question mark)."
    " If you reach 20 questions without a correct guess, say the user wins."
)


chat_history = [{"role": "system", "content": STARTING_PROMPT}]
MAX_TURNS = 30
question_count = 0


def enforce_one_question(text, max_chars=120):
    """Extract a single yes/no question from AI response."""
    import re
    if not isinstance(text, str):
        text = str(text or "")
    
    # If it looks like a guess (contains "I think", "It is", etc.), return as-is without '?'
    guess_patterns = [r'\bI think\b', r'\bIt is\b', r'\bIt\'s\b', r'\bMy guess is\b']
    for pattern in guess_patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            # Remove any trailing question mark from guesses
            return text.strip().rstrip('?').strip()
    
    # Otherwise, treat as a question
    q = text.split('?', 1)[0].strip()
    if not q:
        return "Is this person real (not fictional)?"
    
    q = re.split(r'\bor\b', q, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    q = q[:max(1, max_chars - 1)].rstrip(" .,!?:;") + "?"
    
    if not re.match(r'^(Is|Are|Was|Were|Do|Does|Did|Has|Have|Can|Will|Would)\b', q, flags=re.IGNORECASE):
        q = "Is the person alive today?"
    return q


def ollama_chat(messages, model=DEFAULT_MODEL, timeout=90):
    """Call Ollama's /api/chat with messages[], return assistant string."""
    print(f"[OLLAMA] Sending request to Ollama ({model})...")
    print(f"[OLLAMA] Message count: {len(messages)}")
    
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_ctx": 2048,
                    "num_predict": 128
                }
            },
            timeout=timeout
        )
        
        if resp.status_code == 200:
            data = resp.json()
            content = data.get("message", {}).get("content", "No response generated")
            print(f"[OLLAMA] Response received: {content}")
            return content
        else:
            print(f"[OLLAMA] Error: Status {resp.status_code}")
            return f"Error: Ollama returned status {resp.status_code}"
    except Exception as e:
        print(f"[OLLAMA] Exception: {repr(e)}")
        return f"Error: {str(e)}"


def query_ollama(user_text):
    """Query Ollama and return the next question."""
    global chat_history, question_count
    
    print(f"[OLLAMA] User input: {user_text}")
    
    # First question
    if len(chat_history) == 1:
        q1 = "Is the person real (not a fictional character)?"
        chat_history.append({"role": "assistant", "content": q1})
        question_count = 1
        print(f"[OLLAMA] First question (Q{question_count}): {q1}")
        return q1
    
    # Add user response
    chat_history.append({"role": "user", "content": user_text})
    
    # Trim history
    if len(chat_history[1:]) > MAX_TURNS:
        chat_history = [chat_history[0]] + chat_history[-(MAX_TURNS):]
    
    # Get AI response
    ai_reply_raw = ollama_chat(chat_history, model=DEFAULT_MODEL, timeout=90)
    ai_reply = enforce_one_question(ai_reply_raw)
    
    chat_history.append({"role": "assistant", "content": ai_reply})
    question_count += 1
    
    print(f"[OLLAMA] Next question (Q{question_count}): {ai_reply}")
    return ai_reply


def speak_text(text):
    """Text-to-speech using espeak."""
    print(f"[TTS] Speaking: {text}")
    try:
        subprocess.run(['espeak', text], check=False)
        print("[TTS] Speech completed")
    except Exception as e:
        print(f"[TTS] Error: {e}")


# ---------------- Voice Recognition ----------------
audio_q = queue.Queue()
word_detected = threading.Event()
detected_word = None


try:
    SAMPLE_RATE = int(sd.query_devices(None, "input")["default_samplerate"])
except Exception:
    SAMPLE_RATE = 16000
print(f"[AUDIO] Using SAMPLE_RATE: {SAMPLE_RATE}")


try:
    model = Model(lang="en-us")
    print("[VOSK] Model loaded successfully")
except Exception as e:
    print(f"[VOSK] Could not load model: {e}")
    sys.exit(1)


SILENCE_RMS_THRESHOLD = 800
CONF_THRESHOLD = 0.80


def audio_callback(indata, frames, time_info, status):
    if status:
        print(f"[AUDIO] Status: {status}", file=sys.stderr)
    audio_q.put(bytes(indata))


def has_word_with_conf(res_dict, target_word, min_conf=0.0):
    """Check if target word is in result with sufficient confidence."""
    for w in res_dict.get("result", []):
        if w.get("word", "").lower() == target_word.lower():
            conf = float(w.get("conf", w.get("confidence", 0.0)))
            if conf >= min_conf:
                return True
    
    txt = res_dict.get("text", "").strip().lower().replace("[unk]", "").strip()
    return txt == target_word.lower()


def listen_for_word(target_word):
    """Listen for a specific word (ready, yes, or no)."""
    global detected_word
    
    recognizer = KaldiRecognizer(model, SAMPLE_RATE, f'["{target_word}", "[unk]"]')
    word_detected.clear()
    detected_word = None
    
    print(f"[VOSK] Listening for '{target_word}'...")
    
    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=8192,
                           dtype="int16", channels=1, callback=audio_callback):
        while not word_detected.is_set():
            data = audio_q.get()
            
            rms = np.sqrt(np.mean(np.frombuffer(data, dtype=np.int16).astype(np.float64)**2))
            if rms < SILENCE_RMS_THRESHOLD:
                continue
            
            if recognizer.AcceptWaveform(data):
                res = json.loads(recognizer.Result())
                text = res.get("text", "").strip()
                print(f"[VOSK] Final result: {repr(text)}")
                
                if has_word_with_conf(res, target_word, min_conf=CONF_THRESHOLD):
                    print(f"[VOSK] Detected '{target_word}' with confidence")
                    detected_word = target_word
                    word_detected.set()


def listen_for_yes_or_no():
    """Listen for either 'yes' or 'no'."""
    global detected_word
    
    recognizer = KaldiRecognizer(model, SAMPLE_RATE, '["yes", "no", "[unk]"]')
    word_detected.clear()
    detected_word = None
    
    print("[VOSK] Listening for 'yes' or 'no'...")
    
    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=8192,
                           dtype="int16", channels=1, callback=audio_callback):
        while not word_detected.is_set():
            data = audio_q.get()
            
            rms = np.sqrt(np.mean(np.frombuffer(data, dtype=np.int16).astype(np.float64)**2))
            if rms < SILENCE_RMS_THRESHOLD:
                continue
            
            if recognizer.AcceptWaveform(data):
                res = json.loads(recognizer.Result())
                text = res.get("text", "").strip()
                print(f"[VOSK] Final result: {repr(text)}")
                
                if has_word_with_conf(res, "yes", min_conf=CONF_THRESHOLD):
                    print("[VOSK] Detected 'yes'")
                    detected_word = "yes"
                    word_detected.set()
                elif has_word_with_conf(res, "no", min_conf=CONF_THRESHOLD):
                    print("[VOSK] Detected 'no'")
                    detected_word = "no"
                    word_detected.set()


# ---------------- Main Game Loop ----------------
if __name__ == "__main__":
    UI_DIR = "UI"
    START_IMG = os.path.join(UI_DIR, "Start.png")
    SUCCESS_IMG = os.path.join(UI_DIR, "Success.png")
    FAIL_IMG = os.path.join(UI_DIR, "Fail.png")
    
    print("[MAIN] Starting Twenty Questions Game")
    print(f"[MAIN] CWD: {os.getcwd()}")
    print(f"[MAIN] START_IMG exists: {os.path.exists(START_IMG)}")
    print(f"[MAIN] SUCCESS_IMG exists: {os.path.exists(SUCCESS_IMG)}")
    print(f"[MAIN] FAIL_IMG exists: {os.path.exists(FAIL_IMG)}")
    
    try:
        # Show start screen and wait for "ready"
        show_image(START_IMG)
        print("[MAIN] Waiting for 'ready'...")
        
        listen_for_word("ready")
        print("[MAIN] User is ready! Starting game...")
        
        # Main game loop
        game_won = False
        last_answer = ""
        
        for round_num in range(1, 21):
            img_path = os.path.join(UI_DIR, f"{round_num}.png")
            print(f"\n[MAIN] ===== Round {round_num}/20 =====")
            
            # Get question from Ollama
            if round_num == 1:
                question = query_ollama("")  # Triggers first question
            else:
                question = query_ollama(last_answer)
            
            # Check if it's a guess (doesn't end with '?')
            is_guess = not question.strip().endswith('?')
            
            if is_guess:
                print(f"[MAIN] AI made a guess on round {round_num}!")
                
                # Show the guess with confirmation prompt
                guess_text = question + " Is that correct?"
                if os.path.exists(img_path):
                    show_text_on_image(img_path, guess_text)
                else:
                    print(f"[MAIN] Warning: {img_path} not found, using round 1 image")
                    show_text_on_image(os.path.join(UI_DIR, "1.png"), guess_text)
                
                # Speak the guess
                speak_text(question)
                time.sleep(0.5)
                speak_text("Is that correct?")
                
                # Listen for confirmation
                listen_for_yes_or_no()
                
                if detected_word == "yes":
                    print(f"[MAIN] AI guessed correctly in {round_num} questions! Game won!")
                    show_image(SUCCESS_IMG)
                    speak_text("I got it! Great game!")
                    game_won = True
                    time.sleep(5)
                    break
                else:
                    print("[MAIN] AI's guess was wrong")
                    last_answer = "no"
                    
                    if round_num >= 20:
                        print("[MAIN] That was round 20, AI failed to guess")
                        break
                    else:
                        print("[MAIN] Continuing to next round...")
                        continue
            
            # It's a regular question
            if os.path.exists(img_path):
                show_text_on_image(img_path, question)
            else:
                print(f"[MAIN] Warning: {img_path} not found, using round 1 image")
                show_text_on_image(os.path.join(UI_DIR, "1.png"), question)
            
            # Speak the question
            speak_text(question)
            
            # Listen for yes/no answer
            listen_for_yes_or_no()
            last_answer = detected_word if detected_word else "yes"
            print(f"[MAIN] User answered: {last_answer}")
        
        # Check final result
        if not game_won:
            print("[MAIN] Reached end without correct guess - user wins!")
            show_image(FAIL_IMG)
            speak_text("You win! I couldn't guess it in 20 questions.")
            time.sleep(5)
        
        print("[MAIN] Game complete!")
        
    except KeyboardInterrupt:
        print("\n[MAIN] Exiting (KeyboardInterrupt)")
    except Exception as e:
        print(f"[MAIN] Error: {repr(e)}")
        import traceback
        traceback.print_exc()
    finally:
        clear_display((0,0,0))
        backlight.value = False
        print("[MAIN] Cleanup complete")




