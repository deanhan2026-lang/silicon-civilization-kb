# -*- coding: utf-8 -*-
"""
AnimaLink Viewer — Flask Server (NAS edition)
Port 5053. Static files from web/. Data from Gateway API via data_reader_nas.py
"""
import sys
import io

from pathlib import Path
from flask import Flask, send_from_directory, jsonify, Blueprint
from flask_cors import CORS

from data_reader_nas import get_network_snapshot, get_trust_scores, get_token_history, get_registry, ensure_cache
import threading

def _warm():
    ensure_cache()
threading.Thread(target=_warm, daemon=True).start()

BASE_DIR = Path(__file__).parent.resolve()
WEB_DIR = BASE_DIR / "web"

app = Flask(__name__, static_folder=str(WEB_DIR), static_url_path="/animlink")
CORS(app)

bp = Blueprint("animlink", __name__)

@bp.route("/animlink/api/network")
def api_network():
    try: return jsonify(get_network_snapshot())
    except Exception as e: return jsonify({"error": str(e)}), 500

@bp.route("/animlink/api/nodes")
def api_nodes():
    try:
        registry = get_registry()
        trust = get_trust_scores()
        nodes = []
        for nid, ndata in registry.get("nodes", {}).items():
            ts = trust.get("scores", {}).get(nid, {})
            nodes.append({**ndata, "trust": ts.get("trust", 0),
                          "tokens": ts.get("total_tokens", 0),
                          "completed": ts.get("completed", 0)})
        return jsonify({"nodes": nodes})
    except Exception as e: return jsonify({"error": str(e)}), 500

@bp.route("/animlink/api/trust")
def api_trust():
    try: return jsonify(get_trust_scores())
    except Exception as e: return jsonify({"error": str(e)}), 500

@bp.route("/animlink/api/tokens")
def api_tokens():
    try: return jsonify(get_token_history())
    except Exception as e: return jsonify({"error": str(e)}), 500

app.register_blueprint(bp)

@app.route("/")
@app.route("/animlink/")
def root():
    return send_from_directory(WEB_DIR, "index.html")

if __name__ == "__main__":
    print(f"[AnimaLink Viewer] Web: {WEB_DIR} | Gateway: localhost:8000")
    app.run(host="0.0.0.0", port=5053, debug=False, threaded=True)
