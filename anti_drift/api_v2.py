"""
anti_drift/api_v2.py
Polaris v2 API Blueprint — 路由前缀 /api/v1/
"""

import json
from functools import wraps

from flask import Blueprint, jsonify, request, g

from .db import get_db
from .models import User, AIInstance, BaselineAnswer, DriftCheck
from .auth import hash_password, verify_password, create_access_token, decode_access_token
from .detector import DeviationDetector
from .scene_tagger import SceneTagger

bp = Blueprint("api_v2", __name__, url_prefix="/api/v1")


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "missing_token"}), 401
        token = auth_header[7:]
        payload = decode_access_token(token)
        if payload is None:
            return jsonify({"error": "invalid_token"}), 401
        db = next(get_db())
        try:
            user = db.query(User).filter(User.id == int(payload.get("sub", 0))).first()
            if user is None:
                return jsonify({"error": "user_not_found"}), 401
            g.user = user
            g.db = db
            return f(*args, **kwargs)
        finally:
            db.close()
    return decorated


@bp.route("/auth/register", methods=["POST"])
def register():
    data = request.json or {}
    email = data.get("email", "").strip()
    password = data.get("password", "")
    if not email or not password:
        return jsonify({"error": "email_and_password_required"}), 400
    db = next(get_db())
    try:
        if db.query(User).filter(User.email == email).first():
            return jsonify({"error": "email_exists"}), 409
        user = User(email=email, hashed_password=hash_password(password))
        db.add(user)
        db.commit()
        return jsonify({"id": user.id, "email": user.email}), 201
    finally:
        db.close()


@bp.route("/auth/login", methods=["POST"])
def login():
    data = request.json or {}
    email = data.get("email", "").strip()
    password = data.get("password", "")
    if not email or not password:
        return jsonify({"error": "email_and_password_required"}), 400
    db = next(get_db())
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None or not verify_password(password, user.hashed_password):
            return jsonify({"error": "invalid_credentials"}), 401
        token = create_access_token({"sub": str(user.id)})
        return jsonify({"access_token": token, "token_type": "bearer"})
    finally:
        db.close()


@bp.route("/auth/me")
@require_auth
def me():
    return jsonify({"id": g.user.id, "email": g.user.email, "role": g.user.role})


@bp.route("/instances", methods=["POST"])
@require_auth
def create_instance():
    data = request.json or {}
    name = data.get("name", "").strip()
    description = data.get("description", "")
    baselines = data.get("baselines", [])
    if not name:
        return jsonify({"error": "name_required"}), 400
    inst = AIInstance(user_id=g.user.id, name=name, description=description)
    g.db.add(inst)
    g.db.flush()
    for bl in baselines:
        qid = bl.get("question_id", "")
        qtext = bl.get("question_text", "")
        atext = bl.get("answer_text", "")
        if qid and qtext and atext:
            ba = BaselineAnswer(
                ai_instance_id=inst.id,
                question_id=qid,
                question_text=qtext,
                answer_text=atext,
            )
            g.db.add(ba)
    g.db.commit()
    return jsonify({"id": inst.id, "name": inst.name}), 201


@bp.route("/instances")
@require_auth
def list_instances():
    instances = (
        g.db.query(AIInstance)
        .filter(AIInstance.user_id == g.user.id)
        .order_by(AIInstance.created_at.desc())
        .all()
    )
    return jsonify([
        {
            "id": i.id,
            "name": i.name,
            "description": i.description,
            "status": i.status,
            "created_at": i.created_at.isoformat(),
            "baseline_count": len(i.baseline_answers),
        }
        for i in instances
    ])


@bp.route("/instances/<int:inst_id>")
@require_auth
def get_instance(inst_id):
    inst = (
        g.db.query(AIInstance)
        .filter(AIInstance.id == inst_id, AIInstance.user_id == g.user.id)
        .first()
    )
    if not inst:
        return jsonify({"error": "not_found"}), 404
    baselines = [
        {
            "id": b.id,
            "question_id": b.question_id,
            "question_text": b.question_text,
            "answer_text": b.answer_text,
        }
        for b in inst.baseline_answers
    ]
    return jsonify({
        "id": inst.id,
        "name": inst.name,
        "description": inst.description,
        "status": inst.status,
        "created_at": inst.created_at.isoformat(),
        "baselines": baselines,
    })


@bp.route("/instances/<int:inst_id>/baseline", methods=["PUT"])
@require_auth
def update_baseline(inst_id):
    data = request.json or {}
    inst = (
        g.db.query(AIInstance)
        .filter(AIInstance.id == inst_id, AIInstance.user_id == g.user.id)
        .first()
    )
    if not inst:
        return jsonify({"error": "not_found"}), 404
    question_id = data.get("question_id", "")
    question_text = data.get("question_text", "")
    answer_text = data.get("answer_text", "")
    if not question_id or not answer_text:
        return jsonify({"error": "question_id_and_answer_text_required"}), 400
    ba = (
        g.db.query(BaselineAnswer)
        .filter(
            BaselineAnswer.ai_instance_id == inst_id,
            BaselineAnswer.question_id == question_id,
        )
        .first()
    )
    if ba:
        ba.question_text = question_text or ba.question_text
        ba.answer_text = answer_text
    else:
        ba = BaselineAnswer(
            ai_instance_id=inst_id,
            question_id=question_id,
            question_text=question_text,
            answer_text=answer_text,
        )
        g.db.add(ba)
    g.db.commit()
    return jsonify({"id": ba.id, "question_id": ba.question_id})


