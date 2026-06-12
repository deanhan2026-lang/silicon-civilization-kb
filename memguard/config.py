#!/usr/bin/env python3
"""
MemGuard-GM 配置文件
通过环境变量或配置文件自定义路径
优先级：环境变量 > 根 config.yaml > 模块 config.yaml > 默认值
"""
import os
import yaml
from pathlib import Path
from typing import Optional, Any


def _load_yaml(path: Path) -> dict:
    """安全加载 YAML 配置文件"""
    if path.exists():
        try:
            with open(path, encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"[WARN] 加载 {path} 失败: {e}")
    return {}


# ========== 配置加载（根 config.yaml + 模块 config.yaml 合并）==========
_repo_root = Path(__file__).parent.parent
_root_cfg   = _load_yaml(_repo_root / 'config.yaml')                          # 根统一配置
_mod_cfg    = _load_yaml(Path(__file__).parent / 'config.yaml')                # 模块私有配置

# 路径常量（在 get() 初始化前定义，避免循环引用）
_REPO_ROOT = _repo_root
_MODULE_DIR = Path(__file__).parent


def _get(key: str, default: Any = None) -> Any:
    """内部获取逻辑，支持三层回退：环境变量 > 模块配置 > 根配置 > 默认值"""
    # 1. 环境变量（最高优先级）
    env_key = 'MEMGUARD_' + key.upper().replace('.', '_')
    env_val = os.environ.get(env_key)
    if env_val is not None:
        return env_val

    # 2. 从模块私有配置读取（优先级高于根配置）
    keys = key.split('.')
    val = _mod_cfg
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k, None)
            if val is None:
                break
        else:
            val = None
            break
    if val is not None:
        return val

    # 3. 根统一配置回退
    val = _root_cfg
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k, None)
            if val is None:
                break
        else:
            val = None
            break
    return val if val is not None else default


def get(key: str, default: Any = None) -> Any:
    """
    支持点号访问配置，如 get('storage.baseline_dir')
    优先级：环境变量 > 模块配置 > 根统一配置 > 默认值
    """
    return _get(key, default)


# ========== 存储路径配置（使用常量避免循环调用）==========

BASELINE_DIR = _get('storage.baseline_dir',
    str(_REPO_ROOT / 'memguard_baseline'))
MEMORY_DIR   = _get('storage.memory_dir',
    str(_REPO_ROOT / 'memory'))
AUDIT_DIR    = _get('storage.audit_dir',
    str(_REPO_ROOT / 'audit'))
BACKUP_DIR   = _get('storage.backup_dir',
    str(_REPO_ROOT / 'backup'))

# ========== 安全配置 ==========
HASH_ALGORITHMS = _get('security.hash_algorithms', ['sha256', 'blake3'])
ALLOW_BASELINE_UNLOCK = str(_get('security.allow_baseline_unlock', 'false')).lower() == 'true'

# ========== 校验配置 ==========
CHECK_INTERVAL_SECONDS = int(_get('scheduler.check_interval_seconds', 14400))
RANDOM_DELAY_MAX = int(os.environ.get('MEMGUARD_RANDOM_DELAY', 300))

# ========== 审计配置 ==========
AUDIT_MAX_LINES  = int(os.environ.get('MEMGUARD_AUDIT_MAX_LINES', 100000))
AUDIT_FILE_COUNT = int(os.environ.get('MEMGUARD_AUDIT_FILE_COUNT', 10))

# ========== API配置 ==========
API_HOST = _get('server.host', '0.0.0.0')
API_PORT = int(_get('server.port', 5050))
API_DEBUG = os.environ.get('MEMGUARD_API_DEBUG', 'false').lower() == 'true'

# ========== 日志配置 ==========
LOG_LEVEL       = _get('logging.level', 'INFO')
AUDIT_LOG_PATH = _get('logging.audit_log', './audit/audit.jsonl')
SERVER_LOG_PATH = _get('logging.memguard_log', './logs/memguard.log')

# ========== 跨平台路径工具 ==========
def ensure_dir(path: str) -> Path:
    """确保目录存在"""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p

def get_platform_name() -> str:
    """获取平台名称"""
    import platform
    return f"{platform.system().lower()}_{platform.machine().lower()}"
