# Chatterboxes
**COLLABORATORS: Jully Li (hl2568), Weicong Hong (wh528), Feier Su (fs495), Sirui Wang (sw2449)**
[![Watch the video](https://user-images.githubusercontent.com/1128669/135009222-111fe522-e6ba-46ad-b6dc-d1633d21129c.png)](https://www.youtube.com/embed/Q8FWzLMobx0?start=19)

In this lab, we want you to design interaction with a speech-enabled device--something that listens and talks to you. This device can do anything *but* control lights (since we already did that in Lab 1).  First, we want you first to storyboard what you imagine the conversational interaction to be like. Then, you will use wizarding techniques to elicit examples of what people might say, ask, or respond.  We then want you to use the examples collected from at least two other people to inform the redesign of the device.

We will focus on **audio** as the main modality for interaction to start; these general techniques can be extended to **video**, **haptics** or other interactive mechanisms in the second part of the Lab.

## Prep for Part 1: Get the Latest Content and Pick up Additional Parts 

Please check instructions in [prep.md](prep.md) and complete the setup before class on Wednesday, Sept 23rd.

### Pick up Web Camera If You Don't Have One

Students who have not already received a web camera will receive their [Logitech C270 Webcam](https://www.amazon.com/Logitech-Desktop-Widescreen-Calling-Recording/dp/B004FHO5Y6/ref=sr_1_3?crid=W5QN79TK8JM7&dib=eyJ2IjoiMSJ9.FB-davgIQ_ciWNvY6RK4yckjgOCrvOWOGAG4IFaH0fczv-OIDHpR7rVTU8xj1iIbn_Aiowl9xMdeQxceQ6AT0Z8Rr5ZP1RocU6X8QSbkeJ4Zs5TYqa4a3C_cnfhZ7_ViooQU20IWibZqkBroF2Hja2xZXoTqZFI8e5YnF_2C0Bn7vtBGpapOYIGCeQoXqnV81r2HypQNUzFQbGPh7VqjqDbzmUoloFA2-QPLa5lOctA.L5ztl0wO7LqzxrIqDku9f96L9QrzYCMftU_YeTEJpGA&dib_tag=se&keywords=webcam%2Bc270&qid=1758416854&sprefix=webcam%2Bc270%2Caps%2C125&sr=8-3&th=1) and bluetooth speaker on Wednesday at the beginning of lab. If you cannot make it to class this week, please contact the TAs to ensure you get these. 

### Get the Latest Content

As always, pull updates from the class Interactive-Lab-Hub to both your Pi and your own GitHub repo. There are 2 ways you can do so:

**\[recommended\]**Option 1: On the Pi, `cd` to your `Interactive-Lab-Hub`, pull the updates from upstream (class lab-hub) and push the updates back to your own GitHub repo. You will need the *personal access token* for this.

```
pi@ixe00:~$ cd Interactive-Lab-Hub
pi@ixe00:~/Interactive-Lab-Hub $ git pull upstream Fall2025
pi@ixe00:~/Interactive-Lab-Hub $ git add .
pi@ixe00:~/Interactive-Lab-Hub $ git commit -m "get lab3 updates"
pi@ixe00:~/Interactive-Lab-Hub $ git push
```

Option 2: On your your own GitHub repo, [create pull request](https://github.com/FAR-Lab/Developing-and-Designing-Interactive-Devices/blob/2022Fall/readings/Submitting%20Labs.md) to get updates from the class Interactive-Lab-Hub. After you have latest updates online, go on your Pi, `cd` to your `Interactive-Lab-Hub` and use `git pull` to get updates from your own GitHub repo.

## Part 1.
### Setup 

Activate your virtual environment

```
pi@ixe00:~$ cd Interactive-Lab-Hub
pi@ixe00:~/Interactive-Lab-Hub $ cd Lab\ 3
pi@ixe00:~/Interactive-Lab-Hub/Lab 3 $ python3 -m venv .venv
pi@ixe00:~/Interactive-Lab-Hub $ source .venv/bin/activate
(.venv)pi@ixe00:~/Interactive-Lab-Hub $ 
```

Run the setup script
```(.venv)pi@ixe00:~/Interactive-Lab-Hub $ pip install -r requirements.txt  ```

Next, run the setup script to install additional text-to-speech dependencies:
```
(.venv)pi@ixe00:~/Interactive-Lab-Hub/Lab 3 $ ./setup.sh
```

### Text to Speech 

In this part of lab, we are going to start peeking into the world of audio on your Pi! 

We will be using the microphone and speaker on your webcamera. In the directory is a folder called `speech-scripts` containing several shell scripts. `cd` to the folder and list out all the files by `ls`:

```
pi@ixe00:~/speech-scripts $ ls
Download        festival_demo.sh  GoogleTTS_demo.sh  pico2text_demo.sh
espeak_demo.sh  flite_demo.sh     lookdave.wav
```

You can run these shell files `.sh` by typing `./filename`, for example, typing `./espeak_demo.sh` and see what happens. Take some time to look at each script and see how it works. You can see a script by typing `cat filename`. For instance:

```
pi@ixe00:~/speech-scripts $ cat festival_demo.sh 
#from: https://elinux.org/RPi_Text_to_Speech_(Speech_Synthesis)#Festival_Text_to_Speech
```
You can test the commands by running
```
echo "Just what do you think you're doing, Dave?" | festival --tts
```

Now, you might wonder what exactly is a `.sh` file? 
Typically, a `.sh` file is a shell script which you can execute in a terminal. The example files we offer here are for you to figure out the ways to play with audio on your Pi!

You can also play audio files directly with `aplay filename`. Try typing `aplay lookdave.wav`.

\*\***Write your own shell file to use your favorite of these TTS engines to have your Pi greet you by name.**\*\*
(This shell file should be saved to your own repo for this lab.)

Shell file: https://github.com/siruiii/Interactive-Lab-Hub/blob/f60a190fbbe2c7a8e6154d53bfbb73955c6a41fb/Lab%203/speech-scripts/name.sh

Add execute permission before run `./name.sh` in speech-scripts folder
```bash
chmod +x name.sh
```
---
Bonus:
[Piper](https://github.com/rhasspy/piper) is another fast neural based text to speech package for raspberry pi which can be installed easily through python with:
```
pip install piper-tts
```
and used from the command line. Running the command below the first time will download the model, concurrent runs will be faster. 
```
echo 'Welcome to the world of speech synthesis!' | piper \
  --model en_US-lessac-medium \
  --output_file welcome.wav
```
Check the file that was created by running `aplay welcome.wav`. Many more languages are supported and audio can be streamed dirctly to an audio output, rather than into an file by:

```
echo 'This sentence is spoken first. This sentence is synthesized while the first sentence is spoken.' | \
  piper --model en_US-lessac-medium --output-raw | \
  aplay -r 22050 -f S16_LE -t raw -
```
  
### Speech to Text

Next setup speech to text. We are using a speech recognition engine, [Vosk](https://alphacephei.com/vosk/), which is made by researchers at Carnegie Mellon University. Vosk is amazing because it is an offline speech recognition engine; that is, all the processing for the speech recognition is happening onboard the Raspberry Pi. 

Make sure you're running in your virtual environment with the dependencies already installed:
```
source .venv/bin/activate
```

Test if vosk works by transcribing text:

```
vosk-transcriber -i recorded_mono.wav -o test.txt
```

You can use vosk with the microphone by running 
```
python test_microphone.py -m en
```

---
Bonus:
[Whisper](https://openai.com/index/whisper/) is a neural network–based speech-to-text (STT) model developed and open-sourced by OpenAI. Compared to Vosk, Whisper generally achieves higher accuracy, particularly on noisy audio and diverse accents. It is available in multiple model sizes; for edge devices such as the Raspberry Pi 5 used in this class, the tiny.en model runs with reasonable latency even without a GPU.

By contrast, Vosk is more lightweight and optimized for running efficiently on low-power devices like the Raspberry Pi. The choice between Whisper and Vosk depends on your scenario: if you need higher accuracy and can afford slightly more compute, Whisper is preferable; if your priority is minimal resource usage, Vosk may be a better fit.

In this class, we provide two Whisper options: A quantized 8-bit faster-whisper model for speed, and the standard Whisper model. Try them out and compare the trade-offs.

Make sure you're in the Lab 3 directory with your virtual environment activated:
```
cd ~/Interactive-Lab-Hub/Lab\ 3/speech-scripts
source ../.venv/bin/activate
```

Then test the Whisper models:
```
python whisper_try.py
```
and

```
python faster_whisper_try.py
```
\*\***Write your own shell file that verbally asks for a numerical based input (such as a phone number, zipcode, number of pets, etc) and records the answer the respondent provides.**\*\*

Shell file: https://github.com/siruiii/Interactive-Lab-Hub/blob/f60a190fbbe2c7a8e6154d53bfbb73955c6a41fb/Lab%203/speech-scripts/zipcode.sh

Download the voice files before run `./zipcode.sh` in speech-scripts folder
```bash
# Create voices directory if it doesn't exist
mkdir -p ~/.local/share/piper-tts/voices/

# Download the voice files
cd ~/.local/share/piper-tts/voices/

# Download both the model (.onnx) and config (.json) files
wget https://github.com/rhasspy/piper/releases/download/2023.11.14-2/en_US-lessac-medium.onnx
wget https://github.com/rhasspy/piper/releases/download/2023.11.14-2/en_US-lessac-medium.onnx.json
```

Play the recorded zipcode audio file `zipcode.wav`
```bash
aplay zipcode.wav
```

### 🤖 NEW: AI-Powered Conversations with Ollama

Want to add intelligent conversation capabilities to your voice projects? **Ollama** lets you run AI models locally on your Raspberry Pi for sophisticated dialogue without requiring internet connectivity!

#### Quick Start with Ollama

**Installation** (takes ~5 minutes):
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Download recommended model for Pi 5
ollama pull phi3:mini

# Install system dependencies for audio (required for pyaudio)
sudo apt-get update
sudo apt-get install -y portaudio19-dev python3-dev

# Create separate virtual environment for Ollama (due to pyaudio conflicts)
cd ollama/
python3 -m venv ollama_venv
source ollama_venv/bin/activate

# Install Python dependencies in separate environment
pip install -r ollama_requirements.txt
```
#### Ready-to-Use Scripts

We've created three Ollama integration scripts for different use cases:

**1. Basic Demo** - Learn how Ollama works:
```bash
python3 ollama_demo.py
```

**2. Voice Assistant** - Full speech-to-text + AI + text-to-speech:
```bash
python3 ollama_voice_assistant.py
```

**3. Web Interface** - Beautiful web-based chat with voice options:
```bash
python3 ollama_web_app.py
# Then open: http://localhost:5000
```

#### Integration in Your Projects

Simple example to add AI to any project:
```python
import requests

def ask_ai(question):
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": "phi3:mini", "prompt": question, "stream": False}
    )
    return response.json().get('response', 'No response')

# Use it anywhere!
answer = ask_ai("How should I greet users?")
```

**📖 Complete Setup Guide**: See `OLLAMA_SETUP.md` for detailed instructions, troubleshooting, and advanced usage!

\*\***Try creating a simple voice interaction that combines speech recognition, Ollama processing, and text-to-speech output. Document what you built and how users responded to it.**\*\*

Testing with the web app
```bash
export PYTHONIOENCODING=utf-8
python3 ollama_web_app.py
```
![web-app-test](proj_docs/web-app-test.png)

### Serving Pages

In Lab 1, we served a webpage with flask. In this lab, you may find it useful to serve a webpage for the controller on a remote device. Here is a simple example of a webserver.

```
pi@ixe00:~/Interactive-Lab-Hub/Lab 3 $ python server.py
 * Serving Flask app "server" (lazy loading)
 * Environment: production
   WARNING: This is a development server. Do not use it in a production deployment.
   Use a production WSGI server instead.
 * Debug mode: on
 * Running on http://0.0.0.0:5000/ (Press CTRL+C to quit)
 * Restarting with stat
 * Debugger is active!
 * Debugger PIN: 162-573-883
```
From a remote browser on the same network, check to make sure your webserver is working by going to `http://<YourPiIPAddress>:5000`. You should be able to see "Hello World" on the webpage.

### Storyboard

Storyboard and/or use a Verplank diagram to design a speech-enabled device. (Stuck? Make a device that talks for dogs. If that is too stupid, find an application that is better than that.) 

\*\***Post your storyboard and diagram here.**\*\*

Write out what you imagine the dialogue to be. Use cards, post-its, or whatever method helps you develop alternatives or group responses. 

During the brainstorming process, we came up with several ideas and made storyboards for each of them:
#### Storyboard 1 - 20 Questions game
A verbal guessing game with the device where the user thinks of a person, place, or thing, and the device has a limit of asking 20 yes-or-no questions to guess what it is.
<p align="center">
  <img src="proj_docs/storyboard-1.png" alt="20 questions device storyboard" />
</p>  

#### Storyboard 2 - Interview/presentation mock
A voice practice coach that prompts questions, times responses, and gives quick feedback on pacing, content, and clarity, aiming to help users mock upcoming interview/presentation tasks.
<p align="center">
  <img src="proj_docs/storyboard-2.png" alt="Interview/Presentation Mock storyboard" />
</p>  

#### Storyboard 3 - Smart doorstep assistant
Smart Doorstep Assistant is a two-way, multimodal communicator for home entrances. detects knocks, asks visitors their purpose, and notifies the resident. It converts visitors’ spoken/typed messages into natural-sounding speech, and lets residents with voice loss reply by typing, tapping preset phrases, or choosing pictograms that are spoken aloud at the door.
<p align="center">
  <img src="proj_docs/storyboard-3.png" alt="Interview/Presentation Mock storyboard" />
</p>  

#### Storyboard 4 - Sleep talk logger
Sleep Talk Logger is an overnight companion that listens and records the brief speech events while you sleep, records them, and turns them into a clean, time-stamped journal you can review in the morning. 
<p align="center">
  <img src="proj_docs/storyboard-4.png" alt="Sleep Talk Logger storyboard" width=400px />
</p> 

_(Images generated by ChatGPT-5)_

\*\***Please describe and document your process.**\*\*

After discussion, we decided go with the first idea of 20 questions game bot. Here is how we plan the game scene to be:

For the 20 Questions game bot, the bot sits in a corner and invites play when someone approaches. A webcam presence check (no images stored) detects a face for ~2 seconds, then prompts: “Want to play 20 Questions? Say ‘let’s play’ or wave.” If the visitor responds, it onboards and starts; if not or they decline, it quietly returns to idle and won’t re-prompt until after a short cooldown.

**Planned Dialogue:** 

Note: In reality, users’ responses may vary. The script is provided only as an example of how the conversation could unfold.

<details>
<summary> <b>Dialogue Script</b> </summary> 

Device: Want to play 20 Questions? Say ‘let’s play’ or wave.

User: Let's play.
 
Device: Think of a person. Say “ready” when you’re set.
 
User: Ready.
 
Device: Great! I’ll ask up to 20 yes-or-no questions. First: Is this person real?
 
User: Yes.
 
Device: Are they currently alive?
 
User: Yes.
 
Device: Are they a musician?
 
User: Yes.
 
Device: Are they British?
 
User: No.
 
Device: Are they famous for avant-garde fashion?
 
User: Yes.
 
Device: Have they won an Oscar for Best Original Song?
 
User: Yes.
 
Device: Have they released jazz albums with Tony Bennett?
 
User: Yes.
 
Device: I guess… Lady Gaga.
 
User: Correct.
 
Device: Nailed it in 7 questions! Want a rematch?
</details>

### Acting out the dialogue

Find a partner, and *without sharing the script with your partner* try out the dialogue you've designed, where you (as the device designer) act as the device you are designing.  Please record this interaction (for example, using Zoom's record feature).

\*\***Describe if the dialogue seemed different than what you imagined when it was acted out, and how.**\*\*

**How we act out the dialogue:**
<p align="center">
  <a href="https://youtu.be/93-dGnLfw1I" target="_blank">
    <img src="https://img.youtube.com/vi/93-dGnLfw1I/hqdefault.jpg" alt="Acting Out the Dialogue" width="600"/>
  </a>
</p>

**Feedback:**

Back-to-back yes or no questions worked, but without a visual/progress cue, the user couldn’t tell how far along we were (How many questions the device had asked), this felt more noticeable when spoken. In Part B, we could think about how to add a quick mid-game recap after Q4–5 (“So far: real, alive, musician, not British…” or “So far, I had asked 4 questions…”) to ground the user.

### Wizarding with the Pi (optional)
In the [demo directory](./demo), you will find an example Wizard of Oz project. In that project, you can see how audio and sensor data is streamed from the Pi to a wizard controller that runs in the browser.  You may use this demo code as a template. By running the `app.py` script, you can see how audio and sensor data (Adafruit MPU-6050 6-DoF Accel and Gyro Sensor) is streamed from the Pi to a wizard controller that runs in the browser `http://<YouPiIPAddress>:5000`. You can control what the system says from the controller as well!

\*\***Describe if the dialogue seemed different than what you imagined, or when acted out, when it was wizarded, and how.**\*\*

We used the following prompt to interact with the Ollama Voice Assistant in order to act out our script:

**LLM system prompt:** 
You are a Twenty Questions bot: the user silently thinks of a person, answers only “yes” or “no,” and you ask up to 20 concise, polite, speakable questions (one question at a time) that start broad and then narrow based on their answers to identify the person within the limit (you win if you guess correctly within 20; otherwise the user wins).

**How we interact with Ollama:**
Source code: https://github.com/siruiii/Interactive-Lab-Hub/blob/f60a190fbbe2c7a8e6154d53bfbb73955c6a41fb/Lab%203/ollama/test.py

We revised the `ollama_web_app.py` and tested the interaction by running `test.py` in ollama folder
```bash
cd ollama
source ollama_venv/bin/activate
python3 test.py
```
<p align="center">
  <a href="https://www.youtube.com/watch?v=MWF14AGxWc4" target="_blank">
    <img src="https://img.youtube.com/vi/MWF14AGxWc4/hqdefault.jpg" alt="Watch the demo" width="600">
  </a>
</p>

**Feedback & Reflection:**

- Ollama struggled with processing complex prompts, and its response time did not match our expectations. In practice, this could lead to user frustration. In the testing, it required us to continually revise and simplify our prompts.
- When testing a sample game with Ollama, the time it took to guess the correct name often exceeded 20 questions.



# Lab 3 Part 2

For Part 2, you will redesign the interaction with the speech-enabled device using the data collected, as well as feedback from part 1.

## Prep for Part 2

1. What are concrete things that could use improvement in the design of your device? For example: wording, timing, anticipation of misunderstandings...
2. What are other modes of interaction _beyond speech_ that you might also use to clarify how to interact?
3. Make a new storyboard, diagram and/or script based on these reflections.

## Prototype your system

The system should:
* use the Raspberry Pi 
* use one or more sensors
* require participants to speak to it. 

*Document how the system works*

*Include videos or screencaptures of both the system and the controller.*

<details>
  <summary><strong>Submission Cleanup Reminder (Click to Expand)</strong></summary>
  
  **Before submitting your README.md:**
  - This readme.md file has a lot of extra text for guidance.
  - Remove all instructional text and example prompts from this file.
  - You may either delete these sections or use the toggle/hide feature in VS Code to collapse them for a cleaner look.
  - Your final submission should be neat, focused on your own work, and easy to read for grading.
  
  This helps ensure your README.md is clear professional and uniquely yours!
</details>

## Test the system
Try to get at least two people to interact with your system. (Ideally, you would inform them that there is a wizard _after_ the interaction, but we recognize that can be hard.)

Answer the following:

### What worked well about the system and what didn't?
\*\**your answer here*\*\*

### What worked well about the controller and what didn't?

\*\**your answer here*\*\*

### What lessons can you take away from the WoZ interactions for designing a more autonomous version of the system?

\*\**your answer here*\*\*


### How could you use your system to create a dataset of interaction? What other sensing modalities would make sense to capture?

\*\**your answer here*\*\*






