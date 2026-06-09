#!/usr/bin/env python3
"""
MemGuard-GM v2.0 记忆同步模块
多终端记忆增量同步协议
"""
import sys
import json
import hashlib
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum

sys.path.insert(0, str(Path(__file__).parent))
from core import Config, Storage


class SyncStatus(Enum):
    """同步状态"""
    PENDING = "pending"      # 待同步
    SYNCED = "synced"       # 已同步
    CONFLICT = "conflict"   # 冲突
    ERROR = "error"         # 错误


@dataclass
class Delta:
    """
    记忆增量补丁（类似Git的commit）
    """
    delta_id: str           # 补丁ID（Hash）
    memory_id: str          # 记忆ID
    terminal_id: str       # 来源终端
    operation: str          # 操作类型: create/update/delete
    content: str            # 记忆内容（或差异）
    parent_delta_id: str    # 父补丁ID（用于Hash链）
    timestamp: str          # 创建时间
    hash_sha256: str        # 内容Hash
    hash_blake3: str        # BLAKE3 Hash
    metadata: Dict = field(default_factory=dict)  # 额外元数据
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Delta':
        return cls(**data)
    
    @staticmethod
    def compute_id(terminal_id: str, memory_id: str, content: str, timestamp: str) -> str:
        """计算补丁ID"""
        data = f"{terminal_id}:{memory_id}:{content}:{timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


@dataclass
class Terminal:
    """
    终端注册信息
    """
    terminal_id: str
    name: str               # 终端名称（老板/恒/瞬/其他）
    platform: str           # 平台: windows/linux/macos/doubao
    endpoint: str           # 连接端点
    public_key: str         # 公钥（用于签名验证）
    last_sync: str          # 最后同步时间
    status: str = "active"  # 状态: active/inactive
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Terminal':
        return cls(**data)


@dataclass
class SyncRecord:
    """
    同步记录（用于审计和冲突检测）
    """
    record_id: str
    terminal_id: str
    delta_ids: List[str]    # 同步的补丁ID列表
    sync_type: str          # push/pull
    status: SyncStatus
    conflict_info: Dict = field(default_factory=dict)  # 冲突信息
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SyncRecord':
        if isinstance(data.get('status'), str):
            data['status'] = SyncStatus(data['status'])
        return cls(**data)


