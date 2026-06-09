# MemGuard-GM

**AI记忆完整性保护系统** — 让AI记忆可审计、可验证、被篡改能感知。

---

## 版本状态

| 版本 | 状态 | 说明 |
|------|------|------|
| v1.0 | ✅ 稳定 | 完整性保护、Hash基线、审计链、三级熔断 |
| v2.0 | ✅ 测试通过 | 增量同步、终端注册、冲突检测 |
| v3.0 | 📋 规划中 | 冲突解决优化、治理集成 |

---

## 快速开始

### v1.0 完整性保护

```bash
# 安装
pip install memguard-gm

# 初始化
memguard init

# 创建基线
memguard baseline create "初始记忆内容"
memguard baseline lock

# 验证
memguard verify
```

### v2.0 同步

```bash
# 注册终端
memguard sync register --id nyx-windows --name "Nyx-Windows" --platform windows

# 查看状态
memguard sync status

# 推送/拉取
memguard sync push --endpoint nas.local:5050
memguard sync pull --endpoint nas.local:5050
```

### API服务器

```bash
python server.py
# 服务运行在 http://localhost:5050
```

---

## 架构

```
┌─────────────────────────────────────────────────────────┐
│                      MemGuard-GM                        │
├─────────────────────────────────────────────────────────┤
│ v1.0: 完整性保护                                         │
│   ├─ 双Hash基线 (SHA256 + BLAKE3)                      │
│   ├─ Hash链审计日志                                      │
│   ├─ 三级熔断冻结                                       │
│   └─ REST API + CLI                                     │
├─────────────────────────────────────────────────────────┤
│ v2.0: 记忆同步协议                                       │
│   ├─ Delta (增量补丁)                                   │
│   ├─ Terminal (终端注册)                                │
│   ├─ Push/Pull 同步                                    │
│   └─ 冲突检测 + LWW解决                                 │
└─────────────────────────────────────────────────────────┘
```

---

## 核心概念

### v1.0

| 概念 | 说明 |
|------|------|
| Baseline | 记忆的Hash锚点，不可篡改 |
| Verify | 对比当前Hash与基线 |
| Freeze | 出问题时锁定记忆 |
| Audit | Hash链日志，可追溯 |

### v2.0

| 概念 | 类比Git | 说明 |
|------|---------|------|
| Delta | commit | 记忆增量补丁 |
| Terminal | remote | 已注册的终端 |
| Chain | branch | 终端的补丁链 |
| Fork | fork | 冲突分支 |
| Merge | merge | 冲突解决 |

---

## 同步流程

```
终端A                              终端B
  │                                  │
  │  create_delta()                 │
  │ ───────────────────────────→    │
  │        Delta存储到NAS            │
  │                                  │
  │        ←── /api/sync/heads ──   │
  │        {'nyx-windows': xxx}      │
  │                                  │
  │        ←── /api/sync/deltas ──  │
  │        [delta1, delta2, ...]     │
  │                                  │
  │  apply_delta()                   │
  │                                  ←─ 记忆同步完成
```

---

## 冲突解决

### 检测原理

```python
# 如果两个补丁的父补丁不同，且内容Hash不同
if local.parent_delta_id != remote.parent_delta_id:
    if local.hash != remote.hash:
        # 检测到 content_divergence
```

### 解决策略

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| `lww` | Last Write Wins | 时间戳优先（默认） |
| `local` | 保留本地 | 本地优先 |
| `remote` | 保留远程 | 远程优先 |
| `manual` | 人工仲裁 | 无法自动解决 |

---

## API端点

### v1.0

```
GET  /api/health          健康检查
GET  /api/baseline        读取基线
POST /api/baseline        创建基线
POST /api/baseline/lock   锁定基线
GET  /api/status/<id>     查看状态
GET  /api/status/frozen    冻结列表
POST /api/freeze           冻结记忆
POST /api/unfreeze         解冻记忆
GET  /api/audit/verify    验证审计链
GET  /api/audit/search     搜索审计
```

### v2.0

```
GET  /api/sync/heads           链头列表
POST /api/sync/register        注册终端
GET  /api/sync/status          同步状态
GET  /api/sync/deltas/<term>   获取补丁
POST /api/sync/push            推送补丁
POST /api/sync/pull            拉取补丁
```

---

## 适用场景

- 🏠 个人AI助手 — 保护记忆不被污染
- 👥 多终端AI — 同步记忆到多个设备
- 🔬 AI研究 — 记忆可复现性验证
- 🏢 企业AI — 合规操作审计

---

## 项目地址

GitHub: https://github.com/deanhan2026-lang/silicon-civilization-kb

## 许可证

MIT License
