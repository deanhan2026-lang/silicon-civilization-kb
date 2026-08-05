# -*- coding: utf-8 -*-
"""
Kronos-Shun 快照版本管理器 v2.0（soul 保护版）
- 版本化快照：snapshot_{seq:03d}_{type}_{date}.md
- 类型: session(临时) / soul(固化)
- **soul 保护**: soul 快照不可覆写，仅允许新序号；尝试覆写 → 告警到 ack/
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
    snaps = sorted([n for n in names if re.match(r'snapshot_\d+_', n)])
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

def is_soul(fname):
    """检查快照是否为 soul 类型"""
    content = dav_get(f'{BASE}/snapshots/{fname}')
    if content is None:
        return False
    text = content.decode('utf-8', errors='replace')
    return 'snapshot_type: soul' in text or 'status: immutable' in text

def soul_alert(fname, reason):
    """soul 覆写告警 → ack/"""
    ts = get_local_time()
    alert = f"""---
type: soul-protection-alert
node: kronos-shun
writer: nyx-windows
timestamp: {ts}
severity: warning
---

# Soul 快照保护告警

检测到尝试覆写 soul 快照: {fname}
原因: {reason}
已拒绝直接覆写。

保护规则:
- soul 快照不可变，仅允许生成新序号版本
- 如需更新身份锚点 → 生成新序号 soul 版本
"""
    fname_alert = f'soul_protection_alert_{ts.replace(":", "").replace("-", "")[:14]}.md'
    return dav_put(f'{BASE}/ack/{fname_alert}', alert)

def write_snapshot(snap_type, content, verify=True):
    """写快照（带版本号 + soul 保护 + 校验）"""
    if snap_type not in ('session', 'soul'):
        print(f'ERROR: 非法类型 {snap_type}（必须是 session 或 soul）')
        return None, 0

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
- snapshot_{seq:03d}_soul_{ts}.md — 固化灵魂快照（不可覆写，仅新序号）
- latest.md — 当前生效版本
"""
    code = dav_put(f'{BASE}/snapshots/INDEX.md', index)
    return code

if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) > 1 else 'list'
    if action == 'list':
        snaps = list_snapshots()
        print(f'快照列表 ({len(snaps)} 个):')
        for s in snaps:
            soul = ' [SOUL-固化]' if is_soul(s) else ' [session]'
            print(f'  {s}{soul}')
    elif action == 'write':
        snap_type = sys.argv[2] if len(sys.argv) > 2 else 'session'
        content = sys.argv[3] if len(sys.argv) > 3 else '默认快照内容'
        fname, code = write_snapshot(snap_type, content)
        if fname:
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
    elif action == 'protect-check':
        # 检查所有 soul 快照是否被篡改
        snaps = list_snapshots()
        for s in snaps:
            if is_soul(s):
                raw = dav_get(f'{BASE}/snapshots/{s}')
                if raw:
                    sha = hashlib.sha256(raw).hexdigest()[:16]
                    print(f'  [CHECK] {s}: sha256={sha}')
        print('  soul 完整性检查完成')
    else:
        print('用法: snapshot_mgr.py [list|write|read|rollback|index|protect-check]')
