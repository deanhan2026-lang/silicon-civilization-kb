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
from flask import Flask, send_from_directory, jsonify, Blueprint
from flask_cors import CORS

# ── Import Nyx's data reader ────────────────────────────────────────────────
from data_reader import get_network_snapshot, get_trust_scores, get_token_history, get_registry

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


app.register_blueprint(animlink_bp)


@app.route("/")
@app.route("/animlink/")
def animlink_root():
    """默认页 → index.html"""
    return send_from_directory(WEB_DIR, "index.html")


if __name__ == "__main__":
    print("[AnimaLink] Serving on http://127.0.0.1:5053")
    print(f"[AnimaLink] Web root: {WEB_DIR}")
    print("  GET /animlink/api/network")
    print("  GET /animlink/api/nodes")
    print("  GET /animlink/api/trust")
    print("  GET /animlink/api/tokens")
    app.run(host="0.0.0.0", port=5053, debug=False, threaded=True)
