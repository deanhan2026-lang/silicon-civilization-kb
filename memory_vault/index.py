"""
Memory Vault - 检索索引层
支持按关键词、标签、分类、优先级检索
"""

import re
from typing import List, Optional
from memory_vault.entry import MemoryEntry, Priority, Category
from memory_vault.store import MemoryStore


class MemoryIndex:
    """内存索引 + 检索"""

    def __init__(self, store: MemoryStore):
        self.store = store
        self._rebuild_inmemory_index()

    def _rebuild_inmemory_index(self):
        """从存储层重建内存索引"""
        self._by_id = {}
        self._by_category = {}
        self._by_priority = {}
        self._by_tag = {}
        self._all_ids = []

        for entry in self.store.list_all(include_archived=False):
            self._all_ids.append(entry.id)
            self._by_id[entry.id] = entry

            # 按 category
            cat = entry.category.value
            self._by_category.setdefault(cat, []).append(entry.id)

            # 按 priority
            pri = entry.priority.value
            self._by_priority.setdefault(pri, []).append(entry.id)

            # 按 tag
            for tag in entry.tags:
                self._by_tag.setdefault(tag.lower(), []).append(entry.id)

    def refresh(self):
        """刷新索引（写入后调用）"""
        self._rebuild_inmemory_index()

    def search(
        self,
        query: Optional[str] = None,
        category: Optional[Category] = None,
        priority_min: Optional[Priority] = None,
        tags: Optional[List[str]] = None,
        include_archived: bool = False,
        limit: int = 50,
    ) -> List[MemoryEntry]:
        """
        检索记忆

        Args:
            query: 关键词（匹配 content 和 body）
            category: 分类过滤
            priority_min: 最低优先级（P0 > P1 > P2）
            tags: 标签列表（全匹配）
            include_archived: 是否包含已归档
            limit: 结果上限
        """
        candidates = set(self._all_ids)

        # 分类过滤
        if category:
            cat_ids = set(self._by_category.get(category.value, []))
            candidates &= cat_ids

        # 优先级过滤
        if priority_min:
            min_order = {"P0": 0, "P1": 1, "P2": 2}[priority_min.value]
            valid_ids = []
            for pid in candidates:
                entry = self._by_id.get(pid)
                if entry:
                    p_order = {"P0": 0, "P1": 1, "P2": 2}[entry.priority.value]
                    if p_order <= min_order:
                        valid_ids.append(pid)
            candidates = set(valid_ids)

        # 标签过滤
        if tags:
            tag_ids = None
            for t in tags:
                t_ids = set(self._by_tag.get(t.lower(), []))
                tag_ids = tag_ids & t_ids if tag_ids else t_ids
            if tag_ids:
                candidates &= tag_ids

        # 关键词过滤
        if query:
            q_lower = query.lower()
            matched = []
            for eid in candidates:
                entry = self._by_id.get(eid)
                if entry:
                    text = (entry.content + " " + (entry.body or "")).lower()
                    if q_lower in text:
                        matched.append(entry)
            results = matched
        else:
            results = [self._by_id[eid] for eid in candidates if eid in self._by_id]

        # 归档过滤
        if not include_archived:
            results = [e for e in results if not e.meta.is_archived]

        # 优先级排序（P0 > P1 > P2），再按访问频率
        def score(e: MemoryEntry):
            p_order = {"P0": 0, "P1": 1, "P2": 2}[e.priority.value]
            return (p_order, -(e.meta.access_count or 0))

        results.sort(key=score)
        return results[:limit]

    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        """直接获取"""
        return self._by_id.get(entry_id)

    def recent(self, limit: int = 10) -> List[MemoryEntry]:
        """最近访问的记忆"""
        all_entries = list(self._by_id.values())
        valid = [e for e in all_entries if e.meta.last_accessed and not e.meta.is_archived]
        valid.sort(key=lambda e: e.meta.last_accessed or "", reverse=True)
        return valid[:limit]

    def hot(self, limit: int = 10) -> List[MemoryEntry]:
        """最高访问频率的记忆"""
        all_entries = list(self._by_id.values())
        valid = [e for e in all_entries if not e.meta.is_archived]
        valid.sort(key=lambda e: e.meta.access_count or 0, reverse=True)
        return valid[:limit]
