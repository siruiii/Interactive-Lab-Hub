
"""
RGB Proximity Server
--------------------
- Up to 3 Raspberry Pis connect and stream proximity from APDS9960 sensors.
- Each Pi is assigned to a color channel (R, G, B).
- If a channel is inactive (device not connected or timed out), a fixed fallback value is used.
- The web UI shows the live color swatch and connection status.

Run:
  python app.py

Env (optional):
  FIXED_INACTIVE_VALUE: int 0-255 (default 0)
  CHANNEL_TIMEOUT_SEC: int seconds before a channel is considered inactive (default 5)
  HOST: bind host (default 0.0.0.0)
  PORT: port (default 5000)
"""
import os
import time
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit

FIXED_INACTIVE_VALUE = int(os.getenv("FIXED_INACTIVE_VALUE", "0"))
CHANNEL_TIMEOUT_SEC = int(os.getenv("CHANNEL_TIMEOUT_SEC", "5"))
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5000"))

# Optional static assignment of MAC addresses to channels. Put your Pis' MACs here if desired.
# Example:
# STATIC_ASSIGN = {"aa:bb:cc:dd:ee:ff": "R", "11:22:33:44:55:66": "G", "77:88:99:aa:bb:cc": "B"}
STATIC_ASSIGN = {}

app = Flask(__name__)
app.config["SECRET_KEY"] = "rgb-prox-2025"
socketio = SocketIO(app, cors_allowed_origins="*")

# Channel state
channels = {
    "R": {"mac": None, "value": FIXED_INACTIVE_VALUE, "last_seen": None},
    "G": {"mac": None, "value": FIXED_INACTIVE_VALUE, "last_seen": None},
    "B": {"mac": None, "value": FIXED_INACTIVE_VALUE, "last_seen": None},
}

# Dynamic round-robin order for assignment when not using STATIC_ASSIGN
dynamic_order = ["R", "G", "B"]

def now():
    return datetime.utcnow()

def is_active(ts):
    if not ts:
        return False
    return (now() - ts) <= timedelta(seconds=CHANNEL_TIMEOUT_SEC)

def assign_channel(mac):
    # If statically assigned, honor it
    if mac in STATIC_ASSIGN:
        return STATIC_ASSIGN[mac]
    # If already assigned, return that
    for ch, info in channels.items():
        if info["mac"] == mac:
            return ch
    # Otherwise, assign the first free channel R->G->B
    for ch in dynamic_order:
        if channels[ch]["mac"] is None:
            channels[ch]["mac"] = mac
            return ch
    # If all taken, reuse the one with oldest last_seen (least recently active)
    oldest_ch = min(channels.keys(), key=lambda c: channels[c]["last_seen"] or datetime.min)
    channels[oldest_ch]["mac"] = mac
    return oldest_ch

def sanitize(v):
    try:
        v = int(v)
    except Exception:
        v = 0
    return max(0, min(255, v))

def current_rgb():
    # If a channel hasn't been seen recently, treat as inactive (fallback value)
    rgb = {}
    for ch in ["R", "G", "B"]:
        info = channels[ch]
        if is_active(info["last_seen"]):
            rgb[ch] = sanitize(info["value"])
        else:
            rgb[ch] = FIXED_INACTIVE_VALUE
    return (rgb["R"], rgb["G"], rgb["B"])

def broadcast_state():
    r, g, b = current_rgb()
    payload = {
        "rgb": {"r": r, "g": g, "b": b},
        "channels": {
            ch: {
                "mac": info["mac"],
                "value": sanitize(info["value"]),
                "active": is_active(info["last_seen"]),
                "last_seen": info["last_seen"].isoformat() if info["last_seen"] else None,
            }
            for ch, info in channels.items()
        },
        "inactive_fallback": FIXED_INACTIVE_VALUE,
        "timeout_sec": CHANNEL_TIMEOUT_SEC,
        "server_time": now().isoformat() + "Z",
    }
    socketio.emit("state", payload, broadcast=True)

@socketio.on("connect")
def on_connect():
    emit("hello", {"message": "connected"})
    broadcast_state()

@socketio.on("proximity")
def on_proximity(data):
    # Expected data: {"mac": "...", "value": 0-255}
    mac = (data or {}).get("mac")
    val = (data or {}).get("value")
    if not mac:
        return
    ch = assign_channel(mac)
    channels[ch]["last_seen"] = now()
    channels[ch]["value"] = sanitize(val)
    broadcast_state()

