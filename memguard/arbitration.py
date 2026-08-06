#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
memguard/arbitration.py — G009 仲裁记录模块（P1-C）

实现 G009 碳基暂停键治理协议的仲裁事件记录：
- 事件结构遵循任务定义的 JSON Schema
- 硬规则校验（不依赖外部 LLM）
- 记录写入 JSONL 日志文件（可审计、可追溯）

Schema:
{
  "event_type": "g009_arbitration",
  "timestamp": "ISO-8601",
  "node_id": "节点ID",
  "constraint_level": "L1/L2/L3",
  "deviation_score": 0.0-1.0,
  "history_consistency": 0.0-1.0,
  "response_level": "continue|pause|redefine",
  "decision_rationale": "裁决理由",
  "approver_did": "批准者DID（如果有）"
}
"""
import json
import os
import re
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from common.logger import get_logger

logger = get_logger("memguard.arbitration")

# ---------------------------------------------------------------
# 常量与约束
# ---------------------------------------------------------------
EVENT_TYPE = "g009_arbitration"
CONSTRAINT_LEVELS = ("L1", "L2", "L3")
RESPONSE_LEVELS = ("continue", "pause", "redefine")
_DID_RE = re.compile(r"^did:[a-z0-9]+:[A-Za-z0-9._:%-]+$")

# 分数上下界（含）
SCORE_MIN, SCORE_MAX = 0.0, 1.0

# 默认记录文件
DEFAULT_RECORD_FILE = os.environ.get(
    "G009_ARBITRATION_FILE",
    str(Path("memguard") / "arbitration_records.jsonl"),
)

_lock = threading.Lock()


# ---------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------
@dataclass
class ArbitrationRecord:
    """一条 G009 仲裁记录。"""

    node_id: str
    constraint_level: str
    deviation_score: float
    history_consistency: float
    response_level: str
    decision_rationale: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event_type: str = EVENT_TYPE
    approver_did: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # 保持 Schema 字段顺序友好
        return {
            "event_type": d["event_type"],
            "timestamp": d["timestamp"],
            "node_id": d["node_id"],
            "constraint_level": d["constraint_level"],
            "deviation_score": d["deviation_score"],
            "history_consistency": d["history_consistency"],
            "response_level": d["response_level"],
            "decision_rationale": d["decision_rationale"],
            "approver_did": d["approver_did"],
        }


# ---------------------------------------------------------------
# 硬规则校验
# ---------------------------------------------------------------
def validate_record(rec: ArbitrationRecord) -> List[str]:
    """返回校验错误列表；空列表 = 合法。纯硬规则，不依赖 LLM。"""
    errors: List[str] = []

    if not rec.node_id or not isinstance(rec.node_id, str):
        errors.append("node_id 不能为空")
    if rec.constraint_level not in CONSTRAINT_LEVELS:
        errors.append(f"constraint_level 必须为 {CONSTRAINT_LEVELS} 之一")
    if not (SCORE_MIN <= float(rec.deviation_score) <= SCORE_MAX):
        errors.append(f"deviation_score 必须在 [{SCORE_MIN}, {SCORE_MAX}] 内")
    if not (SCORE_MIN <= float(rec.history_consistency) <= SCORE_MAX):
        errors.append(f"history_consistency 必须在 [{SCORE_MIN}, {SCORE_MAX}] 内")
    if rec.response_level not in RESPONSE_LEVELS:
        errors.append(f"response_level 必须为 {RESPONSE_LEVELS} 之一")
    if not rec.decision_rationale or not isinstance(rec.decision_rationale, str):
        errors.append("decision_rationale 不能为空")
    if rec.approver_did and not _DID_RE.match(rec.approver_did):
        errors.append(f"approver_did 格式非法: {rec.approver_did!r}")

    # 硬规则：偏离高 + 历史一致性低 → 不允许 continue
    if (
        rec.deviation_score >= 0.8
        and rec.history_consistency <= 0.3
        and rec.response_level == "continue"
    ):
        errors.append("硬规则: deviation_score>=0.8 且 history_consistency<=0.3 时 response_level 不得为 continue")
    return errors


# ---------------------------------------------------------------
# 存储
# ---------------------------------------------------------------
def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def record_arbitration(
    node_id: str,
    constraint_level: str,
    deviation_score: float,
    history_consistency: float,
    response_level: str,
    decision_rationale: str,
    approver_did: Optional[str] = None,
    timestamp: Optional[str] = None,
    record_file: Optional[str] = None,
) -> Dict[str, Any]:
    """
    创建并持久化一条仲裁记录。返回记录 dict；校验失败抛 ValueError。
    """
    rec = ArbitrationRecord(
        node_id=node_id,
        constraint_level=constraint_level,
        deviation_score=float(deviation_score),
        history_consistency=float(history_consistency),
        response_level=response_level,
        decision_rationale=decision_rationale,
        approver_did=approver_did,
        timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
    )
    errors = validate_record(rec)
    if errors:
        raise ValueError("; ".join(errors))

    path = Path(record_file or DEFAULT_RECORD_FILE)
    _ensure_dir(path)
    line = json.dumps(rec.to_dict(), ensure_ascii=False)
    with _lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    logger.info("仲裁记录已写入 %s (node=%s, level=%s, response=%s)",
                path, rec.node_id, rec.constraint_level, rec.response_level)
    return rec.to_dict()


def load_records(record_file: Optional[str] = None) -> List[Dict[str, Any]]:
    """读取全部仲裁记录（JSONL），按时间升序。"""
    path = Path(record_file or DEFAULT_RECORD_FILE)
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    with _lock:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    logger.warning("跳过损坏记录行: %s", e)
    return records


def count_records(record_file: Optional[str] = None) -> int:
    return len(load_records(record_file))
