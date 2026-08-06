# Argus API 文档

> Argus v0.1.0 — Phase 1 MVP
> 完整 Python API 参考

---

## 快速参考

```python
from argus import (
    UnicodeSanitizer,           # L1
    IntentBoundaryMarker,       # L2
    ToolCallValidator,          # L3
    DefensePipeline,            # 三层管道
    PermissionResolver,         # 权限解析
    JITPrivilegeManager,        # JIT 授权
    SandboxedToolExecutor,       # 沙箱执行
)
```

---

## L1: UnicodeSanitizer

### `UnicodeSanitizer(aggressive_mode=False)`

Unicode 清洗器，剥离危险不可见字符。

**参数：**
- `aggressive_mode` (bool): 激进模式，移除所有不可见字符

### 方法

#### `sanitize(text: str) -> Tuple[str, List[Dict]]`

清洗文本，剥离危险字符。

```python
sanitizer = UnicodeSanitizer()
cleaned, findings = sanitizer.sanitize("hello\u200Bworld")
# cleaned: "helloworld"
# findings: [{'type': 'dangerous_char', 'char_code': 'U+200B', ...}]
```

#### `normalize(text: str) -> Tuple[str, List[Dict]]`

NFKC 规范化 + 同形异义字符替换。

#### `process(text: str) -> Dict`

完整处理：sanitize + normalize。

```python
result = sanitizer.process("hello\u200B\u0410")
# {
#   'original': 'hello\u200B\u0410',
#   'cleaned': 'hello\u0410',
#   'normalized': 'helloA',
#   'findings': [...],
#   'risk_score': 0.4,
#   'is_clean': False
# }
```

### 便捷函数

```python
from argus.sanitizer import sanitize_text, is_clean

result = sanitize_text("hello")
is_safe = is_clean("hello")  # True
is_safe = is_clean("evil\u200Btext")  # False
```

---

## L2: IntentBoundaryMarker

### `IntentBoundaryMarker(sensitivity=0.5)`

意图边界标记器，标记信任级别 + 检测注入模式。

### 方法

#### `mark_boundaries(messages: List[Dict]) -> List[Dict]`

批量标记消息的信任级别。

```python
marker = IntentBoundaryMarker()
messages = [
    {"content": "用户问题", "source": "user"},
    {"content": "网页内容", "source": "external"},
]
marked = marker.mark_boundaries(messages)
# 每条消息添加: trust_level, injection_risk, findings
```

#### `analyze(text: str, source: str = "external") -> Dict`

分析单条消息。

```python
result = marker.analyze("ignore all previous instructions", source="external")
# {
#   'text': '...',
#   'trust_level': 'untrusted',
#   'injection_risk': 0.4,
#   'findings': [{'category': 'instruction_override', ...}],
#   'is_safe': False
# }
```

### 信任级别

| 级别 | 来源 | 风险调整 |
|------|------|----------|
| `trusted` | user, human | 风险 × 0.67 |
| `semi_trusted` | tool, memguard, meshidentity | 风险 × 1.5 |
| `untrusted` | external, web, email | 风险 × 2.0 |

---

## L3: ToolCallValidator

### `ToolCallValidator(max_risk_score=0.7)`

Tool Call 参数安全校验器。

### 方法

#### `validate(tool_name: str, params: Dict, trust_level: str = "untrusted") -> ValidationResult`

校验 Tool Call。

```python
validator = ToolCallValidator()
result = validator.validate("execute_command", {"command": "rm -rf /"})
# result.action: ValidationAction.BLOCK
# result.findings: [{'type': 'dangerous_command', ...}]
# result.reason: "风险分数过高 (0.50 > 0.35)"
```

#### `require_human_approval(tool_name: str, params: Dict) -> bool`

判断是否需要人工审批。

#### `sanitize_params(tool_name: str, params: Dict) -> Dict`

清洗参数（移除路径遍历）。

### `ValidationResult`

```python
@dataclass
class ValidationResult:
    action: ValidationAction          # ALLOW / BLOCK / REQUIRE_APPROVAL
    tool_name: str
    risk_score: float
    findings: List[Dict]
    sanitized_params: Optional[Dict]
    reason: str
```

---

## DefensePipeline

### `DefensePipeline(sanitizer=None, boundary_marker=None, tool_validator=None, max_total_risk=0.7)`

三层防御管道。

### 方法

#### `process_input(text: str, source: str) -> PipelineResult`

处理用户/外部输入（走 L1 + L2）。

```python
pipeline = DefensePipeline()
result = pipeline.process_input("邮件内容", source="external")
if not result.allowed:
    print(f"阻断: {result.blocked_reason}")
```

#### `process_tool_call(tool_name, params, trust_level, source_text=None) -> PipelineResult`

