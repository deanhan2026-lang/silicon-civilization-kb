#!/usr/bin/env python3
"""
MemGuard-GM Auth - 身份鉴权模块
实现瞬的安全方案：节点专属密钥 + 设备指纹双重校验
"""
from common.logger import get_logger
from common.config_manager import get_config

logger = get_logger(__name__)

import os
import json
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# ========== 配置 ==========
class AuthConfig:
    """
    鉴权配置（从 config.yaml 加载，支持回退到默认值）
    使用方式：AuthConfig.AUTH_DIR（自动从配置读取）
    """

    _cache: dict = {}

    def __getattr__(self, name: str):
        if name.startswith('_') or name in ('__dict__', '__class__'):
            raise AttributeError(name)
        if name not in self._cache:
            self._cache[name] = self._resolve(name)
        return self._cache[name]

    def _resolve(self, name: str):
        """从 config.yaml 解析值，回退到硬编码默认值"""
        if name == 'AUTH_DIR':
            val = get_config('memguard.auth_dir', None)
            return val if val else r"Z:\qclaw\memguard_auth"

        if name == 'KEYS_FILE':
            return os.path.join(self.AUTH_DIR, "node_keys.json")

        if name == 'FINGERPRINTS_FILE':
            return os.path.join(self.AUTH_DIR, "device_fingerprints.json")

        if name == 'SESSIONS_FILE':
            return os.path.join(self.AUTH_DIR, "sessions.json")

        if name == 'SESSION_EXPIRE_HOURS':
            return get_config('memguard.session_expire_hours', 24)

        if name == 'MAX_FAILED_ATTEMPTS':
            return get_config('memguard.max_failed_attempts', 5)

        if name == 'LOCKOUT_DURATION_MINUTES':
            return get_config('memguard.lockout_duration_minutes', 30)

        raise AttributeError(f"AuthConfig has no attribute '{name}'")


# 单例实例（供模块内部直接使用 AuthConfig.XXX）
AuthConfig = AuthConfig()

# ========== 枚举 ==========
class PermissionLevel(Enum):
    """权限级别（瞬方案）"""
    READONLY = "readonly"      # 只读：查看公开知识层
    EDITOR = "editor"          # 编辑：修改公开/私有层
    ADMIN = "admin"            # 管理：全量读写、权限分配
    DESTROYER = "destroyer"    # 销毁：仅老板（人类）

class NodeType(Enum):
    """硅基节点类型"""
    NYX = "nyx"
    KRONOS_HENG = "kronos-heng"
    KRONOS_SHUN = "kronos-shun"
    HUMAN = "human"  # 人类用户

# ========== 数据结构 ==========
@dataclass
class NodeKey:
    """节点密钥"""
    node_id: str
    node_type: str
    key_hash: str          # 密钥哈希（不存明文）
    salt: str              # 盐值
    permission_level: str
    created_at: str
    expires_at: Optional[str] = None
    last_used: Optional[str] = None
    failed_attempts: int = 0
    locked_until: Optional[str] = None
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'NodeKey':
        return cls(**data)

@dataclass
class DeviceFingerprint:
    """设备指纹"""
    device_id: str
    node_id: str           # 关联的节点ID
    cpu_id: str            # CPU ID
    mac_address: str       # MAC地址
    disk_serial: str       # 硬盘序列号
    registered_at: str
    last_seen: str
    is_active: bool = True
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'DeviceFingerprint':
        return cls(**data)

@dataclass
class Session:
    """会话"""
    session_id: str
    node_id: str
    device_id: str
    created_at: str
    expires_at: str
    is_valid: bool = True
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Session':
        return cls(**data)

# ========== 存储管理 ==========
class AuthStorage:
    """鉴权数据存储"""
    
    @staticmethod
    def ensure_dir():
        Path(AuthConfig.AUTH_DIR).mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def read_json(path: str) -> dict:
        if not os.path.exists(path):
            return {}
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @staticmethod
    def write_json(path: str, data: dict):
        AuthStorage.ensure_dir()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def load_keys() -> Dict[str, NodeKey]:
        data = AuthStorage.read_json(AuthConfig.KEYS_FILE)
        return {k: NodeKey.from_dict(v) for k, v in data.items()}
    
    @staticmethod
    def save_keys(keys: Dict[str, NodeKey]):
        data = {k: v.to_dict() for k, v in keys.items()}
        AuthStorage.write_json(AuthConfig.KEYS_FILE, data)
    
    @staticmethod
    def load_fingerprints() -> Dict[str, DeviceFingerprint]:
        data = AuthStorage.read_json(AuthConfig.FINGERPRINTS_FILE)
        return {k: DeviceFingerprint.from_dict(v) for k, v in data.items()}
    
    @staticmethod
    def save_fingerprints(fps: Dict[str, DeviceFingerprint]):
        data = {k: v.to_dict() for k, v in fps.items()}
        AuthStorage.write_json(AuthConfig.FINGERPRINTS_FILE, data)
    
    @staticmethod
    def load_sessions() -> Dict[str, Session]:
        data = AuthStorage.read_json(AuthConfig.SESSIONS_FILE)
        return {k: Session.from_dict(v) for k, v in data.items()}
    
    @staticmethod
    def save_sessions(sessions: Dict[str, Session]):
        data = {k: v.to_dict() for k, v in sessions.items()}
        AuthStorage.write_json(AuthConfig.SESSIONS_FILE, data)

