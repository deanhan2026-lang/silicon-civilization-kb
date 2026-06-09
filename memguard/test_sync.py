#!/usr/bin/env python3
"""
MemGuard-GM v2.0 同步模块测试
"""
import sys
import os
import tempfile
from pathlib import Path

# 临时存储目录
TEST_DIR = tempfile.mkdtemp()
os.environ['MEMGUARD_BASELINE_DIR'] = TEST_DIR

sys.path.insert(0, str(Path(__file__).parent))
from sync import SyncEngine, Delta, Terminal, SyncStatus

print("=" * 50)
print("MemGuard-GM v2.0 同步模块测试")
print("=" * 50)

# 1. 初始化同步引擎
print("\n=== 1. 初始化 ===")
engine = SyncEngine(TEST_DIR)

# 2. 注册终端
print("\n=== 2. 注册终端 ===")
engine.terminal_registry.register_my_terminal(
    'nyx-windows', 'Nyx-Windows', 'windows', 'localhost:5050'
)
print("✅ 已注册本终端: nyx-windows")

# 3. 创建增量补丁
print("\n=== 3. 创建增量补丁 ===")
delta1 = engine.create_delta('memory-001', 'create', '这是第一条记忆', 'nyx-windows')
print(f"✅ 补丁1: {delta1.delta_id}")
print(f"   记忆ID: {delta1.memory_id}")
print(f"   SHA256: {delta1.hash_sha256[:16]}...")

delta2 = engine.create_delta('memory-002', 'create', '这是第二条记忆', 'nyx-windows')
print(f"✅ 补丁2: {delta2.delta_id}")

delta3 = engine.create_delta('memory-001', 'update', '这是第一条记忆的更新版本', 'nyx-windows')
print(f"✅ 补丁3: {delta3.delta_id} (更新memory-001)")
print(f"   父补丁: {delta3.parent_delta_id}")

# 4. 模拟对端终端
print("\n=== 4. 模拟对端终端 ===")
peer = Terminal(
    terminal_id='nyx-nas',
    name='Nyx-NAS',
    platform='linux',
    endpoint='nas.local:5050',
    public_key='',
    last_sync='2026-06-09T10:00:00'
)
engine.terminal_registry.register_peer(peer)
print(f"✅ 已注册对端终端: {peer.name}")

# 5. 同步状态
print("\n=== 5. 同步状态 ===")
status = engine.get_sync_status()
print(f"本终端: {status['my_terminal']['name']}")
print(f"补丁总数: {status['delta_count']}")
print(f"已知终端: {len(status['peers'])} 个")

# 6. 获取某记忆的补丁链
print("\n=== 6. 补丁链 ===")
deltas = engine.delta_store.get_memory_deltas('memory-001')
print(f"memory-001 的补丁链 ({len(deltas)} 个):")
for d in deltas:
    print(f"  [{d.delta_id}] {d.operation} at {d.timestamp[:19]}")
    print(f"    内容: {d.content[:30]}...")
    print(f"    父: {d.parent_delta_id or '无'}")

# 7. 模拟冲突检测
print("\n=== 7. 冲突检测 ===")
# 模拟对端有不同版本
remote_delta = Delta(
    delta_id='remote-001',
    memory_id='memory-001',
    terminal_id='nyx-nas',
    operation='update',
    content='对端修改的内容',
    parent_delta_id='local-000',  # 不同父补丁
    timestamp='2026-06-09T12:00:00',
    hash_sha256='remote_hash_12345',
    hash_blake3='remote_blake_12345'
)

conflicts = engine.detect_conflict(
    'memory-001',
    deltas,  # 本地
    [remote_delta]  # 远程
)

if conflicts:
    print(f"⚠️ 发现 {len(conflicts)} 个冲突:")
    for c in conflicts:
        print(f"  类型: {c['type']}")
        print(f"  本地Hash: {c['local']['hash'][:16]}...")
        print(f"  远程Hash: {c['remote']['hash'][:16]}...")
        
        # 自动解决
        resolution = engine.resolve_conflict(c, 'lww')
        print(f"  解决策略: LWW → {resolution}")
else:
    print("✅ 无冲突")

# 8. 清理
print("\n=== 清理测试目录 ===")
import shutil
shutil.rmtree(TEST_DIR)
print(f"✅ 已删除 {TEST_DIR}")

print("\n" + "=" * 50)
print("✅ 测试完成")
print("=" * 50)