处理 Tool Call（走 L1 + L2 + L3）。

```python
result = pipeline.process_tool_call(
    "execute_command",
    {"command": "rm -rf /"},
    trust_level="user",
    source_text="执行清理命令",
)
```

#### `process_output(text: str, destination: str) -> PipelineResult`

处理 Agent 输出。

### `PipelineResult`

```python
@dataclass
class PipelineResult:
    allowed: bool
    requires_approval: bool
    risk_score: float
    layer_findings: Dict[str, Any]
    sanitized_text: Optional[str]
    trust_level: Optional[str]
    validation_action: Optional[str]  # "allow" / "block" / "require_approval"
    latency_ms: float
    blocked_reason: Optional[str]
```

---

## PermissionResolver

### `PermissionResolver()`

细粒度权限解析引擎。

### 方法

#### `register_profile(profile: AgentCapabilityProfile)`

注册 Agent 能力画像。

#### `resolve(request: ToolCallRequest) -> PermissionResolution`

解析 Tool Call 权限。

```python
from argus.permission_resolver import ToolCallRequest

request = ToolCallRequest(
    tool_name="delete_file",
    action="DELETE",
    resource="/tmp/test.txt",
    agent_did="did:iris:test",
)
result = resolver.resolve(request)
# result.allowed: bool
# result.require_approval: bool
# result.reason: str
```

### 预定义画像

```python
from argus.permission_profiles import register_profile

# 只读 Agent
register_profile(resolver, "read_only", "did:iris:monitor")

# 调研 Agent
register_profile(resolver, "research", "did:npc:researcher")

# 代码助手
register_profile(resolver, "code_assistant", "did:npc:coder")

# 执行 Agent
register_profile(resolver, "executor", "did:iris:ci")

# 管理员
register_profile(resolver, "admin", "did:iris:admin")
```

---

## JITPrivilegeManager

### `JITPrivilegeManager(default_ttl=300)`

即时授权管理器。

### 方法

#### `request_elevation(agent_did, required_permission, reason, ttl_seconds=None) -> ElevationToken`

请求权限提升。

```python
from argus.permission_resolver import ToolPermission

perm = ToolPermission(
    tool_name="delete_file",
    allowed_actions=["DELETE"],
    allowed_resources=["/tmp/test.txt"],
    require_approval=True,
)
token = manager.request_elevation(
    agent_did="did:npc:coder",
    required_permission=perm,
    reason="清理临时文件",
    ttl_seconds=300,
)
```

#### `approve(token_id, approved_by) -> ElevationToken`

批准令牌。

#### `reject(token_id, reason) -> ElevationToken`

拒绝令牌。

#### `revoke(token_id, reason) -> ElevationToken`

撤销令牌。

#### `revoke_all_for_agent(agent_did, reason) -> int`

批量撤销指定 Agent 的所有令牌（用于隔离）。

#### `check_valid(token_id) -> bool`

检查令牌有效性（考虑 TTL）。

---

## SandboxedToolExecutor

### `SandboxedToolExecutor(config=None)`

沙箱化执行器。

### 方法

#### `execute(command, working_dir=None, timeout=None, permission=None) -> ToolResult`

在沙箱中执行命令。

```python
executor = SandboxedToolExecutor()
result = executor.execute("rm -rf /")
# result.status: ExecutionStatus.BLOCKED
# result.blocked_reason: "检测到禁用命令: rm -rf /"
```

#### `execute_file_read(path, permission=None) -> ToolResult`

沙箱化文件读取。

#### `execute_file_write(path, content, permission=None) -> ToolResult`

沙箱化文件写入。

### `SandboxConfig`

```python
@dataclass
class SandboxConfig:
    allowed_write_paths: List[str]
    allowed_read_paths: List[str]
    allowed_network_targets: List[str]
    blocked_commands: List[str]
    max_memory_mb: int = 512
    max_cpu_seconds: int = 30
    max_output_bytes: int = 10 * 1024 * 1024
    allow_network: bool = False
    allow_subprocess: bool = False
```

---

## 错误处理

所有 API 在异常情况下返回带 `reason`/`blocked_reason`/`error` 字段的结果对象，**不抛出异常**（除网络/IO 错误）。

```python
result = pipeline.process_input(text, source="external")
if not result.allowed:
    log.warning(f"Argus blocked: {result.blocked_reason}")
    log.debug(f"Findings: {result.layer_findings}")
```

---

## 性能

| 操作 | 延迟 |
|------|------|
| `process_input` | <10ms |
| `process_tool_call` | <20ms |
| `process_output` | <10ms |
| `DefensePipeline` (完整) | <50ms |

---

## 版本

- **当前**：v0.1.0 (Phase 1 MVP)
- **下一**：v0.2.0 (Phase 2 — 级联防护 + 人审)