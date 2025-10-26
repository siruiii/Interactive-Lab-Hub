# Observant Systems

**COLLABORATORS: Jully Li (hl2568), Weicong Hong (wh528), Feier Su (fs495), Sirui Wang (sw2449)**


For lab this week, we focus on creating interactive systems that can detect and respond to events or stimuli in the environment of the Pi, like the Boat Detector we mentioned in lecture. 
Your **observant device** could, for example, count items, find objects, recognize an event or continuously monitor a room.

This lab will help you think through the design of observant systems, particularly corner cases that the algorithms need to be aware of.

## Prep

1.  Install VNC on your laptop if you have not yet done so. This lab will actually require you to run script on your Pi through VNC so that you can see the video stream. Please refer to the [prep for Lab 2](https://github.com/FAR-Lab/Interactive-Lab-Hub/blob/-/Lab%202/prep.md#using-vnc-to-see-your-pi-desktop).
2.  Install the dependencies as described in the [prep document](prep.md). 
3.  Read about [OpenCV](https://opencv.org/about/),[Pytorch](https://pytorch.org/), [MediaPipe](https://mediapipe.dev/), and [TeachableMachines](https://teachablemachine.withgoogle.com/).
4.  Read Belloti, et al.'s [Making Sense of Sensing Systems: Five Questions for Designers and Researchers](https://www.cc.gatech.edu/~keith/pubs/chi2002-sensing.pdf).

### For the lab, you will need:
1. Pull the new Github Repo
1. Raspberry Pi
1. Webcam 

### Deliverables for this lab are:
1. Show pictures, videos of the "sense-making" algorithms you tried.
1. Show a video of how you embed one of these algorithms into your observant system.
1. Test, characterize your interactive device. Show faults in the detection and how the system handled it.

## Overview
Building upon the paper-airplane metaphor (we're understanding the material of machine learning for design), here are the four sections of the lab activity:

A) [Play](#part-a)

B) [Fold](#part-b)

C) [Flight test](#part-c)

D) [Reflect](#part-d)

---

### Part A
### Play with different sense-making algorithms.

#### Pytorch for object recognition

For this first demo, you will be using PyTorch and running a MobileNet v2 classification model in real time (30 fps+) on the CPU. We will be following steps adapted from [this tutorial](https://pytorch.org/tutorials/intermediate/realtime_rpi.html).

![torch](Readme_files/pyt.gif)


To get started, install dependencies into a virtual environment for this exercise as described in [prep.md](prep.md).

Make sure your webcam is connected.

You can check the installation by running:

```
python -c "import torch; print(torch.__version__)"
```

If everything is ok, you should be able to start doing object recognition. For this default example, we use [MobileNet_v2](https://arxiv.org/abs/1801.04381). This model is able to perform object recognition for 1000 object classes (check [classes.json](classes.json) to see which ones.

Start detection by running  

```
python infer.py
```

The first 2 inferences will be slower. Now, you can try placing several objects in front of the camera.

Read the `infer.py` script and become familiar with the code. You can change the video resolution and frames per second (FPS). You may also use the weights of the larger pre-trained mobilenet_v3_large model, as described [here](https://pytorch.org/tutorials/intermediate/realtime_rpi.html#model-choices).

#### More classes

[PyTorch supports transfer learning](https://pytorch.org/tutorials/beginner/transfer_learning_tutorial.html), so you can fine‑tune and transfer learn models to recognize your own objects. It requires extra steps, so we won't cover it here.

For more details on transfer learning and deployment to embedded devices, see Deep Learning on Embedded Systems: A Hands‑On Approach Using Jetson Nano and Raspberry Pi (Tariq M. Arif). [Chapter 10](https://onlinelibrary.wiley.com/doi/10.1002/9781394269297.ch10) covers transfer learning for object detection on desktop, and [Chapter 15](https://onlinelibrary.wiley.com/doi/10.1002/9781394269297.ch15) describes moving models to the Pi using ONNX.

### Machine Vision With Other Tools
The following sections describe tools ([MediaPipe](#mediapipe) and [Teachable Machines](#teachable-machines)).

#### MediaPipe

A established open source and efficient method of extracting information from video streams comes out of Google's [MediaPipe](https://mediapipe.dev/), which offers state of the art face, face mesh, hand pose, and body pose detection.

![Media pipe](Readme_files/mp.gif)

To get started, install dependencies into a virtual environment for this exercise as described in [prep.md](prep.md):

Each of the installs will take a while, please be patient. After successfully installing mediapipe, connect your webcam to your Pi and use **VNC to access to your Pi**, open the terminal, and go to Lab 5 folder and run the hand pose detection script we provide:
(***it will not work if you use ssh from your laptop***)


```
(venv-ml) pi@ixe00:~ $ cd Interactive-Lab-Hub/Lab\ 5
(venv-ml) pi@ixe00:~ Interactive-Lab-Hub/Lab 5 $ python hand_pose.py
```

Try the two main features of this script: 1) pinching for percentage control, and 2) "[Quiet Coyote](https://www.youtube.com/watch?v=qsKlNVpY7zg)" for instant percentage setting. Notice how this example uses hardcoded positions and relates those positions with a desired set of events, in `hand_pose.py`. 

Consider how you might use this position based approach to create an interaction, and write how you might use it on either face, hand or body pose tracking.

(You might also consider how this notion of percentage control with hand tracking might be used in some of the physical UI you may have experimented with in the last lab, for instance in controlling a servo or rotary encoder.)



#### Moondream Vision-Language Model

[Moondream](https://www.ollama.com/library/moondream) is a lightweight vision-language model that can understand and answer questions about images. Unlike the classification models above, Moondream can describe images in natural language and answer specific questions about what it sees.

To use Moondream, first make sure Ollama is running and pull the model:
```bash
ollama pull moondream
```

Then run the simple demo script:
```bash
python moondream_simple.py
```

This will capture an image from your webcam and let you ask questions about it in natural language. Note that vision-language models are slower than classification models (responses may take up to minutes on a Raspberry Pi). There are newer models like [LFM2-VL](https://huggingface.co/LiquidAI/LFM2-VL-450M-GGUF), but many are very recent and not yet optimized for embedded devices.

**Design consideration**: Think about how slower response times change your interaction design. What kinds of observant systems benefit from thoughtful, delayed responses rather than real-time classification? Consider systems that monitor over longer time periods or provide periodic summaries rather than instant feedback.

#### Teachable Machines
Google's [TeachableMachines](https://teachablemachine.withgoogle.com/train) is very useful for prototyping with the capabilities of machine learning. We are using [a python package](https://github.com/MeqdadDev/teachable-machine-lite) with tensorflow lite to simplify the deployment process.

![Tachable Machines Pi](Readme_files/tml_pi.gif)

To get started, install dependencies into a virtual environment for this exercise as described in [prep.md](prep.md):

After installation, connect your webcam to your Pi and use **VNC to access to your Pi**, open the terminal, and go to Lab 5 folder and run the example script:
(***it will not work if you use ssh from your laptop***)


```
(venv-tml) pi@ixe00:~ Interactive-Lab-Hub/Lab 5 $ python tml_example.py
```


Next train your own model. Visit [TeachableMachines](https://teachablemachine.withgoogle.com/train), select Image Project and Standard model. The raspberry pi 4 is capable to run not just the low resource models. Second, use the webcam on your computer to train a model. *Note: It might be advisable to use the pi webcam in a similar setting you want to deploy it to improve performance.*  For each class try to have over 150 samples, and consider adding a background or default class where you have nothing in view so the model is trained to know that this is the background. Then create classes based on what you want the model to classify. Lastly, preview and iterate. Finally export your model as a 'Tensorflow lite' model. You will find an '.tflite' file and a 'labels.txt' file. Upload these to your pi (through one of the many ways such as [scp](https://www.raspberrypi.com/documentation/computers/remote-access.html#using-secure-copy), sftp, [vnc](https://help.realvnc.com/hc/en-us/articles/360002249917-VNC-Connect-and-Raspberry-Pi#transferring-files-to-and-from-your-raspberry-pi-0-6), or a connected visual studio code remote explorer).
![Teachable Machines Browser](Readme_files/tml_browser.gif)
![Tensorflow Lite Download](Readme_files/tml_download-model.png)

Include screenshots of your use of Teachable Machines, and write how you might use this to create your own classifier. Include what different affordances this method brings, compared to the OpenCV or MediaPipe options.

#### (Optional) Legacy audio and computer vision observation approaches
In an earlier version of this class students experimented with observing through audio cues. Find the material here:
[Audio_optional/audio.md](Audio_optional/audio.md). 
Teachable machines provides an audio classifier too. If you want to use audio classification this is our suggested method. 

In an earlier version of this class students experimented with foundational computer vision techniques such as face and flow detection. Techniques like these can be sufficient, more performant, and allow non discrete classification. Find the material here:
[CV_optional/cv.md](CV_optional/cv.md).

### Part B
### Construct a simple interaction.

* Pick one of the models you have tried, and experiment with prototyping an interaction.
* This can be as simple as the boat detector shown in lecture.
* Try out different interaction outputs and inputs.


**\*\*\*Describe and detail the interaction, as well as your experimentation here.\*\*\***
#### Gesture DJ 2.0
- Concept: Use hand gestures to control music
- Description: For this lab, we built a gesture-based sound controller using MediaPipe Hands on the Raspberry Pi. The interaction is based on using simple hand gestures to modulate sound in real time. Specifically, the pinch distance between the thumb and index finger of the hand controls music volume.

In experimentation, we tested the system under different lighting, camera angles, and backgrounds to observe detection stability. The MediaPipe hand model performed well with distinct hand shapes, but lost tracking under low light or when the hand was partially out of frame.

### Part C
### Test the interaction prototype

Now flight test your interactive prototype and **note down your observations**:
For example:
1. When does it what it is supposed to do?
```
- Stable tracking with good, even lighting.
- An entire hand being captured by the camera.
- Single hand centered in frame.
- Clear index–thumb pinch gesture facing the camera.
- Slow clear movements.
```
2. When does it fail?
```
- Low light / backlighting
- Hand partially out of frame, making pinch distance become unreliable
- High-speed gestures
- Multiple hands/people entering the frame, causing wrong hand selection
- Non-stable/shaking camera
```
3. When it fails, why does it fail?
```
- Low light / backlighting: The webcam sensor struggles to detect edges and contrast when illumination is uneven; the hand becomes underexposed, causing the model to misread contours and landmark points.
- Hand partially out of frame, making pinch distance become unreliable: The algorithm depends on seeing both fingers fully to measure pinch distance or classify a pose.
- High-speed gestures: Rapid movement causes motion blur, making frames appear smeared.
- Multiple hands/people entering the frame, causing wrong hand selection: When the model tries to track several candidates simultaneously, it may assign the wrong landmarks to the active user.
- Non-stable/shaking camera: When the camera moves, the background and relative hand position both shift.
```
4. Based on the behavior you have seen, what other scenarios could cause problems?
```
- Gloves, rings, or long sleeves (partially) covering fingers.
- Shadows casting finger-like edges.
- Background hands/objects (posters/hand images) close to the camera field.
- Non-frontal hand poses (e.g., thumb hidden behind palm).
- User fatigue; lacking accessibility considerations on hand tremors or limited range of motion.
```

**\*\*\*Think about someone using the system. Describe how you think this will work.\*\*\***
1. Are they aware of the uncertainties in the system?
```
Users might not be fully aware of the underlying uncertainties. When the pitch suddenly jumps or the volume cuts out, they may assume they made an incorrect gesture rather than realizing that the hand-tracking model temporarily lost confidence. 
```

2. How bad would they be impacted by a miss classification?
```
A misclassification here is relatively low-impact, it just creates an unexpected or off-key sound rather than a critical failure. However, frequent noise, pitch spikes, or muted moments could disrupt the creative flow or make the experience feel inconsistent. 
```

3. How could change your interactive system to address this?
```
- State + confidence UI: On-screen overlay with per-hand confidence bars; color-code stable/unstable.
Auditory safety rails:
- Clamp pitch to a musical scale; glide (portamento) between notes.
- Volume ramp (attack/release) to avoid pops when confidence drops.
- Role locking: Explicit “Calibrate” gesture to lock which hand controls pitch/volume; show labels on-screen.
- Accessibility mode: Larger pinch thresholds, steadier smoothing, optional dwell-based input.
```

4. Are there optimizations you can try to do on your sense-making algorithm.
```
- Confidence-gated pipeline: Only emit volume updates if both the hand score and the two landmark visibilities (thumb/index tips) exceed a threshold.
- Outlier rejection + temporal smoothing
- Non-linear mapping for better control: Map pinch distance → volume with a non-linear function
```

### Part D
### Characterize your own Observant system

Now that you have experimented with one or more of these sense-making systems **characterize their behavior**.
During the lecture, we mentioned questions to help characterize a material:
* What can you use X for?
```
- Hands-free, real-time system volume control by pinching thumb–index (maps pinch distance → 0–100%).
- One-gesture mute: the “quiet coyote!” (mixed long/short inter-finger distances) forces volume to 0%.
```
* What is a good environment for X?
```
Even front lighting, uncluttered background, single hand centered and fully in frame.
```
* What is a bad environment for X?
```
- Low light, backlighting, or fast motion.
- Multiple hands/people in frame, or hands partially off-screen/occluded.
```
* When will X break?
```
Input assumptions violated: Hand landmarks not returned (no hand / lost tracking) → UI keeps drawing old bar; volume stays at last value.
```
* When it breaks how will X break?
```
No hand detection (e.g., detectionCon=0): landmarks empty most frames → volume never updates, bar stays at last drawn, music continues at last set loudness.
```
* What are other properties/behaviors of X?
```
- Starts at 50% volume unconditionally (set_volume(50) at boot).
- Linear mapping from pinch distance 50→300 px to 0→100% (no smoothing/hysteresis; can feel twitchy).
```
* How does X feel?
```
- Immediate and expressive when lighting is good and motion is moderate.
- Occasionally surprising: mute snaps on/off when the “quiet coyote!”; volume can spike if distance briefly jumps.
```

**\*\*\*Include a short video demonstrating the answers to these questions.\*\*\***

Source code: https://github.com/siruiii/Interactive-Lab-Hub/blob/4fc51543e8a3d962f654d912089122a11d45ea90/Lab%205/dj2.py

Video: 
- https://youtube.com/shorts/SH_TeEvClkg?feature=share
- https://youtube.com/shorts/OTi3Ou8AaQY?feature=share

### Part 2.

Following exploration and reflection from Part 1, finish building your interactive system, and demonstrate it in use with a video.

**\*\*\*Include a short video demonstrating the finished result.\*\*\***
