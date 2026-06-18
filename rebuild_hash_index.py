#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重建 hash_index.json - 只保留实际存在的文件
"""
import os
import json
import hashlib
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).parent.resolve()
HASH_INDEX = REPO_ROOT / "hash_index.json"

# 要扫描的目录（相对于仓库根目录）
SCAN_DIRS = ["concept", "entity", "event", "rule", "artifact", "value"]

def compute_file_hash(filepath: Path) -> str:
    """计算文件 SHA256 哈希"""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def rebuild_index():
    """重建索引"""
    new_index = {}
    
    for dir_name in SCAN_DIRS:
        dir_path = REPO_ROOT / dir_name
        if not dir_path.exists():
            print(f"[跳过] {dir_name}/ 目录不存在")
            continue
        
        for md_file in dir_path.glob("*.md"):
            # 相对路径（在 hash_index.json 中的键格式）
            rel_path = f"{dir_name}\\{md_file.name}"
            
            # 计算哈希
            file_hash = compute_file_hash(md_file)
            stat = md_file.stat()
            
            new_index[rel_path] = {
                "hash": file_hash,
                "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "size": stat.st_size
            }
            print(f"[添加] {rel_path}")
    
    # 写回文件
    HASH_INDEX.write_text(json.dumps(new_index, ensure_ascii=False, indent=2), encoding="utf-8")
    
    print(f"\n[完成] 共索引 {len(new_index)} 个文件")
    print(f"   输出: {HASH_INDEX}")

if __name__ == "__main__":
    rebuild_index()
