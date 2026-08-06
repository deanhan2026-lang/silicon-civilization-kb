#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
meshidentity/history.py — 节点历史行为轨迹存储（G009 P1-D）

存储节点行为事件（JSONL）：
  - node_id: 节点 DID
  - timestamp: 行为时间戳 (ISO-8601)
  - behavior_type: normal | suspicious | violation
  - goal: 关联目标（可选）
"""
import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from common.logger import get_logger

logger = get_logger("meshidentity.history")

BEHAVIOR_TYPES = ("normal", "suspicious", "violation")

DEFAULT_HISTORY_FILE = os.environ.get(
    "MESH_HISTORY_FILE",
    str(Path("meshidentity") / "behavior_history.jsonl"),
)

_lock = threading.Lock()


def record_behavior(
    node_id: str,
    behavior_type: str,
    goal: Optional[str] = None,
    timestamp: Optional[str] = None,
    history_file: Optional[str] = None,
) -> Dict[str, Any]:
    """记录一条节点行为。校验失败抛 ValueError。"""
    if not node_id or not isinstance(node_id, str):
        raise ValueError("node_id 不能为空")
    if behavior_type not in BEHAVIOR_TYPES:
        raise ValueError(f"behavior_type 必须为 {BEHAVIOR_TYPES} 之一")
    event = {
        "node_id": node_id,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "behavior_type": behavior_type,
        "goal": goal,
    }
    path = Path(history_file or DEFAULT_HISTORY_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    logger.info("行为已记录: node=%s type=%s", node_id, behavior_type)
    return event


def _parse_ts(ts: str) -> datetime:
    # 兼容带/不带时区的 ISO-8601
    s = ts
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def load_history(
    node_id: Optional[str] = None,
    since: Optional[datetime] = None,
    history_file: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """读取行为记录；可按节点和时间过滤。返回升序列表。"""
    path = Path(history_file or DEFAULT_HISTORY_FILE)
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    with _lock:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if node_id and ev.get("node_id") != node_id:
                    continue
                if since is not None:
                    try:
                        if _parse_ts(ev.get("timestamp", "")) < since:
                            continue
                    except (ValueError, TypeError):
                        continue
                out.append(ev)
    out.sort(key=lambda e: e.get("timestamp", ""))
    return out
