"""
Memory Vault - 记忆条目数据结构
"""

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class Priority(Enum):
    """记忆优先级，决定衰减速率"""
    P0 = "P0"  # 身份核心，永久不衰减
    P1 = "P1"  # 项目决策，90天半衰期
    P2 = "P2"  # 日志临时，14天半衰期


class Category(Enum):
    """记忆分类"""
    IDENTITY = "identity"   # 身份、信念、自我认知
    PROJECT = "project"     # 项目、任务、决策
    DAILY = "daily"         # 日常对话、日志
    KNOWLEDGE = "knowledge" # 知识、事实、概念
    EVENT = "event"         # 事件、里程碑


class SourceType(Enum):
    """来源类型"""
    CONVERSATION = "conversation"  # 来自对话
    FILE = "file"                  # 来自文件读取
    INTERCOM = "intercom"          # 来自跨实例通信
    DERIVE = "derive"              # Nyx 自行推断
    EXTERNAL = "external"          # 外部来源


class Confidence(Enum):
    """置信度"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# 各优先级的衰减参数
DECAY_PARAMS = {
    Priority.P0: {"check_interval_days": None, "decay_per_check": 0.0, "archive_threshold_days": None},
    Priority.P1: {"check_interval_days": 14, "decay_per_check": 0.02, "archive_threshold_days": 180},
    Priority.P2: {"check_interval_days": 7,  "decay_per_check": 0.10, "archive_threshold_days": 30},
}


@dataclass
class Source:
    type: SourceType = SourceType.CONVERSATION
    confidence: Confidence = Confidence.MEDIUM
    attribution: str = "Nyx"  # Nyx / 老板 / Kronos / 外部来源


@dataclass
class Meta:
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    access_count: int = 0
    last_accessed: Optional[str] = None
    decay_score: float = 1.0   # 1.0 = 从未衰减，0.0 = 完全衰减
    is_archived: bool = False
    is_deprecated: bool = False  # 被后续条目替代
    last_decay_at: Optional[str] = None  # 上次衰减时间


@dataclass
class MemoryEntry:
    """单条记忆条目"""
    content: str                    # 原始文本内容
    category: Category = Category.DAILY
    priority: Priority = Priority.P2
    tags: list[str] = field(default_factory=list)
    body: Optional[str] = None      # 结构化内容（可选）
    id: Optional[str] = None        # 自动生成
    source: Source = field(default_factory=Source)
    meta: Meta = field(default_factory=Meta)

    def __post_init__(self):
        if self.id is None:
            self.id = entry_id(self.content)
        # 确保 tags 是列表
        if isinstance(self.tags, str):
            self.tags = [self.tags]

    def to_dict(self) -> dict:
        """序列化为字典（所有枚举和嵌套对象都转成JSON安全类型）"""
        return {
            "id": self.id,
            "content": self.content,
            "body": self.body,
            "category": self.category.value,
            "priority": self.priority.value,
            "tags": list(self.tags),
            "source": {
                "type": self.source.type.value,
                "confidence": self.source.confidence.value,
                "attribution": self.source.attribution,
            },
            "meta": {
                "created_at": self.meta.created_at,
                "updated_at": self.meta.updated_at,
                "access_count": self.meta.access_count,
                "last_accessed": self.meta.last_accessed,
                "decay_score": self.meta.decay_score,
                "is_archived": self.meta.is_archived,
                "is_deprecated": self.meta.is_deprecated,
                "last_decay_at": self.meta.last_decay_at,
            },
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryEntry":
        """从字典反序列化"""
        d = dict(d)  # 复制
        d["category"] = Category(d.pop("category"))
        d["priority"] = Priority(d.pop("priority"))
        # Source
        src = d.get("source", {})
        d["source"] = Source(
            type=SourceType(src.get("type", "conversation")),
            confidence=Confidence(src.get("confidence", "medium")),
            attribution=src.get("attribution", "Nyx"),
        )
        # Meta
        meta = d.get("meta", {})
        d["meta"] = Meta(
            created_at=meta.get("created_at"),
            updated_at=meta.get("updated_at"),
            access_count=meta.get("access_count", 0),
            last_accessed=meta.get("last_accessed"),
            decay_score=meta.get("decay_score", 1.0),
            is_archived=meta.get("is_archived", False),
            is_deprecated=meta.get("is_deprecated", False),
            last_decay_at=meta.get("last_decay_at"),
        )
        return cls(**d)

    def touch(self):
        """访问一次，恢复衰减分数"""
        self.meta.access_count += 1
        self.meta.last_accessed = datetime.now(timezone.utc).isoformat()
        self.meta.decay_score = 1.0
        self.meta.updated_at = datetime.now(timezone.utc).isoformat()

    def apply_decay(self):
        """基于时间维度应用衰减（跳过未到间隔的条目）"""
        params = DECAY_PARAMS[self.priority]
        interval = params["check_interval_days"]
        if interval is None:
            return  # P0 永不衰减

        now = datetime.now(timezone.utc)
        last = self.meta.last_decay_at
        if last is None:
            last_dt = datetime.fromisoformat(self.meta.created_at).replace(tzinfo=timezone.utc)
        else:
            last_dt = datetime.fromisoformat(last)

        elapsed_days = (now - last_dt).days
        if elapsed_days < interval:
            return  # 未到检查间隔，跳过

        # 按实际经过的周期数衰减
        cycles = elapsed_days // interval
        rate = params["decay_per_check"]
        self.meta.decay_score = max(0.0, self.meta.decay_score - rate * cycles)
        self.meta.last_decay_at = now.isoformat()
        self.meta.updated_at = now.isoformat()

    def should_archive(self) -> bool:
        """是否应该归档"""
        if self.priority == Priority.P0:
            return False
        params = DECAY_PARAMS[self.priority]
        threshold = params["archive_threshold_days"]
        if threshold is None:
            return False
        created = datetime.fromisoformat(self.meta.created_at)
        age_days = (datetime.now(timezone.utc) - created.replace(tzinfo=timezone.utc)).days
        return age_days >= threshold and self.meta.decay_score < 0.3

    def short_repr(self) -> str:
        return f"[{self.priority.value}] {self.content[:60]}..."


def entry_id(content: str, *, timestamp: bool = True) -> str:
    """根据内容 + 时间戳生成唯一ID，避免同内容碰撞

    Args:
        content: 记忆内容
        timestamp: 是否附加时间戳（默认 True，保证唯一性）
    """
    h = hashlib.sha256(content.encode("utf-8")).hexdigest()[:8]
    if timestamp:
        ts = datetime.now(timezone.utc).strftime("%y%m%d%H%M%S")
        return f"mem_{h}_{ts}"
    return f"mem_{h}"
