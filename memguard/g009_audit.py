#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
memguard/audit.py — MemGuard 审计日志（P1-C 集成）

- 通用审计日志（JSONL）：任何重要事件可记录
- 集成仲裁：仲裁事件自动写入审计日志（审计流水与仲裁记录一致）
"""
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from common.logger import get_logger
from memguard import arbitration as _arb

logger = get_logger("memguard.audit")

DEFAULT_AUDIT_FILE = os.environ.get(
    "G009_AUDIT_FILE",
    str(Path("memguard") / "audit_log.jsonl"),
)

_lock = threading.Lock()


def log_event(
    event: str,
    actor: str,
    detail: Optional[Dict[str, Any]] = None,
    audit_file: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """写入一条审计事件。"""
    record = {
        "event": event,
        "actor": actor,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "detail": detail or {},
    }
    path = Path(audit_file or DEFAULT_AUDIT_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    logger.info("审计事件: %s by %s", event, actor)
    return record


def record_arbitration_event(arb_record: Dict[str, Any], audit_file: Optional[str] = None) -> Dict[str, Any]:
    """
    仲裁事件集成：将一条仲裁记录（arbitration.record_arbitration 的返回值）
    同时写入审计日志。
    """
    return log_event(
        event="g009_arbitration",
        actor=arb_record.get("node_id", "unknown"),
        detail=arb_record,
        audit_file=audit_file,
        timestamp=arb_record.get("timestamp"),
    )


def load_audit(audit_file: Optional[str] = None) -> list:
    path = Path(audit_file or DEFAULT_AUDIT_FILE)
    if not path.exists():
        return []
    out = []
    with _lock:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return out
