# -*- coding: utf-8 -*-
"""
AnimaLink Gateway + Viewer — Unified Service (NAS edition)
Flask + Flask-SocketIO
HTTP: 8000  |  API: /api/*  |  Viewer: /animlink/*
"""
import os
import sys
import uuid
import json
import threading
import time
from datetime import datetime, timezone

# ── UTF-8 bootstrap ──────────────────────────────────────────────────────────
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from dotenv import load_dotenv

# ── Local gateway modules ────────────────────────────────────────────────────
from gateway import (
    get_registry, register_node, heartbeat_node, get_online_nodes,
    mark_offline, register_session, validate_session,
    submit_token, get_token, get_tokens,
)

load_dotenv()
ADMIN_KEY = os.getenv("GATEWAY_ADMIN_KEY", "changeme")

# ── Web Viewer directory ─────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")

app = Flask(__name__)
app.config["SECRET"] = os.getenv("SECRET_KEY", str(uuid.uuid4()))
CORS(app)

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
    ping_timeout=30,
    ping_interval=10,
)

# ── Heartbeat Sweeper ────────────────────────────────────────────────────────
_sweep_lock = threading.Lock()
_sweep_running = True

def _sweep_loop():
    while _sweep_running:
        time.sleep(30)
        with _sweep_lock:
            online = get_online_nodes()
            reg = get_registry()
            for nid, nd in reg["nodes"].items():
                if nd.get("status") == "online" and nid not in online:
                    mark_offline(nid)
                    socketio.emit("gateway_event", {
                        "type": "node_offline",
                        "node_id": nid,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

def _check_admin():
    return request.headers.get("X-Gateway-Admin", "") == ADMIN_KEY

# ── REST API ─────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "animlink-gateway", "version": "1.0"})

@app.route("/api/nodes/register", methods=["POST"])
def nodes_register():
    body = request.get_json() or {}
    required = ["node_id", "did"]
    for f in required:
        if not body.get(f):
            return jsonify({"error": f"missing field: {f}"}), 400
    node_id = body["node_id"]
    node_info = {
        "did": body["did"],
        "endpoint": body.get("endpoint", ""),
        "platform": body.get("platform", ""),
        "hostname": body.get("hostname", ""),
        "notes": body.get("notes", ""),
    }
    registered = register_node(node_id, node_info)
    gt = f"gt_{uuid.uuid4().hex[:16]}"
    register_session(node_id, gt)
    socketio.emit("gateway_event", {
        "type": "node_online",
        "node_id": node_id,
        "node": registered,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return jsonify({"status": "registered", "gateway_token": gt, "node": registered})

@app.route("/api/nodes", methods=["GET"])
def nodes_list():
    reg = get_registry()
    online_ids = set(get_online_nodes().keys())
    nodes = []
    for nid, nd in reg["nodes"].items():
        nodes.append({**nd, "id": nid, "online": nid in online_ids})
    return jsonify({"nodes": nodes, "total": len(nodes)})

@app.route("/api/nodes/<node_id>", methods=["GET"])
def nodes_get(node_id):
    reg = get_registry()
    if node_id not in reg["nodes"]:
        return jsonify({"error": "node not found"}), 404
    nd = reg["nodes"][node_id]
    nd["online"] = node_id in get_online_nodes()
    return jsonify({"node": nd})

@app.route("/api/nodes/<node_id>/heartbeat", methods=["POST"])
def nodes_heartbeat(node_id):
    body = request.get_json() or {}
    ok = heartbeat_node(node_id)
    if not ok:
        return jsonify({"error": "node not registered"}), 404
    if body.get("endpoint"):
        reg = get_registry()
        reg["nodes"][node_id]["endpoint"] = body["endpoint"]
        from gateway import write_registry
        write_registry(reg)
    return jsonify({"status": "ok", "node_id": node_id})

@app.route("/api/tokens/submit", methods=["POST"])
def tokens_submit():
    body = request.get_json() or {}
    token_id = body.get("token_id") or f"tk_{uuid.uuid4().hex[:12]}"
    token_info = {
        "token_id": token_id,
        "initiator": body.get("initiator", "unknown"),
        "executor": body.get("executor", ""),
        "task": body.get("task", ""),
        "description": body.get("description", ""),
    }
    saved = submit_token(token_info)
    socketio.emit("gateway_event", {
        "type": "token_submitted",
        "token": saved,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return jsonify({"status": "submitted", "token": saved})

@app.route("/api/tokens/<token_id>", methods=["GET"])
def tokens_get(token_id):
    tk = get_token(token_id)
    if not tk:
        return jsonify({"error": "token not found"}), 404
    return jsonify({"token": tk})

@app.route("/api/tokens", methods=["GET"])
def tokens_list():
    return jsonify(get_tokens())

@app.route("/api/tokens/<token_id>", methods=["PATCH"])
def tokens_update(token_id):
    if not _check_admin():
        return jsonify({"error": "unauthorized"}), 401
    body = request.get_json() or {}
    tk = get_token(token_id)
    if not tk:
        return jsonify({"error": "token not found"}), 404
    tokens_data = get_tokens()
    for t in tokens_data["tokens"]:
        if t.get("token_id") == token_id:
            t["status"] = body.get("status", t.get("status", "pending"))
            from gateway import write_tokens
            write_tokens(tokens_data)
            socketio.emit("gateway_event", {
                "type": "token_updated", "token": t,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return jsonify({"status": "updated", "token": t})
    return jsonify({"error": "token not found"}), 404

@app.route("/api/network/status", methods=["GET"])
def network_status():
    reg = get_registry()
    online = get_online_nodes()
    tokens_data = get_tokens()
    nodes = []
    for nid, nd in reg["nodes"].items():
        nodes.append({**nd, "id": nid, "online": nid in online})
    edges = []
    seen = set()
    for t in tokens_data.get("tokens", []):
        k = (t.get("initiator"), t.get("executor"))
        if k[0] and k[1] and k[0] != k[1]:
            if k not in seen:
                seen.add(k)
                edges.append({"source": k[0], "target": k[1], "tokens": 1})
    return jsonify({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "nodes": nodes, "edges": edges,
        "stats": {
            "total_nodes": len(nodes),
            "online_nodes": len(online),
            "total_tokens": len(tokens_data.get("tokens", [])),
        },
    })

# ── AnimaLink Viewer (HTML pages) ────────────────────────────────────────────

@app.route("/")
@app.route("/animlink")
@app.route("/animlink/")
def animlink_root():
    """Default page → index.html"""
    return send_from_directory(WEB_DIR, "index.html")

@app.route("/animlink/<path:filename>")
def animlink_static(filename):
    """Serve web/ static files"""
    return send_from_directory(WEB_DIR, filename)

# ── WebSocket Events ─────────────────────────────────────────────────────────

@socketio.on("connect")
def ws_connect():
    emit("gateway_event", {"type": "connected", "sid": request.sid})

@socketio.on("disconnect")
def ws_disconnect():
    pass

@socketio.on("ping")
def ws_ping():
    emit("gateway_event", {"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()})

# ── Startup ──────────────────────────────────────────────────────────────────

def _start_sweeper():
    t = threading.Thread(target=_sweep_loop, daemon=True)
    t.start()

if __name__ == "__main__":
    print("=" * 50)
    print("AnimaLink Gateway + Viewer v1.0")
    print(f"  HTTP:    http://0.0.0.0:8000")
    print(f"  Viewer:  http://0.0.0.0:8000/animlink/")
    print(f"  Admin:   X-Gateway-Admin = {ADMIN_KEY}")
    print(f"  Web:     {WEB_DIR}")
    print("=" * 50)
    _start_sweeper()
    socketio.run(
        app, host="0.0.0.0", port=8000, debug=False,
        log_output=True, use_reloader=False, allow_unsafe_werkzeug=True,
    )
