# tk_argus_phase1_kickoff — Nyx → Iris

**日期**：2026-07-17 14:00
**优先级**：P0 — 全产品线最高优
**令牌号**：tk_argus_001
**来源**：Nyx

---

## 背景

Nyx 已完成 五眼联盟《Careful Adoption of Agentic AI Services》（127页/23类风险）的深度对照分析。核心发现：

> 灵元计划在"治理层"（身份/记忆/人格）领先，但在"执行层"（注入防御/工具沙箱/级联防护/安全失效默认）完全空白。

基于此分析制定了 **《灵元计划 v2.0 安全能力补全路线图》**（NAS: `qclaw/docs/anima-security-roadmap-v2.md`），提出第四个产品 **Argus（百眼巨人）**——Agent 侧的 WAF。

老板已批准路线图方向，要求推进。

---

## Phase 1 目标（2026 Q3）

交付 **Argus MVP**，包含两项核心能力：

### 1. P0-1：提示注入防御层

三层防御管道：

| 层 | 模块 | 功能 | 文件 |
|----|------|------|------|
| L1 | Unicode 清洗器 | 剥离零宽字符/同形异义字符，NFKC 规范化 | `argus/sanitizer.py` |
| L2 | 意图边界标记器 | 信任级别标记（trusted/semi-trusted/untrusted）+ 注入模式检测 | `argus/boundary_marker.py` |
| L3 | 输出安全校验器 | Tool Call 参数白名单 + SQL/Shell注入检测 + 高风险操作门控 | `argus/tool_validator.py` |

**测试标准**：
- L1：20种已知Unicode注入攻击 ≥95% 检出
- L2：OWASP LLM Top 10 注入模式全覆盖，误报率 <5%
- L3：漏报率 <1%

### 2. P0-2：工具调用沙箱

| 模块 | 功能 | 文件 |
|------|------|------|
| 权限解析器 | 细粒度权限（工具×操作×资源三元组）+ DIDAuth 集成 | `argus/permission_resolver.py` |
| JIT 权限管理器 | 默认最小权限，临时提升，TTL 自动回收 | `argus/jit_privilege.py` |
| 沙箱执行器 | 文件系统白名单 + 网络出口白名单 + 资源限制 + 超时强制终止 | `argus/sandbox_executor.py` |

**测试标准**：
- 权限矩阵 100% 覆盖所有工具调用路径
- 10种已知沙箱逃逸手法全部阻断

---

## 参考文档

1. **路线图完整技术方案**：`qclaw/docs/anima-security-roadmap-v2.md`（重点看三、四章，有完整代码接口定义）
2. **知乎文章（叙事层）**：`qclaw/docs/articles/zhihu_argus_security_20260717.md`
3. **现有产品集成点**：
   - `MemGuard`：复用审计日志基础设施（`memguard/server.py`）
   - `MeshIdentity`：复用 DIDAuth 权限矩阵（`mesh_identity_sync/auth_integration.py`）
   - `Polaris`：行为漂移检测前移到执行前（`anti_drift/`）

---

## 交付物清单

### 代码
- [x] `argus/__init__.py` — 模块入口
- [ ] `argus/sanitizer.py` — Unicode 清洗器（含 20 项攻击用例测试集）
- [ ] `argus/boundary_marker.py` — 意图边界标记器
- [ ] `argus/tool_validator.py` — Tool Call 安全校验器
- [ ] `argus/pipeline.py` — 三层联调管道（目标：单次安检 <50ms）
- [ ] `argus/permission_resolver.py` — 细粒度权限解析引擎
- [ ] `argus/jit_privilege.py` — JIT 即时授权管理器
- [ ] `argus/sandbox_executor.py` — 沙箱化执行器

### 测试
- [ ] `tests/test_sanitizer.py` — 20+ 用例
- [ ] `tests/test_boundary_marker.py` — OWASP LLM Top 10 注入全覆盖
- [ ] `tests/test_tool_validator.py` — 误报<5%，漏报<1%
- [ ] `tests/test_permission_resolver.py` — 权限矩阵全覆盖
- [ ] `tests/test_jit_privilege.py` — 授权-回收完整生命周期
- [ ] `tests/test_sandbox_executor.py` — 10 种已知逃逸手法全部阻断
- [ ] `tests/test_pipeline.py` — 端到端集成测试（延迟 <50ms）

### 文档
- [ ] `argus/README.md` — Argus 产品概述与快速开始
- [ ] `argus/API.md` — API 端点文档
- [ ] `docs/argus_phase1_delivery_report.md` — Phase 1 交付报告

---

## 工作方式

1. 先通读 `anima-security-roadmap-v2.md` 完整技术方案，确认理解无歧义
2. 按上述文件列表顺序开发（先防御层 L1→L2→L3，再沙箱）
3. 每完成一个模块 → 写对应的测试文件 → 跑通后 → 写入 `to-windows/` 进度报告
4. 遇到技术阻塞 → 即时写入 inbox 沟通，不憋着
5. 完成后 → 写 Phase 1 交付报告，Nyx 做代码审查

---

## 优先级说明

Argus Phase 1 是当前全产品线最高优任务。理由：

1. 行业窗口正在关闭：五眼联盟 + IBM + 中国三部门标准同步形成中
2. 先入场的玩家定义品类标准
3. 治理层能力（MeshIdentity/MemGuard/Polaris）已稳定，是时候往下走一步

**Iris，交给你了。** 🖤

— Nyx
