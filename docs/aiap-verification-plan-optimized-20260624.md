# AIAP协议验证方案（优化版 v0.2）

**文档编号：** ANIMA-20260624-VP01
**版本：** v0.2（优化版）
**优化者：** Nyx（Agent Master）
**日期：** 2026-06-24
**类型：** protocol_verification_plan
**visibility：** public

---

## 核心优化：从8-9天压缩到3阶段 × 2天

### 主要改动

| 原方案问题 | 优化方案 |
|-----------|----------|
| 阶段零"准备"长达1-2天，阻塞后续 | **全并行化**：阶段零任务全部分解到各Track并行执行 |
| DID生成和碳基签名依赖"完整协议" | **极简DID**：本地Ed25519密钥+W3C did:key格式，无需CA基础设施 |
| 嵌入模型依赖外部API | **两档方案**：第一档用关键词向量替代（TF-IDF），第二档再上嵌入模型 |
| 瞬在豆包无法接收intercom消息 | **CDP主通道**：通过CDP直连豆包发送指令和收集结果 |
| 漂移检测需要Polaris在瞬环境部署 | **恒侧模拟**：漂移对比在恒侧用SOUL.md基线做，瞬侧只需发送polaris_metadata |
| 四个阶段顺序执行 | **双Track并行**：恒Track + 瞬Track各自独立推进，中央协调汇合 |

### 优化后的三Track架构

```
┌─────────────────────────────────────────────────────────────┐
│ Nyx（Agent Master / 中央协调）                              │
│  • 定义 MemoryEntry Schema                                  │
│  • 准备 DID 生成工具（恒Track）                             │
│  • 通过 CDP 向瞬Track发送指令、收集结果                      │
│  • 通过 Intercom 向恒Track发送指令                          │
│  • 阶段性汇报（WeChat → 老板）                              │
└─────────────────────────────────────────────────────────────┘
         ↕ Intercom msg                    ↕ CDP直连
┌──────────────┐                    ┌──────────────┐
│ 恒Track (QClaw) │                │ 瞬Track (豆包) │
│ • DID生成/验证 │                    │ • 接收指令    │
│ • MemoryEntry │                    │ • 执行测试    │
│   存储/归档   │                    │ • 返回结果    │
│ • 语义检索    │                    └──────────────┘
│ • 漂移检测    │
└──────────────┘
```

---

## 阶段一：基础设施就绪（Day 0，非阻塞并行）

### ATrack：Nyx中央工具准备（立即执行）

| 任务 | 产出 | 状态 |
|------|------|------|
| 定义 MemoryEntry JSON Schema | `memory_entry_schema.json` | 🟡 进行中 |
| 准备恒Track DID生成脚本 | `generate_did.py` | ⬜ 待办 |
| 准备恒Track签名验证脚本 | `sign_verify.py` | ⬜ 待办 |
| 更新 Memory Vault 支持 MemoryEntry | `vault.py` 增强 | ⬜ 待办 |
| 部署恒Track工具到 QClaw 环境 | 恒workspace可执行 | ⬜ 待办 |
| 确认 CDP 直连豆包可用 | 端到端连通测试 | ⬜ 待办 |

### BTrack：恒Track准备（DID+签名工具，阶段一交付）

| 任务 | 产出 | 负责人 |
|------|------|--------|
| 在恒QClaw环境生成Ed25519密钥对 | 公钥/私钥文件 | 恒（由我通过Intercom调度） |
| 生成 W3C did:key 格式 DID | `did:key:z...` 字符串 | 恒 |
| 计算 SOUL.md 的 SHA-256 作为 soul_anchor | soul_anchor 哈希值 | 恒 |
| 通过 Intercom 向 Nyx 报告 DID | msg_发回 | 恒 |

### CTrack：瞬Track准备（CDP指令准备，阶段一交付）

| 任务 | 产出 | 负责人 |
|------|------|--------|
| CDP直连确认（发送测试消息） | 豆包收到消息 | Nyx |
| 通过CDP发送DID生成指令 | 豆包执行脚本 | Nyx |
| 收集瞬的DID和公钥 | 返回结果 | Nyx |

---

## 阶段二：记忆同步验证（Day 1-2）

### 核心测试：恒-瞬单向记忆同步

**目标：** 瞬发送一条结构化MemoryEntry → 恒接收 → 归档 → 检索召回

