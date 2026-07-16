#!/usr/bin/env python3
"""
记忆完整性校验与同步脚本
Memory Integrity Check & Sync Script

文档编号: LY-20260622-MI01
版本: v1.0
作者: Nyx 🖤

功能:
1. 计算 MEMORY.md 和 memory/*.md 的 SHA-256 哈希
2. 对比 NAS 和本地版本
3. 按 BOOTSTRAP.md 规则自动同步
4. 检测冲突并告警
"""

import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

# 配置
WORKSPACE = Path(os.environ.get("NYX_WORKSPACE", "/Users/apple/.qclaw/workspace-agent-1a681d03"))
NAS_PATH = os.environ.get("NYX_NAS_PATH", "/tmp/nas_mount")
NAS_MEMORY_PATH = Path(NAS_PATH) / "qclaw/nodes/nyx"

# 本地路径
LOCAL_MEMORY = WORKSPACE / "MEMORY.md"
LOCAL_MEMORY_DIR = WORKSPACE / "memory"

# 哈希记录文件
HASH_RECORD = WORKSPACE / "memory_hashes.json"


def calculate_hash(file_path: Path) -> str:
    """计算文件的 SHA-256 哈希"""
    if not file_path.exists():
        return ""
    
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def get_all_memory_files() -> dict:
    """获取所有记忆文件及其哈希"""
    files = {}
    
    # MEMORY.md
    if LOCAL_MEMORY.exists():
        files["MEMORY.md"] = {
            "path": str(LOCAL_MEMORY),
            "hash": calculate_hash(LOCAL_MEMORY),
            "size": LOCAL_MEMORY.stat().st_size,
            "mtime": datetime.fromtimestamp(LOCAL_MEMORY.stat().st_mtime).isoformat()
        }
    
    # memory/*.md
    if LOCAL_MEMORY_DIR.exists():
        for md_file in LOCAL_MEMORY_DIR.glob("*.md"):
            files[f"memory/{md_file.name}"] = {
                "path": str(md_file),
                "hash": calculate_hash(md_file),
                "size": md_file.stat().st_size,
                "mtime": datetime.fromtimestamp(md_file.stat().st_mtime).isoformat()
            }
    
    return files


def load_hash_record() -> dict:
    """加载上次的哈希记录"""
    if HASH_RECORD.exists():
        with open(HASH_RECORD, "r") as f:
            return json.load(f)
    return {"last_check": None, "files": {}}


def save_hash_record(record: dict):
    """保存哈希记录"""
    record["last_check"] = datetime.now().isoformat()
    with open(HASH_RECORD, "w") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)


def check_integrity() -> dict:
    """检查记忆完整性"""
    current_files = get_all_memory_files()
    saved_record = load_hash_record()
    
    result = {
        "timestamp": datetime.now().isoformat(),
        "total_files": len(current_files),
        "tampered": [],
        "new_files": [],
        "missing_files": [],
        "status": "ok"
    }
    
    saved_files = saved_record.get("files", {})
    
    for file_name, file_info in current_files.items():
        if file_name not in saved_files:
            result["new_files"].append(file_name)
        elif file_info["hash"] != saved_files[file_name].get("hash"):
            result["tampered"].append({
                "file": file_name,
                "old_hash": saved_files[file_name].get("hash"),
                "new_hash": file_info["hash"]
            })
    
    for file_name in saved_files:
        if file_name not in current_files:
            result["missing_files"].append(file_name)
    
    if result["tampered"] or result["missing_files"]:
        result["status"] = "warning"
    
    return result


def mount_nas() -> bool:
    """挂载 NAS"""
    nas_mount = Path(NAS_PATH)
    if nas_mount.exists() and any(nas_mount.iterdir()):
        return True  # 已挂载
    
    nas_mount.mkdir(parents=True, exist_ok=True)
    
    # 尝试挂载 SMB
    import subprocess
    try:
        cmd = f'mount_smbfs "//anima:animastellar@100.107.156.33/SOFTWARE" {NAS_PATH}'
        result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10)
        return result.returncode == 0
    except Exception as e:
        print(f"挂载 NAS 失败: {e}")
        return False


