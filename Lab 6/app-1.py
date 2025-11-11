#!/usr/bin/env python3
"""
RGB Proximity Server
- Up to 3 Raspberry Pis stream proximity (0..255), each mapped to R/G/B
- Missing channels use a fixed fallback value
- Web UI shows live color and channel status at "/"


Env (optional):
  FIXED_INACTIVE_VALUE: 0-255 (default 0)
  CHANNEL_TIMEOUT_SEC : seconds before a channel is inactive (default 5)
  HOST                : default 0.0.0.0
  PORT                : default 5000
"""


import os
from datetime import datetime, timedelta
from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit


FIXED_INACTIVE_VALUE = int(os.getenv("FIXED_INACTIVE_VALUE", "0"))
CHANNEL_TIMEOUT_SEC  = int(os.getenv("CHANNEL_TIMEOUT_SEC", "5"))
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5000"))


# Optionally pin MACs to channels:
# STATIC_ASSIGN = {"aa:bb:cc:dd:ee:ff":"R","11:22:33:44:55:66":"G","77:88:99:aa:bb:cc":"B"}
STATIC_ASSIGN = {}


app = Flask(__name__)
app.config["SECRET_KEY"] = "rgb-prox-2025"
socketio = SocketIO(app, cors_allowed_origins="*")


channels = {
    "R": {"mac": None, "value": FIXED_INACTIVE_VALUE, "last_seen": None},
    "G": {"mac": None, "value": FIXED_INACTIVE_VALUE, "last_seen": None},
    "B": {"mac": None, "value": FIXED_INACTIVE_VALUE, "last_seen": None},
}
dynamic_order = ["R", "G", "B"]


def now(): return datetime.utcnow()
def is_active(ts): return bool(ts and (now() - ts) <= timedelta(seconds=CHANNEL_TIMEOUT_SEC))
def sanitize(v): 
    try: v = int(v)
    except: v = 0
    return max(0, min(255, v))


def assign_channel(mac):
    if mac in STATIC_ASSIGN:
        return STATIC_ASSIGN[mac]
    for ch, info in channels.items():
        if info["mac"] == mac:
            return ch
    for ch in dynamic_order:
        if channels[ch]["mac"] is None:
            channels[ch]["mac"] = mac
            return ch
    oldest = min(channels.keys(), key=lambda c: channels[c]["last_seen"] or datetime.min)
    channels[oldest]["mac"] = mac
    return oldest


def current_rgb():
    out = {}
    for ch in ["R","G","B"]:
        info = channels[ch]
        out[ch] = sanitize(info["value"]) if is_active(info["last_seen"]) else FIXED_INACTIVE_VALUE
    return out["R"], out["G"], out["B"]


def broadcast_state():
    r,g,b = current_rgb()
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


@socketio.on("identify")
def on_identify(data):
    mac = (data or {}).get("mac")
    ch  = (data or {}).get("channel", "").upper()
    if mac and ch in channels:
        channels[ch]["mac"] = mac
        channels[ch]["last_seen"] = now()
        broadcast_state()


@socketio.on("proximity")
def on_proximity(data):
    mac = (data or {}).get("mac")
    val = (data or {}).get("value")
    if not mac:
        return
    ch = assign_channel(mac)
    channels[ch]["last_seen"] = now()
    channels[ch]["value"] = sanitize(val)
    broadcast_state()


@app.route("/")
def index():
    return render_template_string("""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>RGB Proximity</title>
  <style>
    body{font-family:system-ui,sans-serif;margin:20px}
    .swatch{width:100%;height:30vh;border-radius:12px;border:1px solid #ccc}
    .grid{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:8px;margin-top:16px}
    .cell{border:1px solid #ddd;padding:8px;border-radius:8px}
    .dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:middle}
    .active{background:#16a34a}.inactive{background:#ef4444}
    code{background:#f6f6f6;padding:2px 6px;border-radius:6px}
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


    <div class="cell">R</div><div class="cell" id="macR">-</div><div class="cell" id="valR">0</div><div class="cell" id="statR"><span class="dot inactive"></span>inactive</div>
    <div class="cell">G</div><div class="cell" id="macG">-</div><div class="cell" id="valG">0</div><div class="cell" id="statG"><span class="dot inactive"></span>inactive</div>
    <div class="cell">B</div><div class="cell" id="macB">-</div><div class="cell" id="valB">0</div><div class="cell" id="statB"><span class="dot inactive"></span>inactive</div>
  </div>
  <p style="margin-top:16px">
    Inactive channels fall back to <code id="fallback">0</code>. Timeout: <code id="timeout">5</code>s
  </p>


  <script src="https://cdn.socket.io/4.7.2/socket.io.min.js" crossorigin="anonymous"></script>
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
    socket.on('state', (data) => {
      const {r,g,b} = data.rgb;
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
    print(f"  Channel timeout (s)  : {CHANNEL_TIMEOUT_SEC}")
    print(f"  Host:Port            : {HOST}:{PORT}")
    socketio.run(app, host=HOST, port=PORT)






