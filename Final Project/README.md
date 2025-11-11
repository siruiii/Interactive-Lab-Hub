# Final Project

[Project Plan](#project-plan) 

<!-- [Functioning Project](#functioning-project) 

[Documentation of Design Process](#documentation-of-design-process) 

[Archive of All Code and Design Patterns](#archive-of-all-code-and-design-patterns) 

[Video Demo](#video-demo) 

[Reflections on Process](#reflections-on-process) 

[Group Work Distribution](#group-work-distribution)  -->

## Project Plan

This project will be done by **Jully Li (hl2568), Weicong Hong (wh528), Feier Su (fs495), Sirui Wang (sw2449)** in collaboration.

### Big Idea

#### Object Journal Dock — Tangible Memory Device
**What We’re Building**
- An RFID-based interactive device that recognizes physical objects. When an object is placed on the dock, the device displays past journals or recorded feelings linked to it.
- Users can add new voice or text entries, creating a tangible memory system that connects emotions to objects.

**Fall-back Plan**
The project can pivot to use a QR code-based recognition system. Generate Unique QR code for each object using existing python library and decode them via camera. 

<img src="proj_docs/verplank.jpg" width="900"/>

### Timeline

**November 15** - Finalize device concept & define recognition logic, user flow: Decide detection approach and explore recognition logic

**November 19** - Implement object recognition prototype: UI display, Pi physical UI, validate recognition reliability

**November 23** - Integrate journaling interface: Combine recognition system with journaling UI and PiTFT display.

**December 1** - Functional check-off: Fully working demo: object recognized, previous journals displayed, new entries recordable

**December 8** - Final Presentation: Organize everything into a coherent presentation; complete README

**December 15** - Write-up and documentation

### Parts Needed
- Raspberry Pi
- Adafruit Mini PiTFT
- USB Camera with Microphone
- SparkFun Qwiic Joystick
- SparkFun Qwiic Red and Green Buttons
- RFID Reader
- RFID Tags