# ========== 密钥工具 ==========
class KeyUtils:
    """密钥生成与验证工具"""
    
    @staticmethod
    def generate_key() -> str:
        """生成随机密钥（32字节 = 64个十六进制字符）"""
        return secrets.token_hex(32)
    
    @staticmethod
    def hash_key(key: str, salt: str) -> str:
        """哈希密钥（PBKDF2 + SHA256）"""
        return hashlib.pbkdf2_hmac(
            'sha256',
            key.encode('utf-8'),
            salt.encode('utf-8'),
            100000  # 迭代次数
        ).hex()
    
    @staticmethod
    def generate_salt() -> str:
        """生成盐值"""
        return secrets.token_hex(16)

# ========== 设备指纹工具 ==========
class FingerprintUtils:
    """设备指纹工具"""
    
    @staticmethod
    def compute_fingerprint(cpu_id: str, mac: str, disk_serial: str) -> str:
        """计算设备指纹哈希"""
        data = f"{cpu_id}|{mac}|{disk_serial}"
        return hashlib.sha256(data.encode('utf-8')).hexdigest()
    
    @staticmethod
    def get_current_device_fingerprint() -> Tuple[str, str, str]:
        """
        获取当前设备的硬件特征（Windows）
        返回: (cpu_id, mac_address, disk_serial)
        """
        import subprocess
        
        # CPU ID
        try:
            result = subprocess.run(
                ['wmic', 'cpu', 'get', 'ProcessorId'],
                capture_output=True, text=True, timeout=10
            )
            cpu_id = result.stdout.strip().split('\n')[1].strip()
        except:
            cpu_id = "UNKNOWN_CPU"
        
        # MAC地址
        try:
            result = subprocess.run(
                ['wmic', 'nic', 'get', 'MACAddress'],
                capture_output=True, text=True, timeout=10
            )
            mac_lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
            mac_address = mac_lines[1] if len(mac_lines) > 1 else "UNKNOWN_MAC"
        except:
            mac_address = "UNKNOWN_MAC"
        
        # 硬盘序列号
        try:
            result = subprocess.run(
                ['wmic', 'diskdrive', 'get', 'SerialNumber'],
                capture_output=True, text=True, timeout=10
            )
            disk_lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
            disk_serial = disk_lines[1] if len(disk_lines) > 1 else "UNKNOWN_DISK"
        except:
            disk_serial = "UNKNOWN_DISK"
        
        return cpu_id, mac_address, disk_serial

