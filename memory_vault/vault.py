"""
Memory Vault - 统一API门面
"""

from common.logger import get_logger

logger = get_logger(__name__)

import os
from pathlib import Path
from typing import List, Optional, Dict
from memory_vault.entry import MemoryEntry, Priority, Category, SourceType, Confidence, Source, entry_id
from memory_vault.store import MemoryStore
from memory_vault.index import MemoryIndex


class MemoryVault:
    """
    硅基记忆系统统一入口

    用法示例：
        vault = MemoryVault("./memory_vault")
        vault.remember("今天完成了GitHub Agent集成", priority=P1, category="project", tags=["github"])
        results = vault.recall("GitHub Agent")
        vault.run_decay_cycle()
        vault.stat()
    """

    def __init__(self, base_path: str):
        self.base = Path(base_path)
        self.store = MemoryStore(str(base_path))
        self.index = MemoryIndex(self.store)
        logger.info(f"MemoryVault initialized, base={base_path}")

    # ---- 记得住 ----

    def remember(
        self,
        content: str,
        priority: Priority = Priority.P2,
        category: Category = Category.DAILY,
        tags: Optional[List[str]] = None,
        body: Optional[str] = None,
        source_type: SourceType = SourceType.CONVERSATION,
        confidence: Confidence = Confidence.MEDIUM,
        attribution: str = "Nyx",
    ) -> str:
        """
        存入一条记忆

        Returns:
            记忆条目ID
        """
        entry = MemoryEntry(
            content=content,
            priority=priority,
            category=category,
            tags=tags or [],
            body=body,
            source=Source(type=source_type, confidence=confidence, attribution=attribution),
        )
        eid = self.store.add(entry)
        self.index.add_to_index(entry)
        logger.info(f"记忆已存储: id={eid[:8]}..., priority={priority.value}, category={category.value}, tags={tags}")
        return eid

    # ---- 好调用 ----

    def recall(
        self,
        query: Optional[str] = None,
        category: Optional[Category] = None,
        priority_min: Optional[Priority] = None,
        tags: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[MemoryEntry]:
        """
        检索记忆
        """
        results = self.index.search(
            query=query,
            category=category,
            priority_min=priority_min,
            tags=tags,
            limit=limit,
        )
        logger.debug(f"检索记忆: query={query}, category={category}, results={len(results)}条")
        return results

    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        """直接获取一条记忆"""
        entry = self.index.get(entry_id)
        if entry:
            entry.touch()
            self.store.update(entry)
            self.index.update_in_index(entry)
            logger.debug(f"获取记忆: id={entry_id[:8]}..., content={entry.content[:50]}...")
        else:
            logger.warning(f"记忆未找到: id={entry_id[:8]}...")
        return entry

    def recent(self, limit: int = 10) -> List[MemoryEntry]:
        """最近访问的记忆"""
        results = self.index.recent(limit)
        logger.debug(f"获取最近记忆: {len(results)}条")
        return results

    def hot(self, limit: int = 10) -> List[MemoryEntry]:
        """最高频访问的记忆"""
        results = self.index.hot(limit)
        logger.debug(f"获取热点记忆: {len(results)}条")
        return results

    # ---- 好调用：元信息 ----

    def stat(self) -> Dict:
        """存储统计"""
        s = self.store.stat()
        logger.debug(f"记忆存储统计: {s}")
        return s

    # ---- 可遗忘：衰减 + 归档 ----

    def run_decay_cycle(self) -> Dict:
        """
        执行一次遗忘调度
        - 所有P1/P2条目衰减
        - 达到归档条件的条目自动归档
        Returns:
            {archived: [ids], decayed: count}
        """
        archived_ids = []
        decayed = 0

        for entry in self.store.list_all(include_archived=False):
            entry.apply_decay()

            if entry.should_archive():
                self.store.archive(entry.id)
                self.index.remove_from_index(entry.id)
                archived_ids.append(entry.id)
            else:
                self.store.update(entry)
                self.index.update_in_index(entry)
            decayed += 1

        logger.info(f"遗忘调度完成: 归档 {len(archived_ids)} 条, 衰减 {decayed} 条")
        return {"archived": archived_ids, "decayed": decayed}

    def archive(self, entry_id: str) -> bool:
        """手动归档一条记忆"""
        result = self.store.archive(entry_id)
        if result:
            self.index.remove_from_index(entry_id)
            logger.info(f"记忆已归档: id={entry_id[:8]}...")
        else:
            logger.warning(f"记忆归档失败: id={entry_id[:8]}...")
        return result

    # ---- 一致性检测 ----

    def check_consistency(self) -> List[Dict]:
        """
        检测同category下的矛盾条目
        当前实现：同category下相同标签的条目，列出供人工判断
        """
        from collections import defaultdict
        conflicts = []

        # 按 category + tags 分组
        groups = defaultdict(list)
        for entry in self.store.list_all(include_archived=True):
            if entry.meta.is_archived:
                continue
            key = (entry.category.value, tuple(sorted(entry.tags)))
            groups[key].append(entry)

        for (cat, tags), entries in groups.items():
            if len(entries) > 3:
                # 策略：同一话题超过3条，提示可能冗余
                conflicts.append({
                    "type": "potential_redundancy",
                    "category": cat,
                    "tags": list(tags),
                    "count": len(entries),
                    "entries": [
                        {"id": e.id, "content": e.content[:80], "created": e.meta.created_at}
                        for e in entries
                    ],
                })

        if conflicts:
            logger.warning(f"一致性检测发现 {len(conflicts)} 个潜在冗余组")
        else:
            logger.info("一致性检测通过，无冗余发现")
        return conflicts

    # ---- 来源追溯 ----

    def trace(self, entry_id: str) -> Optional[Dict]:
        """追溯一条记忆的来源"""
        entry = self.store.get(entry_id)
        if not entry:
            logger.warning(f"追溯失败: 记忆未找到 id={entry_id[:8]}...")
            return None
        logger.debug(f"追溯记忆来源: id={entry_id[:8]}..., type={entry.source.type.value}, attribution={entry.source.attribution}")
        return {
            "id": entry.id,
            "content": entry.content[:100],
            "source": {
                "type": entry.source.type.value,
                "confidence": entry.source.confidence.value,
                "attribution": entry.source.attribution,
            },
            "meta": {
                "created_at": entry.meta.created_at,
                "updated_at": entry.meta.updated_at,
                "access_count": entry.meta.access_count,
                "decay_score": entry.meta.decay_score,
                "is_archived": entry.meta.is_archived,
                "is_deprecated": entry.meta.is_deprecated,
            },
        }
