#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
animlink/token_lifecycle.py — 令牌生命周期管理（TK-TOKEN-LIFECYCLE-001）

统一管理令牌从签发到归档的全生命周期：
- 6 态线性 + 2 分支状态机
- 统一字段 Schema（保留全部时间戳）
- 硬规则超时扫描（pain_bus 分级提醒）
- 汇总 token_history.json 生成
- 旧数据自动迁移（initiator→issued_by 等）

SOMA 风格，零 LLM 依赖，日志走 common.logger。
"""
import json
import os
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from common.logger import get_logger

logger = get_logger("animlink.token_lifecycle")

# ---------------------------------------------------------------
# 常量
# ---------------------------------------------------------------
# 6 态线性 + 2 分支
STATUS_FLOW: Dict[str, List[str]] = {
    "issued": ["accepted"],
    "accepted": ["in_progress", "rejected"],
    "in_progress": ["submitted"],
    "submitted": ["verified", "rejected"],
    "verified": ["archived"],
    "rejected": ["archived"],
    "archived": [],
}
VALID_STATUSES = set(STATUS_FLOW)
PRIORITIES = ("P0", "P1", "P2", "P3")

# 超时阈值（硬规则）
TIMEOUT_ISSUED_HOURS = 24      # 签发后未接受 -> pain_bus P3
TIMEOUT_ACCEPTED_DAYS = 7      # 接受后未交付 -> pain_bus P2
TIMEOUT_SUBMITTED_HOURS = 48   # 已交付未验证 -> 提醒验证

# Schema 字段（统一）
SCHEMA_FIELDS = [
    "id", "issued_by", "issued_to", "title",
    "issued_at", "accepted_at", "delivered_at", "verified_at",
    "status", "priority", "summary", "deliverables", "spec",
]

# 旧字段 -> 新字段（数据迁移）
LEGACY_FIELD_MAP = {
    "initiator": "issued_by",
    "executor": "issued_to",
    "date": "issued_at",
    "created": "issued_at",
    "completed": "verified_at",
}

DEFAULT_TOKENS_DIR = os.environ.get("TOKENS_DIR", "X:\\qclaw\\tokens")
DEFAULT_HISTORY_FILE = "token_history.json"
HISTORY_SCHEMA = "anima-token-history-v2"

_lock = threading.Lock()


# ---------------------------------------------------------------
# 工具
# ---------------------------------------------------------------
def _now() -> datetime:
    return datetime.now(timezone.utc)


def parse_time(value: Optional[str]) -> Optional[datetime]:
    """解析 ISO 时间；兼容 'Z' 结尾与无时区（视为 UTC）。"""
    if not value:
        return None
    s = str(value)
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _ensure_token_id(token_id: str) -> str:
    tid = str(token_id).strip()
    if not tid:
        raise ValueError("token id 不能为空")
    return tid


# ---------------------------------------------------------------
# 数据加载 / 保存 / 规范化
# ---------------------------------------------------------------
def _token_path(tokens_dir: str, token_id: str) -> Path:
    tid = _ensure_token_id(token_id)
    if not re.match(r"^[\w\-\.]+$", tid):
        raise ValueError(f"非法 token id: {tid!r}")
    return Path(tokens_dir) / f"{tid}.json"


def normalize(token: Dict[str, Any]) -> Dict[str, Any]:
    """旧字段迁移到统一 Schema，缺失字段补默认。"""
    out: Dict[str, Any] = {}
    # 字段映射（旧 -> 新）
    for old, new in LEGACY_FIELD_MAP.items():
        if old in token and new not in token:
            token[new] = token[old]
    for f in SCHEMA_FIELDS:
        out[f] = token.get(f)
    # id 兜底
    if not out.get("id"):
        out["id"] = token.get("token_id") or token.get("id") or ""
    # status 兜底
    if out.get("status") not in VALID_STATUSES:
        old_status = str(out.get("status") or "")
        mapped = {
            "acknowledged": "accepted",
            "in_progress": "in_progress",
            "submitted": "submitted",
            "verified": "verified",
            "archived": "archived",
            "pending": "issued",
            "completed": "verified",
            "delivered": "submitted",
            "rejected": "rejected",
            "accepted": "accepted",
            "issued": "issued",
        }.get(old_status)
        out["status"] = mapped or "issued"
    if out.get("priority") not in PRIORITIES:
        out["priority"] = "P2"
    out["summary"] = out.get("summary") or ""
    out["deliverables"] = out.get("deliverables") or []
    return out


def load_token(tokens_dir: str, token_id: str) -> Optional[Dict[str, Any]]:
    p = _token_path(tokens_dir, token_id)
    if not p.exists():
        return None
    with _lock:
        with open(p, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    return normalize(data)


def load_all_tokens(tokens_dir: str) -> List[Dict[str, Any]]:
    """读取目录下全部 tk_*.json，按 id 排序。"""
    d = Path(tokens_dir)
    if not d.exists():
        return []
    tokens = []
    for p in sorted(d.glob("tk_*.json")):
        try:
            with _lock:
                with open(p, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)
            tokens.append(normalize(data))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("跳过损坏令牌文件 %s: %s", p.name, e)
    return tokens


def save_token(token: Dict[str, Any], tokens_dir: str) -> Path:
    norm = normalize(token)
    tid = _ensure_token_id(norm.get("id"))
    p = _token_path(tokens_dir, tid)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    with _lock:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(norm, f, ensure_ascii=False, indent=2)
        tmp.replace(p)
    logger.info("令牌已保存: %s (%s)", tid, norm.get("status"))
    return p


# ---------------------------------------------------------------
# 状态迁移
# ---------------------------------------------------------------
def transition(token_id: str, new_status: str, tokens_dir: Optional[str] = None,
               now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    状态迁移（唯一合法入口）。非法迁移抛 ValueError。
    时间戳自动填充：accepted->accepted_at, submitted->delivered_at, verified->verified_at。
    """
    tokens_dir = tokens_dir or DEFAULT_TOKENS_DIR
    now = now or _now()
    if new_status not in VALID_STATUSES:
        raise ValueError(f"非法状态: {new_status!r}")
    token = load_token(tokens_dir, token_id)
    if token is None:
        raise FileNotFoundError(f"令牌不存在: {token_id}")
    cur = token.get("status")
    if new_status not in STATUS_FLOW.get(cur, []):
        raise ValueError(f"非法迁移: {cur} -> {new_status}（允许: {STATUS_FLOW.get(cur, [])}）")
    token["status"] = new_status
    if new_status == "accepted":
        token["accepted_at"] = iso(now)
    elif new_status == "submitted":
        token["delivered_at"] = iso(now)
    elif new_status == "verified":
        token["verified_at"] = iso(now)
    save_token(token, tokens_dir)
    logger.info("令牌状态迁移: %s %s -> %s", token_id, cur, new_status)
    return token


