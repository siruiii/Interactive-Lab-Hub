# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

import time
import board
from adafruit_apds9960.apds9960 import APDS9960
from pygame import mixer # Import the mixer module from pygame

# --- Configuration ---
AUDIO_FILE = "ding-dong.wav" # <-- CHANGE THIS to your MP3 file path
PROXIMITY_THRESHOLD = 255
# ---------------------

# Initialize I2C and APDS-9960 Sensor
i2c = board.I2C()
apds = APDS9960(i2c)
apds.enable_proximity = True

# Initialize Pygame Mixer
try:
    mixer.init()
    # Load the audio file
    alert_sound = mixer.Sound(AUDIO_FILE)
    print(f"Audio file '{AUDIO_FILE}' loaded successfully.")
except Exception as e:
    print(f"Error initializing mixer or loading audio: {e}")
    # You might want to exit the script if audio fails
    # exit(1) 

# Variable to track if the sound has been played since the last reset
sound_played = False

print("Proximity detection started. Move your hand over the sensor.")

while True:
    proximity_value = apds.proximity
    print(f"Proximity: {proximity_value}")
    
    # 1. Check if the proximity is at the target value (255)
    if proximity_value == PROXIMITY_THRESHOLD:
        
        # 2. Check if the sound has NOT been played yet
        if not sound_played:
            
            # Play the sound once
            print("HIGH PROXIMITY DETECTED! Playing sound...")
            alert_sound.play()
            
            # Set the flag so it won't play again until the proximity drops
            sound_played = True
            
    # 3. If proximity drops below the threshold, reset the flag
    else:
        if sound_played:
            print("Proximity dropped. Resetting sound playback flag.")
            sound_played = False

    time.sleep(0.2)