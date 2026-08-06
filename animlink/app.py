# -*- coding: utf-8 -*-
"""
AnimaLink Gateway — Main Service
Flask + Flask-SocketIO
HTTP: 8000  |  WebSocket: 8001
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

from flask import Flask, request, jsonify
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
    """每 30s 检查一次，离线节点标记并广播。"""
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
                    print(f"[Gateway] Node offline: {nid}")

# ── Auth helpers ─────────────────────────────────────────────────────────────

def _check_admin():
    return request.headers.get("X-Gateway-Admin", "") == ADMIN_KEY

def _check_session():
    token = request.headers.get("X-Gateway-Token", "")
    return bool(token and validate_session(token))

# ── REST API ────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "animlink-gateway", "version": "1.0"})


# ── 节点注册 ──────────────────────────────────────────────────────────────

@app.route("/api/nodes/register", methods=["POST"])
def nodes_register():
    """注册新节点。Body: { node_id, did, endpoint, platform, hostname }"""
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

    # 颁发 gateway token
    gt = f"gt_{uuid.uuid4().hex[:16]}"
    register_session(node_id, gt)

    # 广播
    socketio.emit("gateway_event", {
        "type": "node_online",
        "node_id": node_id,
        "node": registered,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    print(f"[Gateway] Node registered: {node_id} ({body.get('platform', '')})")

    return jsonify({
        "status": "registered",
        "gateway_token": gt,
        "node": registered,
    })


@app.route("/api/nodes", methods=["GET"])
def nodes_list():
    """列出所有注册节点（带实时在线状态）。"""
    reg = get_registry()
    online_ids = set(get_online_nodes().keys())
    nodes = []
    for nid, nd in reg["nodes"].items():
        nodes.append({
            **nd,
            "id": nid,
            "online": nid in online_ids,
        })
    return jsonify({"nodes": nodes, "total": len(nodes)})


@app.route("/api/nodes/<node_id>", methods=["GET"])
def nodes_get(node_id):
    """查询指定节点信息。"""
    reg = get_registry()
    if node_id not in reg["nodes"]:
        return jsonify({"error": "node not found"}), 404
    nd = reg["nodes"][node_id]
    nd["online"] = node_id in get_online_nodes()
    return jsonify({"node": nd})


@app.route("/api/nodes/<node_id>/heartbeat", methods=["POST"])
def nodes_heartbeat(node_id):
    """节点心跳保活。Body 可选: { endpoint } 更新连接信息。"""
    body = request.get_json() or {}
    ok = heartbeat_node(node_id)
    if not ok:
        return jsonify({"error": "node not registered"}), 404

    # 如果 body 带了 endpoint，更新连接信息
    if body.get("endpoint"):
        reg = get_registry()
        reg["nodes"][node_id]["endpoint"] = body["endpoint"]
        from gateway import write_registry
        write_registry(reg)

    return jsonify({"status": "ok", "node_id": node_id})


# ── 令牌管理 ──────────────────────────────────────────────────────────────

@app.route("/api/tokens/submit", methods=["POST"])
def tokens_submit():
    """提交令牌。Body: { token_id, initiator, executor, task, description }"""
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
    print(f"[Gateway] Token submitted: {token_id}")

    return jsonify({"status": "submitted", "token": saved})


@app.route("/api/tokens/<token_id>", methods=["GET"])
def tokens_get(token_id):
    """查询令牌状态。"""
    tk = get_token(token_id)
    if not tk:
        return jsonify({"error": "token not found"}), 404
    return jsonify({"token": tk})


@app.route("/api/tokens", methods=["GET"])
def tokens_list():
    """列出所有令牌。"""
    data = get_tokens()
    return jsonify(data)


@app.route("/api/tokens/<token_id>", methods=["PATCH"])
def tokens_update(token_id):
    """更新令牌状态（须 admin）。Body: { status }"""
    if not _check_admin():
        return jsonify({"error": "unauthorized"}), 401
    body = request.get_json() or {}
    tk = get_token(token_id)
    if not tk:
        return jsonify({"error": "token not found"}), 404
    # 直接写回
    tokens_data = get_tokens()
    for t in tokens_data["tokens"]:
        if t.get("token_id") == token_id:
            t["status"] = body.get("status", t.get("status", "pending"))
            from gateway import write_tokens
            write_tokens(tokens_data)
            socketio.emit("gateway_event", {
                "type": "token_updated",
                "token": t,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return jsonify({"status": "updated", "token": t})
    return jsonify({"error": "token not found"}), 404


# ── 网络状态（聚合） ─────────────────────────────────────────────────────

@app.route("/api/network/status", methods=["GET"])
def network_status():
    """网络全局状态。"""
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
            else:
                for e in edges:
                    if e["source"] == k[0] and e["target"] == k[1]:
                        e["tokens"] += 1
                        break

    return jsonify({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "total_nodes": len(nodes),
            "online_nodes": len(online),
            "total_tokens": len(tokens_data.get("tokens", [])),
        },
    })


# ── WebSocket Events ────────────────────────────────────────────────────────

@socketio.on("connect")
def ws_connect():
    print(f"[Gateway] WebSocket client connected: {request.sid}")
    emit("gateway_event", {"type": "connected", "sid": request.sid})


@socketio.on("disconnect")
def ws_disconnect():
    print(f"[Gateway] WebSocket client disconnected: {request.sid}")


@socketio.on("ping")
def ws_ping():
    emit("gateway_event", {"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()})


# ── Startup ────────────────────────────────────────────────────────────────

def _start_sweeper():
    t = threading.Thread(target=_sweep_loop, daemon=True)
    t.start()

if __name__ == "__main__":
    print("=" * 50)
    print("AnimaLink Gateway v1.0")
    print(f"  HTTP:  http://0.0.0.0:8000")
    print(f"  WS:    ws://0.0.0.0:8001")
    print(f"  Admin: X-Gateway-Admin = {ADMIN_KEY}")
    print(f"  Storage: {__import__('gateway').ROOT}")
    print("=" * 50)
    _start_sweeper()
    socketio.run(
        app,
        host="0.0.0.0",
        port=8000,
        debug=False,
        log_output=True,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )
