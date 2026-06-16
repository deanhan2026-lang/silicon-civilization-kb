"""
Memory Vault - 存储层
负责记忆条目的持久化
"""

import json
import os
from pathlib import Path
from typing import Optional, List, Dict
from memory_vault.entry import MemoryEntry


class MemoryStore:
    """JSON文件存储（带内存缓存）"""

    def __init__(self, base_path: str):
        self.base = Path(base_path)
        self.entries_dir = self.base / "entries"
        self.archive_dir = self.base / "archive"
        self.index_file = self.base / "index.json"
        self._cache: Dict[str, Optional[MemoryEntry]] = {}
        self._idx_cache: Optional[dict] = None   # in-memory index cache
        self._ensure_dirs()

    def _ensure_dirs(self):
        self.entries_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        if not self.index_file.exists():
            self._save_index({})

    # ---- 索引管理 ----

    def _load_index(self) -> dict:
        # 先查内存缓存，避免重复磁盘IO
        if self._idx_cache is not None:
            return self._idx_cache
        try:
            with open(self.index_file, "r", encoding="utf-8") as f:
                self._idx_cache = json.load(f)
                return self._idx_cache
        except (FileNotFoundError, json.JSONDecodeError):
            self._idx_cache = {}
            return {}

    def _save_index(self, index: dict):
        self._idx_cache = index
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

    def _update_index(self, entry: MemoryEntry, op: str = "add"):
        index = self._load_index()  # 走内存缓存，无磁盘IO
        if op == "add" or op == "update":
            index[entry.id] = {
                "category": entry.category.value,
                "priority": entry.priority.value,
                "tags": entry.tags,
                "created_at": entry.meta.created_at,
                "is_archived": entry.meta.is_archived,
                "is_deprecated": entry.meta.is_deprecated,
                "decay_score": entry.meta.decay_score,
                "access_count": entry.meta.access_count,
            }
        elif op == "delete":
            index.pop(entry.id, None)
        self._save_index(index)

    # ---- 核心操作 ----

    def add(self, entry: MemoryEntry) -> str:
        """存入一条记忆，返回ID"""
        path = self._entry_path(entry.id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry.to_dict(), f, ensure_ascii=False, indent=2)
        self._cache[entry.id] = entry
        self._update_index(entry, "add")
        return entry.id

    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        """按ID读取一条记忆（带缓存）"""
        if entry_id in self._cache:
            return self._cache[entry_id]
        path = self._entry_path(entry_id)
        if not path.exists():
            self._cache[entry_id] = None
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            entry = MemoryEntry.from_dict(d)
            self._cache[entry_id] = entry
            return entry
        except (json.JSONDecodeError, KeyError):
            self._cache[entry_id] = None
            return None

    def update(self, entry: MemoryEntry):
        """更新一条记忆"""
        entry.meta.updated_at = entry.meta.updated_at
        path = self._entry_path(entry.id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry.to_dict(), f, ensure_ascii=False, indent=2)
        self._cache[entry.id] = entry
        self._update_index(entry, "update")

    def delete(self, entry_id: str) -> bool:
        """删除一条记忆"""
        path = self._entry_path(entry_id)
        if path.exists():
            path.unlink()
            self._cache.pop(entry_id, None)
            self._update_index(MemoryEntry(content="", id=entry_id), "delete")
            return True
        return False

    def list_all(self, include_archived: bool = False) -> List[MemoryEntry]:
        """列出所有记忆（使用缓存减少文件IO）"""
        results = []
        for eid in self._load_index().keys():
            entry = self.get(eid)  # 走缓存
            if entry and (include_archived or not entry.meta.is_archived):
                results.append(entry)
        return results

    def list_by_category(self, category, include_archived=False) -> List[MemoryEntry]:
        return [e for e in self.list_all(include_archived)
                if e.category.value == category.value]

    def list_by_priority(self, priority, include_archived=False) -> List[MemoryEntry]:
        return [e for e in self.list_all(include_archived)
                if e.priority.value == priority.value]

    def archive(self, entry_id: str) -> bool:
        """归档一条记忆（移动到archive目录）"""
        entry = self.get(entry_id)
        if not entry:
            return False
        entry.meta.is_archived = True
        entry.meta.updated_at = entry.meta.updated_at

        # 写入 archive
        arch_path = self.archive_dir / f"{entry_id}.json"
        with open(arch_path, "w", encoding="utf-8") as f:
            json.dump(entry.to_dict(), f, ensure_ascii=False, indent=2)

        # 从 active 目录删除
        active_path = self._entry_path(entry_id)
        if active_path.exists():
            active_path.unlink()

        self._update_index(entry, "update")
        return True

    def _entry_path(self, entry_id: str) -> Path:
        return self.entries_dir / f"{entry_id}.json"

    # ---- 统计 ----

    def stat(self) -> dict:
        """返回存储统计"""
        index = self._load_index()
        total = len(index)
        by_priority = {"P0": 0, "P1": 0, "P2": 0}
        by_category = {}
        archived = 0
        total_access = 0

        for eid, info in index.items():
            p = info.get("priority", "P2")
            by_priority[p] = by_priority.get(p, 0) + 1
            cat = info.get("category", "daily")
            by_category[cat] = by_category.get(cat, 0) + 1
            if info.get("is_archived"):
                archived += 1
            total_access += info.get("access_count", 0)

        return {
            "total": total,
            "active": total - archived,
            "archived": archived,
            "by_priority": by_priority,
            "by_category": by_category,
            "total_access": total_access,
        }
