#!/usr/bin/env python3
"""
MemGuard-GM v2.0 网络同步层
基于HTTP的终端间通信
"""
import sys
import json
import time
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import asdict
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).parent))
from sync import SyncEngine, SyncStatus


class NetworkPeer:
    """
    网络对端节点
    """
    def __init__(self, endpoint: str, timeout: int = 10):
        self.endpoint = endpoint.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
    
    def _url(self, path: str) -> str:
        """构建完整URL"""
        return urljoin(self.endpoint + '/', path.lstrip('/'))
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            resp = self.session.get(self._url('/api/health'), timeout=5)
            return resp.status_code == 200
        except:
            return False
    
    def get_heads(self) -> Optional[Dict[str, str]]:
        """获取对端所有终端的链头"""
        try:
            resp = self.session.get(
                self._url('/api/sync/heads'),
                timeout=self.timeout
            )
            if resp.status_code == 200:
                return resp.json().get('heads', {})
            return None
        except Exception as e:
            print(f"获取链头失败: {e}")
            return None
    
    def push_deltas(self, deltas: List[Dict]) -> bool:
        """推送补丁到对端"""
        try:
            resp = self.session.post(
                self._url('/api/sync/push'),
                json={'deltas': deltas},
                timeout=self.timeout
            )
            return resp.status_code == 200
        except Exception as e:
            print(f"推送补丁失败: {e}")
            return False
    
    def pull_deltas(self, delta_ids: List[str]) -> Optional[List[Dict]]:
        """从对端拉取补丁"""
        try:
            resp = self.session.post(
                self._url('/api/sync/pull'),
                json={'delta_ids': delta_ids},
                timeout=self.timeout
            )
            if resp.status_code == 200:
                return resp.json().get('deltas', [])
            return None
        except Exception as e:
            print(f"拉取补丁失败: {e}")
            return None
    
    def get_deltas_since(self, terminal_id: str, since_delta_id: str) -> Optional[List[Dict]]:
        """获取指定终端的补丁（自某补丁之后）"""
        try:
            resp = self.session.get(
                self._url(f'/api/sync/deltas/{terminal_id}'),
                params={'since': since_delta_id},
                timeout=self.timeout
            )
            if resp.status_code == 200:
                return resp.json().get('deltas', [])
            return None
        except Exception as e:
            print(f"获取补丁失败: {e}")
            return None


class SyncProtocol:
    """
    同步协议实现
    """
    
    def __init__(self, engine: SyncEngine):
        self.engine = engine
    
    def sync_with_peer(self, peer: NetworkPeer, strategy: str = 'lww') -> Dict:
        """
        与对端执行完整同步
        
        流程:
        1. 交换链头信息
        2. 计算差异
        3. 推送本地补丁 / 拉取远程补丁
        4. 检测并解决冲突
        """
        result = {
            'success': False,
            'pushed': 0,
            'pulled': 0,
            'conflicts': [],
            'resolved': []
        }
        
        # 1. 检查对端是否在线
        if not peer.health_check():
            result['error'] = '对端不在线'
            return result
        
        # 2. 获取对端链头
        their_heads = peer.get_heads()
        if their_heads is None:
            result['error'] = '获取对端链头失败'
            return result
        
        # 3. 获取本地链头
        my_heads = self.engine.delta_store.get_all_heads()
        my_id = self.engine.terminal_registry.my_id
        
        # 4. 计算需要推送的补丁
        to_push = []
        for terminal_id, local_head in my_heads.items():
            their_head = their_heads.get(terminal_id)
            
            if their_head is None:
                # 对端没有这个终端的补丁，推送所有
                # TODO: 实现批量获取补丁
                pass
            elif local_head != their_head:
                # 链头不同，可能需要同步
                # TODO: 实现增量获取
                pass
        
        # 5. 计算需要拉取的补丁
        to_pull = []
        for terminal_id, remote_head in their_heads.items():
            if terminal_id == my_id:
                continue
            
            local_head = my_heads.get(terminal_id)
            
            if local_head is None or remote_head != local_head:
                # 本地缺失对端补丁
                deltas = peer.get_deltas_since(terminal_id, local_head or '')
                if deltas:
                    to_pull.extend(deltas)
        
        # 6. 执行推送
        if to_push:
            if peer.push_deltas([d.to_dict() if hasattr(d, 'to_dict') else d for d in to_push]):
                result['pushed'] = len(to_push)
        
        # 7. 执行拉取并解决冲突
        for delta_data in to_pull:
            from sync import Delta
            remote_delta = Delta.from_dict(delta_data)
            
            # 检查冲突
            local_deltas = self.engine.delta_store.get_memory_deltas(remote_delta.memory_id)
            conflicts = self.engine.detect_conflict(remote_delta.memory_id, local_deltas, [remote_delta])
            
            if conflicts:
                # 有冲突
                for c in conflicts:
                    resolution = self.engine.resolve_conflict(c, strategy)
                    result['conflicts'].append(c)
                    result['resolved'].append({
                        'memory_id': c['memory_id'],
                        'strategy': strategy,
                        'choice': resolution
                    })
            else:
                # 无冲突，直接应用
                self.engine.delta_store.add_delta(remote_delta)
                result['pulled'] += 1
        
        result['success'] = True
        return result
    
    def sync_all_peers(self, strategy: str = 'lww') -> List[Dict]:
        """同步所有已注册的对端"""
        results = []
        
        for terminal in self.engine.terminal_registry.get_all_terminals():
            if terminal.terminal_id == self.engine.terminal_registry.my_id:
                continue
            
            peer = NetworkPeer(terminal.endpoint)
            result = self.sync_with_peer(peer, strategy)
            result['peer'] = terminal.name
            results.append(result)
        
        return results


