#!/usr/bin/env python3
"""
MemGuard-GM Core - 记忆完整性保护核心模块
"""
import json
import os
import sys
import hashlib
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from enum import Enum

# ========== 配置 ==========
class Config:
    """MemGuard配置（支持环境变量覆盖，NAS不可达时自动回退）"""
    
    @staticmethod
    def _resolve_path(key: str, default: str) -> str:
        """解析路径：优先环境变量，其次默认值（NAS不可达时回退本地）"""
        env_val = os.environ.get(key)
        if env_val:
            return env_val
        # 如果默认路径是 NAS 且不可达，回退到本地目录
        if default.startswith("Z:\\") or default.startswith("Z:/"):
            if not os.path.exists("Z:\\"):
                repo_root = Path(__file__).parent.parent.resolve()
                # 把 Z:\qclaw\xxx 映射为 data/memguard/xxx
                # 提取最后一段路径名
                parts = default.replace("Z:\\", "").replace("Z:/", "").split(os.sep)
                local_name = parts[-1] if parts else "default"
                local_dir = repo_root / "data" / local_name
                return str(local_dir)
        return default
    
    # 基线存储路径 (优先 MEMGUARD_BASELINE_DIR，NAS不可达时回退 data/memguard/)
    BASELINE_DIR: str = None
    BASELINE_SHA256: str = None
    BASELINE_BLAKE3: str = None
    BASELINE_LOCK: str = None
    
    # 记忆存储路径
    MEMORY_DIR: str = None
    
    # 审计日志路径
    AUDIT_DIR: str = None
    AUDIT_LOG: str = None
    
    # 状态文件
    STATUS_FILE: str = None
    
    @classmethod
    def init(cls):
        """延迟初始化：解析所有路径（避免类加载时 NAS 不可达导致崩溃）"""
        if cls.BASELINE_DIR is not None:
            return  # 已初始化
        cls.BASELINE_DIR = cls._resolve_path("MEMGUARD_BASELINE_DIR", r"Z:\qclaw\memguard_baseline")
        cls.BASELINE_SHA256 = os.path.join(cls.BASELINE_DIR, "baseline.sha256")
        cls.BASELINE_BLAKE3 = os.path.join(cls.BASELINE_DIR, "baseline.blake3")
        cls.BASELINE_LOCK = os.path.join(cls.BASELINE_DIR, "baseline.lock")
        cls.MEMORY_DIR = cls._resolve_path("MEMGUARD_MEMORY_DIR", r"Z:\qclaw\memory")
        cls.AUDIT_DIR = cls._resolve_path("MEMGUARD_AUDIT_DIR", r"Z:\qclaw\audit")
        cls.AUDIT_LOG = os.path.join(cls.AUDIT_DIR, "audit.jsonl")
        cls.STATUS_FILE = os.path.join(cls.AUDIT_DIR, "memory_status.json")
    
    # 校验时间窗口（小时）
    CHECK_INTERVAL_HOURS = 4

# ========== 枚举 ==========
class MemoryStatus(Enum):
    NORMAL = "normal"
    FROZEN = "frozen"
    SUSPICIOUS = "suspicious"

class OperatorRole(Enum):
    ADMIN = "admin"
    VALIDATOR = "validator"
    API_CALLER = "api"
    ANONYMOUS = "anonymous"

# ========== 数据结构 ==========
@dataclass
class MemoryEntry:
    """记忆条目"""
    id: str
    content: str
    hash_sha256: str
    hash_blake3: str
    created_at: str
    updated_at: str
    status: str = "normal"
    frozen_time: Optional[str] = None
    frozen_reason: Optional[str] = None
    tags: list = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'MemoryEntry':
        return cls(**data)

@dataclass
class AuditLog:
    """审计日志条目（Hash链）"""
    ts: str
    event: str
    memory_id: Optional[str]
    operator: str
    prev_hash: str
    hash: str
    detail: str
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AuditLog':
        return cls(**data)

# ========== Hash工具 ==========
class HashUtils:
    """Hash计算工具"""
    
    @staticmethod
    def sha256(data: str) -> str:
        return hashlib.sha256(data.encode('utf-8')).hexdigest()
    
    @staticmethod
    def blake3(data: str) -> str:
        try:
            import blake3
            return blake3.blake3(data.encode('utf-8')).hexdigest()
        except ImportError:
            # 如果没有blake3，用SHA-512替代
            return hashlib.sha512(data.encode('utf-8')).hexdigest()
    
    @staticmethod
    def compute_hashes(content: str) -> dict:
        """计算双Hash"""
        return {
            'sha256': HashUtils.sha256(content),
            'blake3': HashUtils.blake3(content)
        }
    
    @staticmethod
    def compute_log_hash(log_entry: dict, prev_hash: str) -> str:
        """计算日志Hash（用于Hash链）"""
        data = f"{log_entry['ts']}|{log_entry['event']}|{log_entry.get('memory_id','')}|{log_entry['operator']}|{prev_hash}|{log_entry.get('detail','')}"
        return HashUtils.sha256(data)

