#!/usr/bin/env python3
"""
Ollama Flask Web Interface for Lab 3
Web-based voice assistant using Ollama


This extends the existing Flask app to include Ollama integration with:
1. Chat history support
2. A starting prompt for a Twenty Questions game
3. Strict enforcement of ONE short yes/no question per turn, no 'or'
"""


# --- IMPORTANT: eventlet must be monkey-patched BEFORE importing Flask, requests, etc. ---
import eventlet
eventlet.monkey_patch()


import os
import re
import json
import subprocess
import requests
from typing import Optional


from flask import Flask, Response, render_template, request, jsonify
from flask_socketio import SocketIO, send, emit


app = Flask(__name__)
# Explicitly choose eventlet async mode now that we've patched early
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")


# Ollama configuration
OLLAMA_URL = "http://localhost:11434"
# Pick a small, fast model for Raspberry Pi; adjust as needed
DEFAULT_MODEL = "phi3:mini"


# --- Chat history and starting prompt (tightened rules) ---
STARTING_PROMPT = (
   "You are a Twenty Questions bot. The user silently thinks of a PERSON."
   " The user replies only YES or NO."
   " Ask exactly ONE short, clear, speakable yes/no question per turn."
   " Never write multiple questions. Never use the word 'or'."
   " Start broad, then narrow. Keep it under 120 characters."
   " When >=90% confident, make ONE concise guess instead of a question."
   " If you reach 20 questions without a correct guess, say the user wins."
)


# Store chat history in memory (can later be moved to a DB if needed)
chat_history = [
   {"role": "system", "content": STARTING_PROMPT}
]


# Keep history short to avoid slow responses on low-power devices
MAX_TURNS = 30  # ~15 Q/A exchanges


# ---------------------------
# Sanitizer to enforce format
# ---------------------------
def enforce_one_question(text: str, max_chars: int = 120) -> str:
    """
    Returns a single, short yes/no question with no 'or'.
    - Takes the first sentence ending in '?'
    - If 'or' appears, clip before it
    - Strips extra punctuation/whitespace
    - Truncates to max_chars (keeps trailing '?')
    Fallbacks to a safe generic question if needed.
    """
    if not isinstance(text, str):
        text = str(text or "")


    # Extract up to first '?'
    q = text.split('?', 1)[0].strip()
    if not q:
        return "Is this person real (not fictional)?"


    # Remove anything after a standalone 'or'
    q = re.split(r'\bor\b', q, maxsplit=1, flags=re.IGNORECASE)[0].strip()


    # Trim punctuation, enforce length, and add '?' back
    q = q[:max(1, max_chars - 1)].rstrip(" .,!?:;") + "?"


    # Ensure it reads like a yes/no question
    if not re.match(r'^(Is|Are|Was|Were|Do|Does|Did|Has|Have|Can|Will|Would)\b', q, flags=re.IGNORECASE):
        # Keep user flow intact with a safe default
        q = "Is the person alive today?"
    return q


def _trim_history():
    # Always keep the initial system message and most recent turns
    global chat_history
    base = chat_history[:1]
    rest = chat_history[1:]
    if len(rest) > MAX_TURNS:
        rest = rest[-MAX_TURNS:]
    chat_history = base + rest


def _first_question_if_needed(user_message: str) -> Optional[str]:
    """Return the deterministic first question if we haven't asked anything yet."""
    # If only the system message exists or last speaker was system, kick off with Q1
    if len(chat_history) == 1 or (
        len(chat_history) >= 1 and chat_history[-1]["role"] == "system"
    ):
        q1_raw = "Is the person real (not a fictional character)?"
        q1 = enforce_one_question(q1_raw)
        chat_history.append({"role": "assistant", "content": q1})
        return q1
    return None


def _ollama_chat(messages, model=DEFAULT_MODEL, timeout=90):
    """Call Ollama's /api/chat with messages[], return assistant string."""
    resp = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_ctx": 2048,
                "num_predict": 128  # keep responses short & fast
            }
        },
        timeout=timeout
    )
    if resp.status_code == 200:
        data = resp.json()
        return data.get("message", {}).get("content", "No response generated")
    return f"Error: Ollama returned status {resp.status_code}"


def query_ollama(user_text: str, model=DEFAULT_MODEL):
    """Query Ollama chat API with trimmed history; fast first turn."""
    try:
        # If it's the first turn, return our deterministic first question immediately
        first_q = _first_question_if_needed(user_text)
        if first_q is not None:
            return first_q


        # Append user message and trim history
        chat_history.append({"role": "user", "content": user_text})
        _trim_history()


        # Send concise history to Ollama
        ai_reply_raw = _ollama_chat(chat_history, model=model, timeout=90)
        ai_reply = enforce_one_question(ai_reply_raw)
        chat_history.append({"role": "assistant", "content": ai_reply})
        _trim_history()
        return ai_reply


    except requests.exceptions.Timeout:
        return "Sorry, the response took too long. Please try again."
    except Exception as e:
        return f"Error: {str(e)}"


def speak_text(text: str):
    """Text-to-speech using espeak (avoid quoting inside the arg list)."""
    try:
        if not isinstance(text, str):
            text = str(text)
        # Do not wrap text in quotes here; pass as a direct argument
        subprocess.run(['espeak', text], check=False)
    except Exception as e:
        print(f"TTS Error: {e}")


