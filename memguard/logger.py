#!/usr/bin/env python3
"""
MemGuard 统一日志模块 — JSON 结构化日志
"""
import json
import logging
import sys
from pathlib import Path
from typing import Optional


class JsonFormatter(logging.Formatter):
    """JSON 格式化器"""
    
    def format(self, record):
        log_obj = {
            "timestamp": self.formatTime(record, "%Y-%m-%d %H:%M:%S"),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
        }
        
        # 添加额外字段
        if hasattr(record, "extra"):
            log_obj.update(record.extra)
        
        # 添加异常信息
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_obj, ensure_ascii=False)


def get_logger(name: str, log_file: Optional[str] = None, level: int = logging.INFO):
    """
    获取日志记录器
    
    Args:
        name: 日志记录器名称
        log_file: 日志文件路径（可选）
        level: 日志级别（默认 INFO）
    
    Returns:
        logging.Logger: 配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 避免重复添加 handler
    if not logger.handlers:
        # 控制台输出
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        
        # 文件输出（如果指定）
        if log_file:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(JsonFormatter())
            logger.addHandler(fh)
    
    return logger
