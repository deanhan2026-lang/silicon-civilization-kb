"""
Memory Vault - 检索索引层
支持按关键词、标签、分类、优先级检索
支持语义检索（TF-IDF + jieba）
"""

import re
from typing import List, Optional, Tuple
from memory_vault.entry import MemoryEntry, Priority, Category
from memory_vault.store import MemoryStore
from memory_vault.semantic_search import SemanticSearch


class MemoryIndex:
    """内存索引 + 检索（含语义检索）"""

    def __init__(self, store: MemoryStore, use_semantic: bool = True):
        self.store = store
        self.use_semantic = use_semantic
        self.semantic_search = SemanticSearch() if use_semantic else None
        self._rebuild_inmemory_index()

    def _rebuild_inmemory_index(self):
        """从存储层重建内存索引"""
        self._by_id = {}
        self._by_category = {}
        self._by_priority = {}
        self._by_tag = {}
        self._all_ids = []

        # 重建语义索引
        if self.semantic_search:
            self.semantic_search = SemanticSearch()

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

            # 语义索引
            if self.semantic_search:
                self.semantic_search.index(entry)

        # 重建语义索引的 TF-IDF
        if self.semantic_search:
            self.semantic_search.rebuild_index()

    def add_to_index(self, entry: MemoryEntry):
        """增量添加一条到内存索引"""
        self._all_ids.append(entry.id)
        self._by_id[entry.id] = entry
        cat = entry.category.value
        self._by_category.setdefault(cat, []).append(entry.id)
        pri = entry.priority.value
        self._by_priority.setdefault(pri, []).append(entry.id)
        for tag in entry.tags:
            self._by_tag.setdefault(tag.lower(), []).append(entry.id)
        
        # 语义索引
        if self.semantic_search:
            self.semantic_search.index(entry)

    def remove_from_index(self, entry_id: str):
        """从内存索引移除一条"""
        entry = self._by_id.pop(entry_id, None)
        if entry:
            self._all_ids = [i for i in self._all_ids if i != entry_id]
            cat = entry.category.value
            if cat in self._by_category:
                self._by_category[cat] = [i for i in self._by_category[cat] if i != entry_id]
            pri = entry.priority.value
            if pri in self._by_priority:
                self._by_priority[pri] = [i for i in self._by_priority[pri] if i != entry_id]
            for tag in entry.tags:
                key = tag.lower()
                if key in self._by_tag:
                    self._by_tag[key] = [i for i in self._by_tag[key] if i != entry_id]

    def update_in_index(self, entry: MemoryEntry):
        """更新索引中已存在的条目"""
        if entry.id in self._by_id:
            self._by_id[entry.id] = entry
        else:
            self.add_to_index(entry)

    def refresh(self):
        """全量重建索引（用于初始化或数据损坏后恢复）"""
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

    def semantic_search_query(
        self, query: str, top_k: int = 10, category_filter: Optional[str] = None
    ) -> List[Tuple[MemoryEntry, float]]:
        """
        语义检索（TF-IDF + jieba）
        
        Args:
            query: 查询文本
            top_k: 返回前 K 个结果
            category_filter: 分类过滤（可选）
        
        Returns:
            List of (entry, score) tuples
        """
        if not self.semantic_search:
            return []
        return self.semantic_search.search(query, top_k, category_filter)

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
