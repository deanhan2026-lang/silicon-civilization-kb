"""
Memory Vault - 去重与存储压缩
"""

import hashlib
import json
import uuid
from pathlib import Path
from typing import Optional, List, Dict
from collections import defaultdict
from datetime import datetime, timezone

from memory_vault.entry import (
    MemoryEntry, Category, Priority, Source, SourceType, Confidence, entry_id,
)
from memory_vault.store import MemoryStore


# ===== 公开工具函数 =====

def levenshtein_distance(s1: str, s2: str) -> int:
    """计算两个字符串的编辑距离（公开导出）"""
    if not s1:
        return len(s2)
    if not s2:
        return len(s1)
    m, n = len(s1), len(s2)
    if m > n:
        s1, s2 = s2, s1
        m, n = n, m
    prev = list(range(m + 1))
    for j in range(1, n + 1):
        curr = [j] + [0] * m
        for i in range(1, m + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            curr[i] = min(curr[i - 1] + 1, prev[i] + 1, prev[i - 1] + cost)
        prev = curr
    return prev[m]


class Deduplicator:
    """去重与存储压缩引擎"""

    def __init__(self, store: MemoryStore, similarity_threshold: float = 0.80):
        self.store = store
        self.similarity_threshold = similarity_threshold
        self.hash_index_path: Path = store.base / "hash_index.json"
        self._load_hash_index()

        # 统计计数器
        self.exact_dup_count = 0
        self.similar_dup_count = 0
        self.merged_count = 0
        self.bytes_saved = 0

    # ==================== 内部工具 ====================

    @staticmethod
    def _content_hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _levenshtein_ratio(s1: str, s2: str) -> float:
        """计算编辑距离比率：1 - (distance / max_len)，返回 [0, 1]"""
        dist = levenshtein_distance(s1, s2)
        max_len = max(len(s1), len(s2))
        return 1.0 - dist / max_len if max_len > 0 else 1.0

    def _entry_size_bytes(self, entry: MemoryEntry) -> int:
        """估算单条条目占用的JSON字节数"""
        return len(json.dumps(entry.to_dict(), ensure_ascii=False))

    # ==================== Hash Index 管理 ====================

    def _load_hash_index(self):
        try:
            with open(self.hash_index_path, "r", encoding="utf-8") as f:
                self.hash_index: Dict[str, str] = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.hash_index = {}

    def _save_hash_index(self):
        with open(self.hash_index_path, "w", encoding="utf-8") as f:
            json.dump(self.hash_index, f, ensure_ascii=False, indent=2)

    # ==================== 1. 精确去重 ====================

    def _check_exact(self, entry: MemoryEntry) -> Optional[str]:
        """精确去重：返回已存在的 entry_id 或 None"""
        h = self._content_hash(entry.content)
        existing = self.hash_index.get(h)
        if existing is not None and self.store.get(existing) is not None:
            return existing
        return None

    # ==================== 2. 近似去重 ====================

    def _find_similar(self, entry: MemoryEntry) -> Optional[MemoryEntry]:
        """在同 category 中查找近似重复条目"""
        candidates = self.store.list_by_category(entry.category)
        best_match = None
        best_ratio = self.similarity_threshold

        for candidate in candidates:
            if candidate.id == entry.id:
                continue
            if candidate.meta.is_deprecated:
                continue
            ratio = self._levenshtein_ratio(entry.content, candidate.content)
            if ratio >= best_ratio:
                best_ratio = ratio
                best_match = candidate

        return best_match

    # ==================== 3. 高频话题合并 ====================

    def _topic_groups(self) -> Dict:
        """按 (category, canonical_tags) 分组"""
        groups = defaultdict(list)
        for e in self.store.list_all(include_archived=False):
            if e.meta.is_deprecated:
                continue
            key = (e.category.value, tuple(sorted(e.tags)))
            groups[key].append(e)
        return groups

    @staticmethod
    def _merge_content(entries: List[MemoryEntry]) -> str:
        """将多条条目内容合并为一条摘要"""
        parts = []
        seen = set()
        for e in entries:
            text = e.content.strip()
            if text and text not in seen:
                parts.append(text)
                seen.add(text)
            if e.body and e.body.strip() and e.body.strip() not in seen:
                parts.append(e.body.strip())
                seen.add(e.body.strip())
        return " | ".join(parts) if parts else entries[0].content

    # ==================== 公开接口 ====================

    def check_and_add(self, entry: MemoryEntry) -> dict:
        """
        检查是否重复，决定是否写入

        Returns:
            {"action": "add"|"skip"|"deprecate"|"merge", "entry_id": str, "ref_id": str|None}
        """
        # 1. 精确去重
        existing_id = self._check_exact(entry)
        if existing_id:
            self.exact_dup_count += 1
            size = self._entry_size_bytes(entry)
            self.bytes_saved += size
            return {"action": "skip", "entry_id": existing_id, "ref_id": None}

        # 2. 近似去重
        similar = self._find_similar(entry)
        if similar:
            # 更新已有条目（增加访问次数）
            similar.touch()
            self.store.update(similar)
            # 不存储新条目（节省空间）
            self.similar_dup_count += 1
            self.bytes_saved += self._entry_size_bytes(entry)
            return {"action": "deprecate", "entry_id": similar.id, "ref_id": similar.id}

        # 3. 正常添加
        self.store.add(entry)
        self.hash_index[self._content_hash(entry.content)] = entry.id
        self._save_hash_index()
        return {"action": "add", "entry_id": entry.id, "ref_id": None}

    def run_similarity_check(self, category=None) -> dict:
        """
        扫描所有条目，执行近似去重

        Args:
            category: 如果指定，只扫描该分类

        Returns:
            {"checked": int, "deprecations": [ids], "savings": bytes}
        """
        if category:
            entries = self.store.list_by_category(category, include_archived=False)
        else:
            entries = self.store.list_all(include_archived=False)

        entries = [e for e in entries if not e.meta.is_deprecated]
        entries.sort(key=lambda e: e.meta.created_at)

        checked = 0
        deprecations = []
        savings = 0

        for i in range(len(entries)):
            if entries[i].meta.is_deprecated:
                continue
            for j in range(i + 1, len(entries)):
                if entries[j].meta.is_deprecated:
                    continue
                ratio = self._levenshtein_ratio(entries[i].content, entries[j].content)
                if ratio >= self.similarity_threshold:
                    entries[j].meta.is_deprecated = True
                    entries[j].meta.updated_at = datetime.now(timezone.utc).isoformat()
                    self.store.update(entries[j])
                    deprecations.append(entries[j].id)
                    savings += self._entry_size_bytes(entries[j])
                    self.similar_dup_count += 1
                checked += 1

        self.bytes_saved += savings
        return {
            "checked": checked,
            "deprecations": deprecations,
            "savings": savings,
        }

    def run_topic_merge(self, threshold: int = 5) -> dict:
        """
        高频话题合并：同一 category + tags 超过 N 条时自动合并

        Args:
            threshold: 触发合并的条目数量阈值

        Returns:
            {"merged": int, "entries_deprecated": [ids], "savings": bytes}
        """
        groups = self._topic_groups()
        merged = 0
        entries_deprecated = []
        savings = 0

        for (cat_val, tags), entries in groups.items():
            if len(entries) <= threshold:
                continue

            cat = Category(cat_val)
            entries.sort(key=lambda e: e.meta.created_at)

            merged_entry = MemoryEntry(
                content=self._merge_content(entries),
                category=cat,
                priority=entries[0].priority,
                tags=list(tags),
                body=None,
                source=Source(
                    type=SourceType.DERIVE,
                    confidence=Confidence.HIGH,
                    attribution="Nyx(dedup)",
                ),
            )

            for e in entries:
                e.meta.is_deprecated = True
                e.meta.updated_at = datetime.now(timezone.utc).isoformat()
                self.store.update(e)
                entries_deprecated.append(e.id)
                savings += self._entry_size_bytes(e)

            self.store.add(merged_entry)
            self.hash_index[self._content_hash(merged_entry.content)] = merged_entry.id

            merged += 1
            self.merged_count += 1

        self._save_hash_index()
        self.bytes_saved += savings
        return {
            "merged": merged,
            "entries_deprecated": entries_deprecated,
            "savings": savings,
        }

    def get_savings(self) -> dict:
        """返回压缩统计"""
        return {
            "exact_dup_count": self.exact_dup_count,
            "similar_dup_count": self.similar_dup_count,
            "merged_count": self.merged_count,
            "bytes_saved": self.bytes_saved,
        }

    def reset_stats(self):
        """重置所有统计计数器"""
        self.exact_dup_count = 0
        self.similar_dup_count = 0
        self.merged_count = 0
        self.bytes_saved = 0

    def clear_hash_index(self):
        """清空哈希索引（用于测试）"""
        self.hash_index = {}
        self._save_hash_index()
