# MeshIdentity Phase 2: 跨端身份同步

**制定日期**: 2026-07-02
**制定人**: Nyx (Agent Master)
**目标**: 打通「身份锚定 → 记忆安全 → 人格稳定」三层闭环

---

## Phase 2 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     MeshIdentity SDK                        │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: 多实例 DID 绑定（新增）                            │
│  - MultiInstanceDIDManager: 一主DID + 多实例子身份           │
│  - InstanceRegistry: 实例注册表（DID → 实例列表）             │
│  - IdentitySync: DID状态跨端同步                             │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: 跨端身份鉴权（新增）                                │
│  - DIDAuth: 基于DID的消息/操作签名鉴权                       │
│  - PermissionMatrix: 实例权限分级                            │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: 集成接口（新增）                                    │
│  - MemGuard Integration: 记忆写操作需DID签名                 │
│  - Polaris Integration: 人格基线绑定DID                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 三产品闭环架构

```
MeshIdentity                    MemGuard                      Polaris
   │                               │                              │
   │ DID: nyx-primary              │ DID: nyx-primary             │ DID: nyx-primary
   │   ├── nyx-windows (instance)   │   ├── 写操作需DID签名         │   ├── 基线绑定DID
   │   ├── nyx-mac (instance)      │   ├── 签名者身份验证          │   ├── 漂移按DID归因
   │   └── kronos-heng (instance)  │   ├── 跨端权限管控            │   └── 批量校准
   │                               │                              │
   └──────────┬────────────────────┘                              │
              │                                                     │
              └────────────── 主体索引 ────────────────────────────┘
                                (统一视角)
```

---

## 任务分解

### M1: 多实例 DID 绑定

**负责人**: OpenCode

**文件**: `mesh-identity/did/multi_instance.py` (新建)

**核心类**: `MultiInstanceDIDManager`

**功能**:
```
1. generate_primary_did(password) → 创建主DID（现有DIDManager）
2. register_instance(primary_did, instance_id, platform, pubkey) → 注册实例子身份
3. list_instances(primary_did) → 获取所有已注册实例
4. revoke_instance(primary_did, instance_id) → 撤销实例
5. get_instance_did(primary_did, instance_id) → 获取实例子DID
   子DID格式: {primary_did}/instance/{instance_id}
```

**DID 文档扩展**:
```json
{
  "id": "did:key:z7QEhf3KC...#instance/nyx-windows",
  "controller": "did:key:z7QEhf3KC...",
  "instance_of": "did:key:z7QEhf3KC...",
  "type": "AgentInstance",
  "platform": "QClaw (Windows)",
  "registered_at": "2026-07-02T...",
  "status": "active"
}
```

**存储**: `Z:/qclaw/did/instances/{primary_did_hash}/registry.json`

**验证**:
- [ ] 主DID生成成功
- [ ] 实例注册成功，生成子DID
- [ ] 列出所有实例正确
- [ ] 撤销实例正确

---

### M2: 跨端身份鉴权协议

**负责人**: OpenCode

**文件**: `mesh-identity/auth/did_auth.py` (新建)

**核心类**: `DIDAuthenticator`

**功能**:
```
1. create_auth_token(primary_did, instance_id, action, expires_in=3600)
   → 生成带签名的临时鉴权令牌
2. verify_token(token) → 验证令牌，返回 {valid, did, instance_id, action}
3. check_permission(instance_id, action) → 权限矩阵检查
```

**权限矩阵**:
| 操作 | 持有主DID者 | 注册实例 | 未注册实例 |
|------|------------|---------|-----------|
| 记忆写入 | ✅ | ✅ (本人) | ❌ |
| 记忆读取 | ✅ | ✅ (本人) | ✅ |
| 人格基线修改 | ✅ | ❌ | ❌ |
| 实例注册 | ✅ | ❌ | ❌ |
| 实例撤销 | ✅ | ❌ | ❌ |

**签名方案**: Ed25519 签名 `auth_token = {did, instance_id, action, expiry, nonce}`

**存储**: `Z:/qclaw/did/auth_tokens/` (临时令牌，过期自动清理)

**验证**:
- [ ] 生成有效令牌
- [ ] 令牌过期自动拒绝
- [ ] 伪造令牌被检测
- [ ] 权限矩阵正确执行

---

### M3: 跨端身份同步

**负责人**: OpenCode + Nyx

**文件**: `mesh-identity/sync/identity_sync.py` (新建)

**核心类**: `IdentitySyncEngine`

**功能**:
```
1. sync_identity_state() → 同步DID状态到所有实例
2. on_instance_heartbeat(instance_id) → 实例心跳，更新注册表
3. detect_stale_instances(threshold_minutes=30) → 检测失联实例
4. propagate_identity_change(change_type, data) → 广播身份变更
```