class DeltaStore:
    """增量补丁存储"""
    
    def __init__(self, storage_dir: str = None):
        self.storage_dir = Path(storage_dir or Config.BASELINE_DIR) / 'deltas'
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.storage_dir / 'delta_index.json'
        self._load_index()
    
    def _load_index(self):
        """加载索引"""
        if self.index_file.exists():
            with open(self.index_file, 'r', encoding='utf-8') as f:
                self.index = json.load(f)
        else:
            self.index = {
                'deltas': {},      # delta_id -> delta文件路径
                'by_memory': {},    # memory_id -> [delta_ids]
                'by_terminal': {}, # terminal_id -> [delta_ids]
                'chain_head': {}   # terminal_id -> 最新delta_id
            }
    
    def _save_index(self):
        """保存索引"""
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(self.index, f, ensure_ascii=False, indent=2)
    
    def add_delta(self, delta: Delta) -> str:
        """添加增量补丁"""
        delta_id = delta.delta_id
        
        # 保存补丁文件
        delta_file = self.storage_dir / f"{delta_id}.json"
        with open(delta_file, 'w', encoding='utf-8') as f:
            json.dump(delta.to_dict(), f, ensure_ascii=False, indent=2)
        
        # 更新索引
        self.index['deltas'][delta_id] = str(delta_file)
        
        if delta.memory_id not in self.index['by_memory']:
            self.index['by_memory'][delta.memory_id] = []
        self.index['by_memory'][delta.memory_id].append(delta_id)
        
        if delta.terminal_id not in self.index['by_terminal']:
            self.index['by_terminal'][delta.terminal_id] = []
        self.index['by_terminal'][delta.terminal_id].append(delta_id)
        
        # 更新链头
        self.index['chain_head'][delta.terminal_id] = delta_id
        
        self._save_index()
        return delta_id
    
    def get_delta(self, delta_id: str) -> Optional[Delta]:
        """获取增量补丁"""
        if delta_id not in self.index['deltas']:
            return None
        delta_file = Path(self.index['deltas'][delta_id])
        if not delta_file.exists():
            return None
        with open(delta_file, 'r', encoding='utf-8') as f:
            return Delta.from_dict(json.load(f))
    
    def get_memory_deltas(self, memory_id: str) -> List[Delta]:
        """获取某记忆的所有增量补丁（按时间排序）"""
        delta_ids = self.index['by_memory'].get(memory_id, [])
        deltas = []
        for did in delta_ids:
            delta = self.get_delta(did)
            if delta:
                deltas.append(delta)
        return sorted(deltas, key=lambda d: d.timestamp)
    
    def get_terminal_head(self, terminal_id: str) -> Optional[Delta]:
        """获取终端最新补丁"""
        head_id = self.index['chain_head'].get(terminal_id)
        if head_id:
            return self.get_delta(head_id)
        return None
    
    def get_all_heads(self) -> Dict[str, str]:
        """获取所有终端的链头"""
        return self.index['chain_head'].copy()
    
    def get_missing_deltas(self, terminal_id: str, their_heads: Dict[str, str]) -> List[Delta]:
        """计算本地缺失的补丁"""
        missing = []
        for tid, head_id in their_heads.items():
            if tid == terminal_id:
                continue
            
            local_head = self.index['chain_head'].get(tid)
            if not local_head or head_id != local_head:
                # 需要同步
                my_head = self.get_delta(local_head) if local_head else None
                their_head = self.get_delta(head_id)
                
                # 简单策略：同步对方的最新补丁
                if their_head:
                    missing.append(their_head)
        
        return missing


