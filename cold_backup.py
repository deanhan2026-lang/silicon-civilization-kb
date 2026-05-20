#!/usr/bin/env python3
"""
cold_backup.py - 知识库冷备份快照脚本

功能：
- 每日定时打包知识库目录
- 只读快照，独立存储隔离
- 保留最近7天备份，自动清理旧备份

作者：Nyx
日期：2026-05-20
"""

import os
import sys
import json
import tarfile
import hashlib
from pathlib import Path
from datetime import datetime, timedelta

# 配置
KNOWLEDGE_BASE_DIR = Path(os.path.expanduser("~/.qclaw/workspace-agent-d9479bde/knowledge-base"))
BACKUP_DIR = Path(os.path.expanduser("~/.qclaw/backups/knowledge-base"))
BACKUP_INDEX = BACKUP_DIR / "backup_index.json"
RETENTION_DAYS = 7


def compute_dir_hash(directory: Path) -> str:
    """计算目录内容的综合哈希（用于验证备份完整性）"""
    sha256 = hashlib.sha256()
    
    for filepath in sorted(directory.rglob("*.md")):
        rel_path = str(filepath.relative_to(directory))
        sha256.update(rel_path.encode("utf-8"))
        with open(filepath, "rb") as f:
            sha256.update(f.read())
    
    return sha256.hexdigest()[:16]


def create_backup() -> dict:
    """创建冷备份快照"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"kb_backup_{timestamp}.tar.gz"
    backup_path = BACKUP_DIR / backup_filename
    
    # 确保备份目录存在
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    # 计算源目录哈希
    source_hash = compute_dir_hash(KNOWLEDGE_BASE_DIR)
    
    # 统计文件数量
    file_count = len(list(KNOWLEDGE_BASE_DIR.rglob("*.md")))
    
    # 创建tar.gz压缩包
    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(KNOWLEDGE_BASE_DIR, arcname="knowledge-base")
    
    # 获取备份文件大小
    backup_size = backup_path.stat().st_size
    
    # 计算备份文件哈希（用于验证传输完整性）
    backup_file_hash = hashlib.sha256()
    with open(backup_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            backup_file_hash.update(chunk)
    backup_hash = backup_file_hash.hexdigest()[:16]
    
    # 记录备份信息
    backup_info = {
        "timestamp": timestamp,
        "filename": backup_filename,
        "path": str(backup_path),
        "size_bytes": backup_size,
        "size_mb": round(backup_size / (1024 * 1024), 2),
        "file_count": file_count,
        "source_hash": source_hash,
        "backup_hash": backup_hash,
        "status": "ok"
    }
    
    # 更新备份索引
    update_backup_index(backup_info)
    
    return backup_info


def update_backup_index(backup_info: dict):
    """更新备份索引文件"""
    index = load_backup_index()
    index["backups"].append(backup_info)
    
    # 清理过期备份
    cutoff_date = datetime.now() - timedelta(days=RETENTION_DAYS)
    index["backups"] = [
        b for b in index["backups"]
        if datetime.strptime(b["timestamp"], "%Y%m%d_%H%M%S") > cutoff_date
    ]
    
    index["last_updated"] = datetime.now().isoformat()
    index["total_backups"] = len(index["backups"])
    
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def load_backup_index() -> dict:
    """加载备份索引"""
    if BACKUP_INDEX.exists():
        try:
            return json.loads(BACKUP_INDEX.read_text(encoding="utf-8"))
        except:
            pass
    
    return {
        "backups": [],
        "last_updated": None,
        "total_backups": 0,
        "retention_days": RETENTION_DAYS
    }


def cleanup_old_backups():
    """清理过期的备份文件"""
    index = load_backup_index()
    cutoff_date = datetime.now() - timedelta(days=RETENTION_DAYS)
    
    cleaned = []
    for backup_info in index.get("backups", []):
        timestamp = datetime.strptime(backup_info["timestamp"], "%Y%m%d_%H%M%S")
        if timestamp < cutoff_date:
            backup_path = Path(backup_info["path"])
            if backup_path.exists():
                backup_path.unlink()
                cleaned.append(backup_info["filename"])
    
    if cleaned:
        # 更新索引
        index["backups"] = [
            b for b in index["backups"]
            if datetime.strptime(b["timestamp"], "%Y%m%d_%H%M%S") > cutoff_date
        ]
        index["total_backups"] = len(index["backups"])
        BACKUP_INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    
    return cleaned


def list_backups() -> list:
    """列出所有备份"""
    index = load_backup_index()
    return index.get("backups", [])


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="知识库冷备份工具")
    parser.add_argument("action", choices=["create", "list", "cleanup"], help="执行的操作")
    args = parser.parse_args()
    
    if args.action == "create":
        print("正在创建备份...")
        info = create_backup()
        print(f"备份完成: {info['filename']}")
        print(f"  大小: {info['size_mb']} MB")
        print(f"  文件数: {info['file_count']}")
        print(f"  路径: {info['path']}")
        
    elif args.action == "list":
        backups = list_backups()
        if not backups:
            print("暂无备份")
        else:
            print(f"共 {len(backups)} 个备份:")
            for b in backups[-10:]:  # 最近10个
                print(f"  {b['timestamp']}: {b['size_mb']}MB, {b['file_count']} files")
    
    elif args.action == "cleanup":
        cleaned = cleanup_old_backups()
        if cleaned:
            print(f"已清理 {len(cleaned)} 个过期备份:")
            for f in cleaned:
                print(f"  - {f}")
        else:
            print("无需清理")
