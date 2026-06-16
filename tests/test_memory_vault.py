"""
Memory Vault - MVP 核心测试
测试 entry / store / index / vault 四个模块
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

# 确保导入路径正确
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_vault.entry import MemoryEntry, Priority, Category, SourceType, Confidence, Source, entry_id
from memory_vault.store import MemoryStore
from memory_vault.index import MemoryIndex
from memory_vault.vault import MemoryVault


import pytest

# ===== Fixtures =====

@pytest.fixture
def tmp_vault():
    """创建临时 vault 用于测试"""
    tmp = tempfile.mkdtemp(prefix="vault_test_")
    vault = MemoryVault(tmp)
    yield vault
    shutil.rmtree(tmp, ignore_errors=True)


# ===== entry.py 测试 =====

def test_entry_id_stable():
    """同一内容生成相同ID"""
    id1 = entry_id("GitHub Agent 集成成功")
    id2 = entry_id("GitHub Agent 集成成功")
    assert id1 == id2
    assert id1.startswith("mem_")


def test_entry_creation():
    """记忆条目正确创建"""
    entry = MemoryEntry(
        content="今天完成了 GitHub Agent 集成",
        priority=Priority.P1,
        category=Category.PROJECT,
        tags=["github", "agent"],
    )
    assert entry.priority == Priority.P1
    assert entry.category == Category.PROJECT
    assert "github" in entry.tags
    assert entry.meta.decay_score == 1.0
    assert entry.meta.is_archived is False


def test_entry_serialization():
    """序列化和反序列化"""
    entry = MemoryEntry(
        content="测试内容",
        priority=Priority.P0,
        category=Category.IDENTITY,
        source=Source(type=SourceType.DERIVE, confidence=Confidence.HIGH, attribution="Nyx"),
    )
    d = entry.to_dict()
    restored = MemoryEntry.from_dict(d)
    assert restored.content == entry.content
    assert restored.priority == entry.priority
    assert restored.source.type == SourceType.DERIVE


def test_entry_decay_p0_never():
    """P0 条目永不衰减"""
    entry = MemoryEntry(content="核心身份", priority=Priority.P0)
    for _ in range(100):
        entry.apply_decay()
    assert entry.meta.decay_score == 1.0


def test_entry_decay_p2():
    """P2 条目正常衰减"""
    entry = MemoryEntry(content="日志", priority=Priority.P2)
    entry.apply_decay()
    assert entry.meta.decay_score < 1.0
    assert entry.meta.decay_score > 0.0


def test_entry_touch():
    """touch 恢复衰减分数"""
    entry = MemoryEntry(content="内容", priority=Priority.P2)
    entry.apply_decay()
    entry.apply_decay()
    score_before = entry.meta.decay_score
    entry.touch()
    assert entry.meta.decay_score == 1.0
    assert entry.meta.access_count == 1


# ===== store.py 测试 =====

def test_store_add_get(tmp_vault):
    """存入并读取"""
    vid = tmp_vault.remember("测试记忆", priority=Priority.P2)
    entry = tmp_vault.store.get(vid)
    assert entry is not None
    assert entry.content == "测试记忆"


def test_store_update(tmp_vault):
    """更新记忆"""
    vid = tmp_vault.remember("原始内容", priority=Priority.P2)
    entry = tmp_vault.store.get(vid)
    entry.content = "更新后内容"
    tmp_vault.store.update(entry)
    updated = tmp_vault.store.get(vid)
    assert updated.content == "更新后内容"


def test_store_stat(tmp_vault):
    """统计功能"""
    tmp_vault.remember("P0记忆", priority=Priority.P0, category=Category.IDENTITY)
    tmp_vault.remember("P1记忆", priority=Priority.P1, category=Category.PROJECT)
    tmp_vault.remember("P2记忆", priority=Priority.P2)
    stat = tmp_vault.store.stat()
    assert stat["total"] == 3
    assert stat["by_priority"]["P0"] == 1
    assert stat["by_priority"]["P1"] == 1


# ===== index.py + vault.py 测试 =====

def test_vault_remember_and_recall(tmp_vault):
    """存入并检索"""
    vid = tmp_vault.remember(
        "GitHub Agent 集成成功",
        priority=Priority.P1,
        category=Category.PROJECT,
        tags=["github"],
    )
    results = tmp_vault.recall("GitHub Agent")
    assert len(results) >= 1
    assert any("GitHub Agent" in r.content for r in results)


def test_vault_recall_by_category(tmp_vault):
    """按分类检索"""
    tmp_vault.remember("日志1", category=Category.DAILY)
    tmp_vault.remember("日志2", category=Category.DAILY)
    tmp_vault.remember("项目", category=Category.PROJECT)
    results = tmp_vault.recall(category=Category.DAILY)
    assert all(r.category == Category.DAILY for r in results)


def test_vault_hot(tmp_vault):
    """高频记忆"""
    vid = tmp_vault.remember("高频记忆", priority=Priority.P1)
    for _ in range(5):
        tmp_vault.get(vid)
    hot = tmp_vault.hot(limit=5)
    assert hot[0].id == vid
    assert hot[0].meta.access_count == 5


def test_vault_consistency_check(tmp_vault):
    """一致性检测"""
    for i in range(5):
        tmp_vault.remember(f"同类话题 {i}", category=Category.PROJECT, tags=["test"])
    conflicts = tmp_vault.check_consistency()
    assert len(conflicts) >= 1
    assert conflicts[0]["type"] == "potential_redundancy"


def test_vault_stat(tmp_vault):
    """vault 统计"""
    tmp_vault.remember("P0", priority=Priority.P0, category=Category.IDENTITY)
    tmp_vault.remember("P1", priority=Priority.P1, category=Category.PROJECT)
    stat = tmp_vault.stat()
    assert stat["total"] == 2
    assert stat["active"] == 2


def test_vault_trace(tmp_vault):
    """来源追溯"""
    vid = tmp_vault.remember(
        "测试记忆",
        source_type=SourceType.CONVERSATION,
        confidence=Confidence.HIGH,
        attribution="老板",
    )
    trace = tmp_vault.trace(vid)
    assert trace["source"]["attribution"] == "老板"
    assert trace["source"]["type"] == "conversation"
    assert trace["meta"]["decay_score"] == 1.0


# ===== 6项基本要求验收测试 =====

def test_验收_记得住(tmp_vault):
    """记得住：存入后能取出"""
    vid = tmp_vault.remember("这是一条重要记忆", priority=Priority.P0)
    entry = tmp_vault.get(vid)
    assert entry is not None
    assert entry.content == "这是一条重要记忆"


def test_验收_好调用(tmp_vault):
    """好调用：关键词检索返回正确结果"""
    tmp_vault.remember("OpenCode 集成成功")
    tmp_vault.remember("GitHub Agent 上线")
    results = tmp_vault.recall("OpenCode")
    assert any("OpenCode" in r.content for r in results)


def test_验收_省空间_归档(tmp_vault):
    """省空间：归档后条目不占用活跃存储"""
    vid = tmp_vault.remember("将被归档的记忆", priority=Priority.P2)
    # 模拟快速老化（修改创建时间）
    entry = tmp_vault.store.get(vid)
    entry.meta.created_at = "2026-01-01T00:00:00+00:00"
    entry.meta.decay_score = 0.1
    tmp_vault.store.update(entry)
    # 触发归档检查
    result = tmp_vault.run_decay_cycle()
    assert vid in result["archived"]


def test_验收_一致性_冗余检测(tmp_vault):
    """一致性：检测到冗余条目"""
    for i in range(4):
        tmp_vault.remember(f"同一事件重复{i}", category=Category.EVENT, tags=["meeting"])
    conflicts = tmp_vault.check_consistency()
    assert len(conflicts) > 0


def test_验收_可追溯_来源链(tmp_vault):
    """可追溯：每条记忆有来源信息"""
    vid = tmp_vault.remember("来自老板的指示", attribution="老板", source_type=SourceType.CONVERSATION)
    trace = tmp_vault.trace(vid)
    assert trace["source"]["attribution"] == "老板"
    assert trace["source"]["type"] == "conversation"


def test_验收_可遗忘_衰减(tmp_vault):
    """可遗忘：P2 条目衰减后 decay_score 降低"""
    vid = tmp_vault.remember("临时日志", priority=Priority.P2)
    entry = tmp_vault.store.get(vid)
    assert entry.meta.decay_score == 1.0
    for _ in range(5):
        entry.apply_decay()
    assert entry.meta.decay_score < 1.0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
