#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
meshidentity/consistency.py — 节点行为一致性评分（G009 P1-D）

get_consistency_score(node_id, time_window) -> float (0.0-1.0)

评分语义（任务定义）：
  - 1.0     完全一致，无异常
  - 0.5-0.9 偶尔偏离但可接受
  - 0.0-0.5 频繁偏离或违规

算法（硬规则、可解释、无 LLM 依赖）：
  1. 基础分 1.0
  2. violation 事件扣 0.3，suspicious 事件扣 0.1（normal 不扣）
  3. 时间衰减：越早的事件扣分权重越低（线性衰减到 0）
  4. 结果 clamp 到 [0,1]
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from common.logger import get_logger
from meshidentity import history as _history

logger = get_logger("meshidentity.consistency")

# 扣分权重（硬规则）
_WEIGHTS = {
    "normal": 0.0,
    "suspicious": 0.1,
    "violation": 0.3,
}

# 结果解释档位
def interpret(score: float) -> str:
    if score >= 1.0:
        return "consistent"          # 完全一致
    if score >= 0.9:
        return "minor_deviation"     # 偶尔偏离但可接受
    if score >= 0.5:
        return "acceptable_deviation"
    return "frequent_deviation"      # 频繁偏离或违规


def get_consistency_score(
    node_id: str,
    time_window: timedelta = timedelta(days=7),
    history_file: Optional[str] = None,
    now: Optional[datetime] = None,
) -> float:
    """
    返回节点在时间窗口内的行为一致性评分（0.0-1.0）。
    - 无任何记录 → 1.0（无异常证据）
    - 时间窗口外的记录不参与计算
    """
    now = now or datetime.now(timezone.utc)
    since = now - time_window

    events = _history.load_history(node_id=node_id, since=since, history_file=history_file)
    if not events:
        return 1.0

    total_days = max(time_window.total_seconds() / 86400.0, 1e-9)
    score = 1.0
    for ev in events:
        btype = ev.get("behavior_type", "normal")
        weight = _WEIGHTS.get(btype, 0.0)
        if weight <= 0:
            continue
        try:
            ts = _history._parse_ts(ev.get("timestamp", ""))
        except (ValueError, TypeError):
            continue
        age_days = max((now - ts).total_seconds() / 86400.0, 0.0)
        decay = max(0.0, 1.0 - age_days / total_days)  # 越早权重越低
        score -= weight * decay

    score = max(0.0, min(1.0, score))
    logger.info("一致性评分 node=%s window=%s -> %.2f (%s)",
                node_id, time_window, score, interpret(score))
    return round(score, 4)