@socketio.on("identify")
def on_identify(data):
    # Client can pre-claim a channel: {"mac":"..","channel":"R|G|B"}
    mac = (data or {}).get("mac")
    ch = (data or {}).get("channel", "").upper()
    if mac and ch in channels:
        channels[ch]["mac"] = mac
        channels[ch]["last_seen"] = now()
        broadcast_state()

@app.route("/")
def index():
    # simple page that shows the color swatch + channel table
    return render_template_string("""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>RGB Proximity</title>
      <style>
        body { font-family: system-ui, sans-serif; margin: 20px; }
        .swatch { width: 100%; height: 30vh; border-radius: 12px; border: 1px solid #ccc; }
        .grid { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 8px; margin-top: 16px; }
        .cell { border: 1px solid #ddd; padding: 8px; border-radius: 8px; }
        .dot { display:inline-block; width:10px; height:10px; border-radius: 50%; margin-right:6px; vertical-align: middle; }
        .active { background:#16a34a; }
        .inactive { background:#ef4444; }
        code { background: #f6f6f6; padding: 2px 6px; border-radius: 6px; }
      </style>
    </head>
    <body>
      <h1>RGB Proximity</h1>
      <div id="swatch" class="swatch"></div>
      <p><strong>RGB:</strong> <span id="rgbText">0, 0, 0</span></p>
      <div class="grid">
        <div class="cell"><strong>Channel</strong></div>
        <div class="cell"><strong>MAC</strong></div>
        <div class="cell"><strong>Value</strong></div>
        <div class="cell"><strong>Status</strong></div>
        <div class="cell">R</div>
        <div class="cell" id="macR">-</div>
        <div class="cell" id="valR">0</div>
        <div class="cell" id="statR"><span class="dot inactive"></span>inactive</div>
        <div class="cell">G</div>
        <div class="cell" id="macG">-</div>
        <div class="cell" id="valG">0</div>
        <div class="cell" id="statG"><span class="dot inactive"></span>inactive</div>
        <div class="cell">B</div>
        <div class="cell" id="macB">-</div>
        <div class="cell" id="valB">0</div>
        <div class="cell" id="statB"><span class="dot inactive"></span>inactive</div>
      </div>
      <p style="margin-top:16px">
        Inactive channels fall back to <code id="fallback">0</code>. Timeout: <code id="timeout">5</code>s
      </p>
      <script src="https://cdn.socket.io/4.7.2/socket.io.min.js" integrity="sha384-Pi+KJ7q3oXhMy1WfVJm5Cw6X3iQpN8JWXmV0r3D6q3aTnGGKNNtaOCXp8jVEVb9d" crossorigin="anonymous"></script>
      <script>
        const socket = io();
        function setSwatch(r,g,b){
          const el = document.getElementById('swatch');
          el.style.background = `rgb(${r}, ${g}, ${b})`;
          document.getElementById('rgbText').textContent = `${r}, ${g}, ${b}`;
        }
        function setRow(ch, mac, val, active){
          document.getElementById('mac'+ch).textContent = mac || '-';
          document.getElementById('val'+ch).textContent = val;
          const cell = document.getElementById('stat'+ch);
          cell.innerHTML = '';
          const dot = document.createElement('span');
          dot.className = 'dot ' + (active ? 'active' : 'inactive');
          cell.appendChild(dot);
          cell.appendChild(document.createTextNode(active ? 'active' : 'inactive'));
        }
        socket.on('connect', () => {
          console.log('connected');
        });
        socket.on('state', (data) => {
          const r = data.rgb.r, g = data.rgb.g, b = data.rgb.b;
          setSwatch(r,g,b);
          document.getElementById('fallback').textContent = data.inactive_fallback;
          document.getElementById('timeout').textContent = data.timeout_sec;
          const chs = data.channels;
          ['R','G','B'].forEach(ch => {
            const info = chs[ch];
            setRow(ch, info.mac, info.value, info.active);
          });
        });
      </script>
    </body>
    </html>
    """)

if __name__ == "__main__":
    print("Starting RGB Proximity Server")
    print(f"  Fixed inactive value : {FIXED_INACTIVE_VALUE}")
    print(f"  Channel timeout (sec): {CHANNEL_TIMEOUT_SEC}")
    print(f"  Host:Port            : {HOST}:{PORT}")
    socketio.run(app, host=HOST, port=PORT)
