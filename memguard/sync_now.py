#!/usr/bin/env python3
"""
MemGuard-GM v2.0 同步脚本
一键同步：导出我的补丁 + 拉取其他终端补丁
"""
import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from sync import SyncEngine, Terminal, Delta

# SMB同步根目录
SMB_BASE = Path("Z:/qclaw/memguard_sync")

def ensure_smb():
    SMB_BASE.mkdir(parents=True, exist_ok=True)
    (SMB_BASE / "deltas").mkdir(exist_ok=True)
    (SMB_BASE / "terminals").mkdir(exist_ok=True)

def export_my_deltas(engine: SyncEngine):
    """导出本终端的补丁到NAS"""
    my_id = engine.terminal_registry.my_id
    if not my_id:
        print("  [!] 未注册终端")
        return 0
    
    terminal_dir = SMB_BASE / "deltas" / my_id
    terminal_dir.mkdir(parents=True, exist_ok=True)
    
    delta_ids = engine.delta_store.index['by_terminal'].get(my_id, [])
    exported = 0
    
    for delta_id in delta_ids:
        delta = engine.delta_store.get_delta(delta_id)
        if delta:
            delta_file = terminal_dir / f"{delta_id}.json"
            with open(delta_file, 'w', encoding='utf-8') as f:
                json.dump(delta.to_dict(), f, ensure_ascii=False, indent=2)
            exported += 1
    
    # 导出终端信息
    terminal = engine.terminal_registry.get_my_terminal()
    if terminal:
        info_file = SMB_BASE / "terminals" / f"{my_id}.json"
        with open(info_file, 'w', encoding='utf-8') as f:
            json.dump({
                'terminal_id': terminal.terminal_id,
                'name': terminal.name,
                'platform': terminal.platform,
                'endpoint': terminal.endpoint,
                'last_sync': datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
    
    # 导出链头索引
    head = engine.delta_store.get_terminal_head(my_id)
    heads_file = SMB_BASE / "deltas" / f"{my_id}_heads.json"
    with open(heads_file, 'w', encoding='utf-8') as f:
        json.dump({
            'terminal_id': my_id,
            'chain_head': head.delta_id if head else None,
            'delta_count': len(delta_ids),
            'timestamp': datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)
    
    return exported

def import_other_deltas(engine: SyncEngine):
    """从NAS导入其他终端的补丁"""
    deltas_dir = SMB_BASE / "deltas"
    if not deltas_dir.exists():
        return {}
    
    my_id = engine.terminal_registry.my_id
    results = {}
    
    for terminal_subdir in deltas_dir.iterdir():
        if not terminal_subdir.is_dir():
            continue
        
        terminal_id = terminal_subdir.name
        if terminal_id.endswith('_heads'):
            continue
        
        # 跳过自己
        if terminal_id == my_id:
            continue
        
        imported = 0
        skipped = 0
        
        for delta_file in sorted(terminal_subdir.glob("*.json")):
            delta_id = delta_file.stem
            
            if engine.delta_store.get_delta(delta_id):
                skipped += 1
                continue
            
            with open(delta_file, 'r', encoding='utf-8') as f:
                delta_data = json.load(f)
            
            delta = Delta.from_dict(delta_data)
            engine.delta_store.add_delta(delta)
            imported += 1
        
        # 导入终端信息
        info_file = SMB_BASE / "terminals" / f"{terminal_id}.json"
        if info_file.exists() and not engine.terminal_registry.get_terminal(terminal_id):
            with open(info_file, 'r', encoding='utf-8') as f:
                info = json.load(f)
                peer = Terminal(
                    terminal_id=info['terminal_id'],
                    name=info['name'],
                    platform=info['platform'],
                    endpoint=info.get('endpoint', ''),
                    public_key='',
                    last_sync=info.get('last_sync', '')
                )
                engine.terminal_registry.register_peer(peer)
        
        if imported > 0 or skipped > 0:
            results[terminal_id] = {'imported': imported, 'skipped': skipped}
    
    return results

def main():
    print("=" * 50)
    print("MemGuard-GM 同步")
    print("=" * 50)
    
    ensure_smb()
    
    # 初始化引擎
    engine = SyncEngine()
    my_id = engine.terminal_registry.my_id
    
    print(f"\n本终端: {my_id or '未注册'}")
    if not my_id:
        print("\n[!] 请先注册终端:")
        print("    curl -X POST http://localhost:5050/api/sync/register \\")
        print('      -H "Content-Type: application/json" \\')
        print('      -d \'{"terminal_id":"xxx","name":"xxx","platform":"windows"}\'')
        return
    
    # 导出我的补丁
    print("\n[1] 导出补丁到NAS...")
    exported = export_my_deltas(engine)
    print(f"    导出: {exported} 个补丁")
    
    # 拉取其他终端补丁
    print("\n[2] 从NAS拉取其他终端补丁...")
    results = import_other_deltas(engine)
    
    if results:
        for terminal_id, r in results.items():
            print(f"    {terminal_id}: +{r['imported']} / ~{r['skipped']}")
    else:
        print("    无其他终端补丁")
    
    # 显示状态
    print("\n[3] 同步后状态...")
    status = engine.get_sync_status()
    print(f"    本终端: {status['my_terminal']['name']}")
    print(f"    补丁总数: {status['delta_count']}")
    print(f"    已知终端: {len(status['peers'])} 个")
    
    for peer in status['peers']:
        print(f"      - {peer['name']} ({peer['platform']})")
    
    print("\n[完成]")

if __name__ == '__main__':
    main()
