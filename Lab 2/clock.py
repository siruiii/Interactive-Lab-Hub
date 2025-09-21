import time
import subprocess
import digitalio
import board
import pygame
import glob
import os
from PIL import Image, ImageDraw, ImageFont
import adafruit_rgb_display.st7789 as st7789
from time import strftime




# Initialize pygame mixer for audio
pygame.mixer.init()




def find_audio_file(index, audio_folder="clock_audio"):
    """Find the audio file for the given index (1-12)"""
    audio_file = os.path.join(audio_folder, f"{index}.mp3")
    if os.path.exists(audio_file):
        return audio_file
    else:
        print(f"Warning: No audio file {index}.mp3 found in {audio_folder}")
        return None




def play_audio(audio_file):
    """Play the audio file"""
    try:
        pygame.mixer.music.load(audio_file)
        pygame.mixer.music.play()
        print(f"Playing audio: {audio_file}")
    except pygame.error as e:
        print(f"Error playing audio: {e}")




def stop_audio():
    """Stop the currently playing audio"""
    pygame.mixer.music.stop()
    print("Audio stopped")




def is_audio_playing():
    """Check if audio is currently playing"""
    return pygame.mixer.music.get_busy()




def load_and_resize_images(image_folder="clock_img", width=240, height=135):
    """Load and resize all images for the display (0-1 to 0-12 and 1-1 to 1-12)"""
    images = {}
    
    # Load images for both states (0 = not playing, 1 = playing)
    for state in [0, 1]:
        images[state] = {}
        for i in range(1, 13):  # 1 to 12
            try:
                img_path = f"{image_folder}/{state}-{i}.png"
                img = Image.open(img_path)
                img = img.resize((width, height))
                images[state][i] = img
                print(f"Loaded image {state}-{i}.png")
            except FileNotFoundError:
                print(f"Warning: Could not find {img_path}")
                # Create a placeholder image if file doesn't exist
                placeholder = Image.new("RGB", (width, height), (50, 50, 50))
                images[state][i] = placeholder
    
    return images




def update_display(disp, images, current_index, is_playing, font, width, height, rotation=90):
    """Update the display with the current image and time overlay"""
    # Create new image for this frame
    image = Image.new("RGB", (width, height))
    
    # Choose the appropriate image based on playing state
    state = 1 if is_playing else 0
    background_image = images[state][current_index]
    
    # Paste the background image
    image.paste(background_image, (0, 0))
    
    # Get drawing object for text overlay
    draw = ImageDraw.Draw(image)
    
    # Add time text overlay
    current_time = strftime("%M  %S")
    x = 130
    y = 63
    draw.text((x, y), current_time, font=font, fill="#000000")
    
    # Display the final image
    disp.image(image, rotation)




# Configuration for CS and DC pins (these are FeatherWing defaults on M0/M4):
cs_pin = digitalio.DigitalInOut(board.D5)
dc_pin = digitalio.DigitalInOut(board.D25)
reset_pin = None


# Config for display baudrate (default max is 24mhz):
BAUDRATE = 64000000


# Setup SPI bus using hardware SPI:
spi = board.SPI()


# Create the ST7789 display:
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


# Display dimensions (swapped for landscape)
height = disp.width  # we swap height/width to rotate it to landscape!
width = disp.height
rotation = 90


# Load all images
images = load_and_resize_images("clock_img", width, height)


# Load font
font = ImageFont.truetype("proj_docs/Abel-Regular.ttf", 32)


# Turn on the backlight
backlight = digitalio.DigitalInOut(board.D22)
backlight.switch_to_output()
backlight.value = True


# Setup buttons
buttonA = digitalio.DigitalInOut(board.D23)    # GPIO23 (PIN 16)
buttonB = digitalio.DigitalInOut(board.D24)    # GPIO24 (PIN 18)
# Use internal pull-ups; buttons then read LOW when pressed.
buttonA.switch_to_input(pull=digitalio.Pull.UP)
buttonB.switch_to_input(pull=digitalio.Pull.UP)


# Initial display clear
initial_image = Image.new("RGB", (width, height))
draw = ImageDraw.Draw(initial_image)
draw.rectangle((0, 0, width, height), outline=0, fill=(0, 0, 0))
disp.image(initial_image, rotation)


# State variables
current_index = 1  # Start with index 1 (images 0-1.png/1-1.png, audio 1.mp3)
button_a_last_state = True  # Track previous button state for edge detection
button_b_last_state = True  # Track button B state for edge detection


print(f"Starting display loop. Loaded images for indices 1-12.")
print("Press Button A to cycle through indices 1-12.")
print("Press Button B to play/stop current index audio.")
print(f"Starting with index {current_index}")


while True:
    a_pressed = (buttonA.value == False)
    b_pressed = (buttonB.value == False)
    
    # Check for button A press (edge detection - only trigger on press, not hold)
    if a_pressed and button_a_last_state:
        # Button A was just pressed, move to next index (1-12)
        current_index = (current_index % 12) + 1  # Cycles 1->2->...->12->1
        print(f"Switched to index {current_index}")
        # Stop any currently playing audio when switching indices
        if is_audio_playing():
            stop_audio()
    
    # Check for button B press (edge detection - only trigger on press, not hold)
    if b_pressed and button_b_last_state:
        # Button B was just pressed, toggle audio playback for current index
        if is_audio_playing():
            stop_audio()
        else:
            # Find and play the audio file for current index
            audio_file = find_audio_file(current_index, "clock_audio")
            if audio_file:
                play_audio(audio_file)
            else:
                print(f"No audio file found for index {current_index}")
    
    # Update the last button states
    button_a_last_state = not a_pressed
    button_b_last_state = not b_pressed
    
    # Update the display with current image (based on index and playing state)
    currently_playing = is_audio_playing()
    update_display(disp, images, current_index, currently_playing, font, width, height, rotation)
    
    time.sleep(0.1)  # Reduced sleep time for more responsive display updates