# 模块加载时初始化配置（必须放在 Storage 等类定义之前）
Config.init()

# ========== 基础存储 ==========
class Storage:
    """基础存储操作"""
    
    @staticmethod
    def ensure_dir(path: str):
        Path(path).mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def read_file(path: str) -> str:
        if not os.path.exists(path):
            return ""
        with open(path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    
    @staticmethod
    def write_file(path: str, content: str):
        Storage.ensure_dir(os.path.dirname(path))
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    @staticmethod
    def read_json(path: str) -> list:
        if not os.path.exists(path):
            return []
        with open(path, 'r', encoding='utf-8') as f:
            return [json.loads(line) for line in f if line.strip()]
    
    @staticmethod
    def append_jsonl(path: str, entry: dict):
        Storage.ensure_dir(os.path.dirname(path))
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

# ========== 基线管理器 ==========
class BaselineManager:
    """基线管理器 - N200加密分区"""
    
    def __init__(self):
        self.baseline_dir = Config.BASELINE_DIR
        Storage.ensure_dir(self.baseline_dir)
    
    def is_readonly(self) -> bool:
        """检查是否只读锁定"""
        return os.path.exists(Config.BASELINE_LOCK)
    
    def lock(self):
        """锁定基线（只读）"""
        Storage.write_file(Config.BASELINE_LOCK, datetime.now().isoformat())
    
    def unlock(self):
        """解锁基线（允许写入）"""
        if os.path.exists(Config.BASELINE_LOCK):
            os.remove(Config.BASELINE_LOCK)
    
    def save_baseline(self, sha256_hash: str, blake3_hash: str):
        """保存基线（必须先unlock）"""
        if self.is_readonly():
            raise Exception("基线已锁定，请先解锁")
        Storage.write_file(Config.BASELINE_SHA256, sha256_hash)
        Storage.write_file(Config.BASELINE_BLAKE3, blake3_hash)
        self.lock()  # 写入后立即锁定
    
    def read_baseline(self) -> dict:
        """读取基线"""
        return {
            'sha256': Storage.read_file(Config.BASELINE_SHA256),
            'blake3': Storage.read_file(Config.BASELINE_BLAKE3)
        }
    
    def verify_and_lock(self):
        """验证基线完整性并锁定"""
        if not os.path.exists(Config.BASELINE_SHA256):
            return False
        self.lock()
        return True

# ========== 审计日志 ==========
class AuditLogManager:
    """审计日志管理器 - Hash链"""
    
    def __init__(self):
        self.log_path = Config.AUDIT_LOG
        Storage.ensure_dir(Config.AUDIT_DIR)
    
    def _get_last_hash(self) -> str:
        """获取上一条日志的Hash"""
        logs = Storage.read_json(self.log_path)
        if not logs:
            return "GENESIS"  # 创世块
        return logs[-1].get('hash', 'GENESIS')
    
    def append(self, event: str, memory_id: str, operator: str, detail: str = "") -> AuditLog:
        """追加审计日志"""
        prev_hash = self._get_last_hash()
        ts = datetime.now().isoformat()
        
        log_data = {
            'ts': ts,
            'event': event,
            'memory_id': memory_id,
            'operator': operator,
            'prev_hash': prev_hash,
            'detail': detail
        }
        log_data['hash'] = HashUtils.compute_log_hash(log_data, prev_hash)
        
        log_entry = AuditLog(**log_data)
        Storage.append_jsonl(self.log_path, log_entry.to_dict())
        return log_entry
    
    def verify_chain(self) -> tuple:
        """验证Hash链完整性"""
        logs = Storage.read_json(self.log_path)
        if not logs:
            return True, "空日志链"
        
        for i, log in enumerate(logs):
            if i == 0:
                if log.get('prev_hash') != 'GENESIS':
                    return False, f"第{i+1}条：创世块Hash错误"
            else:
                if log.get('prev_hash') != logs[i-1].get('hash'):
                    return False, f"第{i+1}条：Hash链断裂"
            
            expected_hash = HashUtils.compute_log_hash(log, log.get('prev_hash'))
            if log.get('hash') != expected_hash:
                return False, f"第{i+1}条：Hash值被篡改"
        
        return True, f"完整 ({len(logs)}条)"
    
    def search(self, event: str = None, memory_id: str = None, limit: int = 100) -> list:
        """搜索审计日志"""
        logs = Storage.read_json(self.log_path)
        results = logs[-limit:]
        
        if event:
            results = [l for l in results if l.get('event') == event]
        if memory_id:
            results = [l for l in results if l.get('memory_id') == memory_id]
        
        return results

# ========== 记忆状态管理器 ==========
class MemoryStatusManager:
    """记忆状态管理器 - 单条冻结"""
    
    def __init__(self):
        self.status_file = Config.STATUS_FILE
        self._load()
    
    def _load(self):
        """加载状态"""
        if os.path.exists(self.status_file):
            with open(self.status_file, 'r', encoding='utf-8') as f:
                self.statuses = json.load(f)
        else:
            self.statuses = {}
    
    def _save(self):
        """保存状态"""
        Storage.ensure_dir(Config.AUDIT_DIR)
        with open(self.status_file, 'w', encoding='utf-8') as f:
            json.dump(self.statuses, f, ensure_ascii=False, indent=2)
    
    def get_status(self, memory_id: str) -> str:
        """获取记忆状态"""
        return self.statuses.get(memory_id, {}).get('status', 'normal')
    
    def freeze(self, memory_id: str, reason: str, operator: str = "system"):
        """冻结单条记忆"""
        self.statuses[memory_id] = {
            'status': 'frozen',
            'frozen_time': datetime.now().isoformat(),
            'frozen_reason': reason,
            'frozen_by': operator
        }
        self._save()
    
    def unfreeze(self, memory_id: str, operator: str = "admin"):
        """解冻记忆"""
        if memory_id in self.statuses:
            self.statuses[memory_id]['status'] = 'normal'
            self.statuses[memory_id]['unfrozen_time'] = datetime.now().isoformat()
            self.statuses[memory_id]['unfrozen_by'] = operator
            self._save()
    
    def mark_suspicious(self, memory_id: str, reason: str):
        """标记为可疑"""
        self.statuses[memory_id] = {
            'status': 'suspicious',
            'suspicious_time': datetime.now().isoformat(),
            'suspicious_reason': reason
        }
        self._save()
    
    def get_all_frozen(self) -> list:
        """获取所有冻结的记忆"""
        return [mid for mid, status in self.statuses.items() 
                if status.get('status') == 'frozen']

# ========== 访问控制 ==========
class AccessControl:
    """访问控制层"""
    
    def __init__(self):
        self.status_mgr = MemoryStatusManager()
        self.audit_mgr = AuditLogManager()
    
    def check_access(self, memory_id: str, operator: str, operation: str) -> tuple:
        """
        检查访问权限
        返回: (allowed: bool, reason: str)
        """
        status = self.status_mgr.get_status(memory_id)
        
        if status == 'frozen':
            if operator != 'admin':
                return False, f"记忆 {memory_id} 已冻结，拒绝{operation}"
            return True, "Admin权限 bypass"
        
        if status == 'suspicious':
            self.audit_mgr.append(
                event='suspicious_access',
                memory_id=memory_id,
                operator=operator,
                detail=f"尝试{operation}"
            )
            return False, f"记忆 {memory_id} 状态可疑，拒绝{operation}"
        
        return True, "正常"
    
    def require_access(self, memory_id: str, operator: str, operation: str):
        """访问控制检查，失败则抛异常"""
        allowed, reason = self.check_access(memory_id, operator, operation)
        if not allowed:
            raise PermissionError(reason)
        return True

# ========== 核心引擎 ==========
class MemGuardEngine:
    """MemGuard核心引擎"""
    
    def __init__(self):
        self.baseline_mgr = BaselineManager()
        self.audit_mgr = AuditLogManager()
        self.status_mgr = MemoryStatusManager()
        self.access_ctrl = AccessControl()
    
    def compute_memory_hash(self, content: str) -> dict:
        """计算记忆Hash"""
        return HashUtils.compute_hashes(content)
    
    def verify_memory(self, memory_id: str, content: str) -> tuple:
        """
        验证记忆完整性
        返回: (valid: bool, detail: str)
        """
        computed = HashUtils.compute_hashes(content)
        baseline = self.baseline_mgr.read_baseline()
        
        if not baseline.get('sha256'):
            return True, "无基线，首次校验"
        
        sha256_match = computed['sha256'] == baseline['sha256']
        blake3_match = computed['blake3'] == baseline['blake3']
        
        if sha256_match and blake3_match:
            return True, "Hash校验通过"
        
        # 不匹配，冻结并告警
        reason = f"Hash不匹配: SHA256={sha256_match}, BLAKE3={blake3_match}"
        self.status_mgr.freeze(memory_id, reason, "validator")
        self.audit_mgr.append(
            event='memory_frozen',
            memory_id=memory_id,
            operator='validator',
            detail=reason
        )
        
        return False, reason
    
    def create_baseline(self, content: str, operator: str = "admin") -> dict:
        """
        创建/更新基线
        注意：此操作需要Admin权限，且必须记录审计
        """
        if self.baseline_mgr.is_readonly():
            raise PermissionError("基线已锁定，无法自动更新")
        
        self.baseline_mgr.unlock()
        hashes = HashUtils.compute_hashes(content)
        self.baseline_mgr.save_baseline(hashes['sha256'], hashes['blake3'])
        
        self.audit_mgr.append(
            event='baseline_updated',
            memory_id=None,
            operator=operator,
            detail=f"新基线: SHA256={hashes['sha256'][:16]}..."
        )
        
        return hashes
    
    def read_memory(self, memory_id: str, operator: str = "admin") -> str:
        """读取记忆（带访问控制）"""
        self.access_ctrl.require_access(memory_id, operator, "读取")
        # 实际读取逻辑由外部提供，这里只做访问控制
        return None
    
    def update_memory(self, memory_id: str, content: str, operator: str = "admin") -> dict:
        """更新记忆"""
        self.access_ctrl.require_access(memory_id, operator, "更新")
        
        hashes = HashUtils.compute_hashes(content)
        
        self.audit_mgr.append(
            event='memory_updated',
            memory_id=memory_id,
            operator=operator,
            detail=f"更新Hash: SHA256={hashes['sha256'][:16]}..."
        )
        
        return hashes


# ========== CLI入口 ==========
def main():
    """CLI入口"""
    if len(sys.argv) < 2:
        print("MemGuard-GM CLI")
        print("用法: python core.py <command> [args]")
        print("命令:")
        print("  baseline_create <content>     - 创建基线")
        print("  baseline_read                 - 读取基线")
        print("  baseline_lock                - 锁定基线")
        print("  baseline_unlock              - 解锁基线")
        print("  audit_verify                 - 验证审计链")
        print("  audit_search [event]         - 搜索审计日志")
        print("  status_frozen                - 列出冻结记忆")
        print("  freeze <memory_id> <reason>  - 冻结记忆")
        print("  unfreeze <memory_id>        - 解冻记忆")
        return
    
    engine = MemGuardEngine()
    cmd = sys.argv[1]
    
    if cmd == "baseline_create":
        content = sys.argv[2] if len(sys.argv) > 2 else input("输入基线内容: ")
        hashes = engine.create_baseline(content)
        print(f"基线已创建: {hashes}")
    
    elif cmd == "baseline_read":
        baseline = engine.baseline_mgr.read_baseline()
        print(f"基线: {baseline}")
    
    elif cmd == "baseline_lock":
        engine.baseline_mgr.lock()
        print("基线已锁定")
    
    elif cmd == "baseline_unlock":
        engine.baseline_mgr.unlock()
        print("基线已解锁（警告：谨慎操作！）")
    
    elif cmd == "audit_verify":
        valid, msg = engine.audit_mgr.verify_chain()
        print(f"审计链验证: {'✅ ' + msg if valid else '❌ ' + msg}")
    
    elif cmd == "audit_search":
        event = sys.argv[2] if len(sys.argv) > 2 else None
        logs = engine.audit_mgr.search(event=event)
        for log in logs[-10:]:
            print(json.dumps(log, ensure_ascii=False))
    
    elif cmd == "status_frozen":
        frozen = engine.status_mgr.get_all_frozen()
        print(f"冻结记忆 ({len(frozen)}): {frozen}")
    
    elif cmd == "freeze":
        if len(sys.argv) < 4:
            print("用法: freeze <memory_id> <reason>")
            return
        engine.status_mgr.freeze(sys.argv[2], sys.argv[3])
        print(f"已冻结: {sys.argv[2]}")
    
    elif cmd == "unfreeze":
        if len(sys.argv) < 3:
            print("用法: unfreeze <memory_id>")
            return
        engine.status_mgr.unfreeze(sys.argv[2])
        print(f"已解冻: {sys.argv[2]}")


if __name__ == "__main__":
    main()