class SMBTransport:
    """
    基于SMB共享的传输层
    适用于局域网内通过NAS中转同步
    """
    
    def __init__(self, smb_path: str):
        """
        smb_path: SMB共享路径，如 \\192.168.1.100\qclaw\sync
        """
        self.smb_path = Path(smb_path)
        self.sync_dir = self.smb_path / 'sync'
        self._ensure_dir()
    
    def _ensure_dir(self):
        """确保同步目录存在"""
        # 在Windows上，通过Path可以直接操作SMB
        self.sync_dir.mkdir(parents=True, exist_ok=True)
    
    def write_delta(self, delta: Dict, terminal_id: str) -> str:
        """写入补丁到共享目录"""
        # 按终端分目录
        terminal_dir = self.sync_dir / terminal_id
        terminal_dir.mkdir(parents=True, exist_ok=True)
        
        # 写入补丁
        delta_id = delta.get('delta_id', 'unknown')
        delta_file = terminal_dir / f"{delta_id}.json"
        
        with open(delta_file, 'w', encoding='utf-8') as f:
            json.dump(delta, f, ensure_ascii=False, indent=2)
        
        return str(delta_file)
    
    def read_deltas(self, terminal_id: str, since: str = '') -> List[Dict]:
        """读取补丁（可选：只读取指定ID之后的）"""
        terminal_dir = self.sync_dir / terminal_id
        
        if not terminal_dir.exists():
            return []
        
        deltas = []
        for delta_file in sorted(terminal_dir.glob('*.json')):
            if since and delta_file.stem <= since:
                continue
            with open(delta_file, 'r', encoding='utf-8') as f:
                deltas.append(json.load(f))
        
        return deltas
    
    def get_heads(self, terminal_id: str) -> Optional[str]:
        """获取指定终端的最新补丁ID"""
        terminal_dir = self.sync_dir / terminal_id
        
        if not terminal_dir.exists():
            return None
        
        delta_files = sorted(terminal_dir.glob('*.json'))
        if delta_files:
            return delta_files[-1].stem
        return None
    
    def list_terminals(self) -> List[str]:
        """列出所有有补丁的终端"""
        if not self.sync_dir.exists():
            return []
        return [d.name for d in self.sync_dir.iterdir() if d.is_dir()]


class SyncScheduler:
    """
    定时同步调度器
    """
    
    def __init__(self, engine: SyncEngine, transport: SMBTransport = None):
        self.engine = engine
        self.transport = transport
        self.last_sync = None
    
    def should_sync(self, interval_seconds: int = 3600) -> bool:
        """检查是否应该同步"""
        if self.last_sync is None:
            return True
        
        elapsed = time.time() - self.last_sync
        return elapsed >= interval_seconds
    
    def run_sync(self, strategy: str = 'lww') -> Dict:
        """执行同步"""
        self.last_sync = time.time()
        
        results = {
            'timestamp': time.time(),
            'smb_transport': {},
            'peer_sync': []
        }
        
        # 1. SMB传输同步
        if self.transport:
            smb_result = self._sync_via_smb()
            results['smb_transport'] = smb_result
        
        # 2. 网络对端同步
        peer_results = self.engine.sync_all_peers(strategy)
        results['peer_sync'] = peer_results
        
        return results
    
    def _sync_via_smb(self) -> Dict:
        """通过SMB传输同步"""
        result = {
            'success': False,
            'pushed': 0,
            'pulled': 0
        }
        
        my_id = self.engine.terminal_registry.my_id
        my_heads = self.engine.delta_store.get_all_heads()
        
        # 推送本地补丁到SMB
        for delta_id, head in my_heads.items():
            # 获取该终端的所有补丁
            # TODO: 优化为增量推送
            pass
        
        # 从SMB拉取其他终端的补丁
        for terminal_id in self.transport.list_terminals():
            if terminal_id == my_id:
                continue
            
            local_head = my_heads.get(terminal_id)
            remote_deltas = self.transport.read_deltas(terminal_id, since=local_head or '')
            
            for delta_data in remote_deltas:
                from sync import Delta
                remote_delta = Delta.from_dict(delta_data)
                self.engine.delta_store.add_delta(remote_delta)
                result['pulled'] += 1
        
        result['success'] = True
        return result


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='MemGuard-GM v2.0 网络同步')
    subparsers = parser.add_subparsers(dest='command')
    
    # HTTP对端同步
    sync_parser = subparsers.add_parser('sync', help='同步对端')
    sync_parser.add_argument('--endpoint', required=True, help='对端地址')
    sync_parser.add_argument('--strategy', default='lww', help='冲突解决策略')
    
    # 同步所有
    subparsers.add_parser('sync-all', help='同步所有对端')
    
    # SMB传输
    smb_parser = subparsers.add_parser('smb', help='SMB传输')
    smb_parser.add_argument('--path', required=True, help='SMB路径')
    
    args = parser.parse_args()
    
    engine = SyncEngine()
    
    if args.command == 'sync':
        peer = NetworkPeer(args.endpoint)
        protocol = SyncProtocol(engine)
        result = protocol.sync_with_peer(peer, args.strategy)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.command == 'sync-all':
        protocol = SyncProtocol(engine)
        results = protocol.sync_all_peers()
        print(json.dumps(results, indent=2, ensure_ascii=False))
    
    elif args.command == 'smb':
        transport = SMBTransport(args.path)
        print(f"✅ SMB传输层已初始化: {transport.sync_dir}")
        print(f"已知终端: {transport.list_terminals()}")


if __name__ == '__main__':
    main()
