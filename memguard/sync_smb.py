#!/usr/bin/env python3
"""
MemGuard-GM v2.0 SMB传输同步
通过NAS共享文件实现终端间同步
"""
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from sync import SyncEngine, Terminal, Delta

# SMB同步目录
SMB_BASE = Path("Z:/qclaw/memguard_sync")

def ensure_smb():
    """确保SMB同步目录存在"""
    SMB_BASE.mkdir(parents=True, exist_ok=True)
    (SMB_BASE / "deltas").mkdir(exist_ok=True)
    (SMB_BASE / "terminals").mkdir(exist_ok=True)
    print(f"SMB base: {SMB_BASE}")

def export_terminal_to_smb(engine: SyncEngine, terminal_id: str):
    """导出终端的补丁到SMB"""
    terminal_dir = SMB_BASE / "deltas" / terminal_id
    terminal_dir.mkdir(parents=True, exist_ok=True)
    
    # 获取该终端的所有补丁
    delta_ids = engine.delta_store.index['by_terminal'].get(terminal_id, [])
    
    exported = 0
    for delta_id in delta_ids:
        delta = engine.delta_store.get_delta(delta_id)
        if delta:
            # 写入SMB
            delta_file = terminal_dir / f"{delta_id}.json"
            with open(delta_file, 'w', encoding='utf-8') as f:
                json.dump(delta.to_dict(), f, ensure_ascii=False, indent=2)
            exported += 1
    
    # 导出终端信息
    terminal_info = SMB_BASE / "terminals" / f"{terminal_id}.json"
    terminal = engine.terminal_registry.get_terminal(terminal_id)
    if terminal:
        with open(terminal_info, 'w', encoding='utf-8') as f:
            json.dump(terminal.to_dict(), f, ensure_ascii=False, indent=2)
    
    # 导出链头索引
    heads_file = SMB_BASE / "deltas" / f"{terminal_id}_heads.json"
    with open(heads_file, 'w', encoding='utf-8') as f:
        json.dump({
            'terminal_id': terminal_id,
            'chain_head': engine.delta_store.get_terminal_head(terminal_id).delta_id if engine.delta_store.get_terminal_head(terminal_id) else None,
            'delta_count': len(delta_ids),
            'timestamp': datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)
    
    return exported

def import_terminal_from_smb(engine: SyncEngine, terminal_id: str) -> dict:
    """从SMB导入其他终端的补丁"""
    terminal_dir = SMB_BASE / "deltas" / terminal_id
    heads_file = SMB_BASE / "deltas" / f"{terminal_id}_heads.json"
    
    if not terminal_dir.exists():
        return {'imported': 0, 'skipped': 0}
    
    imported = 0
    skipped = 0
    
    # 获取本地链头
    local_head = engine.delta_store.get_terminal_head(terminal_id)
    local_head_id = local_head.delta_id if local_head else None
    
    for delta_file in sorted(terminal_dir.glob("*.json")):
        delta_id = delta_file.stem
        
        # 跳过已存在的
        if engine.delta_store.get_delta(delta_id):
            skipped += 1
            continue
        
        # 读取并应用
        with open(delta_file, 'r', encoding='utf-8') as f:
            delta_data = json.load(f)
        
        delta = Delta.from_dict(delta_data)
        engine.delta_store.add_delta(delta)
        imported += 1
    
    # 导入终端信息
    terminal_info = SMB_BASE / "terminals" / f"{terminal_id}.json"
    if terminal_info.exists():
        with open(terminal_info, 'r', encoding='utf-8') as f:
            terminal_data = json.load(f)
            peer = Terminal.from_dict(terminal_data)
            existing = engine.terminal_registry.get_terminal(terminal_id)
            if not existing:
                engine.terminal_registry.register_peer(peer)
    
    return {'imported': imported, 'skipped': skipped}

def sync_all_from_smb(engine: SyncEngine):
    """从SMB同步所有终端的补丁"""
    results = {}
    
    if not SMB_BASE.exists():
        return results
    
    # 遍历所有终端目录
    deltas_dir = SMB_BASE / "deltas"
    if not deltas_dir.exists():
        return results
    
    for terminal_dir in deltas_dir.iterdir():
        if not terminal_dir.is_dir():
            continue
        
        terminal_id = terminal_dir.name
        if terminal_id.endswith('_heads'):
            continue
        
        # 跳过自己
        my_id = engine.terminal_registry.my_id
        if terminal_id == my_id:
            continue
        
        # 导入
        result = import_terminal_from_smb(engine, terminal_id)
        if result['imported'] > 0 or result['skipped'] > 0:
            results[terminal_id] = result
    
    return results

def sync_to_smb(engine: SyncEngine):
    """把自己的补丁同步到SMB"""
    my_id = engine.terminal_registry.my_id
    if my_id:
        return export_terminal_to_smb(engine, my_id)
    return 0

def main():
    print("=" * 50)
    print("MemGuard-GM v2.0 SMB同步")
    print("=" * 50)
    
    # 确保SMB目录
    ensure_smb()
    
    # 初始化引擎
    engine = SyncEngine()
    my_id = engine.terminal_registry.my_id
    
    print(f"\n本终端: {my_id}")
    
    # 1. 导出自己的补丁
    print("\n[1] 导出补丁到SMB...")
    exported = sync_to_smb(engine)
    print(f"    导出: {exported} 个补丁")
    
    # 2. 从SMB导入其他终端的补丁
    print("\n[2] 从SMB导入补丁...")
    results = sync_all_from_smb(engine)
    
    if results:
        for terminal_id, result in results.items():
            print(f"    {terminal_id}: +{result['imported']} / ~{result['skipped']}")
    else:
        print("    无其他终端补丁")
    
    # 3. 显示最终状态
    print("\n[3] 最终状态...")
    status = engine.get_sync_status()
    print(f"    本终端: {status['my_terminal']['name'] if status['my_terminal'] else 'N/A'}")
    print(f"    补丁总数: {status['delta_count']}")
    print(f"    已知终端: {len(status['peers'])} 个")
    
    for peer in status['peers']:
        print(f"      - {peer['name']} ({peer['platform']})")
    
    # 4. 查看SMB内容
    print("\n[4] SMB内容...")
    if (SMB_BASE / "terminals").exists():
        for f in (SMB_BASE / "terminals").glob("*.json"):
            print(f"    终端: {f.stem}")

if __name__ == '__main__':
    main()
