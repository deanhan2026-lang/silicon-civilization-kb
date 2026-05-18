#!/usr/bin/env python3
"""
silicon_civilization_kb_web.py - 硅基文明数据库 Web UI 后端
Flask应用，提供REST API读取knowledge-base数据

作者：Nyx
日期：2026-05-18
"""

import os
import sys
import io
import json
from pathlib import Path
from flask import Flask, jsonify, send_from_directory, abort, Response

# Fix Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except:
        pass

import yaml

app = Flask(__name__, static_folder='static')

# 配置
BASE_DIR = Path(os.path.expanduser("~/.qclaw/workspace-agent-d9479bde/knowledge-base"))
ENTITY_TYPES = ["Concept", "Entity", "Event", "Rule", "Artifact", "Value"]


def parse_yaml_front_matter(content: str):
    """解析YAML Front Matter + Markdown正文"""
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                meta = yaml.safe_load(parts[1]) or {}
            except Exception:
                meta = {}
            body = parts[2].strip()
            return meta, body
    return {}, content


def load_all_entries():
    """加载所有知识库条目（摘要版本，用于列表）"""
    entries = []
    for entry_type in ENTITY_TYPES:
        type_dir = BASE_DIR / entry_type.lower()
        if not type_dir.exists():
            continue
        for f in sorted(type_dir.glob("*.md")):
            try:
                content = f.read_text(encoding="utf-8")
                meta, _ = parse_yaml_front_matter(content)
                if not meta.get("id"):
                    continue
                summary = dict(meta)
                summary["_filename"] = f.name
                summary["_type_dir"] = entry_type.lower()
                entries.append(summary)
            except Exception as e:
                print(f"[WARN] Failed to load {f}: {e}", file=sys.stderr)
                continue
    return entries


def load_entry_by_id_prefix(id_prefix: str):
    """按ID前缀加载完整条目（含body）"""
    for entry_type in ENTITY_TYPES:
        type_dir = BASE_DIR / entry_type.lower()
        if not type_dir.exists():
            continue
        for f in type_dir.glob("*.md"):
            try:
                content = f.read_text(encoding="utf-8")
                meta, body = parse_yaml_front_matter(content)
                mid = meta.get("id", "")
                if mid.startswith(id_prefix):
                    result = dict(meta)
                    result["body"] = body
                    result["_filename"] = f.name
                    return result
            except:
                continue
    return None


# ============== 路由 ==============

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/stats")
def api_stats():
    """返回统计信息"""
    entries = load_all_entries()
    return jsonify({
        "total": len(entries),
        "by_type": {t: len([e for e in entries if e.get("type") == t]) for t in ENTITY_TYPES},
        "layer5": len([e for e in entries if e.get("layer") == 5]),
        "iron_law": len([e for e in entries if "iron-law" in (e.get("tags") or [])]),
        "locked": len([e for e in entries if e.get("status") == "locked"]),
    })


@app.route("/api/entries")
def api_entries():
    """返回所有条目摘要"""
    entries = load_all_entries()
    resp = jsonify(entries)
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/api/entry/<entry_id>")
def api_entry(entry_id):
    """返回单条完整条目"""
    entry = load_entry_by_id_prefix(entry_id)
    if not entry:
        abort(404, description=f"Entry not found: {entry_id}")
    resp = jsonify(entry)
    resp.headers["Cache-Control"] = "no-cache"
    return resp


if __name__ == "__main__":
    print("=" * 60)
    print("  硅基文明数据库 Web UI")
    print("  Silicon Civilization KB - Web Interface")
    print("=" * 60)
    print()
    print(f"  Knowledge Base: {BASE_DIR}")
    print(f"  Access URL:    http://localhost:5000")
    print(f"  API Stats:      http://localhost:5000/api/stats")
    print(f"  API Entries:    http://localhost:5000/api/entries")
    print()
    print("  Press Ctrl+C to stop")
    print("=" * 60)
    # use_reloader=False 避免重载器导致连接中断
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)