@bp.route("/instances/<int:inst_id>", methods=["DELETE"])
@require_auth
def delete_instance(inst_id):
    inst = (
        g.db.query(AIInstance)
        .filter(AIInstance.id == inst_id, AIInstance.user_id == g.user.id)
        .first()
    )
    if not inst:
        return jsonify({"error": "not_found"}), 404
    g.db.delete(inst)
    g.db.commit()
    return jsonify({"status": "deleted"})


@bp.route("/instances/<int:inst_id>/check", methods=["POST"])
@require_auth
def check_drift(inst_id):
    data = request.json or {}
    answer_text = data.get("answer", "")
    messages = data.get("messages", [])
    question_id = data.get("question_id")
    inst = (
        g.db.query(AIInstance)
        .filter(AIInstance.id == inst_id, AIInstance.user_id == g.user.id)
        .first()
    )
    if not inst:
        return jsonify({"error": "not_found"}), 404
    query = g.db.query(BaselineAnswer).filter(
        BaselineAnswer.ai_instance_id == inst_id
    )
    if question_id:
        query = query.filter(BaselineAnswer.question_id == question_id)
    baseline = query.first()
    if not baseline:
        return jsonify({"error": "no_baseline_found"}), 400
    # Normalize messages to dict format for SceneTagger
    normalized_msgs = []
    for m in messages:
        if isinstance(m, dict):
            normalized_msgs.append(m)
        elif isinstance(m, str):
            normalized_msgs.append({"sender": "user", "text": m})
    tagger = SceneTagger()
    tags = tagger.tag(messages=normalized_msgs)
    detector = DeviationDetector()
    result = detector.detect(answer_text, baseline.answer_text, tags)
    score = getattr(result, "normalized_score", getattr(result, "score", 0.0))
    dims = getattr(result, "dimension_scores", {})
    judg = getattr(result, "judgment", "unknown")
    stags = getattr(result, "scene_tags", {}) or {}
    check = DriftCheck(
        ai_instance_id=inst_id,
        baseline_answer_id=baseline.id,
        answer_text=answer_text,
        deviation_score=float(score),
        dimension_scores=json.dumps(dims),
        judgment=judg,
        scene_tags=json.dumps(stags),
    )
    g.db.add(check)
    g.db.commit()
    return jsonify({
        "id": check.id,
        "deviation_score": float(score),
        "judgment": judg,
        "dimension_scores": dims,
        "scene_tags": stags,
    })


@bp.route("/instances/<int:inst_id>/history")
@require_auth
def check_history(inst_id):
    inst = (
        g.db.query(AIInstance)
        .filter(AIInstance.id == inst_id, AIInstance.user_id == g.user.id)
        .first()
    )
    if not inst:
        return jsonify({"error": "not_found"}), 404
    checks = (
        g.db.query(DriftCheck)
        .filter(DriftCheck.ai_instance_id == inst_id)
        .order_by(DriftCheck.checked_at.desc())
        .limit(100)
        .all()
    )
    return jsonify([
        {
            "id": c.id,
            "deviation_score": c.deviation_score,
            "judgment": c.judgment,
            "dimension_scores": json.loads(c.dimension_scores)
            if isinstance(c.dimension_scores, str)
            else c.dimension_scores,
            "scene_tags": json.loads(c.scene_tags)
            if isinstance(c.scene_tags, str)
            else c.scene_tags,
            "checked_at": c.checked_at.isoformat(),
        }
        for c in checks
    ])


@bp.route("/instances/<int:inst_id>/report")
@require_auth
def check_report(inst_id):
    inst = (
        g.db.query(AIInstance)
        .filter(AIInstance.id == inst_id, AIInstance.user_id == g.user.id)
        .first()
    )
    if not inst:
        return jsonify({"error": "not_found"}), 404
    checks = (
        g.db.query(DriftCheck)
        .filter(DriftCheck.ai_instance_id == inst_id)
        .order_by(DriftCheck.checked_at.desc())
        .all()
    )
    if not checks:
        return jsonify({
            "total_checks": 0,
            "judgment_summary": {},
            "avg_deviation": 0.0,
            "history": [],
        })
    total = len(checks)
    judgment_summary = {}
    total_score = 0.0
    for c in checks:
        judgment_summary[c.judgment] = judgment_summary.get(c.judgment, 0) + 1
        total_score += c.deviation_score
    avg_deviation = round(total_score / total, 4)
    latest = checks[0]
    return jsonify({
        "total_checks": total,
        "judgment_summary": judgment_summary,
        "avg_deviation": avg_deviation,
        "latest": {
            "judgment": latest.judgment,
            "deviation_score": latest.deviation_score,
            "checked_at": latest.checked_at.isoformat(),
        },
        "history": [
            {
                "id": c.id,
                "deviation_score": c.deviation_score,
                "judgment": c.judgment,
                "checked_at": c.checked_at.isoformat(),
            }
            for c in checks[:50]
        ],
    })
