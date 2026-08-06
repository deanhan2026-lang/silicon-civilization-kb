# -*- coding: utf-8 -*-
"""
ANIMA SOMA · 信箱监控子系统 (mailbox_watch.py)
==============================================
零 LLM 硬规则：周期性扫描 mesh/inbox 各信箱的未处理消息标记，
发现新消息 → 发 P2 疼痛信号（唤醒 LLM 层处理），避免重复通知。

监控对象（发给 Nyx 的消息）：
  - mesh/inbox/nyx-windows/   （新 mesh 协议，.flag / .done 标记）
  - qclaw/inbox/nyx-windows/incoming/  （四节点新架构，_flag.md）

判定规则（硬规则）：
  - 有 .flag / .flag.md 后缀文件 = 有未处理消息
  - 有 .done 后缀 = 已处理归档（忽略）
  - 用 state 文件记录已通知过的 flag，只对新出现的发信号
  - 同一条消息重复扫描不重复发痛（幂等）

用法：
  python mailbox_watch.py scan    # 单次扫描（供调度器调用）
  python mailbox_watch.py status  # 查看当前待处理消息
"""
import os
import sys
import json
import io
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

WORKSPACE = Path(__file__).parent.parent.parent.resolve()
SOMA_DIR  = Path(__file__).parent
STATE_FILE = SOMA_DIR / "mailbox_watch_state.json"

# 监控的收件箱目录（发给 Nyx 的）
INBOXES = [
    WORKSPACE / ".." / "workspace-agent-d9479bde" / "inbox" / "nyx-windows" / "incoming",  # 本地占位（实际在 NAS）
]

# NAS 上的真实 inbox（WebDAV/SMB UNC 路径）
NAS_INBOXES = [
    r"\\100.123.195.10\SOFTWARE\qclaw\mesh\shared\nyx-windows\inbox",  # v2.0 新规范（主）
    r"\\100.123.195.10\SOFTWARE\qclaw\mesh\inbox\nyx-windows",      # v1.0 旧路径（过渡期兼容）
    r"\\100.123.195.10\SOFTWARE\qclaw\inbox\nyx-windows\incoming",  # 四节点新架构（遗留）
]

# 疼痛信号级别
PAIN_LEVEL = "P2"  # 有消息待处理（需 LLM 处理，但不紧急）


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+08:00")


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"notified": [], "last_scan": None}


def save_state(state: dict):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def scan_inbox(directory: Path) -> list:
    """扫描单个 inbox，返回未处理消息标记列表 [(filename, fullpath)]"""
    pending = []
    try:
        if not directory.exists():
            return []
        for f in directory.iterdir():
            name = f.name
            # flag 标记：.flag / _flag.md / .flag.md
            is_flag = name.endswith(".flag") or name == "_flag.md" or name.endswith(".flag.md")
            # done 标记：已处理
            is_done = name.endswith(".done")
            if is_flag and not is_done:
                pending.append((name, str(f)))
    except Exception:
        pass
    return pending


def scan_all() -> list:
    """扫描所有 inbox，返回 [(inbox_name, filename, fullpath)]"""
    results = []
    for path in NAS_INBOXES:
        p = Path(path)
        inbox_name = p.parent.name + "/" + p.name
        for fname, fpath in scan_inbox(p):
            results.append((inbox_name, fname, fpath))
    return results


def emit_pain(message: str, details: dict) -> str:
    """发疼痛信号（复用 pain_bus）"""
    sys.path.insert(0, str(SOMA_DIR))
    try:
        import pain_bus
        return pain_bus.emit(PAIN_LEVEL, "mailbox_watch", message, details=details)
    except Exception as e:
        # pain_bus 不可用时降级为日志
        log_dir = SOMA_DIR / "logs"
        log_dir.mkdir(exist_ok=True)
        with open(log_dir / "mailbox_watch.log", "a", encoding="utf-8") as f:
            f.write(f"[{utcnow()}] {message} (pain_bus unavailable: {e})\n")
        return "log-only"


def run() -> dict:
    """单次扫描：检测新消息 → 发疼痛信号"""
    state = load_state()
    notified = set(state.get("notified", []))
    results = scan_all()

    new_msgs = []
    for inbox_name, fname, fpath in results:
        key = f"{inbox_name}|{fname}"
        if key not in notified:
            new_msgs.append({"inbox": inbox_name, "file": fname})
            notified.add(key)

    # 有新增 → 发疼痛信号
    if new_msgs:
        summary = f"信箱新消息 {len(new_msgs)} 条待处理"
        emit_pain(summary, {"messages": new_msgs})
        state["notified"] = sorted(notified)
        state["last_scan"] = utcnow()
        state["last_new"] = new_msgs
        save_state(state)
        return {"status": "new", "count": len(new_msgs), "messages": new_msgs}
    else:
        state["last_scan"] = utcnow()
        save_state(state)
        return {"status": "clean", "count": 0}


def status() -> dict:
    """查看当前待处理消息"""
    results = scan_all()
    state = load_state()
    return {
        "pending": results,
        "notified_count": len(state.get("notified", [])),
        "last_scan": state.get("last_scan"),
    }


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scan"
    if cmd == "scan":
        print(json.dumps(run(), ensure_ascii=False))
    elif cmd == "status":
        print(json.dumps(status(), ensure_ascii=False))
    else:
        print("Usage: python mailbox_watch.py [scan|status]")
