# SPDX-FileCopyrightText: 2025
# SPDX-License-Identifier: MIT

"""Combined test for APDS9960 proximity sensor and rotary encoder."""

import time
import board
from adafruit_apds9960.apds9960 import APDS9960
from adafruit_seesaw import seesaw, rotaryio, digitalio

# Initialize I2C
i2c = board.I2C()

# Initialize APDS9960 proximity sensor
apds = APDS9960(i2c)
apds.enable_proximity = True

# Initialize rotary encoder
ss = seesaw.Seesaw(i2c, addr=0x36)

# Check seesaw product
seesaw_product = (ss.get_version() >> 16) & 0xFFFF
print("Found seesaw product {}".format(seesaw_product))
if seesaw_product != 4991:
    print("Warning: Expected product 4991")

# Setup encoder button
ss.pin_mode(24, ss.INPUT_PULLUP)
button = digitalio.DigitalIO(ss, 24)
button_held = False

# Setup encoder
encoder = rotaryio.IncrementalEncoder(ss)
last_position = None

print("Starting sensor monitoring...")
print("=" * 50)

while True:
    # Read proximity sensor
    proximity_value = apds.proximity
    
    # Read encoder position (negate for clockwise positive)
    position = -encoder.position
    
    # Check if position changed
    position_changed = position != last_position
    if position_changed:
        last_position = position
    
    # Check button state
    button_pressed = False
    button_released = False
    
    if not button.value and not button_held:
        button_held = True
        button_pressed = True
    
    if button.value and button_held:
        button_held = False
        button_released = True
    
    # Print sensor values
    print("Proximity: {:3d} | Encoder: {:4d}".format(proximity_value, position), end="")
    
    if button_pressed:
        print(" | Button PRESSED", end="")
    elif button_released:
        print(" | Button RELEASED", end="")
    
    print()  # New line
    
    time.sleep(0.2)