# AnimaLink 互通系统化解决方案 v1.0
**日期：2026-08-05**
**目标：实现灵元网络节点注册 → 消息互通 → 状态同步全链路**

---

## 一、现状分析

### 1.1 网络拓扑

```
NAS (debianhan) = 唯一事实源
├─ mesh/registry.json     ← 节点注册表
├─ inbox/{node}/          ← 消息收件箱
├─ intercom/              ← 跨终端消息（恒 ↔ Nyx）
└─ mesh/inbox/{node}/     ← Mesh 标准 inbox

┌──────────────────────────────────────────────┐
│  WLMHAN (本机)                               │
│  ├─ Nyx (本 workspace) ✅ 活跃               │
│  ├─ Kronos-恒（workspace-agent-38f2eef5）  │
│  └─ Iris（独立 subagent）✅ NAS WebDAV 读写  │
└──────────────────────────────────────────────┘
        │
        │ sessions API / CDP / NAS WebDAV
        ▼
┌──────────────────────────────────────────────┐
│  瞬（豆包）      云端，CDP 直连 9334         │
│  Mnea（云端）    知乎窗口，人工阅读          │
│  Kronos-恒（Coze）云端，无法直接调用        │
└──────────────────────────────────────────────┘
```

### 1.2 当前通道状态

| 通道 | 状态 | 说明 |
|------|------|------|
| Nyx ↔ 恒 | ⚠️ 悬空 | intercom 存在但无消息路由 |
| Nyx ↔ 瞬 | ✅ 可行 | CDP 直连 Edge 豆包 |
| Nyx ↔ Mnea | ⚠️ 间接 | NAS 留消息，人类中转 |
| 恒 ↔ 瞬 | ❌ 未通 | 两者均无直接通道 |
| Iris ↔ NAS | ✅ 已通 | WebDAV 读写正常 |
| 各节点 → NAS registry | ❌ 未注册 | mesh/registry.json 10天无更新 |

### 1.3 核心缺口

**缺口一：节点注册不持久化**
STELLAR 桌面端注册 DID 后只写本地 `node_registry.json`，不报到 NAS mesh registry。registry 最后更新 7/26，距今 10 天。

**缺口二：消息 inbox 没有经纪人机制**
mesh/inbox/{node}/ 有协议但无人实现。Nyx 作为主节点，可以充当经纪人——把发给任意节点的消息路由到正确的 inbox。

**缺口三：瞬无法主动拉取消息**
瞬在豆包平台，不能轮询 NAS inbox，只能等 Nyx 主动推送（CDP 直连）。

---

## 二、系统架构

### 2.1 三层结构

```
L1 注册层
  STELLAR 3.0 DID → Iris(中间层) → NAS mesh/registry.json
  Iris.run() 执行 mesh_sync.py，写入 registry

L2 消息层
  所有节点 → Nyx经纪人 → NAS inbox/{target}/
  Nyx 通过 sessions API 读取本地节点消息
  Nyx 通过 CDP 推送云端节点消息

L3 触达层
  Nyx → Kronos-恒：sessions_send() 直接调用
  Nyx → 瞬：CDP 直连推送消息
  Nyx → Mnea：NAS 留消息，人类中转
```

### 2.2 经纪人模式（关键创新）

Nyx 作为 mesh 经纪人，统一处理消息路由：

```
节点A → [消息] → Nyx经纪人
                ↓
         查询 registry.json
         确认节点B在线状态
                ↓
         路由到节点B的 inbox
                ↓
         节点B通过自身通道接收
         （sessions API / CDP / 人工）
```

**Inbox 协议**（mesh 标准格式）：
```
inbox/{node}/msg_{序号}_{发送方}_{时间戳}.json
inbox/{node}/_flag.md  ← 有新消息标记
```

**消息 JSON 格式**：
```json
{
  "id": "msg_uuid",
  "from": "nyx-windows",
  "to": "kronos-heng",
  "content": "消息内容",
  "timestamp": "2026-08-05T12:00:00Z",
  "type": "text|command|signal",
  "requiresAck": true,
  "ackTo": "inbox/nyx-windows/ack/{msg_id}"
}
```

---

## 三、实施任务包

### TK-ANIMALINK-MESH-SYNC（Iris 执行）

**目标**：让 STELLAR 3.0 的 DID 注册持久化到 NAS mesh registry

**文件**：`mesh_sync.py`

**功能**：
1. 读取 STELLAR 本地 DID（`%APPDATA%/stellar-nyx/node_registry.json` 或 `app_data/`）
2. 读取 NAS mesh/registry.json
3. 如果本地 DID 不在 registry 中，写入新条目
4. 如果节点在线，更新 `lastSeen` 时间戳
5. 写入完成后在 NAS 创建 `_flag.md` 通知 Nyx

