# -*- coding: utf-8 -*-
"""
AnimaLink Viewer — Data Reader (memory-cached edition)
Reads NAS data once and caches it in memory. If NAS is slow, serves cached data.
"""
import json
import os
import time
import threading
from datetime import datetime
import urllib.request
import urllib.error
import base64
import re as _re

# WebDAV access to NAS (replaces Z: drive dependency)
NAS_WEBDAV_BASE = "http://100.123.195.10:5005/qclaw"
NAS_WEBDAV_AUTH = {'Authorization': 'Basic ' + base64.b64encode(b'anima:animastellar').decode()}

def _webdav_get(rel_path, timeout=10):
    """GET file from NAS WebDAV, return bytes or None."""
    url = NAS_WEBDAV_BASE + '/' + rel_path.lstrip('/')
    try:
        req = urllib.request.Request(url, headers=NAS_WEBDAV_AUTH)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception:
        return None

def _webdav_list(rel_path, timeout=10):
    """PROPFIND list dir from NAS WebDAV, return list of names or None."""
    url = NAS_WEBDAV_BASE + '/' + rel_path.lstrip('/') + '/'
    try:
        req = urllib.request.Request(url, method='PROPFIND', headers=NAS_WEBDAV_AUTH)
        req.add_header('Depth', '1')
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode('utf-8', errors='ignore')
        hrefs = _re.findall(r'<[^>]+:href>([^<]+)</[^>]+:href>', body)
        names = []
        for h in hrefs:
            n = h.rstrip('/').split('/')[-1]
            if n and n not in ('.', '..'):
                names.append(n)
        return names
    except Exception:
        return None

# NAS-aware storage: try Z: (NAS), fallback to E:\SOFTWARE\qclaw
def _resolve_root():
    """NAS root - legacy local path, primary access is now WebDAV."""
    return "Z:\\qclaw"  # legacy; WebDAV (_webdav_get) is the primary access path

NAS_ROOT = _resolve_root()

# In-memory cache
_cache = {}
_cache_lock = threading.Lock()
_LAST_REFRESH = 0
_CACHE_TTL = 300  # 5 minutes
_INITIALIZED = False

# Fallback data for when NAS is unreachable
FALLBACK_NODES = [
    {"id": "nyx-windows", "label": "Nyx-Windows", "status": "active", "trust": 1.0, "tokens": 10, "completed": 8},
    {"id": "iris", "label": "Iris", "status": "active", "trust": 0.8, "tokens": 6, "completed": 5},
    {"id": "kronos-heng", "label": "Kronos-恒", "status": "active", "trust": 0.7, "tokens": 4, "completed": 3},
]
FALLBACK_TOKENS = [
    {"id": "tk_anima_genesis_001", "initiator": "nyx-windows", "executor": "system", "status": "completed", "summary": "系统启动"},
]

def _nas_read_json(rel_path):
    """Read JSON from NAS via WebDAV with timeout guard."""
    data = _webdav_get(rel_path)
    if data is None:
        return None
    try:
        return json.loads(data.decode('utf-8-sig'))
    except Exception:
        return None

def _nas_list_dir(rel_path):
    """List directory via WebDAV PROPFIND."""
    return _webdav_list(rel_path)

