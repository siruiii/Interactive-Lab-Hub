import cv2
import json
import time
import threading
import sys
import board
from adafruit_apds9960.apds9960 import APDS9960
from pygame import mixer
# Ensure escpos is installed: pip install python-escpos
from escpos.printer import Usb 

# ====================================================================
#                      SYSTEM CONFIGURATION
# ====================================================================

# --- PRINTER & CAMERA CONFIG ---
USB_VENDOR_ID = 0x0416  # Replace with your printer's actual VID/PID
USB_PRODUCT_ID = 0x5011 # Replace with your printer's actual VID/PID
JSON_FILE = 'qr_m.json'
CAMERA_INDEX = 0        # 0 usually refers to the default webcam
MAX_RETRIES = 3         # Maximum number of times to retry printing on failure
RETRY_DELAY = 1.5       # Time (in seconds) to wait between retries

# --- PROXIMITY & AUDIO CONFIG ---
AUDIO_FILE = "Music.MP3" 
PROXIMITY_THRESHOLD = 5
SOUND_VOLUME = 0.5 

# ====================================================================
#                   PRINTER/QR CODE FUNCTIONS
# ====================================================================

def load_messages(file_path):
    """Loads the QR code -> message mapping from a JSON file."""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"--- ERROR: JSON file not found at {file_path}")
        return None
    except json.JSONDecodeError:
        print(f"--- ERROR: Invalid JSON format in {file_path}")
        return None

def print_message(message):
    """Initializes the printer and prints the specified message with retries."""
    
    for attempt in range(MAX_RETRIES):
        print(f"[PRINTER] Attempting to connect and print (Attempt {attempt + 1}/{MAX_RETRIES})...")
        p = None # Initialize printer object
        
        try:
            # 1. Connect to the USB Printer
            p = Usb(USB_VENDOR_ID, USB_PRODUCT_ID) 

            # 2. Initialize the Printer
            p.set(align='center', font='b', height=0, width=1)
            
            # 3. Print Content
            p.text(message + "\n")
            
            # 4. Perform Partial Cut
            p.cut()
            
            print("[PRINTER] SUCCESS: Message successfully sent to the printer.")
            return True # Success, exit function

        except Exception as e:
            error_msg = str(e).encode('ascii', 'replace').decode('ascii')
            print(f"[PRINTER] WARNING: Print attempt failed: {error_msg}")
            
            if attempt < MAX_RETRIES - 1:
                # Wait before retrying
                time.sleep(RETRY_DELAY)
            
        finally:
            # CRITICAL: Explicitly close the connection to release the USB resource
            if p:
                try:
                    p.close()
                    # print("[PRINTER] Connection closed.")
                except Exception as close_e:
                    print(f"[PRINTER] WARNING: Failed to close connection: {str(close_e).encode('ascii', 'replace').decode('ascii')}")


    # If the loop completes without a successful return (True)
    print(f"[PRINTER] FAILURE: All {MAX_RETRIES} print attempts failed.")
    return False

def qr_code_detection_thread(messages_map):
    """Main loop for camera and printer operations (runs in a separate thread)."""
    if not messages_map:
        return

    printed_codes = set()
    cap = cv2.VideoCapture(CAMERA_INDEX)

    if not cap.isOpened():
        print(f"--- ERROR: Could not open video stream at index {CAMERA_INDEX}")
        return

    qr_detector = cv2.QRCodeDetector()
    print("--- STARTUP: QR Code Detector thread started. Press 'q' on video window to quit. ---")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("--- ERROR: Failed to grab frame.")
            break

        data, bbox, rectified_image = qr_detector.detectAndDecode(frame)

        if data:
            if data in messages_map:
                if data not in printed_codes:
                    message_to_print = messages_map[data]
                    print(f"[READ] SUCCESS: Detected new QR Code Data: {data}. Matching message found.")

                    if print_message(message_to_print):
                        printed_codes.add(data)
                        # Optional: Add a short cooldown here if you need it

                else:
                    print(f"[READ] DETECTED: QR code '{data}' detected, but message has already been printed once.")
            
            else:
                print(f"[READ] DETECTED: QR code '{data}' detected, but NO matching message found in JSON.")

            if bbox is not None:
                int_points = bbox[0].astype(int)
                cv2.polylines(frame, [int_points], True, (0, 255, 0), 2)
        
        # Display the resulting frame
        cv2.imshow('QR Code Detector', frame)

        # Break the loop on 'q' key press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Clean up resources for this thread
    cap.release()
    cv2.destroyAllWindows()
    print("--- SHUTDOWN: QR Code Detector thread closed. ---")


