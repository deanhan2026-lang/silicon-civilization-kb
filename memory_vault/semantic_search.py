#!/usr/bin/env python3
"""
语义检索模块 - TF-IDF + 中文分词
基于恒的 AIAP Phase 3 实现
"""

import math
import re
from collections import Counter
from typing import Dict, List, Optional, Tuple
import jieba

from memory_vault.entry import MemoryEntry


class SemanticSearch:
    """TF-IDF 语义检索"""

    def __init__(self):
        self.doc_freq: Dict[str, int] = {}  # 词 -> 文档频率
        self.doc_count: int = 0
        self.doc_vectors: Dict[str, Dict[str, float]] = {}  # entry_id -> {词: tfidf}
        self.entries: Dict[str, MemoryEntry] = {}

    def _tokenize(self, text: str) -> List[str]:
        """分词 + 去停用词"""
        # 中文分词
        tokens = jieba.lcut(text.lower())
        # 过滤：保留中文、英文、数字
        tokens = [t for t in tokens if re.match(r'^[\u4e00-\u9fa5a-z0-9]+$', t)]
        # 去停用词（简化版）
        stopwords = {'的', '是', '在', '了', '和', '与', '或', '有', '这', '那', '为', '对', '中', '上', '下'}
        tokens = [t for t in tokens if t not in stopwords and len(t) > 1]
        return tokens

    def _compute_tf(self, tokens: List[str]) -> Dict[str, float]:
        """计算 TF（词频）"""
        counter = Counter(tokens)
        total = len(tokens) if tokens else 1
        return {word: count / total for word, count in counter.items()}

    def _compute_idf(self, word: str) -> float:
        """计算 IDF"""
        df = self.doc_freq.get(word, 0)
        if df == 0:
            return 0.0
        return math.log(self.doc_count / df)

    def _compute_tfidf(self, tf: Dict[str, float]) -> Dict[str, float]:
        """计算 TF-IDF 向量"""
        tfidf = {}
        for word, tf_val in tf.items():
            idf = self._compute_idf(word)
            tfidf[word] = tf_val * idf
        return tfidf

    def _l2_normalize(self, vec: Dict[str, float]) -> Dict[str, float]:
        """L2 归一化"""
        norm = math.sqrt(sum(v ** 2 for v in vec.values()))
        if norm == 0:
            return vec
        return {k: v / norm for k, v in vec.items()}

    def _cosine_similarity(self, v1: Dict[str, float], v2: Dict[str, float]) -> float:
        """余弦相似度"""
        common_words = set(v1.keys()) & set(v2.keys())
        if not common_words:
            return 0.0
        dot = sum(v1[w] * v2[w] for w in common_words)
        norm1 = math.sqrt(sum(v ** 2 for v in v1.values()))
        norm2 = math.sqrt(sum(v ** 2 for v in v2.values()))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    def index(self, entry: MemoryEntry):
        """索引一条记忆"""
        # 合并 content + body
        text = entry.content
        if entry.body:
            text += " " + entry.body

        # 分词
        tokens = self._tokenize(text)

        # 更新文档频率
        unique_words = set(tokens)
        for word in unique_words:
            self.doc_freq[word] = self.doc_freq.get(word, 0) + 1

        self.doc_count += 1

        # 计算 TF
        tf = self._compute_tf(tokens)

        # 存储词条目
        self.entries[entry.id] = entry
        self.doc_vectors[entry.id] = tf  # 临时存 TF，rebuild 时统一算 TF-IDF

    def rebuild_index(self):
        """重建全量索引（计算 IDF 和 TF-IDF）"""
        for entry_id, tf in self.doc_vectors.items():
            tfidf = self._compute_tfidf(tf)
            self.doc_vectors[entry_id] = self._l2_normalize(tfidf)

    def search(
        self, query: str, top_k: int = 10, category_filter: Optional[str] = None
    ) -> List[Tuple[MemoryEntry, float]]:
        """
        语义检索

        Args:
            query: 查询文本
            top_k: 返回前 K 个结果
            category_filter: 分类过滤（可选）

        Returns:
            List of (entry, score) tuples
        """
        # 查询分词
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # 查询 TF
        query_tf = self._compute_tf(query_tokens)

        # 查询 TF-IDF（使用现有 IDF）
        query_tfidf = self._compute_tfidf(query_tf)
        query_vec = self._l2_normalize(query_tfidf)

        # 计算相似度
        scores = []
        for entry_id, doc_vec in self.doc_vectors.items():
            entry = self.entries.get(entry_id)
            if not entry:
                continue

            # 分类过滤
            if category_filter and entry.category.value != category_filter:
                continue

            sim = self._cosine_similarity(query_vec, doc_vec)
            if sim > 0:
                scores.append((entry, sim))

        # 按相似度排序
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def get_stats(self) -> Dict:
        """获取索引统计"""
        return {
            "doc_count": self.doc_count,
            "vocab_size": len(self.doc_freq),
            "indexed_entries": len(self.doc_vectors),
        }
