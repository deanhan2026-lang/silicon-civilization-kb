"""Polaris 统一配置加载"""
import yaml
import os
from pathlib import Path

_cfg_file = Path(__file__).parent / 'config.yaml'
_config = {}
if _cfg_file.exists():
    with open(_cfg_file, encoding='utf-8') as f:
        _config = yaml.safe_load(f)

def get(key: str, default=None):
    """按点号路径读取配置值

    示例:
        get('detector.weights.semantic')  → 0.40
        get('server.port')                → 5051
        get('nonexistent.key', 'fallback') → 'fallback'
    """
    keys = key.split('.')
    val = _config
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k, default)
        else:
            return default
    return val if val is not None else default