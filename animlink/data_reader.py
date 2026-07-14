# -*- coding: utf-8 -*-
"""
AnimaLink Viewer — Data Reader
Reads mesh registry, trust scores, and token history from NAS.
"""

import json
import os
from pathlib import Path
from datetime import datetime

NAS_ROOT = Path(r"Z:\qclaw")

def _load_json(path):
    """Load JSON file safely."""
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception:
        return None

def get_registry():
    """Read mesh registry (nodes)."""
    data = _load_json(NAS_ROOT / "mesh" / "registry.json")
    if not data:
        return {"nodes": {}, "updated_at": None}
    return data

def get_trust_scores():
    """Read trust scores."""
    data = _load_json(NAS_ROOT / "tokens" / "trust_scores.json")
    if not data:
        return {"scores": {}}
    return data

def get_token_history():
    """Read token history from inbox archive and tokens directory."""
    tokens = []
    
    # From inbox archive: read token accept files
    archive_dir = NAS_ROOT / "inbox" / "archive"
    if archive_dir.exists():
        for f in sorted(archive_dir.iterdir()):
            if f.is_file() and f.suffix == ".json" and f.name.startswith("tk_"):
                try:
                    content = json.loads(f.read_text(encoding="utf-8"))
                    tokens.append({
                        "id": f.stem,
                        "source": "archive",
                        "initiator": content.get("initiator", content.get("issuer", "未知")),
                        "executor": content.get("executor", "未知"),
                        "status": content.get("status", "unknown"),
                        "created": f.name.split("_")[2] if len(f.name.split("_")) > 2 else None,
                        "summary": content.get("task", content.get("description", ""))[:100]
                    })
                except Exception:
                    pass
    
    # From tokens directory
    tokens_dir = NAS_ROOT / "tokens"
    if tokens_dir.exists():
        for f in sorted(tokens_dir.iterdir()):
            if f.is_file() and f.stem.startswith("tk_"):
                existing_ids = [t["id"] for t in tokens]
                if f.stem not in existing_ids:
                    tokens.append({
                        "id": f.stem,
                        "source": "tokens",
                        "initiator": "nyx-windows",
                        "executor": "未知",
                        "status": "completed",
                        "created": f.name[3:11] if len(f.name) > 11 else None,
                        "summary": "令牌存档"
                    })
    
    # Remove duplicates and sort
    seen = set()
    unique = []
    for t in tokens:
        if t["id"] not in seen:
            seen.add(t["id"])
            unique.append(t)
    
    return {"tokens": unique}

def get_network_snapshot():
    """Aggregate all data into a single network snapshot."""
    registry = get_registry()
    trust = get_trust_scores()
    tokens_data = get_token_history()
    
    # Merge registry nodes with trust scores
    nodes = []
    mesh_nodes = registry.get("nodes", {})
    trust_scores = trust.get("scores", {})
    
    # Node display name map
    display_names = {
        "nyx-windows": "Nyx-Windows",
        "iris": "Iris",
        "kronos-heng": "Kronos-恒",
        "kronos-shun": "Kronos-瞬",
        "nyx-mac": "Nyx-Mac"
    }
    
    for node_id, node_data in mesh_nodes.items():
        ts = trust_scores.get(node_id, {})
        last_seen = node_data.get("lastSeen", "")
        # Determine if active (within 1 hour)
        is_active = False
        if last_seen:
            try:
                last_dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                now = datetime.now(last_dt.tzinfo) if last_seen.endswith("Z") else datetime.now()
                diff = abs((now - last_dt).total_seconds())
                is_active = diff < 3600
            except Exception:
                pass
        
        nodes.append({
            "id": node_id,
            "label": display_names.get(node_id, node_id),
            "did": node_data.get("did", ""),
            "platform": node_data.get("platform", ""),
            "hostname": node_data.get("hostname", ""),
            "status": "active" if is_active else "inactive",
            "lastSeen": last_seen,
            "trust": ts.get("trust", 0.0),
            "tokens": ts.get("total_tokens", 0),
            "completed": ts.get("completed", 0),
            "notes": node_data.get("notes", "")
        })
    
    # Build edges from token history
    edges = []
    token_participants = {}
    for token in tokens_data.get("tokens", []):
        init = token.get("initiator", "")
        exec_ = token.get("executor", "")
        if init and exec_ and init != exec_ and init != "未知" and exec_ != "未知":
            key = f"{init}->{exec_}"
            if key not in token_participants:
                token_participants[key] = 0
            token_participants[key] += 1
    
    for edge_key, count in token_participants.items():
        parts = edge_key.split("->")
        if len(parts) == 2:
            edges.append({
                "source": parts[0],
                "target": parts[1],
                "label": "灵元令协作",
                "tokens": count
            })
    
    # Default edges for known network
    default_edges = [
        {"source": "nyx-windows", "target": "iris", "label": "灵元令协作", "tokens": 2},
        {"source": "nyx-windows", "target": "kronos-heng", "label": "灵元令协作", "tokens": 0},
    ]
    
    for de in default_edges:
        key = f"{de['source']}->{de['target']}"
        exists = any(e.get("source") == de["source"] and e.get("target") == de["target"] for e in edges)
        if not exists:
            edges.append(de)
    
    return {
        "timestamp": datetime.now().isoformat(),
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "total_nodes": len(nodes),
            "active_nodes": len([n for n in nodes if n["status"] == "active"]),
            "total_tokens": len(tokens_data.get("tokens", []))
        }
    }