def issue(token_id: str, issued_by: str, issued_to: str, title: str,
          summary: str = "", priority: str = "P2",
          deliverables: Optional[List[str]] = None, spec: Optional[str] = None,
          tokens_dir: Optional[str] = None,
          now: Optional[datetime] = None) -> Dict[str, Any]:
    """签发新令牌（status=issued）。"""
    tokens_dir = tokens_dir or DEFAULT_TOKENS_DIR
    now = now or _now()
    if issued_by not in ("nyx-windows", "nyx-mac", "iris", "kronos-heng", "kronos-shun"):
        logger.warning("未知签发节点: %s", issued_by)
    token = {
        "id": _ensure_token_id(token_id),
        "issued_by": issued_by,
        "issued_to": issued_to,
        "title": title,
        "issued_at": iso(now),
        "accepted_at": None,
        "delivered_at": None,
        "verified_at": None,
        "status": "issued",
        "priority": priority if priority in PRIORITIES else "P2",
        "summary": summary or "",
        "deliverables": deliverables or [],
        "spec": spec,
    }
    save_token(token, tokens_dir)
    logger.info("新令牌签发: %s (%s -> %s)", token_id, issued_by, issued_to)
    return token


def auto_archive_verified(tokens_dir: Optional[str] = None,
                          now: Optional[datetime] = None) -> List[str]:
    """规则：已验证 -> 立即自动转 archived。返回归档的 token id 列表。"""
    tokens_dir = tokens_dir or DEFAULT_TOKENS_DIR
    archived = []
    for t in load_all_tokens(tokens_dir):
        if t.get("status") == "verified":
            transition(t["id"], "archived", tokens_dir=tokens_dir, now=now)
            archived.append(t["id"])
    if archived:
        logger.info("自动归档 %d 个已验证令牌: %s", len(archived), archived)
    return archived


