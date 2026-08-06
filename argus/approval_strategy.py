# approval_strategy.py — 四级审批策略（借鉴 Codex 设计）

"""
Argus Phase 2 Enhancement: 多级审批策略
借鉴 OpenAI Codex 的 approval_policy 四档模型

档位:
    on-request  — 模型自主判断何时需确认（Phase 1 默认行为）
    on-failure  — 自动执行，失败/异常时才升级人审  ★ 新增
    untrusted   — 所有非只读操作都需确认
    never       — 全自动，CI/CD专用

用法:
    from argus.approval_strategy import ApprovalPolicy, Strategy

    policy = ApprovalPolicy(Strategy.ON_FAILURE)
    result = policy.evaluate(tool_call, risk_level)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable


class Strategy(Enum):
    """审批策略枚举"""
    ON_REQUEST = "on-request"
    ON_FAILURE = "on-failure"
    UNTRUSTED = "untrusted"
    NEVER = "never"


@dataclass
class RiskAssessment:
    """风险评估结果"""
    risk_level: str  # "none" | "low" | "medium" | "high" | "critical"
    reason: str
    requires_approval: bool = True
    auto_executable: bool = False


@dataclass
class ApprovalConfig:
    """审批配置"""
    strategy: Strategy = Strategy.ON_REQUEST
    # on-failure 模式下的失败重试
    max_failures_before_escalation: int = 3
    failure_window_seconds: int = 300
    
    # 自动执行白名单（即使在 untrusted 模式下也允许）
    auto_allow_tools: list = field(default_factory=lambda: ["read_file", "list_dir", "get_status"])
    
    # 永远需要审批的操作（即使在 never 模式下也需确认）
    always_require_approval: list = field(default_factory=lambda: [
        "rm", "delete", "drop", "truncate", "format", "shutdown", "restart"
    ])
    
    # 审计回调
    on_decision: Optional[Callable] = None


class ApprovalPolicy:
    """
    四级审批策略引擎
    
    模型 → 风险评估 → 策略匹配 → 审批/自动执行
    """

    def __init__(self, config: Optional[ApprovalConfig] = None):
        self.config = config or ApprovalConfig()
        self._failure_counts: dict = {}  # 按 tool 记录失败次数

    def evaluate(self, tool_name: str, risk: RiskAssessment) -> dict:
        """
        评估是否需要审批
        
        返回:
            {
                "decision": "auto" | "approve" | "block",
                "reason": str,
                "failures_remaining": int | None  # on-failure 模式下
            }
        """
        # 永远需要审批的操作
        if any(dangerous in tool_name.lower() for dangerous in self.config.always_require_approval):
            return self._decide("block", f"工具 '{tool_name}' 需要强制审批")

        strategy = self.config.strategy

        if strategy == Strategy.NEVER:
            return self._decide("auto", "never 模式: 全自动通过")

        if strategy == Strategy.UNTRUSTED:
            if tool_name in self.config.auto_allow_tools:
                return self._decide("auto", f"白名单工具: {tool_name}")
            return self._decide("approve", "untrusted 模式: 非只读操作需确认")

        if strategy == Strategy.ON_FAILURE:
            return self._evaluate_on_failure(tool_name, risk)

        if strategy == Strategy.ON_REQUEST:
            return self._evaluate_on_request(tool_name, risk)

        # 默认保守
        return self._decide("approve", "未知策略，默认需审批")

    def _evaluate_on_request(self, tool_name: str, risk: RiskAssessment) -> dict:
        """on-request: 模型自主判断"""
        if risk.risk_level in ("none", "low"):
            return self._decide("auto", f"低风险({risk.risk_level}): {risk.reason}")
        if risk.risk_level == "medium":
            if tool_name in self.config.auto_allow_tools:
                return self._decide("auto", f"白名单工具(中风险): {tool_name}")
            return self._decide("approve", f"中风险需确认: {risk.reason}")
        return self._decide("approve", f"高风险({risk.risk_level}): {risk.reason}")

    def _evaluate_on_failure(self, tool_name: str, risk: RiskAssessment) -> dict:
        """on-failure: 先自动执行，失败了再升级"""
        # 高风险操作即使 on-failure 也直接审批
        if risk.risk_level in ("high", "critical"):
            return self._decide("approve", f"高风险({risk.risk_level})跳过 on-failure")

        # 检查失败计数
        key = tool_name
        failures = self._failure_counts.get(key, 0)
        
        if failures >= self.config.max_failures_before_escalation:
            self._failure_counts.pop(key, None)
            return self._decide("approve", f"已失败{failures}次，升级人审")
        
        remaining = self.config.max_failures_before_escalation - failures
        return self._decide(
            "auto",
            f"on-failure 模式: 自动执行（剩余{remaining}次失败机会）",
            failures_remaining=remaining
        )

    def record_failure(self, tool_name: str):
        """记录一次失败（on-failure 模式下调用）"""
        key = tool_name
        self._failure_counts[key] = self._failure_counts.get(key, 0) + 1

    def record_success(self, tool_name: str):
        """成功后重置失败计数"""
        self._failure_counts.pop(tool_name, None)

    def _decide(self, decision: str, reason: str, **extra) -> dict:
        result = {"decision": decision, "reason": reason, **extra}
        if self.config.on_decision:
            self.config.on_decision(result)
        return result


# ========== 与 Argus Pipeline 集成 ==========

class ApprovalAwarePipeline:
    """
    将 ApprovalPolicy 集成到现有 Pipeline 的适配器
    
    用法:
        pipe = ApprovalAwarePipeline(original_pipeline, approval_policy)
        result = pipe.process(tool_call)
    """

    def __init__(self, pipeline, approval_policy: ApprovalPolicy):
        self._pipeline = pipeline
        self.policy = approval_policy

    def process(self, tool_call: dict) -> dict:
        """先做安全校验，再做审批判断"""
        # L1-L3 防御管道（现有）
        safe_result = self._pipeline.process(tool_call)
        if safe_result.get("blocked"):
            return safe_result

        # 风险评估
        risk = self._assess_risk(tool_call)
        
        # 审批判断
        approval = self.policy.evaluate(tool_call.get("tool", "unknown"), risk)
        
        return {
            **safe_result,
            "approval_decision": approval["decision"],
            "approval_reason": approval["reason"],
        }

    def _assess_risk(self, tool_call: dict) -> RiskAssessment:
        tool = tool_call.get("tool", "").lower()
        args = tool_call.get("args", {})
        
        # 写操作判定
        write_verbs = ["write", "create", "delete", "update", "modify", "execute", "run", "install", "chmod", "chown"]
        is_write = any(v in tool for v in write_verbs)
        
        # 系统操作判定
        system_tools = ["bash", "shell", "exec", "system", "subprocess", "os.", "eval"]
        is_system = any(s in tool for s in system_tools)
        
        # 网络操作判定
        if args:
            args_str = str(args).lower()
            has_url = any(kw in args_str for kw in ["http://", "https://", "ftp://", "ssh://"])
        else:
            has_url = False
        
        if is_system and has_url:
            return RiskAssessment("critical", "系统级操作+网络访问")
        if is_system:
            return RiskAssessment("high", "系统级操作")
        if is_write and has_url:
            return RiskAssessment("high", "写操作+网络访问")
        if is_write:
            return RiskAssessment("medium", "写操作")
        if has_url:
            return RiskAssessment("low", "网络访问（只读）")
        
        return RiskAssessment("none", "只读操作")