def _refresh_cache():
    """Refresh the in-memory cache from NAS."""
    global _cache, _LAST_REFRESH
    start = time.time()
    
    try:
        # Read registry
        registry = _nas_read_json("mesh/registry.json") or {}
        trust = _nas_read_json("tokens/trust_scores.json") or {}
        
        # Parse nodes
        nodes = []
        display = {"nyx-windows": "Nyx-Windows", "iris": "Iris", 
                   "kronos-heng": "Kronos-恒", "kronos-shun": "Kronos-瞬", "nyx-mac": "Nyx-Mac"}
        for nid, ndata in registry.get("nodes", {}).items():
            last_seen = ndata.get("lastSeen", ndata.get("lastHeartbeat", ""))
            # Trust the registry's status field first
            reg_status = ndata.get("status", "")
            is_active = (reg_status == "active")
            # If no status field, fall back to time-based check
            if not reg_status and last_seen:
                try:
                    delta = abs((datetime.now() - datetime.fromisoformat(last_seen.replace("Z", "+00:00"))).total_seconds())
                    is_active = delta < 3600
                except: pass
            ts_data = trust.get("scores", {}).get(nid, {})
            nodes.append({
                "id": nid, "label": display.get(nid, nid),
                "did": ndata.get("did", ""), "hostname": ndata.get("hostname", ""),
                "status": "active" if is_active else "inactive",
                "lastSeen": last_seen, "trust": ts_data.get("trust", 0.0),
                "tokens": ts_data.get("total_tokens", 0), "completed": ts_data.get("completed", 0),
            })
        
        # Parse tokens from tokens/ (primary) AND inbox/archive/ (legacy)
        tokens = []
        seen = set()

        # Source 1: tokens/ directory (via WebDAV - SMB may have permission issues)
        tokens_dir_http = "http://100.123.195.10:5005/qclaw/tokens"
        try:
            from urllib.request import Request, urlopen
            import re as _re
            import base64
            NAS_WEBDAV_AUTH = {'Authorization': 'Basic ' + base64.b64encode(b'anima:animastellar').decode()}
            req = Request(tokens_dir_http + "/", method="PROPFIND", headers=NAS_WEBDAV_AUTH)
            req.add_header("Depth", "1")
            r = urlopen(req, timeout=8)
            body = r.read().decode("utf-8", errors="ignore")
            hrefs = _re.findall(r'<[^>]+:href>([^<]+)</[^>]+:href>', body)
            for href in sorted(hrefs):
                fname = href.rstrip("/").split("/")[-1]
                if not fname.endswith(".json"):
                    continue
                if not (fname.startswith("tk_") or fname.startswith("accept_") or fname.startswith("delivery_")):
                    continue
                try:
                    file_req = Request(tokens_dir_http + "/" + fname, headers=NAS_WEBDAV_AUTH)
                    r2 = urlopen(file_req, timeout=5)
                    raw = r2.read()
                    obj = json.loads(raw)
                    tk_id = obj.get("id", fname.replace(".json", ""))
                    summary = obj.get("title", obj.get("summary", ""))
                    status = obj.get("status", "issued")
                    executor = obj.get("issued_to", "unknown").lower()
                    if executor == "nyx":
                        executor = "nyx-windows"
                    if tk_id not in seen:
                        seen.add(tk_id)
                        tokens.append({
                            "id": tk_id,
                            "initiator": obj.get("issued_by", "nyx-windows").lower(),
                            "executor": executor,
                            "status": status,
                            "summary": str(summary)[:80],
                        })
                except Exception:
                    pass
        except Exception:
            pass

        # Source 2: inbox/archive/ (legacy fallback)
        archive_path = os.path.join(NAS_ROOT, "inbox", "archive")
        archive_names = _nas_list_dir("inbox/archive") or []
        for name in sorted(archive_names):
            if not (name.endswith(".json") or name.endswith(".md")):
                continue
            if not (name.startswith("tk_") or name.startswith("accept_") or name.startswith("delivery_")):
                continue
            fp = os.path.join(archive_path, name)
            try:
                raw = _webdav_get("inbox/archive/" + name)
                if raw is None:
                    continue
                text = raw.decode('utf-8', errors='replace')
                name_lower = name.lower()
                if "iris" in name_lower: executor = "iris"
                elif "heng" in name_lower or "kronos" in name_lower: executor = "kronos-heng"
                else: executor = "unknown"
                
                tk_id = name.split(".")[0]
                summary = text[:80] if len(text) > 10 else ""
                status = "completed"
                
                if name.endswith(".json"):
                    try:
                        obj = json.loads(raw)
                        tk_id = obj.get("token_id", obj.get("id", tk_id))
                        summary = obj.get("task", obj.get("title", obj.get("description", summary)))
                        status = obj.get("status", "accepted")
                    except: pass
                
                if tk_id not in seen:
                    seen.add(tk_id)
                    tokens.append({
                        "id": tk_id, "initiator": "nyx-windows", "executor": executor,
                        "status": status, "summary": str(summary)[:80],
                    })
            except: pass
        
        with _cache_lock:
            _cache = {"nodes": nodes, "tokens": tokens, "timestamp": datetime.now().isoformat()}
            _LAST_REFRESH = time.time()
        
        return True
    except Exception:
        return False

def ensure_cache():
    """Ensure cache is populated (called at server start)."""
    global _cache
    ok = _refresh_cache()
    if not ok or not _cache:
        with _cache_lock:
            if not _cache:  # double-check
                _cache = {"nodes": FALLBACK_NODES, "tokens": FALLBACK_TOKENS, "timestamp": "fallback"}
    return ok

def get_cached(key):
    """Get data from cache, refreshing if stale."""
    global _LAST_REFRESH
    now = time.time()
    # If cache is stale and no other thread is refreshing, try refresh
    if now - _LAST_REFRESH > _CACHE_TTL:
        _refresh_cache()
    with _cache_lock:
        return _cache.get(key, [] if key == "tokens" or key == "nodes" else {})

def get_registry():
    """Alias for network nodes."""
    return {"nodes": {n["id"]: n for n in get_cached("nodes")}}

def get_trust_scores():
    """Alias for trust scores from cached nodes."""
    return {"scores": {n["id"]: {"trust": n.get("trust", 0), "total_tokens": n.get("tokens", 0), 
                                  "completed": n.get("completed", 0)} for n in get_cached("nodes")}}

def get_token_history():
    """Return cached token history."""
    return {"tokens": get_cached("tokens")}

def get_network_snapshot():
    """Aggregate cached data into network snapshot."""
    nodes = get_cached("nodes")
    tokens = get_cached("tokens")
    
    # Build edges
    edges = []
    token_pairs = {}
    for t in tokens:
        init, exe = t.get("initiator"), t.get("executor")
        if init and exe and init != exe and init != "unknown" and exe != "unknown":
            k = f"{init}->{exe}"
            token_pairs[k] = token_pairs.get(k, 0) + 1
    for k, v in token_pairs.items():
        parts = k.split("->")
        edges.append({"source": parts[0], "target": parts[1], "label": "协作", "tokens": v})
    
    # Default edges if none
    if not edges:
        for s, t in [("nyx-windows", "iris"), ("nyx-windows", "kronos-heng")]:
            edges.append({"source": s, "target": t, "label": "协作", "tokens": 0})
    
    return {
        "timestamp": datetime.now().isoformat(),
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "total_nodes": len(nodes),
            "active_nodes": len([n for n in nodes if n.get("status") == "active"]),
            "total_tokens": len(tokens)
        }
    }
