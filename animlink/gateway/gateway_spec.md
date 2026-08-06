# -*- coding: utf-8 -*-
# AnimaLink Gateway — Specification v1.0

"""
AnimaLink Gateway — Storage Layer
统一读写 Z:\qclaw\gateway\ 下的数据文件
支持 NAS 降级到 E:\SOFTWARE\qclaw\gateway\
"""
import json
import os
import threading
from datetime import datetime, timezone

TZ = timezone.utc

def _resolve_root():
    if os.path.exists(r"Z:\qclaw\gateway"):
        return r"Z:\qclaw\gateway"
    if os.path.exists(r"E:\SOFTWARE\qclaw\gateway"):
        base = r"E:\SOFTWARE\qclaw"
        os.makedirs(os.path.join(base, "gateway"), exist_ok=True)
        return os.path.join(base, "gateway")
    # 最后兜底：本地工作目录
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    gw = os.path.join(base, "gateway_data")
    os.makedirs(gw, exist_ok=True)
    return gw

ROOT = _resolve_root()
_lock = threading.Lock()

def _read(fname, default):
    fp = os.path.join(ROOT, fname)
    try:
        with open(fp, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default()

def _write(fname, data):
    fp = os.path.join(ROOT, fname)
    os.makedirs(ROOT, exist_ok=True)
    with _lock:
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

# Registry

def get_registry():
    return _read("registry.json", lambda: {"nodes": {}, "version": "1.0"})

def write_registry(reg):
    _write("registry.json", reg)

def register_node(node_id, node_info):
    reg = get_registry()
    now = datetime.now(TZ).isoformat()
    reg["nodes"][node_id] = {
        **node_info,
        "status": "online",
        "registered_at": now,
        "last_heartbeat": now,
    }
    write_registry(reg)
    return reg["nodes"][node_id]

def heartbeat_node(node_id):
    reg = get_registry()
    if node_id in reg["nodes"]:
        now = datetime.now(TZ).isoformat()
        reg["nodes"][node_id]["last_heartbeat"] = now
        reg["nodes"][node_id]["status"] = "online"
        write_registry(reg)
        return True
    return False

def get_online_nodes():
    reg = get_registry()
    now = datetime.now(TZ)
    online = {}
    for nid, nd in reg["nodes"].items():
        try:
            last = datetime.fromisoformat(nd.get("last_heartbeat", "").replace("Z", "+00:00"))
            if (now - last).total_seconds() < 90:
                online[nid] = nd
        except Exception:
            pass
    return online

def mark_offline(node_id):
    reg = get_registry()
    if node_id in reg["nodes"]:
        reg["nodes"][node_id]["status"] = "offline"
        write_registry(reg)

# Tokens

def get_tokens():
    return _read("tokens.json", lambda: {"tokens": []})

def write_tokens(tk_data):
    _write("tokens.json", tk_data)

def submit_token(token_info):
    tokens = get_tokens()
    token_info["submitted_at"] = datetime.now(TZ).isoformat()
    token_info["status"] = "pending"
    tokens["tokens"].append(token_info)
    write_tokens(tokens)
    return token_info

def get_token(token_id):
    tokens = get_tokens()
    for t in tokens.get("tokens", []):
        if t.get("token_id") == token_id:
            return t
    return None

# Sessions

def get_sessions():
    return _read("sessions.json", lambda: {"sessions": {}})

def write_sessions(sess):
    _write("sessions.json", sess)

def register_session(node_id, gateway_token):
    sessions = get_sessions()
    sessions["sessions"][gateway_token] = {
        "node_id": node_id,
        "created_at": datetime.now(TZ).isoformat(),
    }
    write_sessions(sessions)

def validate_session(gateway_token):
    sessions = get_sessions()
    return gateway_token in sessions["sessions"]
