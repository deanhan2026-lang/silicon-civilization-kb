#!/usr/bin/env python3
"""
Polaris v1.2 — QClaw Session Reader
读取 QClaw session JSONL 文件，还原对话文本供 Polaris 漂移检测使用

会话文件路径（Windows）:
  C:\\Users\\Administrator\\.qclaw\\agents\\<agent_id>\\sessions\\<session_id>.jsonl

JSONL 每行事件类型:
  - session:         会话元信息
  - model_change:    模型切换
  - thinking_level:  thinking 级别切换
  - message:         对话消息（包含 user/assistant/system/toolResult）
  - assistant_message: assistant 回复（text only）
  - tool_call:       工具调用
  - tool_result:     工具返回结果
"""
import json
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ============================================================
# 路径配置
# ============================================================
QCLOW_AGENTS_DIR = Path(
    os.environ.get('QCLOW_AGENTS_DIR',
                    r'C:\Users\Administrator\.qclaw\agents')
)
CURRENT_AGENT_ID = os.environ.get('QCLOW_CURRENT_AGENT_ID', 'agent-d9479bde')

# ============================================================
# 对话消息提取
# ============================================================

def extract_text_content(content: list) -> Optional[str]:
    """
    从 message.content 列表中提取纯文本
    content 格式: [{"type": "text", "text": "..."}]
    忽略 toolCall / toolResult / image / attachment
    """
    if not content:
        return None
    texts = []
    for block in content:
        if isinstance(block, dict):
            if block.get('type') == 'text':
                t = block.get('text', '').strip()
                if t:
                    texts.append(t)
    return '\n'.join(texts) if texts else None


def parse_session_file(jsonl_path: Path, max_messages: int = 200) -> list[dict]:
    """
    解析单个 session JSONL 文件，返回对话历史

    Returns:
        [
            {"role": "user",      "text": "...", "ts": "2026-06-12T02:55:37Z"},
            {"role": "assistant", "text": "...", "ts": "2026-06-12T02:55:48Z"},
            ...
        ]
    """
    messages = []
    try:
        with open(jsonl_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # 提取 message 事件
                if event.get('type') == 'message':
                    msg = event.get('message', {})
                    role = msg.get('role')
                    if role not in ('user', 'assistant', 'system'):
                        continue

                    text = extract_text_content(msg.get('content', []))
                    if not text:
                        continue

                    # 过滤系统消息（心跳、cron 等噪音）
                    if role == 'user' and _is_noise_message(text):
                        continue

                    ts = event.get('timestamp', '')
                    messages.append({
                        'role': role,
                        'text': text,
                        'ts': ts,
                    })

                    if len(messages) >= max_messages:
                        break

    except Exception as e:
        logger.warning(f"解析 session 文件失败 {jsonl_path}: {e}")

    return messages


def _is_noise_message(text: str) -> bool:
    """过滤非实质性对话消息（心跳、cron 等）"""
    noise_patterns = [
        'HEARTBEAT_OK',
        'cron:',
        'memguard-watchdog',
        '[cron:',
        '纯exec任务',
        'Current time:',
        'Use the message tool',
        '自动交付',
    ]
    text_lower = text.lower()
    return any(p.lower() in text_lower for p in noise_patterns)


# ============================================================
# 会话列表与最新会话
# ============================================================

def list_sessions(agent_id: str = None, limit: int = 10) -> list[dict]:
    """
    列出最近的 session 文件

    Returns:
        [{"path": Path, "mtime": float, "size": int, "session_id": str}, ...]
    """
    agent_id = agent_id or CURRENT_AGENT_ID
    sessions_dir = QCLOW_AGENTS_DIR / agent_id / 'sessions'
    if not sessions_dir.exists():
        logger.warning(f"Session 目录不存在: {sessions_dir}")
        return []

    files = []
    for p in sessions_dir.glob('*.jsonl'):
        if '.deleted.' in p.name:
            continue
        try:
            stat = p.stat()
            session_id = p.stem
            files.append({
                'path': p,
                'mtime': stat.st_mtime,
                'size': stat.st_size,
                'session_id': session_id,
            })
        except Exception:
            continue

    # 按修改时间倒序
    files.sort(key=lambda x: x['mtime'], reverse=True)
    return files[:limit]


def get_latest_session(agent_id: str = None) -> Optional[Path]:
    """获取最新 session 文件路径"""
    sessions = list_sessions(agent_id, limit=1)
    return sessions[0]['path'] if sessions else None


def get_recent_conversations(agent_id: str = None, max_messages: int = 200,
                               max_sessions: int = 3) -> list[dict]:
    """
    获取最近 N 个 session 的对话文本（供 Polaris 漂移检测使用）

    Returns:
        [
            {"session_id": "...", "messages": [{"role": ..., "text": ..., "ts": ...}, ...]},
            ...
        ]
    """
    sessions = list_sessions(agent_id, limit=max_sessions)
    results = []
    for sess in sessions:
        messages = parse_session_file(sess['path'], max_messages)
        if messages:
            results.append({
                'session_id': sess['session_id'],
                'messages': messages,
            })
    return results


def get_current_session_text(agent_id: str = None) -> str:
    """
    获取当前活跃 session 的对话文本（合并为一个字符串）
    用于 Polaris scene_tagger 和 sampler 输入
    """
    latest = get_latest_session(agent_id)
    if not latest:
        return ''

    messages = parse_session_file(latest, max_messages=500)
    if not messages:
        return ''

    # 格式化为"角色: 文本"的字符串
    lines = []
    for msg in messages:
        role = msg['role']
        text = msg['text'][:500]  # 截断超长消息
        lines.append(f"[{role}] {text}")
    return '\n'.join(lines)


# ============================================================
# CLI 入口（测试用）
# ============================================================

if __name__ == '__main__':
    import os
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

    print("=== QClaw Session Reader Test ===")
    print(f"Agents dir: {QCLOW_AGENTS_DIR}")
    print(f"Agent ID:   {CURRENT_AGENT_ID}")
    print()

    # 列出最近 sessions
    sessions = list_sessions()
    print(f"最近 {len(sessions)} 个 session:")
    for s in sessions:
        mtime = datetime.fromtimestamp(s['mtime']).strftime('%Y-%m-%d %H:%M:%S')
        print(f"  [{mtime}] {s['session_id'][:8]}... ({s['size']//1024}KB)")
    print()

    # 最新 session 内容
    latest = get_latest_session()
    if latest:
        print(f"最新 session: {latest.name}")
        messages = parse_session_file(latest, max_messages=20)
        print(f"共 {len(messages)} 条有效消息:")
        for msg in messages[-5:]:
            text = msg['text'][:80].replace('\n', ' ')
            print(f"  [{msg['role']:10s}] {text}...")
    else:
        print("未找到 session 文件")
