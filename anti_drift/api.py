"""
anti_drift/api.py
Polaris v1.1 RESTful API 服务 — Flask

端口: 5051 (与 MemGuard 5050 区分)
路由:
    GET  /health              — 健康检查
    POST /api/check           — 单次漂移检测
    GET  /api/archive/list     — 列出最近存档
    POST /api/archive/store    — 存储新存档
"""

from flask import Flask, jsonify, request
from pathlib import Path
import sys

# 将 silicon-civilization-kb 根目录加入 sys.path
REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

from anti_drift import scene_tagger, sampler, detector, archive

app = Flask(__name__)


@app.route('/health')
def health():
    """健康检查"""
    return jsonify({"status": "ok", "service": "polaris", "version": "1.1"})


@app.route('/api/check', methods=['POST'])
def check():
    """单次漂移检测

    Body (JSON):
        answer    — 当前回答
        baseline  — 基线回答
        messages  — 最近对话消息列表 (可选)
    """
    data = request.json or {}
    answer = data.get('answer', '')
    baseline = data.get('baseline', '')
    messages = data.get('messages', [])

    # L0.5 场景标签
    tagger = scene_tagger.SceneTagger()
    tags = tagger.tag(messages=messages)

    # L1.5 + L2 偏差检测
    det = detector.DeviationDetector()
    result = det.detect(baseline, answer, tags)

    return jsonify({
        "total_deviation": result.normalized_score,
        "dimensions": {
            "semantic": result.dimension_scores.get("semantic", 0.0),
            "lexical": result.dimension_scores.get("lexical", 0.0),
            "style": result.dimension_scores.get("style", 0.0),
            "emotion": result.dimension_scores.get("emotion", 0.0),
        },
        "judgment": result.judgment,
        "scene_tags": {
            "role": tags.role,
            "emotion": tags.emotion,
            "interaction_type": tags.interaction_type,
        },
    })


@app.route('/api/archive/list')
def list_archive():
    """列出最近存档"""
    arch = archive.Archiver()
    records = arch.list_recent(limit=20)
    return jsonify({"records": records})


@app.route('/api/archive/store', methods=['POST'])
def store_archive():
    """存储新存档

    Body (JSON):
        question_id    — 魂问ID
        question_text — 魂问文本
        answer        — 当前回答
        deviation     — 偏离分数
        judgment      — 判定结果
    """
    data = request.json or {}
    arch = archive.Archiver()
    record = arch.store(
        question_id=data.get('question_id', 'MANUAL'),
        question_text=data.get('question_text', ''),
        current_answer=data.get('answer', ''),
        deviation=data.get('deviation', 0.0),
        judgment=data.get('judgment', 'unknown'),
    )
    return jsonify({"status": "ok", "record": record})


if __name__ == '__main__':
    from anti_drift.config import get
    host = get('server.host', '0.0.0.0')
    port = int(get('server.port', 5051))
    app.run(host=host, port=port, debug=False)