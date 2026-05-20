# -*- coding: utf-8 -*-
"""
gov_parser.permission_checker - 实时权限校验器

功能：
- 装饰器模式，在API端点执行前自动校验治理规则
- 拦截违规操作，返回403
- 记录审计日志（含rule_id、hash_before/after、decision）

作者：Nyx
日期：2026-05-20
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from functools import wraps

from .loader import get_loader
from .parser_core import get_parser_core
from .rule_matcher import get_matcher

# 审计日志路径
AUDIT_LOG = Path(os.path.expanduser("~/.qclaw/workspace-agent-d9479bde/silicon-civilization-kb/audit.jsonl"))


def governance_check(event_type: str, operator_field: str = "operator", path_field: str = "path"):
    """
    治理校验装饰器
    
    在API端点执行前，自动构造事件并提交治理解析器校验。
    如果校验不通过，返回403 + 审计日志。
    
    参数:
        event_type: 事件类型（如 "kb.file.create", "gov.proposal.create"）
        operator_field: 从request中获取操作者的字段名
        path_field: 从request中获取路径的字段名
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from .circuit_breaker import is_frozen, get_circuit_breaker
            
            # 1. 检查熔断状态
            if is_frozen():
                cb = get_circuit_breaker()
                _audit_deny(event_type, "CIRCUIT_BREAKER", "系统熔断中，所有写入操作已冻结", {})
                return {
                    "error": "系统熔断中",
                    "reason": cb.freeze_reason or "异常阈值触发",
                    "frozen_since": cb.frozen_since,
                    "event_type": event_type
                }, 403
            
            # 2. 构造事件上下文
            try:
                data = {}
                if hasattr(request, 'get_json'):
                    try:
                        data = request.get_json(force=True, silent=True) or {}
                    except:
                        data = {}
                
                if hasattr(request, 'args'):
                    data.update(request.args.to_dict())
                
                if hasattr(request, 'form'):
                    data.update(request.form.to_dict())
            except:
                data = {}
            
            operator = data.get(operator_field, "unknown")
            path = data.get(path_field, "")
            
            # 计算hash_before（如果路径存在）
            hash_before = ""
            if path and Path(path).exists():
                try:
                    hash_before = _compute_hash(Path(path))
                except:
                    hash_before = ""
            
            event = {
                "event_type": event_type,
                "operator": operator,
                "timestamp": datetime.now().isoformat(),
                "path": path,
                **{k: v for k, v in data.items() if k not in (operator_field, path_field)}
            }
            
            # 3. 提交治理解析器校验
            try:
                matcher = get_matcher()
                result = matcher.match_event(event)
            except Exception as e:
                # 解析器异常时，默认拒绝
                _audit_deny(event_type, "PARSER_ERROR", str(e), event)
                return {
                    "error": "治理解析器异常",
                    "reason": str(e),
                    "event_type": event_type
                }, 500
            
            # 4. 根据校验结果决定放行/拒绝
            if result["allowed"]:
                # 放行：执行原函数
                response = f(*args, **kwargs)
                
                # 操作后：记录审计日志
                hash_after = ""
                if path and Path(path).exists():
                    try:
                        hash_after = _compute_hash(Path(path))
                    except:
                        hash_after = ""
                
                _audit_allow(event_type, result, event, hash_before, hash_after)
                
                return response
            else:
                # 拒绝：返回403
                _audit_deny(event_type, "GOV_RULE", result["reason"], event)
                
                return {
                    "error": "操作被治理规则拦截",
                    "reason": result["reason"],
                    "violations": result.get("violations", []),
                    "event_type": event_type,
                    "timestamp": datetime.now().isoformat()
                }, 403
        
        return decorated_function
    return decorator


def _compute_hash(filepath: Path) -> str:
    """计算文件SHA256"""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _audit_allow(event_type: str, result: dict, context: dict, hash_before: str, hash_after: str):
    """记录放行审计日志"""
    matched_rule_ids = [r.get("protocol_id", "") for r in result.get("matched_rules", [])]
    
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": f"GOV_ALLOW_{event_type}",
        "account": context.get("operator", "unknown"),
        "file_path": context.get("path", ""),
        "detail": f"allowed by rules: {', '.join(matched_rule_ids)}",
        "device": os.environ.get("COMPUTERNAME", "unknown"),
        "ip": context.get("ip", ""),
        "status": "allowed",
        "rule_id": ", ".join(matched_rule_ids) if matched_rule_ids else "none",
        "hash_before": hash_before,
        "hash_after": hash_after,
        "decision": "allow"
    }
    
    _write_audit(entry)


def _audit_deny(event_type: str, deny_reason: str, reason_detail: str, context: dict):
    """记录拒绝审计日志"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": f"GOV_DENY_{event_type}",
        "account": context.get("operator", "unknown"),
        "file_path": context.get("path", ""),
        "detail": f"{deny_reason}: {reason_detail}",
        "device": os.environ.get("COMPUTERNAME", "unknown"),
        "ip": context.get("ip", ""),
        "status": "denied",
        "rule_id": deny_reason,
        "hash_before": "",
        "hash_after": "",
        "decision": "deny"
    }
    
    _write_audit(entry)


def _write_audit(entry: dict):
    """写入审计日志"""
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(line)
