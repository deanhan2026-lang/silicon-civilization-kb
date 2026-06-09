#!/usr/bin/env python3
"""
MemGuard-GM 配置文件
通过环境变量或配置文件自定义路径
"""
import os
from pathlib import Path

# ========== 存储路径配置 ==========

# 基线存储目录（建议使用只读存储）
# 示例: 
#   Linux/Mac: /mnt/nas/memguard_baseline 或 ~/.memguard/baseline
#   Windows:   Z:\memguard_baseline 或 D:\memguard_baseline
#   云存储:    gs://your-bucket/memguard_baseline (需实现适配器)
BASELINE_DIR = os.environ.get('MEMGUARD_BASELINE_DIR', 
    str(Path(__file__).parent.parent / 'memguard_baseline'))

# 记忆文件目录
MEMORY_DIR = os.environ.get('MEMGUARD_MEMORY_DIR',
    str(Path(__file__).parent.parent / 'memory'))

# 审计日志目录
AUDIT_DIR = os.environ.get('MEMGUARD_AUDIT_DIR',
    str(Path(__file__).parent.parent / 'audit'))

# 备份目录（可选，用于三副本）
BACKUP_DIR = os.environ.get('MEMGUARD_BACKUP_DIR',
    str(Path(__file__).parent.parent / 'backup'))

# ========== 安全配置 ==========

# Hash算法选择
HASH_ALGORITHMS = ['sha256', 'blake3']  # 可扩展支持更多算法

# 基线锁定后是否允许解锁（生产环境建议False）
ALLOW_BASELINE_UNLOCK = os.environ.get('MEMGUARD_ALLOW_UNLOCK', 'false').lower() == 'true'

# ========== 校验配置 ==========

# 定时校验间隔（秒）
CHECK_INTERVAL_SECONDS = int(os.environ.get('MEMGUARD_CHECK_INTERVAL', 14400))  # 默认4小时

# 随机延迟范围（秒），防止时序攻击
RANDOM_DELAY_MAX = int(os.environ.get('MEMGUARD_RANDOM_DELAY', 300))  # 默认0-5分钟

# ========== 审计配置 ==========

# 单个审计文件最大行数
AUDIT_MAX_LINES = int(os.environ.get('MEMGUARD_AUDIT_MAX_LINES', 100000))

# 审计文件保留数量
AUDIT_FILE_COUNT = int(os.environ.get('MEMGUARD_AUDIT_FILE_COUNT', 10))

# ========== API配置 ==========

API_HOST = os.environ.get('MEMGUARD_API_HOST', '0.0.0.0')
API_PORT = int(os.environ.get('MEMGUARD_API_PORT', 5050))
API_DEBUG = os.environ.get('MEMGUARD_API_DEBUG', 'false').lower() == 'true'

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
