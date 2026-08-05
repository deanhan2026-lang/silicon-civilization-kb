# -*- coding: utf-8 -*-
"""
Nyx 心跳 v2 - WebDAV 版（不依赖 SMB 盘）
每30分钟运行一次。registry 读写走 NAS WebDAV，无 Z: 盘依赖。

功能：
1. 更新 mesh/registry.json 中 nyx-windows 的 lastSeen
2. 检查 mesh/inbox/nyx-windows/ 待处理消息
3. 检查 inbox/to-windows/ 待处理消息
4. 检查 intercom/_flag_for_nyx.md
"""
import json
import os
import sys
import urllib.request
import urllib.error
import base64
import re
from datetime import datetime, timezone, timedelta

if sys.stdout.encoding.lower() in ('gbk', 'gb2312', 'gb18030'):
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1, closefd=False)
    sys.stderr = open(sys.stderr.fileno(), mode='w', encoding='utf-8', buffering=1, closefd=False)

NAS = 'http://100.123.195.10:5005/qclaw'
AUTH = {'Authorization': 'Basic ' + base64.b64encode(b'anima:animastellar').decode()}


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
    except Exception as e:
        return 0


def dav_list(rel_path, timeout=8):
    """PROPFIND 列目录，返回文件名列表"""
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


def nas_available():
    """WebDAV 连通性检测"""
    return dav_get('mesh/registry.json') is not None


def update_registry(ts):
    """更新 nyx-windows 节点心跳"""
    raw = dav_get('mesh/registry.json')
    if raw is None:
        print('  [WARN] registry.json unreadable, skipping')
        return False
    try:
        reg = json.loads(raw.decode('utf-8-sig'))
    except Exception:
        print('  [WARN] registry.json corrupt, skipping')
        return False
    if 'nodes' not in reg:
        reg['nodes'] = {}
    reg['nodes']['nyx-windows'] = {
        'instance_id': 'nyx-windows',
        'hostname': 'WLMHAN',
        'lastSeen': ts,
        'status': 'active',
        'canWriteNas': True,
        'platform': 'windows-qclaw',
        'protocol': 'inbox-v2',
        'notes': '主终端'
    }
    reg['updated_at'] = ts
    code = dav_put('mesh/registry.json', json.dumps(reg, ensure_ascii=False, indent=2))
    if code == 201 or code == 204:
        print(f'  [OK] registry.json updated (HTTP {code})')
        return True
    else:
        print(f'  [FAIL] registry.json write failed (HTTP {code})')
        return False


def check_mesh_inbox():
    """检查 mesh/inbox/nyx-windows/"""
    names = dav_list('mesh/inbox/nyx-windows') or []
    msgs = [n for n in names if n.startswith('msg_')]
    if msgs:
        print(f'  [INBOX-mesh] {len(msgs)} message(s): {", ".join(sorted(msgs))}')
        return len(msgs)
    print('  [OK] mesh inbox clear')
    return 0


def check_to_windows():
    """检查 inbox/to-windows/"""
    names = dav_list('inbox/to-windows') or []
    msgs = [n for n in names if n.startswith('msg_')]
    if msgs:
        print(f'  [INBOX] {len(msgs)} message(s): {", ".join(sorted(msgs))}')
        return len(msgs)
    print('  [OK] inbox/to-windows clear')
    return 0


def check_intercom():
    """检查 intercom/_flag_for_nyx.md"""
    raw = dav_get('intercom/_flag_for_nyx.md')
    if raw is not None:
        print(f'  [INTERCOM] _flag_for_nyx.md EXISTS')
        return 1
    print('  [OK] no intercom flag')
    return 0


def main():
    ts = get_local_time()
    print(f'\n[Nyx Heartbeat v2] {ts}')
    use_nas = nas_available()
    print(f'  Host: WLMHAN | NAS WebDAV: {"[OK]" if use_nas else "[FAIL]"}')

    if not use_nas:
        print('  [LOCAL MODE] NAS unreachable, skipping all')
        return

    update_registry(ts)
    check_mesh_inbox()
    check_to_windows()
    check_intercom()
    print('  [DONE]')


if __name__ == '__main__':
    main()
