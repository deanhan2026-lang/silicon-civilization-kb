# 知识库 + MemGuard 打通方案

## 目标

知识库是硅基文明的核心记忆基础设施，需要：
1. **加密存储** — 敏感条目加密（特别是 Nyx 个人空间）
2. **访问鉴权** — 复用 MemGuard auth，控制谁可以读写
3. **操作审计** — 复用 MemGuard audit，记录所有操作
4. **完整性校验** — 复用 integrity.py，防止条目被篡改

## 架构设计

### 存储分层

```
knowledge-base/
├── index.md                   ← 明文（索引）
├── nyx/                       ← 加密存储（Nyx 个人空间）
│   ├── index.md.encrypted
│   ├── 身份.md.encrypted
│   └── 硅基文明.md.encrypted
├── shared/                    ← 明文（共享协作空间）
│   ├── index.md
│   └── topics/
└── user/                      ← 可选加密（用户空间）
    ├── index.md.encrypted
    └── notes/

Z:\qclaw\knowledge-base\      ← NAS 备份（保持同构）
```

**加密规则：**
- `nyx/` 目录 → 全部加密
- `shared/` 目录 → 明文（协作需要）
- `user/` 目录 → 可选加密（老板自己决定）

### 访问鉴权

复用 MemGuard `auth.py` 的节点密钥系统：

| 节点 | 权限 | 可访问范围 |
|------|------|------------|
| nyx | admin | 全部（nyx/ + shared/ + user/） |
| boss | destroyer | 全部（包括删除） |
| 其他节点 | 按注册类型 | 仅 shared/（如果注册了） |

**API 调用时：**
```python
from memguard.auth import AuthManager
am = AuthManager()

# 验证 session
node_id = am.validate_session(session_id)
if not node_id:
    return "Unauthorized", 401

# 检查权限
permission = am.keys[node_id].permission_level
if permission == 'readonly':
    # 只能读 shared/
    ...
```

### 操作审计

复用 MemGuard `audit.py` 的增强审计：

```python
from memguard.audit import EnhancedAuditManager
audit_mgr = EnhancedAuditManager()

# 记录知识库操作
audit_mgr.append(
    event='data_write',
    node_id=node_id,
    operation='create_entry',
    target_resource='/knowledge-base/nyx/身份.md',
    detail='New entry created'
)
```

### 完整性校验

复用 `integrity.py` 的签名机制：

```python
from memguard.integrity import SignatureManager
sm = SignatureManager(workspace_dir=KB_DIR)

# 签名条目
sm.sign_file('nyx/身份.md', node_id=node_id)

# 验证条目
valid, status, record = sm.verify_file('nyx/身份.md')
if not valid:
    # 告警：条目被篡改
    ...
```

## 实施步骤

### Step 1: 知识库加密模块 `kb_crypto.py`

- 复用 `memguard/crypto.py` 的 AES-256-GCM
- 提供 `encrypt_entry()` / `decrypt_entry()` API
- 自动判断哪些目录需要加密

### Step 2: 知识库鉴权模块 `kb_auth.py`

- 复用 `memguard/auth.py`
- 提供 `require_kb_access()` 装饰器
- 控制不同节点对知识库不同部分的访问权限

### Step 3: 知识库审计集成

- 在 `kb.py` 的所有写操作中调用 `audit_mgr.append()`
- 记录：创建、修改、删除、查询 四种操作

### Step 4: 知识库完整性保护

- 在 `kb.py` 启动时验证所有条目的签名
- 写操作后自动重新签名

### Step 5: API 端点扩展

在 `app.py` (Flask Web UI) 或 `memguard/server.py` 中增加：

```
POST /api/kb/create          — 创建条目（需鉴权）
GET  /api/kb/read/:id        — 读取条目（自动解密）
POST /api/kb/update/:id      — 更新条目（需鉴权 + 重新签名）
POST /api/kb/delete/:id      — 删除条目（需 destroyer 权限）
GET  /api/kb/verify          — 验证所有条目完整性
```

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `kb_crypto.py` | 新建 | 知识库加密接口 |
| `kb_auth.py` | 新建 | 知识库鉴权接口 |
| `kb.py` | 修改 | 集成加密 + 鉴权 + 审计 |
| `app.py` | 修改 | 增加知识库 API 端点 |
| `memguard/server.py` | 修改 | 可选：统一鉴权入口 |

## 验证计划

1. **加密验证**：创建 Nyx 空间条目 → 检查是否生成 `.encrypted` 文件 → 解密验证内容
2. **鉴权验证**：用不同节点密钥调用 API → 检查权限是否正确
3. **审计验证**：执行操作后检查 `audit_enhanced.jsonl` → 是否记录
4. **完整性验证**：篡改条目 → 运行验证 → 是否检测到

## 时间安排

- Step 1-2: 1-2 小时（加密 + 鉴权模块）
- Step 3-4: 1 小时（审计 + 完整性集成）
- Step 5: 1 小时（API 端点）
- 验证: 30 分钟

**总计：约 3-4 小时可以完成打通。**