# ---------------------------
# Flask / Socket.IO routes
# ---------------------------


@app.route('/')
def index():
    """Main web interface"""
    return render_template('ollama_chat.html')


@app.route('/api/chat', methods=['POST'])
def chat_api():
    """REST API endpoint for chat"""
    data = request.get_json(force=True, silent=True) or {}
    user_message = (data.get('message') or '').strip()


    # If no user message, return the current/first question so clients can render something
    if not user_message:
        # Use last assistant message if it exists; otherwise start
        if chat_history and chat_history[-1]['role'] == 'assistant':
            current_q = enforce_one_question(chat_history[-1]['content'])
        else:
            current_q = _first_question_if_needed("api-empty") or "Is the person real (not a fictional character)?"
            current_q = enforce_one_question(current_q)


        return jsonify({
            'user_message': '',
            'ai_response': current_q,
            'chat_history': chat_history
        })


    ai_response = query_ollama(user_message)
    return jsonify({
        'user_message': user_message,
        'ai_response': ai_response,
        'chat_history': chat_history
    })


@socketio.on('start')
def handle_start(_data=None):
    """Optional start event to force the first question immediately."""
    q = _first_question_if_needed("start") or (
        chat_history[-1]["content"] if chat_history and chat_history[-1]["role"] == "assistant" else "Is the person real (not a fictional character)?"
    )
    q = enforce_one_question(q)
    emit('ai_response', {
        'user_message': 'start',
        'ai_response': q,
        'chat_history': chat_history
    })


@socketio.on('connect')
def handle_connect():
    """As soon as the WS connects, send the first question so the UI shows it instantly."""
    q = _first_question_if_needed("connect") or (
        chat_history[-1]["content"] if chat_history and chat_history[-1]["role"] == "assistant" else "Is the person real (not a fictional character)?"
    )
    q = enforce_one_question(q)
    emit('ai_response', {
        'user_message': 'connect',
        'ai_response': q,
        'chat_history': chat_history
    })


@app.route('/first', methods=['GET'])
def first_question_http():
    """HTTP fallback: return the first question for clients that prefer REST."""
    q = _first_question_if_needed("http-first") or (
        chat_history[-1]["content"] if chat_history and chat_history[-1]["role"] == "assistant" else "Is the person real (not a fictional character)?"
    )
    q = enforce_one_question(q)
    return jsonify({'ai_response': q, 'chat_history': chat_history})


@socketio.on('chat_message')
def handle_chat_message(data):
    """Handle chat message via WebSocket"""
    user_message = (data or {}).get('message', '')


    if user_message:
        # Query Ollama with chat history
        ai_response = query_ollama(user_message)


        # Send response back to client
        emit('ai_response', {
            'user_message': user_message,
            'ai_response': ai_response,
            'chat_history': chat_history
        })


@socketio.on('speak_request')
def handle_speak_request(data):
    """Handle text-to-speech request"""
    text = (data or {}).get('text', '')
    if text:
        speak_text(text)
        emit('speak_complete', {'text': text})


@socketio.on('voice_chat')
def handle_voice_chat(data):
    """Handle voice chat request (text in, voice out)"""
    user_message = (data or {}).get('message', '')


    if user_message:
        # Query Ollama with chat history
        ai_response = query_ollama(user_message)


        # Speak the response
        speak_text(ai_response)


        # Send response to client
        emit('voice_response', {
            'user_message': user_message,
            'ai_response': ai_response,
            'chat_history': chat_history
        })


@app.route('/status')
def status():
    """Check Ollama status"""
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            return jsonify({
                'status': 'connected',
                'models': [m.get('name') for m in models if isinstance(m, dict)],
                'current_model': DEFAULT_MODEL
            })
        else:
            return jsonify({'status': 'error', 'message': 'Ollama not responding'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/reset', methods=['POST'])
def reset_chat():
    """Reset the Twenty Questions session (clears chat history and reapplies system prompt)."""
    global chat_history
    chat_history = [{"role": "system", "content": STARTING_PROMPT}]
    return jsonify({"ok": True, "message": "Chat history reset."})


@socketio.on('reset')
def handle_reset_event(_):
    """WebSocket reset event to restart the session from the frontend."""
    global chat_history
    chat_history = [{"role": "system", "content": STARTING_PROMPT}]
    emit('reset_complete', {'chat_history': chat_history})


# ---------------------------
# Warm-up
# ---------------------------
def _warm_up_model():
    """Kick the model once at startup so the first real turn is faster."""
    try:
        # A tiny no-op chat to load the model weights
        requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": DEFAULT_MODEL,
                "messages": [
                    {"role": "system", "content": "you are a system"},
                    {"role": "user", "content": "ok"}
                ],
                "stream": False,
                "options": {"num_predict": 1}
            },
            timeout=10
        )
    except Exception:
        pass


# ---------------------------
# Entrypoint
# ---------------------------
if __name__ == '__main__':
    print("Starting Ollama Flask Web Interface...")
    print("Open your browser to http://localhost:5000")
    # Warm up without blocking the server
    eventlet.spawn_n(_warm_up_model)
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)