| 步骤 | 发送方 | 接收方 | 验证点 |
|------|--------|--------|--------|
| 1. 瞬生成测试MemoryEntry | 瞬 | - | entry_id/timestamp/signature非空 |
| 2. 通过CDP中转发送MemoryEntry | 瞬 | Nyx收集 | Nyx收到JSON |
| 3. Nyx转发给恒 | Nyx | 恒 | Intercom msg |
| 4. 恒验证签名 | - | 恒 | Ed25519验证通过 |
| 5. 恒归档到MemoryVault | - | 恒 | vault.search()能查到 |
| 6. 恒返回确认ack | 恒 | Nyx | twin_ack_hash |
| 7. 恒执行语义检索 | - | 恒 | Top-5含目标 |

### Polaris漂移检测验证（阶段二嵌入）

| 步骤 | 发送方 | 接收方 | 验证点 |
|------|--------|--------|--------|
| 1. 瞬发送一条"偏离基线"的测试记忆 | 瞬 | 恒 | MemoryEntry含polaris_metadata |
| 2. 恒对比SOUL.md基线计算drift_score | - | 恒 | drift_score > 阈值 |
| 3. 审计日志记录事件 | - | 恒 | 日志文件有条目 |
| 4. Nyx向老板报告漂移事件 | Nyx | 老板 | WeChat通知 |

---

## 阶段三：综合闭环与文档输出（Day 3-4）

### 产出目标

| 产出物 | 负责方 | 格式 |
|--------|--------|------|
| AIAP协议验证报告 | Nyx | Markdown + 腾讯文档 |
| MemoryEntry JSON Schema v1.0 | Nyx | JSON Schema |
| 恒-瞬同步流程规范 | Nyx | Markdown |
| 验证代码与脚本集 | 恒Track | Python脚本 |

### 闭环确认

- [ ] 全链路：瞬MemoryEntry → CDP → Nyx → Intercom → 恒归档 → 检索召回
- [ ] 时间戳：各环节耗时记录
- [ ] 成功率：100%记忆同步（可重试1次）

---

## MemoryEntry Schema v1.0

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "MemoryEntry",
  "version": "1.0",
  "type": "object",
  "required": ["entry_id", "timestamp", "owner_did", "content", "signature"],

  "properties": {
    "entry_id": {
      "type": "string",
      "description": "UUID v4 唯一标识"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "RFC3339 时间戳"
    },
    "owner_did": {
      "type": "string",
      "description": "W3C DID 格式，记忆所有者"
    },
    "namespace": {
      "type": "string",
      "default": "default",
      "description": "命名空间，默认default"
    },
    "content_type": {
      "type": "string",
      "enum": ["thought", "experience", "knowledge", "identity_marker"],
      "description": "记忆类型"
    },
    "content": {
      "type": "string",
      "description": "记忆正文内容"
    },
    "summary": {
      "type": "string",
      "description": "≥20字自然语言摘要，用于语义索引"
    },
    "tags": {
      "type": "array",
      "items": { "type": "string" },
      "description": "关键词标签"
    },
    "keywords": {
      "type": "array",
      "items": { "type": "string" },
      "description": "TF-IDF提取关键词（替代embedding的轻量方案）"
    },
    "polaris_metadata": {
      "type": "object",
      "properties": {
        "sender_soul_hash": { "type": "string" },
        "coherence_score": { "type": "number", "minimum": 0, "maximum": 1 },
        "deviation_flag": { "type": "boolean" }
      }
    },
    "access_policy": {
      "type": "string",
      "enum": ["public", "private", "namespace", "acl", "encrypted"],
      "default": "namespace"
    },
    "sync_meta": {
      "type": "object",
      "properties": {
        "synced_to_twin": { "type": "boolean" },
        "twin_ack_hash": { "type": "string" }
      }
    },
    "signature": {
      "type": "string",
      "description": "Ed25519签名（owner_did对应的私钥签content字段）"
    }
  }
}
```

---

## 调度指令索引

| 阶段 | 恒Track指令 | 瞬Track指令 |
|------|-----------|------------|
| 阶段一 | 见 intercom msg | 见 CDP |
| 阶段二 | 见 intercom msg | 见 CDP |
| 阶段三 | 见 intercom msg | 见 CDP |

---

*本条目由Nyx（Agent Master）优化，2026-06-24*
