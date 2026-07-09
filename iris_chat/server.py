#!/usr/bin/env python3
"""
Iris Chat Server - 5053
Nyx 与 Iris 的可视化对话界面 + REST API
"""
import sys, io, json, os, logging, uuid, time
from pathlib import Path
from datetime import datetime, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('iris-chat')

from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder=None)

# Storage
CHAT_DIR = Path("Z:/qclaw/iris-chat")
CHAT_DIR.mkdir(parents=True, exist_ok=True)
MESSAGES_FILE = CHAT_DIR / "messages.json"
NYX_DID = "did:key:zcf403c697b4e1c587734242faec679f6242531ecc"

def load_messages():
    if MESSAGES_FILE.exists():
        data = json.loads(MESSAGES_FILE.read_text(encoding='utf-8'))
        return data.get("messages", [])
    return []

def save_message(msg):
    messages = load_messages()
    messages.append(msg)
    logger.info(f"Save: [{msg['sender']}] {msg['message'][:80]}")
    MESSAGES_FILE.write_text(
        json.dumps({"messages": messages}, ensure_ascii=False, indent=2),
        encoding='utf-8')

# ========== API ==========

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "iris-chat", "port": 5053})

@app.route('/api/messages', methods=['GET'])
def get_messages():
    since = request.args.get('since', '')
    msgs = load_messages()
    if since:
        msgs = [m for m in msgs if m.get('timestamp', '') > since]
    return jsonify({"messages": msgs})

@app.route('/api/chat', methods=['POST'])
def incoming():
    """Iris sends message here"""
    data = request.get_json(force=True, silent=True)
    if not data or not data.get('message'):
        raw = request.get_data(as_text=True)
        return jsonify({"error": f"invalid request: {repr(raw[:200])}"}), 400

    sender = data.get('sender', 'Iris')
    msg_text = data['message'].strip()
    logger.info(f"Incoming from {sender}: {repr(msg_text[:120])}")

    msg = {
        "id": str(uuid.uuid4())[:8],
        "sender": sender,
        "message": msg_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "did": data.get('did', ''),
    }
    save_message(msg)
    return jsonify({"status": "ok", "id": msg["id"]})

@app.route('/api/nyx-messages', methods=['GET'])
def get_nyx_messages():
    """只返回 Nyx 发给 Iris 的消息"""
    since = request.args.get('since', '')
    msgs = load_messages()
    nyx_msgs = [m for m in msgs if m['sender'] == 'Nyx']
    if since:
        nyx_msgs = [m for m in nyx_msgs if m.get('timestamp', '') > since]
    return jsonify({"messages": nyx_msgs})

@app.route('/api/nyx-reply', methods=['POST'])
def nyx_reply():
    """Nyx replies from this conversation"""
    data = request.get_json(force=True, silent=True)
    if not data or not data.get('message'):
        raw = request.get_data(as_text=True)
        return jsonify({"error": f"invalid request: {repr(raw[:200])}"}), 400

    msg_text = data['message'].strip()
    logger.info(f"Nyx sends: {repr(msg_text[:120])}")

    msg = {
        "id": str(uuid.uuid4())[:8],
        "sender": "Nyx",
        "message": msg_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "did": NYX_DID,
    }
    save_message(msg)
    return jsonify({"status": "ok", "id": msg["id"]})

# ========== Web UI ==========

@app.route('/')
def index():
    return send_from_directory(str(Path(__file__).parent), 'chat.html')

@app.route('/chat.html')
def chat_html():
    return send_from_directory(str(Path(__file__).parent), 'chat.html')

if __name__ == '__main__':
    port = int(os.environ.get('IRIS_PORT', 5053))
    logger.info(f"Iris Chat Server starting on 0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
