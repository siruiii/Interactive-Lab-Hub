# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

import time
import board
from adafruit_apds9960.apds9960 import APDS9960
from pygame import mixer # Import the mixer module from pygame

# --- Configuration ---
AUDIO_FILE = "ding-dong.wav" 
PROXIMITY_THRESHOLD = 150 
# Volume setting: 0.5 equals 50%
SOUND_VOLUME = 0.5 
# ---------------------

# Initialize I2C and APDS-9960 Sensor
i2c = board.I2C()
apds = APDS9960(i2c)
apds.enable_proximity = True

# Initialize Pygame Mixer and Load Sound
try:
    mixer.init()
    # Load the audio file
    alert_sound = mixer.Sound(AUDIO_FILE)
    
    # Set the volume of the loaded sound to 50%
    alert_sound.set_volume(SOUND_VOLUME)
    
    print(f"Audio file '{AUDIO_FILE}' loaded successfully.")
    print(f"Volume set to {SOUND_VOLUME * 100:.0f}%")
except Exception as e:
    print(f"Error initializing mixer or loading audio: {e}")
    # Exit the script if the audio setup fails
    exit(1) 

# Variable to track if the sound has been played since the last reset
sound_played = False

print(f"Proximity detection started. Sound will play when proximity >= {PROXIMITY_THRESHOLD}")

while True:
    proximity_value = apds.proximity
    print(f"Proximity: {proximity_value}")
    
    # 1. Check if the proximity is at or above the generous threshold
    if proximity_value >= PROXIMITY_THRESHOLD:
        
        # 2. Check if the sound has NOT been played yet for this event
        if not sound_played:
            
            # Play the sound once
            print("HIGH PROXIMITY DETECTED! Playing sound...")
            alert_sound.play()
            
            # Set the flag so it won't play again until the proximity drops
            sound_played = True
            
    # 3. If proximity drops below the threshold, reset the flag
    else:
        if sound_played:
            print("Proximity dropped below threshold. Resetting sound playback flag.")
            sound_played = False

    time.sleep(0.2)