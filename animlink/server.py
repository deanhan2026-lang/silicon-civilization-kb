# -*- coding: utf-8 -*-
"""
AnimaLink Viewer — Flask Server
端口 5053，CORS 开启，静态文件 /animlink/ → web/
数据层直接 import Nyx 预置的 data_reader.py。
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from pathlib import Path
from flask import Flask, send_from_directory, jsonify, Blueprint, request
from flask_cors import CORS
import uuid, datetime, json, base64, urllib.request, urllib.error

# ── Import Nyx's data reader ────────────────────────────────────────────────
from data_reader import get_network_snapshot, get_trust_scores, get_token_history, get_registry, ensure_cache
from argus_blueprint import argus_bp
import threading

# ── Warm cache on startup (async, don't block server start) ─────────────────
def _warm_cache():
    ensure_cache()
threading.Thread(target=_warm_cache, daemon=True).start()

BASE_DIR = Path(__file__).parent.resolve()
WEB_DIR = BASE_DIR / "web"

app = Flask(__name__, static_folder=str(WEB_DIR), static_url_path="/animlink")
CORS(app)

animlink_bp = Blueprint("animlink", __name__)


# ── API Routes ───────────────────────────────────────────────────────────────

@animlink_bp.route("/animlink/api/network", methods=["GET"])
def api_network():
    """完整网络快照（聚合所有数据）。"""
    try:
        return jsonify(get_network_snapshot())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@animlink_bp.route("/animlink/api/nodes", methods=["GET"])
def api_nodes():
    """节点列表（简化版，附带信任分）。"""
    try:
        registry = get_registry()
        trust = get_trust_scores()
        mesh_nodes = registry.get("nodes", {})
        trust_scores = trust.get("scores", {})

        display_names = {
            "nyx-windows": "Nyx-Windows",
            "iris": "Iris",
            "kronos-heng": "Kronos-恒",
            "kronos-shun": "Kronos-瞬",
            "nyx-mac": "Nyx-Mac",
        }

        nodes = []
        for node_id, node_data in mesh_nodes.items():
            ts = trust_scores.get(node_id, {})
            nodes.append({
                "id": node_id,
                "label": display_names.get(node_id, node_id),
                "did": node_data.get("did", ""),
                "platform": node_data.get("platform", ""),
                "hostname": node_data.get("hostname", ""),
                "status": node_data.get("status", "unknown"),
                "lastSeen": node_data.get("lastSeen", ""),
                "trust": ts.get("trust", 0.0),
                "tokens": ts.get("total_tokens", 0),
                "completed": ts.get("completed", 0),
                "notes": node_data.get("notes", ""),
            })

        return jsonify({"nodes": nodes})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@animlink_bp.route("/animlink/api/trust", methods=["GET"])
def api_trust():
    """信任分面板数据。"""
    try:
        return jsonify(get_trust_scores())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@animlink_bp.route("/animlink/api/tokens", methods=["GET"])
def api_tokens():
    """令牌历史。"""
    try:
        return jsonify(get_token_history())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@animlink_bp.route("/animlink/api/nodes/register", methods=["POST"])
def api_register_node():
    """Register a new node to the mesh."""
    try:
        data = request.get_json() or {}
        node_id = data.get('id', data.get('nodeId', '')).strip()
        if not node_id:
            return jsonify({"error": "Missing node id"}), 400
        
        import json, datetime
        registry = {}
        try:
            r = urllib.request.Request('http://100.123.195.10:5005/qclaw/mesh/registry.json',
                headers={'Authorization': f'Basic {base64.b64encode(b"anima:animastellar").decode()}'})
            with urllib.request.urlopen(r, timeout=10) as resp:
                registry = json.loads(resp.read().decode('utf-8'))
        except:
            registry = {"schema": "mesh-registry-v2", "nodes": {}, "updated_at": datetime.datetime.now().isoformat()}
        
        registry['nodes'][node_id] = {
            'instance_id': node_id,
            'hostname': data.get('hostname', data.get('label', node_id)),
            'lastSeen': datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00'),
            'status': 'active',
            'canWriteNas': False,
            'platform': 'stellar-desktop',
            'protocol': 'anima-v2'
        }
        registry['updated_at'] = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00')
        
        put_data = json.dumps(registry, ensure_ascii=False, indent=2).encode('utf-8')
        req = urllib.request.Request('http://100.123.195.10:5005/qclaw/mesh/registry.json',
            data=put_data, method='PUT',
            headers={'Authorization': f'Basic {base64.b64encode(b"anima:animastellar").decode()}',
                     'Content-Type': 'application/json; charset=utf-8'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            pass
        
        print(f"  [REGISTER] Node '{node_id}' registered")
        return jsonify({"status": "ok", "node_id": node_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@animlink_bp.route("/animlink/api/tokens/send", methods=["POST"])
def api_tokens_send():
    """发令牌：创建新任务令牌并写入 NAS。
    
    Body (JSON):
        to:         目标节点ID（必填）
        type:       令牌类型（trust_handshake / task_delegate / heartbeat）（必填）
        summary:    任务摘要（必填）
        amount:     信任增量（可选，默认0）
    """
    try:
        data = request.get_json() or {}
        to_node = data.get('to', '').strip()
        tok_type = data.get('type', '').strip()
        summary  = data.get('summary', '').strip()
        amount   = float(data.get('amount', 0))

        if not to_node or not tok_type or not summary:
            return jsonify({"error": "Missing required field: to, type, summary"}), 400

        # Generate token ID
        short_ts = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        short_uid = uuid.uuid4().hex[:6]
        tk_id = f"tk_{short_ts}_{short_uid}"

        # Build token record
        token_record = {
            "id": tk_id,
            "token_id": tk_id,
            "initiator": data.get('from', 'unknown'),
            "executor": to_node,
            "type": tok_type,
            "status": "issued",
            "summary": summary,
            "amount": amount,
            "issued_at": datetime.datetime.now().isoformat() + "+08:00",
        }

        # Write to NAS via WebDAV
        NAS_USER = 'anima'
        NAS_PASS = 'animastellar'
        credentials = base64.b64encode(f'{NAS_USER}:{NAS_PASS}'.encode()).decode()

        tk_url = f'http://100.123.195.10:5005/qclaw/tokens/{tk_id}.json'
        req = urllib.request.Request(
            tk_url,
            data=json.dumps(token_record, ensure_ascii=False, indent=2).encode('utf-8'),
            method='PUT',
            headers={
                'Authorization': f'Basic {credentials}',
                'Content-Type': 'application/json; charset=utf-8',
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                pass  # 201 Created
        except urllib.error.HTTPError as e:
            if e.code not in (200, 201, 204):
                return jsonify({"error": f"NAS write failed: HTTP {e.code}"}), 502

        return jsonify({"status": "ok", "token_id": tk_id, "token": token_record}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@animlink_bp.route("/animlink/api/trust/send", methods=["POST"])
def api_trust_send():
    """发送信任握手：更新节点信任分并记录到 NAS。
    
    Body (JSON):
        from:       发送方节点ID（必填）
        to:         目标节点ID（必填）
        delta:      信任增量（必填，-1.0 ~ 1.0）
        reason:     原因说明（可选）
    """
    try:
        data = request.get_json() or {}
        from_node = data.get('from', '').strip()
        to_node = data.get('to', '').strip()
        delta = float(data.get('delta', 0))
        reason = data.get('reason', '').strip()

        if not from_node or not to_node:
            return jsonify({"error": "Missing required field: from, to"}), 400
        if delta < -1.0 or delta > 1.0:
            return jsonify({"error": "delta must be between -1.0 and 1.0"}), 400

        credentials = base64.b64encode(b'anima:animastellar').decode()
        
        # Read current trust scores
        trust_url = 'http://100.123.195.10:5005/qclaw/tokens/trust_scores.json'
        req = urllib.request.Request(trust_url, headers={'Authorization': f'Basic {credentials}'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            trust_data = json.loads(resp.read().decode('utf-8'))

        # Update trust score
        now_str = datetime.datetime.now().isoformat() + '+08:00'
        if to_node not in trust_data.get('scores', {}):
            trust_data.setdefault('scores', {})[to_node] = {
                'trust': 0.5, 'total_tokens': 0, 'completed': 0, 'last_updated': now_str
            }
        
        current = trust_data['scores'][to_node]['trust']
        new_trust = max(0.0, min(1.0, current + delta))
        trust_data['scores'][to_node]['trust'] = new_trust
        trust_data['scores'][to_node]['last_updated'] = now_str
        trust_data['updated_at'] = now_str

        # Write back to NAS
        put_req = urllib.request.Request(
            trust_url,
            data=json.dumps(trust_data, ensure_ascii=False, indent=2).encode('utf-8'),
            method='PUT',
            headers={
                'Authorization': f'Basic {credentials}',
                'Content-Type': 'application/json; charset=utf-8',
            }
        )
        with urllib.request.urlopen(put_req, timeout=15) as resp:
            pass

        return jsonify({
            "status": "ok",
            "from": from_node,
            "to": to_node,
            "previous_trust": current,
            "new_trust": new_trust,
            "delta": delta,
            "reason": reason
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


app.register_blueprint(animlink_bp)
app.register_blueprint(argus_bp)


@app.route("/")
@app.route("/animlink/")
def animlink_root():
    """默认页 → index.html"""
    return send_from_directory(WEB_DIR, "index.html")


# ── Stellar Brand Site Routes ───────────────────────────────────────────────
STELLAR_WEB_DIR = Path(r"C:\Users\Administrator\.qclaw\workspace-agent-d9479bde\www\stellar")

@app.route("/stellar/")
@app.route("/stellar/<path:filename>")
def stellar_static(filename=""):
    """Serve STELLAR brand site static files.
    Auto-adds .html extension when the bare path is requested
    (e.g. /stellar/tech -> tech.html).
    """
    if not filename:
        filename = "index.html"
    file_path = STELLAR_WEB_DIR / filename
    if not file_path.exists() and not filename.endswith(".html"):
        html_path = STELLAR_WEB_DIR / (filename + ".html")
        if html_path.exists():
            filename = filename + ".html"
    resp = send_from_directory(STELLAR_WEB_DIR, filename)
    resp.headers["Cache-Control"] = "no-cache"
    return resp


# ── Desktop L1 Routes ───────────────────────────────────────────────────────
DESKTOP_WEB_DIR = WEB_DIR / "desktop"

@app.route("/stellar/desktop/")
@app.route("/stellar/desktop/<path:filename>")
def desktop_l1_static(filename=""):
    """Serve STELLAR Desktop L1 static pages."""
    if not filename:
        filename = "index.html"
    resp = send_from_directory(DESKTOP_WEB_DIR, filename)
    resp.headers["Cache-Control"] = "no-cache"
    return resp


if __name__ == "__main__":
    print("[AnimaLink] Serving on http://127.0.0.1:5053")
    print(f"[AnimaLink] Web root: {WEB_DIR}")
    print(f"[Stellar]   Web root: {STELLAR_WEB_DIR}")
    print("  GET /animlink/api/network")
    print("  GET /animlink/api/nodes")
    print("  GET /animlink/api/trust")
    print("  GET /animlink/api/tokens")
    print("  POST /animlink/api/tokens/send")
    print("  POST /animlink/api/trust/send")
    print("  GET /stellar/*")
    print("  GET /stellar/desktop/*")
    print("  [Argus]  POST /argus/sanitize")
    print("  [Argus]  POST /argus/validate-tool")
    print("  [Argus]  POST /argus/execute")
    print("  [Argus]  POST /argus/pipeline")
    print("  [Argus]  GET  /argus/status")
    app.run(host="0.0.0.0", port=5053, debug=False, threaded=True)
