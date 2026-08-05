# -*- coding: utf-8 -*-
"""
AnimaLink 经纪人路由器 v1.0
- 扫描 NAS mesh/inbox/{node}/ 中的新消息
- 按目标路由:
  * kronos-heng  → 保持 inbox（恒自行轮询）+ 写 flag
  * kronos-shun  → 通过 CDP 推送到豆包
  * iris         → 保持 inbox + flag
  * nyx-windows  → 标记为待处理（Nyx 主会话读取）
- 记录路由日志到 NAS mesh/outbox/
"""
import json
import os
import sys
import io
import time
import urllib.request
import urllib.error
import base64
import re
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

NAS = 'http://100.123.195.10:5005/qclaw'
AUTH = {'Authorization': 'Basic ' + base64.b64encode(b'anima:animastellar').decode()}

# 本脚本所在目录（用于调用 shun_bridge）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def get_local_time():
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%S+08:00")


def dav_get(rel_path, timeout=8):
    url = NAS + '/' + rel_path.lstrip('/')
    try:
        req = urllib.request.Request(url, headers=AUTH)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception:
        return None


def dav_put(rel_path, content, timeout=8):
    url = NAS + '/' + rel_path.lstrip('/')
    try:
        req = urllib.request.Request(url, data=content.encode('utf-8'), method='PUT', headers=AUTH)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except Exception:
        return 0


def dav_list(rel_path, timeout=8):
    url = NAS + '/' + rel_path.lstrip('/') + '/'
    try:
        req = urllib.request.Request(url, method='PROPFIND', headers=AUTH)
        req.add_header('Depth', '1')
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode('utf-8', errors='ignore')
        hrefs = re.findall(r'<[^>]+:href>([^<]+)</[^>]+:href>', body)
        names = []
        for h in hrefs:
            n = h.rstrip('/').split('/')[-1]
            if n and n not in ('.', '..'):
                names.append(n)
        return names
    except Exception:
        return None


def read_msg(rel_path):
    raw = dav_get(rel_path)
    if raw is None:
        return None
    return raw.decode('utf-8', errors='replace')


def is_processed(node, fname):
    """检查消息是否已处理（存在 .done 标记）"""
    done = dav_get(f'mesh/inbox/{node}/{fname}.done')
    return done is not None


def mark_processed(node, fname):
    """标记消息已处理"""
    dav_put(f'mesh/inbox/{node}/{fname}.done', get_local_time())


def route_to_shun(content):
    """通过 CDP 推送到豆包"""
    try:
        import subprocess
        # 提取消息正文（去掉 frontmatter）
        body = content
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                body = parts[2].strip()
        # 截断防止过长
        body = body[:500]
        r = subprocess.run(
            [sys.executable, os.path.join(SCRIPT_DIR, 'shun_bridge.py'), 'send', body],
            capture_output=True, text=True, timeout=60, encoding='utf-8', errors='replace'
        )
        out = (r.stdout or '') + (r.stderr or '')
        if '已发送' in out or '✅' in out:
            return True, out[-200:]
        return False, out[-200:]
    except Exception as e:
        return False, str(e)


def route_message(node, fname, content):
    """路由单条消息"""
    # 解析目标（从文件名或内容 frontmatter）
    target = None
    m = re.search(r'^to:\s*(.+)$', content, re.MULTILINE)
    if m:
        target = m.group(1).strip().lower()
    if not target:
        # 从 inbox 目录名推断（msg_发件人_... 的目录本身就是收件人）
        target = node

    ts = get_local_time()
    log_entry = {
        'ts': ts,
        'from_inbox': node,
        'file': fname,
        'target': target,
        'action': 'pending',
        'detail': ''
    }

    # 路由决策
    if target in ('kronos-heng', 'heng'):
        log_entry['action'] = 'keep-inbox'
        log_entry['detail'] = '恒自行轮询 mesh/inbox/kronos-heng/'
        # 写 flag 提醒恒
        dav_put(f'mesh/inbox/kronos-heng/_flag.md', f'新消息: {fname} @ {ts}')
    elif target in ('kronos-shun', 'shun'):
        ok, detail = route_to_shun(content)
        log_entry['action'] = 'cdp-push' if ok else 'cdp-fail'
        log_entry['detail'] = detail
    elif target in ('iris',):
        log_entry['action'] = 'keep-inbox'
        log_entry['detail'] = 'Iris 自行轮询 mesh/inbox/iris/'
        dav_put(f'mesh/inbox/iris/_flag.md', f'新消息: {fname} @ {ts}')
    else:
        log_entry['action'] = 'unknown-target'
        log_entry['detail'] = f'目标 {target} 无路由规则'

    # 记录路由日志
    outbox_name = f'route_{node}_{re.sub(r"[^0-9]", "", ts)}.json'
    dav_put(f'mesh/outbox/{outbox_name}', json.dumps(log_entry, ensure_ascii=False, indent=2))

    return log_entry


def main():
    print(f'\n[AnimaLink Broker] {get_local_time()}')
    nodes = ['nyx-windows', 'kronos-heng', 'kronos-shun', 'iris', 'mnea']
    total_routed = 0

    for node in nodes:
        try:
            names = dav_list(f'mesh/inbox/{node}') or []
        except Exception:
            continue
        msgs = [n for n in names if n.startswith('msg_') and n.endswith('.md')]
        if not msgs:
            continue
        for fname in sorted(msgs):
            if is_processed(node, fname):
                continue
            content = read_msg(f'mesh/inbox/{node}/{fname}')
            if content is None:
                continue
            log = route_message(node, fname, content)
            if log['action'] != 'unknown-target':
                mark_processed(node, fname)
            print(f"  [{node}] {fname} -> {log['action']} ({log['detail'][:60]})")
            total_routed += 1

    if total_routed == 0:
        print('  无待路由消息')
    else:
        print(f'  共路由 {total_routed} 条消息')


if __name__ == '__main__':
    main()
