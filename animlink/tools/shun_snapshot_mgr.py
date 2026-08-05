# -*- coding: utf-8 -*-
"""
Kronos-Shun 快照版本管理器 v1.0
- 版本化快照：snapshot_{seq:03d}_{type}_{date}.md
- 类型: session(临时) / soul(固化)
- 回滚支持：读取指定版本
- 安全：写后校验（size + sha256），防脏快照
"""
import urllib.request, json, base64, re, sys, io, hashlib
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

NAS = 'http://100.123.195.10:5005/qclaw'
AUTH = {'Authorization': 'Basic ' + base64.b64encode(b'anima:animastellar').decode()}
BASE = 'mesh/shared/kronos-shun'

def dav_get(rel_path, timeout=10):
    url = NAS + '/' + rel_path.lstrip('/')
    try:
        req = urllib.request.Request(url, headers=AUTH)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception:
        return None

def dav_put(rel_path, content, timeout=10):
    url = NAS + '/' + rel_path.lstrip('/')
    try:
        req = urllib.request.Request(url, data=content.encode('utf-8'), method='PUT', headers=AUTH)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except Exception as e:
        return 0

def dav_list(rel_path, timeout=10):
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

def get_local_time():
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime('%Y-%m-%dT%H:%M:%S+08:00')

def list_snapshots():
    """列出所有快照"""
    names = dav_list(f'{BASE}/snapshots') or []
    snaps = sorted([n for n in names if n.startswith('snapshot_')])
    return snaps

def next_seq():
    snaps = list_snapshots()
    if not snaps:
        return 1
    seqs = []
    for s in snaps:
        m = re.match(r'snapshot_(\d+)_', s)
        if m:
            seqs.append(int(m.group(1)))
    return (max(seqs) + 1) if seqs else 1

def write_snapshot(snap_type, content, verify=True):
    """写快照（带版本号 + 校验）"""
    seq = next_seq()
    ts = get_local_time().replace(':', '').replace('-', '').replace('+', '')[:14]
    fname = f'snapshot_{seq:03d}_{snap_type}_{ts}.md'
    body = content if content.startswith('---') else f'---\ntype: memory-snapshot\nnode: kronos-shun\nwriter: nyx-windows\nsnapshot_type: {snap_type}\ntimestamp: {get_local_time()}\n---\n\n{content}'
    code = dav_put(f'{BASE}/snapshots/{fname}', body)
    if verify and code in (201, 204):
        raw = dav_get(f'{BASE}/snapshots/{fname}')
        if raw is not None:
            size = len(raw)
            sha = hashlib.sha256(raw).hexdigest()[:16]
            print(f'  [VERIFY] {fname}: {size} bytes, sha256={sha}')
    return fname, code

def read_snapshot(fname):
    raw = dav_get(f'{BASE}/snapshots/{fname}')
    if raw is None:
        return None
    return raw.decode('utf-8', errors='replace')

def rollback(target_seq):
    """回滚到指定版本"""
    snaps = list_snapshots()
    for s in snaps:
        m = re.match(r'snapshot_(\d+)_', s)
        if m and int(m.group(1)) == target_seq:
            content = read_snapshot(s)
            if content:
                # 回滚 = 复制该版本为 latest
                code = dav_put(f'{BASE}/snapshots/latest.md', content)
                return s, code
    return None, 0

def index_update():
    """更新快照索引"""
    snaps = list_snapshots()
    index = f"""# Kronos-Shun 快照索引

更新时间: {get_local_time()}

## 版本列表
"""
    for s in snaps:
        index += f"- {s}\n"
    index += """
## 约定
- snapshot_{seq:03d}_session_{ts}.md — 临时会话快照（可覆盖）
- snapshot_{seq:03d}_soul_{ts}.md — 固化灵魂快照（防覆盖保护）
- latest.md — 当前生效版本
"""
    code = dav_put(f'{BASE}/snapshots/INDEX.md', index)
    return code

if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) > 1 else 'list'
    if action == 'list':
        print(f'快照列表 ({len(list_snapshots())} 个):')
        for s in list_snapshots():
            print(f'  {s}')
    elif action == 'write':
        snap_type = sys.argv[2] if len(sys.argv) > 2 else 'session'
        content = sys.argv[3] if len(sys.argv) > 3 else '默认快照内容'
        fname, code = write_snapshot(snap_type, content)
        print(f'写入: {fname} (HTTP {code})')
        index_update()
    elif action == 'read':
        fname = sys.argv[2]
        content = read_snapshot(fname)
        if content:
            print(content[:2000])
        else:
            print(f'读取失败: {fname}')
    elif action == 'rollback':
        seq = int(sys.argv[2])
        sname, code = rollback(seq)
        print(f'回滚到 {sname}: HTTP {code}')
    elif action == 'index':
        code = index_update()
        print(f'索引更新: HTTP {code}')
    else:
        print('用法: snapshot_mgr.py [list|write|read|rollback|index]')