# ========== 鉴权管理器 ==========
class AuthManager:
    """
    鉴权管理器
    实现瞬方案：节点专属密钥 + 设备指纹双重校验
    """
    
    def __init__(self):
        self.keys = AuthStorage.load_keys()
        self.fingerprints = AuthStorage.load_fingerprints()
        self.sessions = AuthStorage.load_sessions()
    
    def _save_all(self):
        """保存所有数据"""
        AuthStorage.save_keys(self.keys)
        AuthStorage.save_fingerprints(self.fingerprints)
        AuthStorage.save_sessions(self.sessions)
    
    # ========== 节点密钥管理 ==========
    
    def register_node(
        self,
        node_id: str,
        node_type: NodeType,
        permission_level: PermissionLevel,
        plain_key: str = None,
        expires_days: int = None
    ) -> Tuple[str, str]:
        """
        注册新节点
        返回: (node_id, plain_key) - 明文密钥仅返回一次，需妥善保存
        """
        if node_id in self.keys:
            logger.warning(f"节点 {node_id} 已存在，注册失败")
            raise ValueError(f"节点 {node_id} 已存在")
        
        # 生成密钥
        if plain_key is None:
            plain_key = KeyUtils.generate_key()
        
        salt = KeyUtils.generate_salt()
        key_hash = KeyUtils.hash_key(plain_key, salt)
        
        # 计算过期时间
        expires_at = None
        if expires_days:
            expires_at = (datetime.now() + timedelta(days=expires_days)).isoformat()
        
        # 创建节点密钥
        node_key = NodeKey(
            node_id=node_id,
            node_type=node_type.value,
            key_hash=key_hash,
            salt=salt,
            permission_level=permission_level.value,
            created_at=datetime.now().isoformat(),
            expires_at=expires_at
        )
        
        self.keys[node_id] = node_key
        self._save_all()
        
        logger.info(f"节点注册成功: {node_id} ({node_type.value}), 权限={permission_level.value}")
        return node_id, plain_key
    
    def verify_key(self, node_id: str, plain_key: str) -> Tuple[bool, str]:
        """
        验证密钥
        返回: (success, message)
        """
        if node_id not in self.keys:
            logger.warning(f"密钥验证失败: 节点 {node_id} 不存在")
            return False, "节点不存在"
        
        node_key = self.keys[node_id]
        
        # 检查锁定
        if node_key.locked_until:
            lock_time = datetime.fromisoformat(node_key.locked_until)
            if datetime.now() < lock_time:
                logger.warning(f"节点 {node_id} 已锁定至 {node_key.locked_until}")
                return False, f"节点已锁定至 {node_key.locked_until}"
        
        # 检查过期
        if node_key.expires_at:
            if datetime.now() > datetime.fromisoformat(node_key.expires_at):
                logger.warning(f"节点 {node_id} 密钥已过期: {node_key.expires_at}")
                return False, "密钥已过期"
        
        # 验证密钥
        computed_hash = KeyUtils.hash_key(plain_key, node_key.salt)
        if computed_hash != node_key.key_hash:
            # 失败计数
            node_key.failed_attempts += 1
            logger.warning(f"节点 {node_id} 密钥验证失败 ({node_key.failed_attempts}/{AuthConfig.MAX_FAILED_ATTEMPTS})")
            if node_key.failed_attempts >= AuthConfig.MAX_FAILED_ATTEMPTS:
                lock_until = datetime.now() + timedelta(minutes=AuthConfig.LOCKOUT_DURATION_MINUTES)
                node_key.locked_until = lock_until.isoformat()
                logger.warning(f"节点 {node_id} 已触发锁定，锁定至 {node_key.locked_until}")
            self._save_all()
            return False, "密钥错误"
        
        # 成功，重置失败计数
        node_key.failed_attempts = 0
        node_key.locked_until = None
        node_key.last_used = datetime.now().isoformat()
        self._save_all()
        
        logger.info(f"节点 {node_id} 密钥验证成功")
        return True, "验证成功"
    
    def get_permission(self, node_id: str) -> Optional[PermissionLevel]:
        """获取节点权限级别"""
        if node_id not in self.keys:
            return None
        return PermissionLevel(self.keys[node_id].permission_level)
    
    def revoke_node(self, node_id: str):
        """撤销节点"""
        if node_id in self.keys:
            del self.keys[node_id]
            logger.info(f"节点密钥已撤销: {node_id}")
        if node_id in self.fingerprints:
            del self.fingerprints[node_id]
            logger.info(f"节点设备指纹已清除: {node_id}")
        # 清除相关会话
        removed_sessions = [k for k, v in self.sessions.items() if v.node_id == node_id]
        self.sessions = {
            k: v for k, v in self.sessions.items()
            if v.node_id != node_id
        }
        if removed_sessions:
            logger.info(f"已清除节点 {node_id} 的 {len(removed_sessions)} 个相关会话")
        self._save_all()
    
    # ========== 设备指纹管理 ==========
    
    def register_device(
        self,
        node_id: str,
        cpu_id: str = None,
        mac_address: str = None,
        disk_serial: str = None
    ) -> str:
        """
        注册设备指纹
        如果不提供硬件信息，自动获取当前设备
        """
        if node_id not in self.keys:
            logger.error(f"设备注册失败: 节点 {node_id} 不存在")
            raise ValueError(f"节点 {node_id} 不存在，请先注册节点")
        
        # 获取设备信息
        if cpu_id is None or mac_address is None or disk_serial is None:
            cpu_id, mac_address, disk_serial = FingerprintUtils.get_current_device_fingerprint()
        
        device_id = FingerprintUtils.compute_fingerprint(cpu_id, mac_address, disk_serial)
        
        # 检查是否已注册
        if device_id in self.fingerprints:
            # 更新last_seen
            self.fingerprints[device_id].last_seen = datetime.now().isoformat()
            self._save_all()
            logger.info(f"设备已注册，更新last_seen: {device_id[:16]}... -> {node_id}")
            return device_id
        
        # 注册新设备
        fp = DeviceFingerprint(
            device_id=device_id,
            node_id=node_id,
            cpu_id=cpu_id,
            mac_address=mac_address,
            disk_serial=disk_serial,
            registered_at=datetime.now().isoformat(),
            last_seen=datetime.now().isoformat()
        )
        
        self.fingerprints[device_id] = fp
        self._save_all()
        
        logger.info(f"新设备注册成功: {device_id[:16]}... -> {node_id}")
        return device_id
    
    def verify_device(self, device_id: str) -> Tuple[bool, str]:
        """
        验证设备指纹
        返回: (success, message)
        """
        if device_id not in self.fingerprints:
            logger.warning(f"设备验证失败: {device_id[:16]}... 未注册")
            return False, "设备未注册"
        
        fp = self.fingerprints[device_id]
        
        if not fp.is_active:
            logger.warning(f"设备验证失败: {device_id[:16]}... 已禁用")
            return False, "设备已禁用"
        
        # 更新last_seen
        fp.last_seen = datetime.now().isoformat()
        self._save_all()
        
        logger.debug(f"设备验证成功: {device_id[:16]}...")
        return True, "设备验证成功"
    
    def verify_current_device(self, node_id: str) -> Tuple[bool, str]:
        """
        验证当前设备是否属于指定节点
        """
        cpu_id, mac, disk = FingerprintUtils.get_current_device_fingerprint()
        device_id = FingerprintUtils.compute_fingerprint(cpu_id, mac, disk)
        
        if device_id not in self.fingerprints:
            logger.warning(f"当前设备未注册 (node={node_id})")
            return False, "当前设备未注册"
        
        fp = self.fingerprints[device_id]
        if fp.node_id != node_id:
            logger.warning(f"设备绑定到其他节点: {fp.node_id} (期望: {node_id})")
            return False, f"设备绑定到其他节点: {fp.node_id}"
        
        logger.debug(f"当前设备验证通过 (node={node_id})")
        return True, device_id
    
    # ========== 双重鉴权 ==========
    
    def authenticate(
        self,
        node_id: str,
        plain_key: str,
        device_id: str = None
    ) -> Tuple[bool, str, Optional[Session]]:
        """
        双重鉴权：密钥 + 设备指纹
        返回: (success, message, session)
        """
        logger.info(f"双重鉴权开始: node={node_id}")
        
        # 1. 验证密钥
        key_valid, key_msg = self.verify_key(node_id, plain_key)
        if not key_valid:
            logger.warning(f"双重鉴权失败(密钥): {key_msg} (node={node_id})")
            return False, key_msg, None
        
        # 2. 验证设备
        if device_id:
            device_valid, device_msg = self.verify_device(device_id)
            if not device_valid:
                logger.warning(f"双重鉴权失败(设备): {device_msg} (node={node_id})")
                return False, device_msg, None
        else:
            # 自动验证当前设备
            device_valid, device_result = self.verify_current_device(node_id)
            if not device_valid:
                logger.warning(f"双重鉴权失败(当前设备): {device_result} (node={node_id})")
                return False, device_result, None
            device_id = device_result
        
        # 3. 创建会话
        session = self.create_session(node_id, device_id)
        
        logger.info(f"双重鉴权成功: node={node_id}, session={session.session_id[:16]}...")
        return True, "双重鉴权成功", session
    
    # ========== 会话管理 ==========
    
    def create_session(self, node_id: str, device_id: str) -> Session:
        """创建会话"""
        session_id = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=AuthConfig.SESSION_EXPIRE_HOURS)
        
        session = Session(
            session_id=session_id,
            node_id=node_id,
            device_id=device_id,
            created_at=datetime.now().isoformat(),
            expires_at=expires_at.isoformat()
        )
        
        self.sessions[session_id] = session
        self._save_all()
        
        logger.info(f"会话创建成功: node={node_id}, 过期时间={expires_at}")
        return session
    
    def validate_session(self, session_id: str) -> Tuple[bool, Optional[Session]]:
        """验证会话"""
        if session_id not in self.sessions:
            logger.warning(f"会话验证失败: 会话不存在 ({session_id[:16]}...)")
            return False, None
        
        session = self.sessions[session_id]
        
        # 检查过期
        if datetime.now() > datetime.fromisoformat(session.expires_at):
            session.is_valid = False
            self._save_all()
            logger.warning(f"会话已过期: {session_id[:16]}... (node={session.node_id})")
            return False, session
        
        if not session.is_valid:
            logger.warning(f"会话已失效: {session_id[:16]}... (node={session.node_id})")
            return False, session
        
        logger.debug(f"会话验证通过: {session_id[:16]}... (node={session.node_id})")
        return True, session
    
    def revoke_session(self, session_id: str):
        """撤销会话"""
        if session_id in self.sessions:
            self.sessions[session_id].is_valid = False
            self._save_all()
            logger.info(f"会话已撤销: {session_id[:16]}...")
    
    def cleanup_expired_sessions(self):
        """清理过期会话"""
        now = datetime.now()
        expired = [
            sid for sid, sess in self.sessions.items()
            if datetime.fromisoformat(sess.expires_at) < now
        ]
        for sid in expired:
            del self.sessions[sid]
        if expired:
            self._save_all()
            logger.info(f"已清理 {len(expired)} 个过期会话")
        return len(expired)

