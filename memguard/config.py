#!/usr/bin/env python3
"""
MemGuard-GM 配置文件
通过环境变量或配置文件自定义路径
"""
import os
import yaml
from pathlib import Path
from typing import Optional, Any

# ========== YAML 配置加载 ==========
_config = {}
_cfg_file = Path(__file__).parent / 'config.yaml'
if _cfg_file.exists():
    try:
        with open(_cfg_file, encoding='utf-8') as f:
            _config = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"[WARN] 加载 config.yaml 失败: {e}")

def get(key: str, default: Any = None) -> Any:
    """
    支持点号访问配置，如 get('storage.baseline_dir')
    优先级：环境变量 > YAML 配置 > 默认值
    """
    # 1. 检查环境变量（支持 MEMGUARD_BASELINE_DIR 格式）
    env_key = 'MEMGUARD_' + key.upper().replace('.', '_')
    env_val = os.environ.get(env_key)
    if env_val is not None:
        return env_val
    
    # 2. 从 YAML 配置中读取
    keys = key.split('.')
    val = _config
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k, default)
        else:
            return default
    
    return val if val is not None else default

# ========== 存储路径配置 ==========

# 基线存储目录（建议使用只读存储）
# 示例: 
#   Linux/Mac: /mnt/nas/memguard_baseline 或 ~/.memguard/baseline
#   Windows:   Z:\memguard_baseline 或 D:\memguard_baseline
#   云存储:    gs://your-bucket/memguard_baseline (需实现适配器)
BASELINE_DIR = get('storage.baseline_dir', 
    str(Path(__file__).parent.parent / 'memguard_baseline'))

# 记忆文件目录
MEMORY_DIR = get('storage.memory_dir',
    str(Path(__file__).parent.parent / 'memory'))

# 审计日志目录
AUDIT_DIR = get('storage.audit_dir',
    str(Path(__file__).parent.parent / 'audit'))

# 备份目录（可选，用于三副本）
BACKUP_DIR = get('storage.backup_dir',
    str(Path(__file__).parent.parent / 'backup'))

# ========== 安全配置 ==========

# Hash算法选择
HASH_ALGORITHMS = get('security.hash_algorithms', ['sha256', 'blake3'])

# 基线锁定后是否允许解锁（生产环境建议False）
ALLOW_BASELINE_UNLOCK = get('security.allow_baseline_unlock', 'false').lower() == 'true'

# ========== 校验配置 ==========

# 定时校验间隔（秒）
CHECK_INTERVAL_SECONDS = int(get('scheduler.check_interval_seconds', 14400))

# 随机延迟范围（秒），防止时序攻击
RANDOM_DELAY_MAX = int(os.environ.get('MEMGUARD_RANDOM_DELAY', 300))

# ========== 审计配置 ==========

# 单个审计文件最大行数
AUDIT_MAX_LINES = int(os.environ.get('MEMGUARD_AUDIT_MAX_LINES', 100000))

# 审计文件保留数量
AUDIT_FILE_COUNT = int(os.environ.get('MEMGUARD_AUDIT_FILE_COUNT', 10))

# ========== API配置 ==========

API_HOST = get('server.host', '0.0.0.0')
API_PORT = int(get('server.port', 5050))
API_DEBUG = os.environ.get('MEMGUARD_API_DEBUG', 'false').lower() == 'true'

# ========== 日志配置 ==========

LOG_LEVEL = get('logging.level', 'INFO')
AUDIT_LOG_PATH = get('logging.audit_log', './audit/audit.jsonl')
SERVER_LOG_PATH = get('logging.server_log', './memguard/server.log')

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
