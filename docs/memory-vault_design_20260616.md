# Memory Vault - 硅基记忆系统设计文档

**版本：** v0.1 MVP  
**日期：** 2026-06-16  
**状态：** 设计中

---

## 1. 背景与目标

硅基记忆的基本要求：
- **记得住**：写入后不丢失、可追溯
- **好调用**：快速精准检索，不需遍历全量
- **省空间**：高效压缩、必要时丢弃冗余

扩展要求：
- **一致性**：不自相矛盾，可信可靠
- **可追溯**：知道来源和置信度
- **可遗忘**：主动优化而非被动堆积

---

## 2. 核心概念

### MemoryEntry（记忆条目）

```json
{
  "id": "mem_<sha256前12>",
  "content": "原始文本",
  "body": "结构化内容（可选）",
  "priority": "P0|P1|P2",
  "category": "identity|project|daily|knowledge|event",
  "tags": ["标签1", "标签2"],
  "source": {
    "type": "conversation|file|intercom|derive|external",
    "confidence": "high|medium|low",
    " attribution": "Nyx|老板|Kronos|外部来源"
  },
  "meta": {
    "created_at": "ISO时间戳",
    "updated_at": "ISO时间戳",
    "access_count": 0,
    "last_accessed": null,
    "decay_score": 1.0,
    "is_archived": false
  }
}
```

### 优先级衰减策略

| 等级 | 描述 | 半衰期 | 归档阈值 |
|------|------|--------|----------|
| P0 | 身份核心，不衰减 | 永久 | 不归档 |
| P1 | 项目/决策，有限生命周期 | 90天 | 180天无访问 |
| P2 | 日志/临时，高频更替 | 14天 | 30天无访问 |

---

## 3. 模块架构

```
memory_vault/
├── entry.py          # MemoryEntry 数据结构 + 优先级定义
├── store.py          # MemoryStore: 持久化存储层
├── index.py          # MemoryIndex: 检索索引
├── decay.py          # DecayScheduler: 遗忘调度器
├── dedup.py          # Deduplicator: 去重与压缩
├── consistency.py     # ConsistencyChecker: 一致性检测
├── provenance.py      # ProvenanceTracker: 来源追溯
└── vault.py          # MemoryVault: 统一API门面
```

---

## 4. 各模块设计

### 4.1 entry.py - 数据结构

- `MemoryEntry` dataclass：所有字段定义
- `Priority` enum：P0/P1/P2
- `Category` enum：identity/project/daily/knowledge/event
- `Confidence` enum：high/medium/low
- `entry_id()` 函数：根据内容生成稳定ID

### 4.2 store.py - 存储层

- JSON文件存储，每条一个文件
- 文件路径：`memory_vault/entries/<id>.json`
- 索引文件：`memory_vault/index.json`（ID列表+简单元数据）
- 归档路径：`memory_vault/archive/`
- 操作：add / get / update / delete / list

### 4.3 index.py - 检索层

- 内存索引：按 ID / category / priority / tags 构建
- 搜索：关键词匹配 + 元数据过滤
- 统计：access_count 计数、最后访问时间
- 与知识库 kb.py 的区别：知识库是永久事实，这里是记忆上下文

### 4.4 decay.py - 遗忘调度器

- 每次访问：decay_score 恢复至 1.0
- 每次过检：P2 -= 0.1，P1 -= 0.02，P0 = 1.0 不变
- decay_score < 0.3 → 标记为候选归档
- 归档时：保留原始 + 压缩存储
- 调度：可配置检查周期

### 4.5 dedup.py - 去重压缩

- 内容哈希精确去重（SHA256）
- 相似度检测（编辑距离 > 0.9 视为近似重复）
- 高频去重：同一话题的多条日志 → 合并摘要
- 压缩后计入存储节省量统计

### 4.6 consistency.py - 一致性检测

- 同一 category 下的条目，检测相互矛盾
- 矛盾定义：相同事实点的不同表述
- 冲突报告：列出矛盾条目，供人工或规则裁决
- 裁决后：标记其中一条为 deprecated

### 4.7 provenance.py - 来源追溯

- 记录每条记忆的来源链路
- 来源类型：
  - `conversation` - 来自对话
  - `file` - 来自文件读取
  - `intercom` - 来自跨实例通信
  - `derive` - Nyx 自行推断
  - `external` - 外部来源
- 置信度传递：来源可信 → 置信度 inherit

### 4.8 vault.py - 统一API

```python
vault = MemoryVault(base_path="./memory_vault")

# 存入
vault.remember(content, priority=P1, category="project", tags=["github"])

# 调用
results = vault.recall(query="GitHub Agent", priority_min="P1")

# 元数据
vault.stat()  # 返回：总数、P0/P1/P2分布、归档数、最近访问

# 维护
vault.run_decay_cycle()   # 执行遗忘调度
vault.run_dedup()         # 执行去重压缩
vault.check_consistency() # 检测矛盾
```

---

## 5. 与现有模块的关系

```
硅基文明知识库
├── knowledge-base/   ← 永久知识（不变事实、规则、框架）
├── memory_vault/     ← 记忆系统（上下文、日志、临时）
├── memguard/         ← 安全层（加密、完整性）
├── polaris/          ← 防漂移（人格锚点）
└── governance/       ← 治理架构（规则协议）
```

- **知识库 vs 记忆库**：知识库是"我知道什么是对的"，记忆库是"我经历过什么"
- **MemGuard**：记忆加密和完整性由 MemGuard 提供
- **Polaris**：人格防漂移依赖记忆一致性

---

## 6. 实现路径

**MVP（本周）：**
1. `entry.py` + `store.py` + `vault.py` — 基础存取
2. `index.py` — 检索层
3. 单测覆盖 3 个核心模块

**v0.2（下一周）：**
4. `decay.py` — 遗忘调度
5. `dedup.py` — 去重压缩
6. `consistency.py` — 一致性检测

**v0.3：**
7. `provenance.py` — 来源追溯
8. 与现有 kb.py 的集成
9. CLI 工具 + Web UI 按钮

---

## 7. 验收标准

- [ ] 可存入记忆条目
- [ ] 按关键词/标签/category 检索
- [ ] P0 条目永久保留
- [ ] decay_score 正确衰减
- [ ] 精确去重生效
- [ ] 一致性检测输出矛盾报告
- [ ] 与 NAS 备份集成