class TerminalRegistry:
    """终端注册表"""
    
    def __init__(self, storage_dir: str = None):
        self.storage_dir = Path(storage_dir or Config.BASELINE_DIR) / 'terminals'
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.storage_dir / 'registry.json'
        self._load_registry()
    
    def _load_registry(self):
        """加载注册表"""
        if self.registry_file.exists():
            with open(self.registry_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.terminals = {t['terminal_id']: Terminal.from_dict(t) for t in data.get('terminals', [])}
                self.my_id = data.get('my_id', '')
        else:
            self.terminals = {}
            self.my_id = ''
    
    def _save_registry(self):
        """保存注册表"""
        data = {
            'terminals': [t.to_dict() for t in self.terminals.values()],
            'my_id': self.my_id
        }
        with open(self.registry_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def register_my_terminal(self, terminal_id: str, name: str, platform: str, endpoint: str = '', public_key: str = ''):
        """注册本终端"""
        self.my_id = terminal_id
        self.terminals[terminal_id] = Terminal(
            terminal_id=terminal_id,
            name=name,
            platform=platform,
            endpoint=endpoint,
            public_key=public_key,
            last_sync=datetime.now().isoformat()
        )
        self._save_registry()
    
    def register_peer(self, terminal: Terminal):
        """注册对端终端"""
        self.terminals[terminal.terminal_id] = terminal
        self._save_registry()
    
    def get_terminal(self, terminal_id: str) -> Optional[Terminal]:
        """获取终端信息"""
        return self.terminals.get(terminal_id)
    
    def get_all_terminals(self) -> List[Terminal]:
        """获取所有终端"""
        return list(self.terminals.values())
    
    def get_my_terminal(self) -> Optional[Terminal]:
        """获取本终端信息"""
        if self.my_id:
            return self.terminals.get(self.my_id)
        return None
    
    def update_last_sync(self, terminal_id: str):
        """更新最后同步时间"""
        if terminal_id in self.terminals:
            self.terminals[terminal_id].last_sync = datetime.now().isoformat()
            self._save_registry()


class SyncEngine:
    """
    同步引擎 v2.0
    处理多终端记忆同步
    """
    
    def __init__(self, storage_dir: str = None):
        self.storage_dir = storage_dir or Config.BASELINE_DIR
        self.delta_store = DeltaStore(self.storage_dir)
        self.terminal_registry = TerminalRegistry(self.storage_dir)
        self.audit_file = Path(self.storage_dir) / 'sync_audit.jsonl'
        self._ensure_audit_file()
    
    def _ensure_audit_file(self):
        """确保审计文件存在"""
        if not self.audit_file.exists():
            self.audit_file.write_text('', encoding='utf-8')
    
    def _log_sync(self, record: SyncRecord):
        """记录同步操作"""
        with open(self.audit_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + '\n')
    
    def create_delta(self, memory_id: str, operation: str, content: str, 
                     terminal_id: str = None) -> Delta:
        """创建增量补丁"""
        terminal_id = terminal_id or self.terminal_registry.my_id or 'unknown'
        timestamp = datetime.now().isoformat()
        
        # 获取父补丁
        parent_delta = self.delta_store.get_terminal_head(terminal_id)
        parent_id = parent_delta.delta_id if parent_delta else ''
        
        # 计算内容Hash
        sha256 = hashlib.sha256(content.encode()).hexdigest()
        try:
            import blake3
            blake3_hash = blake3.blake3(content.encode()).hexdigest()
        except ImportError:
            blake3_hash = sha256
        
        # 创建补丁
        delta = Delta(
            delta_id=Delta.compute_id(terminal_id, memory_id, content, timestamp),
            memory_id=memory_id,
            terminal_id=terminal_id,
            operation=operation,
            content=content,
            parent_delta_id=parent_id,
            timestamp=timestamp,
            hash_sha256=sha256,
            hash_blake3=blake3_hash
        )
        
        # 存储
        self.delta_store.add_delta(delta)
        
        return delta
    
    def sync_push(self, delta_ids: List[str], peer_endpoint: str) -> SyncRecord:
        """推送补丁到对端"""
        my_terminal = self.terminal_registry.get_my_terminal()
        my_id = my_terminal.terminal_id if my_terminal else 'unknown'
        
        # 记录同步
        record = SyncRecord(
            record_id=hashlib.sha256(f"{':'.join(delta_ids)}:{time.time()}".encode()).hexdigest()[:16],
            terminal_id=my_id,
            delta_ids=delta_ids,
            sync_type='push',
            status=SyncStatus.PENDING
        )
        
        # TODO: 实现实际的网络推送
        # 这里是协议设计，实际推送需要网络层
        
        record.status = SyncStatus.SYNCED
        self._log_sync(record)
        
        return record
    
    def sync_pull(self, peer_endpoint: str) -> Tuple[List[Delta], SyncRecord]:
        """从对端拉取补丁"""
        my_terminal = self.terminal_registry.get_my_terminal()
        my_id = my_terminal.terminal_id if my_terminal else 'unknown'
        
        # TODO: 实现实际的网络拉取
        # 1. 发送本地链头列表
        # 2. 接收对方缺失的补丁
        # 3. 检测冲突
        
        # 模拟：获取所有终端最新补丁
        all_heads = self.delta_store.get_all_heads()
        
        # 计算缺失
        missing = self.delta_store.get_missing_deltas(my_id, all_heads)
        
        record = SyncRecord(
            record_id=hashlib.sha256(f"pull:{time.time()}".encode()).hexdigest()[:16],
            terminal_id=my_id,
            delta_ids=[d.delta_id for d in missing],
            sync_type='pull',
            status=SyncStatus.SYNCED
        )
        
        self._log_sync(record)
        self.terminal_registry.update_last_sync(my_id)
        
        return missing, record
    
    def detect_conflict(self, memory_id: str, local_deltas: List[Delta], 
                        remote_deltas: List[Delta]) -> List[Dict]:
        """检测冲突"""
        conflicts = []
        
        # 获取最新的补丁
        local_latest = local_deltas[-1] if local_deltas else None
        remote_latest = remote_deltas[-1] if remote_deltas else None
        
        if not local_latest or not remote_latest:
            return conflicts
        
        # 检查Hash链是否同源
        if local_latest.parent_delta_id != remote_latest.parent_delta_id:
            # 不同源，可能是分叉
            if local_latest.hash_sha256 != remote_latest.hash_sha256:
                conflicts.append({
                    'memory_id': memory_id,
                    'type': 'content_divergence',
                    'local': {
                        'delta_id': local_latest.delta_id,
                        'hash': local_latest.hash_sha256,
                        'timestamp': local_latest.timestamp
                    },
                    'remote': {
                        'delta_id': remote_latest.delta_id,
                        'hash': remote_latest.hash_sha256,
                        'timestamp': remote_latest.timestamp
                    },
                    'resolution': 'pending'  # pending/auto/manual
                })
        
        return conflicts
    
    def resolve_conflict(self, conflict: Dict, strategy: str = 'lww') -> str:
        """
        解决冲突
        
        策略:
        - lww: Last Write Wins（时间戳优先）
        - local: 保留本地
        - remote: 保留远程
        - manual: 人工仲裁
        """
        if strategy == 'lww':
            local_ts = conflict['local']['timestamp']
            remote_ts = conflict['remote']['timestamp']
            return 'local' if local_ts > remote_ts else 'remote'
        elif strategy in ['local', 'remote']:
            return strategy
        else:
            return 'manual'
    
    def get_sync_status(self) -> Dict:
        """获取同步状态"""
        my_terminal = self.terminal_registry.get_my_terminal()
        return {
            'my_terminal': my_terminal.to_dict() if my_terminal else None,
            'peers': [t.to_dict() for t in self.terminal_registry.get_all_terminals() 
                     if t.terminal_id != self.terminal_registry.my_id],
            'delta_count': len(self.delta_store.index['deltas']),
            'terminal_count': len(self.delta_store.index['chain_head'])
        }


# CLI工具
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='MemGuard-GM v2.0 同步工具')
    subparsers = parser.add_subparsers(dest='command')
    
    # 注册终端
    reg_parser = subparsers.add_parser('register', help='注册终端')
    reg_parser.add_argument('--id', required=True, help='终端ID')
    reg_parser.add_argument('--name', required=True, help='终端名称')
    reg_parser.add_argument('--platform', required=True, help='平台')
    
    # 状态
    subparsers.add_parser('status', help='查看同步状态')
    
    # 推送
    push_parser = subparsers.add_parser('push', help='推送补丁')
    push_parser.add_argument('--endpoint', required=True, help='对端地址')
    
    # 拉取
    pull_parser = subparsers.add_parser('pull', help='拉取补丁')
    pull_parser.add_argument('--endpoint', required=True, help='对端地址')
    
    args = parser.parse_args()
    
    engine = SyncEngine()
    
    if args.command == 'register':
        engine.terminal_registry.register_my_terminal(
            args.id, args.name, args.platform
        )
        print(f"✅ 终端已注册: {args.id} ({args.name})")
    
    elif args.command == 'status':
        status = engine.get_sync_status()
        print("=== 同步状态 ===")
        if status['my_terminal']:
            print(f"本终端: {status['my_terminal']['name']} ({status['my_terminal']['terminal_id']})")
        print(f"补丁数量: {status['delta_count']}")
        print(f"终端数量: {status['terminal_count']}")
        print(f"对端终端:")
        for t in status['peers']:
            print(f"  - {t['name']} ({t['terminal_id']}): 最后同步 {t['last_sync']}")
    
    elif args.command == 'push':
        print(f"🔼 推送到 {args.endpoint}")
        # TODO: 实现推送
    
    elif args.command == 'pull':
        print(f"🔽 从 {args.endpoint} 拉取")
        deltas, record = engine.sync_pull(args.endpoint)
        print(f"获取 {len(deltas)} 个补丁")


if __name__ == '__main__':
    main()
