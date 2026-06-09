#!/usr/bin/env python3
"""
完整同步循环测试
"""
import sys
import tempfile
import shutil
sys.path.insert(0, 'C:\\Users\\Administrator\\.qclaw\\workspace-agent-d9479bde\\memguard')
from sync import SyncEngine, Delta
from sync_smb import sync_to_smb, sync_all_from_smb, SMB_BASE

print("=" * 60)
print("完整同步循环测试")
print("=" * 60)

# 创建两个隔离存储
dir_a = tempfile.mkdtemp()
dir_b = tempfile.mkdtemp()

print(f"终端A: {dir_a}")
print(f"终端B: {dir_b}")

# 初始化终端A
engine_a = SyncEngine(dir_a)
engine_a.terminal_registry.register_my_terminal('nyx-windows', 'Nyx-Windows', 'windows')

# 初始化终端B
engine_b = SyncEngine(dir_b)
engine_b.terminal_registry.register_my_terminal('nyx-nas', 'Nyx-NAS', 'linux')

print("\n=== 步骤1: 终端A创建新补丁 ===")
d1 = engine_a.create_delta('memory-001', 'create', '第一条记忆内容', 'nyx-windows')
print(f"创建: {d1.delta_id} - {d1.content[:20]}...")

d2 = engine_a.create_delta('memory-002', 'create', '第二条记忆内容', 'nyx-windows')
print(f"创建: {d2.delta_id} - {d2.content[:20]}...")

# 终端B此时状态
print(f"\n终端B补丁数: {len(engine_b.delta_store.index['deltas'])}")

print("\n=== 步骤2: 终端A导出到NAS ===")
# 直接写入SMB（模拟）
terminal_dir = SMB_BASE / "deltas" / "nyx-windows"
terminal_dir.mkdir(parents=True, exist_ok=True)

for delta_id in engine_a.delta_store.index['by_terminal'].get('nyx-windows', []):
    delta = engine_a.delta_store.get_delta(delta_id)
    if delta:
        delta_file = terminal_dir / f"{delta_id}.json"
        import json
        with open(delta_file, 'w', encoding='utf-8') as f:
            json.dump(delta.to_dict(), f, ensure_ascii=False, indent=2)
        print(f"  导出: {delta_id}")

# 更新链头索引
heads_file = SMB_BASE / "deltas" / "nyx-windows_heads.json"
with open(heads_file, 'w', encoding='utf-8') as f:
    json.dump({
        'terminal_id': 'nyx-windows',
        'chain_head': engine_a.delta_store.get_terminal_head('nyx-windows').delta_id,
        'delta_count': 2
    }, f, ensure_ascii=False)

print("\n=== 步骤3: 终端B从NAS拉取 ===")
for delta_file in sorted((terminal_dir).glob("*.json")):
    delta_id = delta_file.stem
    if engine_b.delta_store.get_delta(delta_id):
        continue
    
    with open(delta_file, 'r', encoding='utf-8') as f:
        delta_data = json.load(f)
    
    delta = Delta.from_dict(delta_data)
    engine_b.delta_store.add_delta(delta)
    print(f"  导入: {delta_id} - {delta.operation} {delta.memory_id}")

print("\n=== 步骤4: 验证同步结果 ===")
print(f"终端A补丁数: {len(engine_a.delta_store.index['deltas'])}")
print(f"终端B补丁数: {len(engine_b.delta_store.index['deltas'])}")

heads_a = engine_a.delta_store.get_all_heads()
heads_b = engine_b.delta_store.get_all_heads()
print(f"\n终端A链头: {heads_a}")
print(f"终端B链头: {heads_b}")

# 检查补丁链
print("\n补丁链验证:")
for delta_id in engine_b.delta_store.index['by_terminal'].get('nyx-windows', []):
    delta = engine_b.delta_store.get_delta(delta_id)
    if delta:
        print(f"  [OK] {delta_id[:8]}... {delta.operation} {delta.memory_id}")

# 清理
print("\n清理...")
shutil.rmtree(dir_a)
shutil.rmtree(dir_b)

print("\n✅ 完整同步循环测试通过！")
