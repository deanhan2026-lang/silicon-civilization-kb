"""
Memory Vault - Dedup 模块测试
"""

import sys, os, tempfile, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from memory_vault.entry import MemoryEntry, Priority, Category, SourceType, Confidence
from memory_vault.store import MemoryStore
from memory_vault.dedup import Deduplicator, levenshtein_distance


@pytest.fixture
def tmp_store():
    tmp = tempfile.mkdtemp(prefix="dedup_test_")
    store = MemoryStore(Path(tmp))
    yield store
    shutil.rmtree(tmp, ignore_errors=True)


# ===== 工具函数测试 =====

def test_levenshtein_identical():
    assert levenshtein_distance("hello", "hello") == 0

def test_levenshtein_one_char():
    assert levenshtein_distance("hello", "hallo") == 1

def test_levenshtein_insert():
    assert levenshtein_distance("hello", "hello!") == 1

def test_levenshtein_empty():
    assert levenshtein_distance("", "") == 0
    assert levenshtein_distance("abc", "") == 3

def test_levenshtein_reverse():
    assert levenshtein_distance("kitten", "sitting") == 3


# ===== 精确去重 =====

def test_exact_dedup_adds_new(tmp_store):
    """首次添加返回add"""
    dedup = Deduplicator(tmp_store)
    e = MemoryEntry(content="GitHub Agent 集成", priority=Priority.P1, category=Category.PROJECT)
    r = dedup.check_and_add(e)
    assert r["action"] == "add"

def test_exact_dedup_skips_duplicate(tmp_store):
    """重复内容返回skip"""
    dedup = Deduplicator(tmp_store)
    e1 = MemoryEntry(content="GitHub Agent 集成", priority=Priority.P1, category=Category.PROJECT)
    r1 = dedup.check_and_add(e1)
    e2 = MemoryEntry(content="GitHub Agent 集成", priority=Priority.P1, category=Category.PROJECT)
    r2 = dedup.check_and_add(e2)
    assert r2["action"] == "skip"
    assert r2["entry_id"] == r1["entry_id"]

def test_exact_dedup_stats(tmp_store):
    """精确去重统计计数"""
    dedup = Deduplicator(tmp_store)
    for _ in range(3):
        dedup.check_and_add(MemoryEntry(content="重复内容", priority=Priority.P2))
    stats = dedup.get_savings()
    assert stats["exact_dup_count"] == 2  # 前两次add，第三次skip


# ===== 近似去重 =====

def test_similar_content_deprecated(tmp_store):
    """近似重复内容标记为deprecated"""
    dedup = Deduplicator(tmp_store, similarity_threshold=0.15)
    e1 = MemoryEntry(content="GitHub Agent 今天完成了集成测试", priority=Priority.P1, category=Category.PROJECT)
    dedup.check_and_add(e1)
    e2 = MemoryEntry(content="GitHub Agent 今天完成了集成测试！", priority=Priority.P1, category=Category.PROJECT)
    r2 = dedup.check_and_add(e2)
    assert r2["action"] == "deprecate"

def test_different_category_not_dedup(tmp_store):
    """不同category不做近似去重"""
    dedup = Deduplicator(tmp_store, similarity_threshold=0.1)
    dedup.check_and_add(MemoryEntry(content="今天很开心", priority=Priority.P2, category=Category.DAILY))
    r = dedup.check_and_add(MemoryEntry(content="今天很开心！", priority=Priority.P2, category=Category.PROJECT))
    assert r["action"] == "add"  # 不同category，不视为重复


# ===== 统计 =====

def test_get_savings_structure(tmp_store):
    """压缩统计包含所有字段"""
    dedup = Deduplicator(tmp_store)
    s = dedup.get_savings()
    assert all(k in s for k in ["exact_dup_count", "similar_dup_count", "merged_count", "bytes_saved"])

def test_reset_stats(tmp_store):
    """重置统计"""
    dedup = Deduplicator(tmp_store)
    dedup.check_and_add(MemoryEntry(content="test", priority=Priority.P2))
    dedup.reset_stats()
    assert dedup.get_savings()["exact_dup_count"] == 0


# ===== 批量检查 =====

def test_run_similarity_check_returns_dict(tmp_store):
    """批量相似度检查返回结构"""
    dedup = Deduplicator(tmp_store, similarity_threshold=0.15)
    for i in range(3):
        dedup.check_and_add(MemoryEntry(content=f"GitHub Agent 完成测试 {i}", priority=Priority.P1, category=Category.PROJECT))
    result = dedup.run_similarity_check()
    assert all(k in result for k in ["checked", "deprecations", "savings"])


# ===== 话题合并 =====

def test_topic_merge_below_threshold(tmp_store):
    """低于阈值不合并"""
    dedup = Deduplicator(tmp_store)
    for i in range(3):
        e = MemoryEntry(content=f"话题{i}", priority=Priority.P2, category=Category.PROJECT)
        dedup.check_and_add(e)
    result = dedup.run_topic_merge(threshold=5)
    assert result["merged"] == 0

def test_topic_merge_above_threshold(tmp_store):
    """超过阈值触发合并：直接写store（绕过去重），保证有6条非deprecated条目"""
    # 直接写入store，模拟已有大量条目后再运行merge的场景
    for i in range(6):
        e = MemoryEntry(content=f"项目记录{i}", priority=Priority.P2, category=Category.PROJECT, tags=["merge-test"])
        tmp_store.add(e)
    dedup = Deduplicator(tmp_store)
    result = dedup.run_topic_merge(threshold=5)
    assert result["merged"] >= 1
    assert len(result["entries_deprecated"]) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
