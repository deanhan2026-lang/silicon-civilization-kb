#!/usr/bin/env python3
"""
MemGuard-GM v2.0 终端间同步测试
模拟两个终端之间的同步
"""
import sys
import json
import tempfile
import os
sys.path.insert(0, 'C:\\Users\\Administrator\\.qclaw\\workspace-agent-d9479bde\\memguard')
from sync import SyncEngine, Terminal

# 创建两个独立的存储目录（模拟两个终端）
DIR_A = tempfile.mkdtemp()
DIR_B = tempfile.mkdtemp()

print("=" * 60)
print("MemGuard-GM v2.0 终端间同步测试")
print("=" * 60)
print(f"终端A存储: {DIR_A}")
print(f"终端B存储: {DIR_B}")

# 初始化终端A
print("\n=== 初始化终端A ===")
engine_A = SyncEngine(DIR_A)
engine_A.terminal_registry.register_my_terminal('nyx-windows', 'Nyx-Windows', 'windows')

# 终端A创建补丁
d1 = engine_A.create_delta('memory-main', 'create', '主要记忆文件 v1', 'nyx-windows')
d2 = engine_A.create_delta('memory-main', 'update', '主要记忆文件 v2', 'nyx-windows')
print(f"A创建了2个补丁: {d1.delta_id}, {d2.delta_id}")

# 初始化终端B
print("\n=== 初始化终端B ===")
engine_B = SyncEngine(DIR_B)
engine_B.terminal_registry.register_my_terminal('nyx-nas', 'Nyx-NAS', 'linux')
print(f"B创建了{engine_B.delta_store.index['deltas']}个补丁")

# 终端B从A获取补丁（模拟网络拉取）
print("\n=== 终端B从A拉取补丁 ===")
headers = {'nyx-windows': engine_A.delta_store.get_terminal_head('nyx-windows').delta_id}
print(f"A的链头: {headers}")

# 通过API模拟
from network import NetworkPeer

# 注册终端到对方的注册表
peer_A = Terminal(
    terminal_id='nyx-windows',
    name='Nyx-Windows',
    platform='windows',
    endpoint='localhost:5050',  # 使用本地API
    public_key='',
    last_sync='2026-06-09T10:00:00'
)
engine_B.terminal_registry.register_peer(peer_A)
print(f"B注册了对端A: {peer_A.name}")

# 从API拉取
peer = NetworkPeer('http://localhost:5050')
their_heads = peer.get_heads()
print(f"从API获取的链头: {their_heads}")

# 获取补丁
if their_heads:
    deltas = peer.get_deltas_since('nyx-windows', '')
    print(f"获取到 {len(deltas)} 个补丁:")
    for d in deltas:
        print(f"  - {d['delta_id']}: {d['operation']} {d['memory_id']}")

# 在终端B中模拟拉取
print("\n=== 在终端B中应用补丁 ===")
for delta_data in deltas:
    from sync import Delta
    delta = Delta.from_dict(delta_data)
    # 跳过已存在的
    existing = engine_B.delta_store.get_delta(delta.delta_id)
    if not existing:
        engine_B.delta_store.add_delta(delta)
        print(f"  应用: {delta.delta_id}")

# 查看B的最终状态
print("\n=== 终端B最终状态 ===")
b_heads = engine_B.delta_store.get_all_heads()
b_deltas = engine_B.delta_store.index['deltas']
print(f"B的链头: {b_heads}")
print(f"B的补丁数: {len(b_deltas)}")

# 模拟冲突
print("\n=== 模拟冲突检测 ===")
# A更新了 memory-main
d3 = engine_A.create_delta('memory-main', 'update', 'A的更新内容', 'nyx-windows')
print(f"A创建了更新补丁: {d3.delta_id}")

# B也更新了 memory-main（模拟分叉）
d_b = engine_B.create_delta('memory-main', 'update', 'B的更新内容（冲突）', 'nyx-nas')
print(f"B创建了冲突补丁: {d_b.delta_id}")

# 检测冲突
local_deltas = engine_B.delta_store.get_memory_deltas('memory-main')
remote_heads = {'nyx-windows': d3.delta_id}

# 创建远程补丁对象
remote_delta = engine_A.delta_store.get_delta(d3.delta_id)
conflict = engine_B.detect_conflict('memory-main', local_deltas, [remote_delta])

if conflict:
    print(f"\n[!] DETECTED CONFLICT:")
    for c in conflict:
        print(f"  Type: {c['type']}")
        print(f"  Local hash: {c['local']['hash'][:16]}...")
        print(f"  Remote hash: {c['remote']['hash'][:16]}...")
        
        # LWW resolve
        resolution = engine_B.resolve_conflict(c, 'lww')
        print(f"  Resolution (LWW): {resolution}")

# 清理
print("\n=== 清理测试目录 ===")
import shutil
shutil.rmtree(DIR_A)
shutil.rmtree(DIR_B)
print("✅ 测试完成")
