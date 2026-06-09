#!/usr/bin/env python3
"""
模拟另一个终端从NAS拉取补丁
"""
import sys
import tempfile
import shutil
sys.path.insert(0, 'C:\\Users\\Administrator\\.qclaw\\workspace-agent-d9479bde\\memguard')
from sync import SyncEngine

print("=" * 60)
print("模拟：另一个终端从NAS拉取补丁")
print("=" * 60)

# 创建新的隔离存储（模拟另一个终端）
new_dir = tempfile.mkdtemp()
print(f"\n新终端存储: {new_dir}")

# 初始化新终端
engine_new = SyncEngine(new_dir)
engine_new.terminal_registry.register_my_terminal('nyx-nas', 'Nyx-NAS', 'linux')

print(f"新终端: {engine_new.terminal_registry.my_id}")
print(f"初始补丁数: {len(engine_new.delta_store.index['deltas'])}")

# 从NAS拉取
print("\n从NAS同步...")
from sync_smb import sync_all_from_smb, SMB_BASE

results = sync_all_from_smb(engine_new)

print(f"\n同步结果:")
for terminal_id, result in results.items():
    print(f"  {terminal_id}: +{result['imported']} / ~{result['skipped']}")

# 查看新终端的状态
print("\n新终端最终状态:")
heads = engine_new.delta_store.get_all_heads()
print(f"  链头: {heads}")
print(f"  补丁数: {len(engine_new.delta_store.index['deltas'])}")

# 获取memory-main的完整补丁链
print("\n补丁链详情:")
for delta_id in engine_new.delta_store.index['by_terminal'].get('nyx-windows', []):
    delta = engine_new.delta_store.get_delta(delta_id)
    if delta:
        print(f"  [{delta.delta_id}] {delta.operation} {delta.memory_id}")
        print(f"    内容: {delta.content[:30]}...")
        print(f"    父: {delta.parent_delta_id or '无'}")

# 清理
print("\n清理测试目录...")
shutil.rmtree(new_dir)

print("\n✅ 模拟完成！")
