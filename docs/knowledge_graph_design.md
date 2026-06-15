# 知识图谱与关系推理 - 需求与设计

## 目标
增强知识库的**关系推理能力**：
- 自动发现条目间的引用/派生/冲突关系
- 检测矛盾条目（如同一概念的不同定义）
- 支持"相关条目推荐"

## 核心功能

### 1. 关系提取
从条目内容和元数据中自动提取关系：
- `REFERENCES`: 条目A引用条目B
- `DERIVED_FROM`: 条目B派生于条目A
- `CONTRADICTS`: 条目A与条目B矛盾
- `RELATED_TO`: 条目A与条目B相关（基于标签/关键词）

### 2. 关系存储
在 `data/relations.json` 存储关系图：
```json
{
  "nodes": [
    {"id": "entry_001", "type": "concept", "labels": ["硅基文明", "核心框架"]},
    {"id": "entry_002", "type": "rule", "labels": ["G001"]}
  ],
  "edges": [
    {"source": "entry_001", "target": "entry_002", "type": "REFERENCES"},
    {"source": "entry_003", "target": "entry_001", "type": "CONTRADICTS", "reason": "对'意识'的定义不同"}
  ]
}
```

### 3. 冲突检测
扫描关系图，发现：
- 直接冲突：`A CONTRADICTS B`
- 间接冲突：`A REFERENCES B`, `B CONTRADICTS C` → 警告A与C可能冲突
- 循环引用：`A REFERENCES B`, `B REFERENCES A`（可能是合理的互引用，但也可能是错误）

### 4. 相关条目推荐
给定条目X，推荐相关条目：
- 直接关系（REFERENCES/DERIVED_FROM/RELATED_TO）
- 共享标签的条目
- 共享关键词的条目

## 实现方案

### Phase 1: 基础关系提取（1周）
- [ ] 解析条目YAML front matter中的`references:`字段
- [ ] 从条目正文提取`[[entry_id]]`格式的引用
- [ ] 构建基础关系图（存储在`data/relations.json`）

### Phase 2: 自动关系发现（2周）
- [ ] NLP方法：提取条目正文中的关键概念，匹配其他条目标题/标签
- [ ] 检测矛盾：对比同一概念在不同条目中的描述
- [ ] 关系推理：传递性推理（A引用B，B引用C → A间接引用C）

### Phase 3: API与可视化（1周）
- [ ] API端点：`GET /api/relations/<entry_id>` 获取条目关系
- [ ] API端点：`GET /api/conflicts` 列出所有检测到的冲突
- [ ] Web UI：可视化关系图（使用D3.js或Cytoscape.js）

## 技术栈
- **图数据库**（可选，Phase 2+）：
  - NetworkX（Python，适合小规模）
  - Neo4j（生产级，需要单独部署）
- **NLP库**（Phase 2）：
  - spaCy（英文）
  - jieba +pkuseg（中文）
- **前端可视化**：
  - D3.js（灵活但复杂）
  - Cytoscape.js（专为网络图设计）

## 与现有系统集成
- `kb.py`：添加`--relations`参数，输出条目关系
- `api.py`：添加关系查询端点
- Web UI：在条目详情页显示"相关条目"和"关系图"

## 验收标准
- [ ] 自动提取至少3种关系类型
- [ ] 检测到至少1个矛盾条目对
- [ ] API响应时间 <100ms（100条目规模）
- [ ] 关系图可视化正常渲染

## 参考资料
- NetworkX文档：https://networkx.org/
- 知识图谱构建方法：https://www.zotero.org/groups/2429057/prattwiki/wiki/7S2EI
- 矛盾检测论文：https://aclanthology.org/2020.coling-main.244/

## 优先级
- **P2**（进阶级） - 可在P0/P1完成后启动
- 预计工作量：4周（1周基础 + 2周自动发现 + 1周API/可视化）

---
*创建时间：2026-06-15*  
*创建者：Nyx*  
*状态：需求整理完成，等待开发启动*
