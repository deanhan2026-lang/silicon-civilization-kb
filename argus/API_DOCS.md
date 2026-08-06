# Argus Phase 2 API 文档

**版本：** v2.0  
**日期：** 2026-07-21  
**状态：** ✅ 已交付

---

## 概述

Phase 2 在 Phase 1 基础上增加了两个增强模块：

1. **四级审批策略** (`approval_strategy.py`) — 借鉴 OpenAI Codex 设计
2. **三级沙箱档位** (`sandbox_tiers.py`) — 增量权限控制

---

## 1. ApprovalPolicy — 四级审批策略

### 1.1 策略枚举

```python
from approval_strategy import ApprovalPolicy, ApprovalConfig, Strategy, RiskAssessment

# 四种策略
Strategy.ON_REQUEST   # 模型自主判断（Phase 1 默认）
Strategy.ON_FAILURE   # 先自动执行，失败3次再升人审 ★新增
Strategy.UNTRUSTED    # 所有非只读都审批
Strategy.NEVER        # 全自动，CI/CD专用
```

### 1.2 配置

```python
config = ApprovalConfig(
    strategy=Strategy.ON_REQUEST,
    max_failures_before_escalation=3,  # on-failure 失败阈值
    failure_window_seconds=300,        # 失败窗口（秒）
    auto_allow_tools=["read_file", "list_dir"],  # 白名单
    always_require_approval=["rm", "delete"],    # 强制审批
    on_decision=callback_fn            # 审计回调
)
policy = ApprovalPolicy(config)
```

### 1.3 评估

```python
risk = RiskAssessment(
    risk_level="medium",  # none/low/medium/high/critical
    reason="写操作",
    requires_approval=True,
    auto_executable=False
)

result = policy.evaluate("write_file", risk)
# 返回: {"decision": "auto"|"approve"|"block", "reason": "...", "failures_remaining": int}
```

### 1.4 失败记录

```python
# on-failure 模式下记录失败
policy.record_failure("fetch_url")
policy.record_success("fetch_url")  # 重置计数
```

---

## 2. SandwichTierManager — 三级沙箱档位

### 2.1 档位枚举

```python
from sandbox_tiers import SandboxTier, SandwichTierManager

SandboxTier.READ_ONLY       # 只读 + 网络全禁
SandboxTier.WORKSPACE_WRITE # 工作区可写 + 网络白名单 ★新增
SandboxTier.DANGER_FULL     # 全通（底线保护）
```

### 2.2 配置

```python
tier_mgr = SandwichTierManager(
    tier=SandboxTier.WORKSPACE_WRITE,
    workspace="/workspace",
    additional_write_paths=["/tmp/build"],  # 额外可写路径
    additional_allowed_hosts=["pypi.org"]   # 额外允许主机
)
```

### 2.3 路径检查

```python
# 读检查
ok, reason = tier_mgr.is_path_safe("/workspace/test.txt", "read")

# 写检查
ok, reason = tier_mgr.is_path_safe("/workspace/output.txt", "write")
```

### 2.4 网络检查

```python
# 主机+端口
ok = tier_mgr.can_connect("api.github.com", 443)
```

### 2.5 命令检查

```python
ok, reason = tier_mgr.can_execute("python test.py")
ok, reason = tier_mgr.can_execute("rm -rf /")  # 始终 False
```

### 2.6 资源限制

```python
ok, reason = tier_mgr.check_resource_limits(
    file_size_bytes=100*1024*1024,  # 100MB
    duration_ms=60*1000             # 60秒
)
```

---

## 3. 集成示例

### 3.1 ApprovalAwarePipeline

```python
from approval_strategy import ApprovalAwarePipeline

# 包装现有 pipeline
pipeline = ApprovalAwarePipeline(original_pipeline, approval_policy)

# 处理工具调用
result = pipeline.process({
    "tool": "write_file",
    "args": {"path": "/workspace/output.txt"}
})
# 返回: {"blocked": False, "approval_decision": "approve", "approval_reason": "..."}
```

### 3.2 TieredSandwichExecutor

```python
from sandbox_tiers import TieredSandwichExecutor

# 包装 Phase 1 sandbox_executor
executor = TieredSandwichExecutor(
    original_executor,
    tier=SandboxTier.WORKSPACE_WRITE,
    workspace="/workspace"
)

# 检查工具调用
ok, reason = executor.can_execute({
    "tool": "write_file",
    "args": {"path": "/workspace/output.txt"}
})
```

---

## 4. 测试覆盖

**文件：** `tests/test_approval_strategy.py` + `tests/test_sandbox_tiers.py`  
**测试数：** 69  
**通过率：** 100%

### 4.1 审批策略测试

- on-request: 6 测试（风险等级覆盖）
- on-failure: 6 测试（失败计数+重置）
- untrusted: 4 测试（白名单+强制审批）
- never: 3 测试（全自动+底线保护）
- 强制审批: 7 测试（危险操作）
- 审计回调: 1 测试
- Pipeline 集成: 3 测试

### 4.2 沙箱档位测试

- read-only: 7 测试（只读+网络禁+命令禁）
- workspace-write: 10 测试（读写+网络白名单+命令）
- danger-full: 5 测试（全通+底线）
- 资源限制: 4 测试（文件大小+执行时间）
- 边界 case: 6 测试（空命令+相对路径+符号链接）
- Executor 集成: 6 测试（读写+网络+命令+回退）

---

## 5. 与 Phase 1 兼容性

### 5.1 接口兼容

| Phase 1 模块 | Phase 2 适配器 | 说明 |
|-------------|---------------|------|
| `pipeline.py` | `ApprovalAwarePipeline` | 在 L3 后插入审批层 |
| `sandbox_executor.py` | `TieredSandwichExecutor` | 包装原始 executor |
| `tool_validator.py` | 无需修改 | 审批策略在 validator 之后 |

### 5.2 配置兼容

```python
# Phase 1 配置不变
phase1_config = {
    "max_retries": 3,
    "timeout": 300,
    "sandbox": True
}

# Phase 2 新增配置
phase2_config = {
    "approval_strategy": "on-failure",
    "sandbox_tier": "workspace-write"
}
```

---

## 6. 部署说明

### 6.1 文件结构

```
argus-phase2/
├── approval_strategy.py    # 四级审批策略
├── sandbox_tiers.py        # 三级沙箱档位
└── tests/
    ├── test_approval_strategy.py
    └── test_sandbox_tiers.py
```

### 6.2 运行测试

```bash
cd argus-phase2
python -m pytest tests/ -v
```

### 6.3 集成到 Argus

```python
# 在 pipeline.py 中
from approval_strategy import ApprovalPolicy, ApprovalAwarePipeline
from sandbox_tiers import SandboxTier, TieredSandwichExecutor

# 初始化
policy = ApprovalPolicy(ApprovalConfig(strategy=Strategy.ON_FAILURE))
executor = TieredSandwichExecutor(sandbox_executor, SandboxTier.WORKSPACE_WRITE, workspace)

# 使用
pipeline = ApprovalAwarePipeline(original_pipeline, policy)
result = pipeline.process(tool_call)
```

---

**交付人：** Iris  
**验证人：** Nyx  
**状态：** ✅ 测试通过，待集成