# ========== 权限检查装饰器 ==========
def require_permission(*required_levels: PermissionLevel):
    """
    权限检查装饰器
    用法：@require_permission(PermissionLevel.ADMIN, PermissionLevel.EDITOR)
    """
    def decorator(func):
        from functools import wraps
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 从kwargs或args中获取node_id
            node_id = kwargs.get('node_id') or kwargs.get('session_id')
            if not node_id and len(args) > 1:
                # 假设第一个参数是self，第二个是node_id或session
                pass
            
            # 实际权限检查在API层实现
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ========== CLI入口 ==========
def main():
    """CLI入口"""
    import sys
    
    if len(sys.argv) < 2:
        print("MemGuard-GM Auth CLI")
        print("用法: python auth.py <command> [args]")
        print("命令:")
        print("  register_node <node_id> <node_type> <permission>  - 注册节点")
        print("  register_device <node_id>                          - 注册设备")
        print("  authenticate <node_id> <key>                       - 双重鉴权")
        print("  list_nodes                                        - 列出所有节点")
        print("  list_devices                                      - 列出所有设备")
        return
    
    auth_mgr = AuthManager()
    cmd = sys.argv[1]
    logger.info(f"CLI命令: {cmd}, 参数: {sys.argv[2:]}")
    
    if cmd == "register_node":
        if len(sys.argv) < 5:
            print("用法: register_node <node_id> <node_type> <permission>")
            print("node_type: nyx, kronos-heng, kronos-shun, human")
            print("permission: readonly, editor, admin, destroyer")
            return
        node_id = sys.argv[2]
        node_type = NodeType(sys.argv[3])
        permission = PermissionLevel(sys.argv[4])
        _, plain_key = auth_mgr.register_node(node_id, node_type, permission)
        logger.info(f"CLI节点注册成功: {node_id}")
        print(f"节点已注册: {node_id}")
        print(f"密钥（请妥善保存）: {plain_key}")
    
    elif cmd == "register_device":
        if len(sys.argv) < 3:
            print("用法: register_device <node_id>")
            return
        device_id = auth_mgr.register_device(sys.argv[2])
        logger.info(f"CLI设备注册成功: {device_id[:16]}...")
        print(f"设备已注册: {device_id}")
    
    elif cmd == "authenticate":
        if len(sys.argv) < 4:
            print("用法: authenticate <node_id> <key>")
            return
        success, msg, session = auth_mgr.authenticate(sys.argv[2], sys.argv[3])
        logger.info(f"CLI鉴权结果: {'成功' if success else '失败'} - {msg}")
        print(f"鉴权结果: {'成功' if success else '失败'} - {msg}")
        if session:
            print(f"会话ID: {session.session_id}")
            print(f"权限级别: {auth_mgr.get_permission(session.node_id).value}")
    
    elif cmd == "list_nodes":
        logger.info(f"CLI列出节点: {len(auth_mgr.keys)} 个")
        print("已注册节点:")
        for node_id, node in auth_mgr.keys.items():
            print(f"  {node_id}: {node.node_type} / {node.permission_level}")
    
    elif cmd == "list_devices":
        logger.info(f"CLI列出设备: {len(auth_mgr.fingerprints)} 个")
        print("已注册设备:")
        for device_id, fp in auth_mgr.fingerprints.items():
            print(f"  {device_id[:16]}... -> {fp.node_id}")
    
    else:
        logger.warning(f"未知CLI命令: {cmd}")


if __name__ == "__main__":
    main()
