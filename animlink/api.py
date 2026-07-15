# -*- coding: utf-8 -*-
"""
AnimaLink Viewer — API Routes
注册 4 个路由端点，供 server.py 挂载。
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from flask import Blueprint, jsonify
from data_reader import get_network_snapshot, get_trust_scores, get_token_history, get_registry

animlink_bp = Blueprint("animlink", __name__)


@animlink_bp.route("/animlink/api/network", methods=["GET"])
def api_network():
    """
    完整网络快照（聚合所有数据）。
    GET /animlink/api/network
    """
    try:
        data = get_network_snapshot()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@animlink_bp.route("/animlink/api/nodes", methods=["GET"])
def api_nodes():
    """
    节点列表（简化版，附带信任分）。
    GET /animlink/api/nodes
    """
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
    """
    信任分面板数据。
    GET /animlink/api/trust
    """
    try:
        trust = get_trust_scores()
        return jsonify(trust)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@animlink_bp.route("/animlink/api/tokens", methods=["GET"])
def api_tokens():
    """
    令牌历史。
    GET /animlink/api/tokens
    """
    try:
        tokens_data = get_token_history()
        return jsonify(tokens_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
