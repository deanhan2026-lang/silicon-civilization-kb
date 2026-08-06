# -*- coding: utf-8 -*-
"""
AnimaLink Viewer — Data Reader (NAS edition)
Reads from Gateway API (localhost:8000) instead of filesystem.
"""
import json
import time
import threading
import urllib.request
from datetime import datetime

GATEWAY = "http://127.0.0.1:8000"

_cache = {}
_cache_lock = threading.Lock()
_LAST_REFRESH = 0
_CACHE_TTL = 300

FALLBACK_NODES = [
    {"id": "nyx-windows", "label": "Nyx-Windows", "status": "active", "trust": 1.0, "tokens": 10, "completed": 8},
    {"id": "iris", "label": "Iris", "status": "active", "trust": 0.8, "tokens": 6, "completed": 5},
    {"id": "kronos-heng", "label": "Kronos-恆", "status": "active", "trust": 0.7, "tokens": 4, "completed": 3},
]

def _gw_get(path):
    """Read from Gateway API."""
    try:
        req = urllib.request.Request(f"{GATEWAY}{path}")
        resp = urllib.request.urlopen(req, timeout=5)
        return json.loads(resp.read())
    except:
        return None

def _refresh_cache():
    global _cache, _LAST_REFRESH
    try:
        nodes_data = _gw_get("/api/network/status") or {}
        tokens_data = _gw_get("/api/tokens") or {}

        gw_nodes = nodes_data.get("nodes", [])
        nodes = []
        display = {"nyx-windows": "Nyx-Windows", "iris": "Iris",
                   "kronos-heng": "Kronos-恆", "kronos-shun": "Kronos-瞬", "nyx-mac": "Nyx-Mac",
                   "iris-windows": "Iris-Windows"}
        for n in gw_nodes:
            nodes.append({
                "id": n.get("id", ""),
                "label": display.get(n.get("id", ""), n.get("id", "")),
                "did": n.get("did", ""),
                "hostname": n.get("hostname", ""),
                "status": "active" if n.get("online") else "inactive",
                "lastSeen": n.get("last_heartbeat", ""),
                "trust": n.get("trust", 0.0),
                "tokens": n.get("tokens", 0),
                "completed": n.get("completed", 0),
            })

        tk_list = tokens_data.get("tokens", [])
        tokens = []
        for t in tk_list:
            tokens.append({
                "id": t.get("id", ""),
                "initiator": t.get("initiator", ""),
                "executor": t.get("executor", ""),
                "status": t.get("status", "unknown"),
                "summary": str(t.get("summary", ""))[:80],
            })

        with _cache_lock:
            _cache = {"nodes": nodes, "tokens": tokens, "timestamp": datetime.now().isoformat()}
            _LAST_REFRESH = time.time()
        return True
    except:
        return False

def ensure_cache():
    global _cache
    ok = _refresh_cache()
    if not ok or not _cache:
        with _cache_lock:
            if not _cache:
                _cache = {"nodes": FALLBACK_NODES, "tokens": [], "timestamp": "fallback"}
    return ok

def get_cached(key):
    global _LAST_REFRESH
    if time.time() - _LAST_REFRESH > _CACHE_TTL:
        _refresh_cache()
    with _cache_lock:
        return _cache.get(key, [])

def get_registry():
    return {"nodes": {n["id"]: n for n in get_cached("nodes")}}

def get_trust_scores():
    nodes = get_cached("nodes")
    return {"scores": {n["id"]: {"trust": n.get("trust", 0),
                                  "total_tokens": n.get("tokens", 0),
                                  "completed": n.get("completed", 0)} for n in nodes}}

def get_token_history():
    return {"tokens": get_cached("tokens")}

def get_network_snapshot():
    nodes = get_cached("nodes")
    tokens = get_cached("tokens")
    edges = []
    pairs = {}
    for t in tokens:
        a, b = t.get("initiator"), t.get("executor")
        if a and b and a != b and a != "unknown" and b != "unknown":
            pairs[f"{a}->{b}"] = pairs.get(f"{a}->{b}", 0) + 1
    for k, v in pairs.items():
        p = k.split("->")
        edges.append({"source": p[0], "target": p[1], "label": "协作", "tokens": v})
    if not edges:
        edges.append({"source": "nyx-windows", "target": "iris", "label": "协作", "tokens": 0})
    return {
        "timestamp": datetime.now().isoformat(),
        "nodes": nodes,
        "edges": edges,
        "stats": {"total_nodes": len(nodes),
                  "active_nodes": len([n for n in nodes if n.get("status") == "active"]),
                  "total_tokens": len(tokens)}
    }