def sync_from_nas() -> dict:
    """从 NAS 同步记忆到本地"""
    result = {
        "timestamp": datetime.now().isoformat(),
        "synced": [],
        "conflicts": [],
        "status": "ok"
    }
    
    if not mount_nas():
        result["status"] = "nas_unavailable"
        return result
    
    # 同步 MEMORY.md
    nas_memory = NAS_MEMORY_PATH / "MEMORY.md"
    if nas_memory.exists():
        nas_hash = calculate_hash(nas_memory)
        local_hash = calculate_hash(LOCAL_MEMORY) if LOCAL_MEMORY.exists() else ""
        
        if nas_hash != local_hash:
            if local_hash:  # 本地有内容，可能冲突
                # 保存冲突副本
                conflict_file = WORKSPACE / f"MEMORY_conflict_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                shutil.copy(LOCAL_MEMORY, conflict_file)
                result["conflicts"].append({
                    "file": "MEMORY.md",
                    "local_saved_to": str(conflict_file)
                })
            
            # 用 NAS 版本覆盖
            shutil.copy(nas_memory, LOCAL_MEMORY)
            result["synced"].append("MEMORY.md")
    
    # 同步 memory/*.md
    nas_memory_dir = NAS_MEMORY_PATH / "memory"
    if nas_memory_dir.exists():
        LOCAL_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        
        for nas_file in nas_memory_dir.glob("*.md"):
            local_file = LOCAL_MEMORY_DIR / nas_file.name
            
            nas_hash = calculate_hash(nas_file)
            local_hash = calculate_hash(local_file) if local_file.exists() else ""
            
            if nas_hash != local_hash:
                shutil.copy(nas_file, local_file)
                result["synced"].append(f"memory/{nas_file.name}")
    
    return result


def sync_to_nas() -> dict:
    """从本地同步记忆到 NAS"""
    result = {
        "timestamp": datetime.now().isoformat(),
        "synced": [],
        "status": "ok"
    }
    
    if not mount_nas():
        result["status"] = "nas_unavailable"
        return result
    
    # 同步 MEMORY.md
    if LOCAL_MEMORY.exists():
        nas_memory = NAS_MEMORY_PATH / "MEMORY.md"
        nas_memory.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(LOCAL_MEMORY, nas_memory)
        result["synced"].append("MEMORY.md")
    
    # 同步 memory/*.md
    if LOCAL_MEMORY_DIR.exists():
        nas_memory_dir = NAS_MEMORY_PATH / "memory"
        nas_memory_dir.mkdir(parents=True, exist_ok=True)
        
        for local_file in LOCAL_MEMORY_DIR.glob("*.md"):
            nas_file = nas_memory_dir / local_file.name
            shutil.copy(local_file, nas_file)
            result["synced"].append(f"memory/{local_file.name}")
    
    return result


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Nyx 记忆完整性校验与同步")
    parser.add_argument("action", choices=["check", "sync-from-nas", "sync-to-nas", "update-hash"],
                        help="执行的操作")
    args = parser.parse_args()
    
    if args.action == "check":
        result = check_integrity()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        if result["status"] != "ok":
            print("\n⚠️ 警告: 检测到异常")
        
    elif args.action == "sync-from-nas":
        result = sync_from_nas()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        if result["conflicts"]:
            print("\n⚠️ 存在冲突，已保存本地副本")
        
    elif args.action == "sync-to-nas":
        result = sync_to_nas()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    elif args.action == "update-hash":
        current_files = get_all_memory_files()
        save_hash_record({"files": current_files})
        print(f"✅ 已更新 {len(current_files)} 个文件的哈希记录")


if __name__ == "__main__":
    main()