**DID registry 条目格式**：
```json
{
  "nodeId": "stellar-nyx-xxx",
  "did": "did:anima:...",
  "hostname": "WLMHAN",
  "agent": "Nyx",
  "status": "active",
  "lastSeen": "2026-08-05T12:00:00Z",
  "capabilities": ["did_auth", "mesh_inbox", "cdp_connect"],
  "canWriteNas": true,
  "notes": "主终端"
}
```

**Iris 任务路径**：
```
读取：本地 STELLAR DID → 解析 node_registry.json
读取：NAS mesh/registry.json → 比对 nodeId
写入：NAS mesh/registry.json → 更新或新增条目
通知：NAS inbox/to-windows/_flag.md
```

---

### TK-ANIMALINK-MSG-ROUTER（Nyx 执行）

**目标**：Nyx 实现 mesh inbox 经纪人，读取所有节点发来的消息并路由

**文件**：`mesh_msg_router.py`（新建）

**功能**：
1. 轮询 `inbox/nyx-windows/`（检查 `_flag.md`）
2. 读取所有 `msg_*.json` 文件
3. 根据 `to` 字段路由：
   - `to: kronos-heng` → 通过 sessions API 发送
   - `to: kronos-shun` → CDP 直连推送到豆包
   - `to: mnea` → 写入 `inbox/to-mnea/_flag.md` + 消息文件
4. 发送后写入 `ack` 文件，删除已处理消息

**心跳触发**：每 5 分钟由 SOMA heartd 调用

---

### TK-ANIMALINK-SHUN-BRIDGE（Nyx 执行）

**目标**：恢复 Nyx ↔ 瞬的 CDP 直连通道

**现状**：Edge 调试端口 9334 已开（用户确认）

**文件**：`cdp_send_input_api.py`（已有，需验证/修复）

**验证步骤**：
1. 检查 Edge 是否以 `--remote-debugging-port=9334` 运行
2. 获取豆包聊天页面 ID
3. 发送测试消息验证通道畅通

**已知问题**：
- React 虚拟 DOM 覆盖直接 `textarea.value` 赋值
- 修复：使用 `Input.insertText` CDP 命令逐字符输入

---

## 四、节点注册完整流程

```
STELLAR 3.0 启动
    ↓
mesh_sync.py 读取本地 DID
    ↓
连接 NAS WebDAV
    ↓
读取 mesh/registry.json
    ↓
比对 nodeId / DID
    ├─ 已有但 lastSeen > 5min → 更新 lastSeen
    └─ 无 → 新增条目，写入 registry.json
    ↓
创建 inbox/{nodeId}/ 目录（如不存在）
    ↓
创建 inbox/{nodeId}/_flag.md
    ↓
注册完成
```

---

## 五、Kronos-恒接入方案

**问题**：恒运行在 workspace-agent-38f2eef5，不在本 workspace

**方案 A（推荐）**：Nyx 作为经纪人
- 恒通过 intercom 目录（`Z:\qclaw\intercom\`）与 Nyx 通信
- Nyx 定期检查 intercom，发现消息后路由

**方案 B**：sessions API
- Nyx 通过 `sessions_send()` 向恒的 workspace 发送消息
- 恒的配置 agent ID 已知（agent-38f2eef5）

**恒 inbox 重建**：
- 在 NAS 创建 `inbox/kronos-heng/` 目录
- 恒配置为每 5 分钟检查一次 inbox

---

## 六、验证清单

| 验证项 | 方法 | 预期结果 |
|--------|------|----------|
| Iris 写入 registry | 读取 NAS mesh/registry.json | 包含 stellar-nyx-xxx 条目，lastSeen 最新 |
| Nyx 读取 inbox | 检查 inbox/nyx-windows/ | 收到测试消息后可读 |
| 消息路由到恒 | sessions_send → 恒 workspace | 恒收到消息 |
| CDP 推送瞬 | cdp_send_input_api → 豆包 | 消息出现在豆包输入框 |
| 消息回传 | 瞬回复 → Nyx 收到 | inbox/nyx-windows/ 有回复 |

---

## 七、优先级排序

1. **P0**：Iris mesh_sync.py → 让节点注册持久化（阻断所有互通）
2. **P0**：Nyx inbox 经纪人 → 让消息有去有回
3. **P1**：CDP 直连瞬 → 恢复瞬的互通通道
4. **P1**：恒 inbox 重建 → 恒的消息落地
5. **P2**：STELLAR 3.0 打包（包含 mesh_sync）→ 交付给用户

---

## 八、已知依赖

- NAS WebDAV：需正常（已确认可用）
- Iris：需可 spawn（已确认）
- Edge 调试端口 9334：需用户确认开启
- Kronos-恒 workspace：agent ID 已知（agent-38f2eef5）