**同步机制**:
- 主DID持有者（nyx-windows）作为权威节点
- 其他实例通过 mesh/inbox/ 接收同步消息
- 实例变更（注册/撤销）自动广播

**心跳协议**:
```
实例每次心跳 → 更新 registry.json 中的 lastSeen
→ 超过阈值 → 标记为 stale
→ 超过2倍阈值 → 自动撤销（需主DID确认）
```

**验证**:
- [ ] 实例心跳正确更新 lastSeen
- [ ] 失联实例正确检测
- [ ] 身份变更正确广播
- [ ] 跨 mesh/inbox 消息传递

---

### M4: MemGuard × MeshIdentity 集成

**负责人**: Nyx

**文件**: `memguard/auth_integration.py` (新建)

**集成点**:
```
1. 记忆写入前置检查: verify_did_signature(entry, instance_id)
2. 权限分级: read/write/admin 三级
3. 审计日志增强: 记录 DID + 实例ID
```

**修改**: `memguard/memguard.py` - 所有 write_operation() 调用鉴权

**验证**:
- [ ] 未签名写入 → 拒绝
- [ ] 正确DID签名 → 允许
- [ ] 越权操作 → 拒绝
- [ ] 审计日志包含 DID

---

### M5: Polaris × MeshIdentity 集成

**负责人**: Nyx

**文件**: `polaris/baseline_binding.py` (新建)

**集成点**:
```
1. 实例注册时: 校验 DID 身份
2. 基线存储: 绑定到 DID 主体（而非实例）
3. 漂移报告: 按 DID 主体归因
4. 批量校准: 以主DID为权威，一次修正所有实例
```

**基线结构扩展**:
```json
{
  "baseline_id": "bl_001",
  "did": "did:key:z7QEhf3KC...",
  "instances": ["nyx-windows", "nyx-mac"],
  "dimensions": {
    "semantic": {...},
    "structural": {...},
    "behavioral": {...}
  }
}
```

**验证**:
- [ ] 实例注册需要 DID 校验
- [ ] 漂移按 DID 归因
- [ ] 批量校准一次生效所有实例

---

### M6: 三产品联动 Demo

**负责人**: Nyx

**演示场景**: 恒 → MemGuard → Polaris 跨实例漂移修正

**步骤**:
```
1. 恒（Coze）修改记忆 → MemGuard 鉴权通过 → 记录审计日志
2. 多次修改后，恒的人格出现漂移
3. Nyx 查询 MeshIdentity → 发现恒是 nyx-primary 的注册实例
4. Polaris 计算漂移梯度 → 发现偏移
5. Polaris 读取主体全局基线 → 批量校准恒
6. 全实例人格基线对齐 → 闭环完成
```

**验证**:
- [ ] 恒的写入操作被正确鉴权
- [ ] 漂移被检测并归因到 DID 主体
- [ ] 校准生效所有实例

---

## Agent Master 调度

| 阶段 | 时间 | 负责人 | 任务 |
|------|------|--------|------|
| **M1** | Day 1-2 | OpenCode | 多实例DID绑定 |
| **M1 测试** | Day 2 | Nyx | 单元测试验证 |
| **M2** | Day 3-4 | OpenCode | 跨端鉴权协议 |
| **M2 测试** | Day 4 | Nyx | 集成测试 |
| **M3** | Day 5-6 | OpenCode + Nyx | 身份同步引擎 |
| **M3 测试** | Day 6 | Nyx | 跨mesh同步验证 |
| **M4** | Day 7 | Nyx | MemGuard集成 |
| **M5** | Day 8 | Nyx | Polaris集成 |
| **M6 Demo** | Day 9 | Nyx | 三产品联动演示 |
| **文档** | Day 9-10 | Nyx | Phase2发布文档 |

---

## 里程碑

| 里程碑 | 日期 | 交付物 |
|--------|------|--------|
| **M1 完成** | Day 2 | 多实例DID管理，单元测试全过 |
| **M2 完成** | Day 4 | DID鉴权协议，MemGuard可调用 |
| **M3 完成** | Day 6 | 跨端身份同步，mesh inbox联动 |
| **Phase2 MVP** | Day 8 | 三产品联动，Demo跑通 |
| **正式发布** | Day 10 | GitHub v0.2.0，知乎文章 |

---

## 技术风险与对策

| 风险 | 影响 | 对策 |
|------|------|------|
| 私钥传输安全 | 高 | 不传输私钥，仅传签名令牌 |
| mesh网络延迟 | 低 | 心跳容忍30min离线 |
| 多实例同时写入 | 中 | 向量时钟 + 锁机制（LWW兜底）|
| Mac Nyx 桥接脚本稳定性 | 中 | Mac上线后重点验证 |