# ====================================================================
#                  PROXIMITY/AUDIO FUNCTIONS
# ====================================================================

def proximity_detection_thread():
    """Main loop for proximity sensor and audio playback (runs in a separate thread)."""
    
    # --- Initialization ---
    try:
        i2c = board.I2C()
        apds = APDS9960(i2c)
        apds.enable_proximity = True
    except Exception as e:
        print(f"--- ERROR: APDS-9960 sensor initialization failed: {e}. Check wiring/I2C.")
        return

    # Initialize Pygame Mixer and Load Sound
    try:
        mixer.init()
        alert_sound = mixer.Sound(AUDIO_FILE)
        alert_sound.set_volume(SOUND_VOLUME)
        print(f"[AUDIO] Audio file '{AUDIO_FILE}' loaded successfully.")
        print(f"[AUDIO] Volume set to {SOUND_VOLUME * 100:.0f}%")
    except Exception as e:
        print(f"--- ERROR: Audio initialization failed: {e}")
        # If audio fails, the thread can't fulfill its purpose, so we exit
        return

    sound_played = False
    print(f"--- STARTUP: Proximity thread started. Sound plays when proximity >= {PROXIMITY_THRESHOLD} ---")

    # --- Main Loop ---
    while True:
        try:
            proximity_value = apds.proximity
            # print(f"[PROX] Proximity: {proximity_value}") # Log only when needed to avoid spam
            
            # 1. Check if the proximity is at or above the generous threshold
            if proximity_value >= PROXIMITY_THRESHOLD:
                
                # 2. Check if the sound has NOT been played yet for this event
                if not sound_played:
                    
                    # Play the sound once
                    print("[PROX] HIGH PROXIMITY DETECTED! Playing sound...")
                    alert_sound.play()
                    
                    # Set the flag so it won't play again until the proximity drops
                    sound_played = True
                    
            # 3. If proximity drops below the threshold, reset the flag
            else:
                if sound_played:
                    print("[PROX] Proximity dropped below threshold. Resetting sound playback flag.")
                    sound_played = False

        except Exception as e:
            print(f"--- ERROR: Proximity loop encountered an error: {e}")
            # Wait briefly before continuing to prevent rapid error loops
            time.sleep(1.0)
            
        time.sleep(0.2)


# ====================================================================
#                            MAIN EXECUTION
# ====================================================================

if __name__ == "__main__":
    messages_map = load_messages(JSON_FILE)
    
    if not messages_map:
        print("--- SHUTDOWN: Cannot start QR detector without a valid JSON map. ---")
        sys.exit(1)

    # 1. Create threads
    qr_thread = threading.Thread(target=qr_code_detection_thread, args=(messages_map,))
    prox_thread = threading.Thread(target=proximity_detection_thread)

    # Set threads as daemon so they don't prevent the main program from exiting
    # (especially useful for the proximity thread which has no 'q' key break)
    qr_thread.daemon = True
    prox_thread.daemon = True

    # 2. Start threads
    print("\nStarting system with two concurrent threads...")
    qr_thread.start()
    prox_thread.start()

    # 3. Keep the main thread alive until the QR thread (which handles the 'q' quit) finishes.
    # This prevents the program from immediately exiting.
    qr_thread.join()

    print("--- SYSTEM HALT: QR thread finished. Exiting main program. ---")
    sys.exit(0)