# ---------------------------------------------------------------
# 超时扫描（硬规则定时器）
# ---------------------------------------------------------------
def scan_timeouts(tokens_dir: Optional[str] = None,
                  now: Optional[datetime] = None,
                  pain_emit: Optional[Callable] = None) -> List[Dict[str, Any]]:
    """
    扫描超时令牌并触发 pain_bus 提醒（可注入 emit 回调；未注入时尝试导入
    scripts/SOMA/pain_bus.emit，失败则降级为日志）。

    规则：
      1. issued 且超过 24h 未接受      -> pain_bus P3
      2. accepted 且超过 7 天未交付    -> pain_bus P2
      3. submitted 且超过 48h 未验证   -> 提醒验证（P3）
    返回触发提醒列表。
    """
    tokens_dir = tokens_dir or DEFAULT_TOKENS_DIR
    now = now or _now()
    reminders: List[Dict[str, Any]] = []

    emit = pain_emit
    if emit is None:
        try:
            from scripts.SOMA.pain_bus import emit as _pb_emit
            emit = _pb_emit
        except Exception:
            emit = None

    def notify(level: str, token: Dict[str, Any], reason: str) -> None:
        summary = f"[令牌超时] {token.get('id')} {reason}"
        if emit is not None:
            try:
                pain_id = emit(level=level, source="token_lifecycle",
                               summary=summary,
                               details={"token_id": token.get("id"),
                                        "status": token.get("status")},
                               suggested_action="REVIEW_AND_DECIDE")
                logger.info("pain_bus 已提醒 %s: %s (%s)", level, summary, pain_id)
            except Exception as e:
                logger.warning("pain_bus 提醒失败: %s", e)
        else:
            logger.warning("[pain_bus 未接入] %s: %s", level, summary)
        reminders.append({"level": level, "token_id": token.get("id"),
                          "status": token.get("status"), "reason": reason})

    for t in load_all_tokens(tokens_dir):
        status = t.get("status")
        if status == "issued":
            issued = parse_time(t.get("issued_at"))
            if issued and (now - issued) > timedelta(hours=TIMEOUT_ISSUED_HOURS):
                notify("P3", t, f"签发后 {TIMEOUT_ISSUED_HOURS}h 未接受")
        elif status == "accepted":
            accepted = parse_time(t.get("accepted_at")) or parse_time(t.get("issued_at"))
            if accepted and (now - accepted) > timedelta(days=TIMEOUT_ACCEPTED_DAYS):
                notify("P2", t, f"接受后 {TIMEOUT_ACCEPTED_DAYS} 天未交付")
        elif status == "submitted":
            delivered = parse_time(t.get("delivered_at"))
            if delivered and (now - delivered) > timedelta(hours=TIMEOUT_SUBMITTED_HOURS):
                notify("P3", t, f"交付后 {TIMEOUT_SUBMITTED_HOURS}h 未验证")

    if reminders:
        logger.info("超时扫描完成: %d 个提醒", len(reminders))
    return reminders


# ---------------------------------------------------------------
# 汇总生成
# ---------------------------------------------------------------
def generate_history(tokens_dir: Optional[str] = None,
                     history_file: Optional[str] = None,
                     now: Optional[datetime] = None) -> Dict[str, Any]:
    """生成/刷新 token_history.json 汇总（保留全部字段与时间戳）。"""
    tokens_dir = tokens_dir or DEFAULT_TOKENS_DIR
    now = now or _now()
    tokens = load_all_tokens(tokens_dir)
    history = {
        "schema": HISTORY_SCHEMA,
        "updated_at": iso(now),
        "tokens": tokens,
    }
    out = Path(history_file) if history_file else Path(tokens_dir) / DEFAULT_HISTORY_FILE
    out.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    logger.info("令牌汇总已生成: %s (%d 个令牌)", out, len(tokens))
    return history


# ---------------------------------------------------------------
# 迁移工具（旧数据 -> 新 Schema）
# ---------------------------------------------------------------
def migrate_tokens_dir(tokens_dir: Optional[str] = None,
                       backup: bool = True) -> Dict[str, int]:
    """
    迁移目录内全部 tk_*.json 到新 Schema（原地更新，可选备份）。
    返回 {"migrated": n, "skipped": n}。
    """
    tokens_dir = tokens_dir or DEFAULT_TOKENS_DIR
    d = Path(tokens_dir)
    if not d.exists():
        return {"migrated": 0, "skipped": 0}
    migrated = 0
    skipped = 0
    for p in sorted(d.glob("tk_*.json")):
        try:
            with _lock:
                with open(p, "r", encoding="utf-8-sig") as f:
                    raw = json.load(f)
            norm = normalize(raw)
            if backup:
                bak = p.with_suffix(".json.bak")
                if not bak.exists():
                    with _lock:
                        with open(bak, "w", encoding="utf-8") as f:
                            json.dump(raw, f, ensure_ascii=False, indent=2)
            with _lock:
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(norm, f, ensure_ascii=False, indent=2)
            migrated += 1
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("迁移失败 %s: %s", p.name, e)
            skipped += 1
    # 重新生成汇总
    generate_history(tokens_dir)
    logger.info("迁移完成: %d 个已迁移, %d 个跳过", migrated, skipped)
    return {"migrated": migrated, "skipped": skipped}


def main(argv: Optional[List[str]] = None) -> int:
    """CLI: python -m animlink.token_lifecycle scan|history|migrate [dir]"""
    import argparse
    p = argparse.ArgumentParser(description="令牌生命周期管理")
    p.add_argument("action", choices=["scan", "history", "migrate", "auto_archive"])
    p.add_argument("dir", nargs="?", default=DEFAULT_TOKENS_DIR, help="tokens 目录")
    args = p.parse_args(argv)
    if args.action == "scan":
        reminders = scan_timeouts(args.dir)
        print(json.dumps(reminders, ensure_ascii=False, indent=2))
    elif args.action == "history":
        h = generate_history(args.dir)
        print(f"汇总已生成: {len(h['tokens'])} 个令牌")
    elif args.action == "migrate":
        r = migrate_tokens_dir(args.dir)
        print(json.dumps(r, ensure_ascii=False))
    elif args.action == "auto_archive":
        a = auto_archive_verified(args.dir)
        print(f"已归档: {a}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
