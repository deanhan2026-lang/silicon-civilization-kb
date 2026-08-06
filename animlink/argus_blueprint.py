# -*- coding: utf-8 -*-
"""
Argus 安全网关 Blueprint — 挂载到 AnimaLink
百眼巨人：Agent 侧的 WAF，提供提示注入检测、工具调用验证、沙箱执行。

Phase 1: 提示注入检测 API + 状态监控
Phase 2+: 工具调用验证、沙箱执行（需客户端嵌入重构）
"""
import sys, os, json, datetime, base64, urllib.request

sys.path.insert(0, str(os.path.join(os.path.dirname(__file__), '..')))
from argus import (
    UnicodeSanitizer, IntentBoundaryMarker
)

from flask import Blueprint, request, jsonify

argus_bp = Blueprint("argus", __name__)

# ── 单例初始化 ────────────────────────────────────────────────────────────────
_sanitizer = UnicodeSanitizer()
_boundary = IntentBoundaryMarker()

# ── NAS 审计日志存储 ──────────────────────────────────────────────────────────
NAS_BASE = "http://100.123.195.10:5005/qclaw"
AUTH_HEADER = f"Basic {base64.b64encode(b'anima:animastellar').decode()}"


def _write_audit(entry: dict):
    """写入审计日志到 NAS。"""
    try:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:21]
        url = f"{NAS_BASE}/argus/audit_{ts}.json"
        req = urllib.request.Request(
            url,
            data=json.dumps(entry, ensure_ascii=False, indent=2).encode("utf-8"),
            method="PUT",
            headers={"Authorization": AUTH_HEADER, "Content-Type": "application/json; charset=utf-8"},
        )
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception:
        pass  # 审计失败不阻塞主流程


# ══════════════════════════════════════════════════════════════════════════════
# API 端点
# ══════════════════════════════════════════════════════════════════════════════

@argus_bp.route("/argus/sanitize", methods=["POST"])
def api_sanitize():
    """提示注入检测 Phase 1。
    
    Body: {"prompt": "用户输入文本", "source": "user|external"}
    Returns: {"safe": bool, "score": float, "findings": [...], "sanitized": str}
    """
    try:
        data = request.get_json() or {}
        prompt = data.get("prompt", "")
        source = data.get("source", "external")

        # L1: Unicode 清理（清洗混淆字符）
        cleaned, issues = _sanitizer.sanitize(prompt)
        
        # L2: 意图边界检测
        result = _boundary.analyze(cleaned, source)
        is_safe = result.get("is_safe", True)
        findings = result.get("findings", [])
        score = result.get("injection_risk", 0.0)
        
        # 合并 sanitizer issues 到 findings
        for issue in issues:
            findings.append({"type": "unicode_issue", "detail": issue})

        _write_audit({
            "type": "sanitize", "source": source, "safe": is_safe,
            "score": score, "findings": findings, "prompt_length": len(prompt),
            "timestamp": datetime.datetime.now().isoformat()
        })

        return jsonify({
            "safe": is_safe,
            "score": score,
            "findings": findings,
            "sanitized": cleaned if not is_safe else prompt
        })

    except Exception as e:
        # 安全失效默认：阻断
        return jsonify({"safe": False, "error": str(e), "findings": [{"type": "system_error", "detail": str(e)}]}), 500


@argus_bp.route("/argus/status", methods=["GET"])
def api_argus_status():
    """Argus 服务状态。"""
    return jsonify({
        "service": "Argus Security Gateway",
        "version": "0.2.0",
        "modules": [
            "sanitizer",
            "boundary_marker",
            "tool_validator",
            "permission_resolver",
            "jit_privilege",
            "sandbox_executor",
            "approval_strategy",
            "sandbox_tiers"
        ],
        "status": "active",
        "timestamp": datetime.datetime.now().isoformat()
    })
