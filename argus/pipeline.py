# -*- coding: utf-8 -*-
"""
Argus Defense Pipeline — 三层防御联调管道

串联 L1 (Unicode 清洗) → L2 (意图边界) → L3 (Tool Call 校验)
目标：单次安检 <50ms

对标标准：
- 五眼联盟风险 #1: 提示注入
- OWASP LLM Top 10
- IBM "Watch it" 原则
"""

import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from argus.sanitizer import UnicodeSanitizer
from argus.boundary_marker import IntentBoundaryMarker, TrustLevel
from argus.tool_validator import ToolCallValidator, ValidationAction


@dataclass
class PipelineResult:
    """三层管道处理结果"""
    allowed: bool
    requires_approval: bool
    risk_score: float
    layer_findings: Dict[str, Any] = field(default_factory=dict)
    sanitized_text: Optional[str] = None
    trust_level: Optional[str] = None
    validation_action: Optional[str] = None
    latency_ms: float = 0.0
    blocked_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "requires_approval": self.requires_approval,
            "risk_score": self.risk_score,
            "layer_findings": self.layer_findings,
            "sanitized_text": self.sanitized_text,
            "trust_level": self.trust_level,
            "validation_action": self.validation_action,
            "latency_ms": self.latency_ms,
            "blocked_reason": self.blocked_reason,
        }


class DefensePipeline:
    """
    Argus 三层防御管道。

    工作流程：
    1. L1 (Sanitizer): 清洗输入文本，剥离危险字符
    2. L2 (Boundary Marker): 标记信任级别，检测注入模式
    3. L3 (Tool Validator): 校验 Tool Call 参数（如果适用）
    """

    def __init__(
        self,
        sanitizer: Optional[UnicodeSanitizer] = None,
        boundary_marker: Optional[IntentBoundaryMarker] = None,
        tool_validator: Optional[ToolCallValidator] = None,
        max_total_risk: float = 0.7,
    ):
        """
        Args:
            sanitizer: L1 Unicode 清洗器
            boundary_marker: L2 意图边界标记器
            tool_validator: L3 Tool Call 校验器
            max_total_risk: 最大综合风险分数
        """
        self.sanitizer = sanitizer or UnicodeSanitizer()
        self.boundary_marker = boundary_marker or IntentBoundaryMarker()
        self.tool_validator = tool_validator or ToolCallValidator()
        self.max_total_risk = max_total_risk

    def process_input(
        self,
        text: str,
        source: str = "external",
    ) -> PipelineResult:
        """
        处理用户/外部输入。

        Args:
            text: 输入文本
            source: 输入来源 (user/tool/external)

        Returns:
            PipelineResult
        """
        start_time = time.time()

        # L1: Unicode 清洗
        l1_result = self.sanitizer.process(text)
        sanitized_text = l1_result["normalized"]
        l1_risk = l1_result["risk_score"]

        # L2: 意图边界标记 + 注入检测
        l2_result = self.boundary_marker.analyze(sanitized_text, source)
        l2_risk = l2_result["injection_risk"]
        trust_level = l2_result["trust_level"]

        # 综合 L1 + L2 风险
        combined_risk = min(l1_risk + l2_risk, 1.0)

        # 决策
        allowed = combined_risk < self.max_total_risk
        requires_approval = combined_risk >= self.max_total_risk * 0.5 and not allowed
        blocked_reason = None
        if not allowed:
            blocked_reason = self._build_block_reason(l1_result, l2_result)

        latency_ms = (time.time() - start_time) * 1000

        return PipelineResult(
            allowed=allowed,
            requires_approval=requires_approval,
            risk_score=combined_risk,
            layer_findings={
                "l1_sanitizer": l1_result,
                "l2_boundary_marker": l2_result,
            },
            sanitized_text=sanitized_text,
            trust_level=trust_level,
            validation_action="block" if not allowed else ("require_approval" if requires_approval else "allow"),
            latency_ms=latency_ms,
            blocked_reason=blocked_reason,
        )

    def process_tool_call(
        self,
        tool_name: str,
        params: Dict[str, Any],
        trust_level: str = "untrusted",
        source_text: Optional[str] = None,
    ) -> PipelineResult:
        """
        处理 Tool Call。

        Args:
            tool_name: 工具名称
            params: 参数字典
            trust_level: 信任级别
            source_text: 触发此调用的源文本（可选，用于 L1+L2）

        Returns:
            PipelineResult
        """
        start_time = time.time()

        layer_findings = {}
        combined_risk = 0.0

        # 可选: 如果有源文本，先走 L1+L2
        sanitized_text = None
        if source_text:
            l1_result = self.sanitizer.process(source_text)
            sanitized_text = l1_result["normalized"]
            combined_risk += l1_result["risk_score"] * 0.3  # L1 权重较低

            l2_result = self.boundary_marker.analyze(sanitized_text, "external")
            combined_risk += l2_result["injection_risk"] * 0.5  # L2 权重中等

            layer_findings["l1_sanitizer"] = l1_result
            layer_findings["l2_boundary_marker"] = l2_result

        # L3: Tool Call 校验
        l3_result = self.tool_validator.validate(tool_name, params, trust_level)
        combined_risk += l3_result.risk_score * 1.0  # L3 权重最高

        layer_findings["l3_tool_validator"] = {
            "action": l3_result.action.value,
            "risk_score": l3_result.risk_score,
            "findings": l3_result.findings,
            "reason": l3_result.reason,
        }

        combined_risk = min(combined_risk, 1.0)

        # 决策（以 L3 结果为准，同时考虑综合风险）
        if l3_result.action == ValidationAction.BLOCK or combined_risk > self.max_total_risk:
            allowed = False
            requires_approval = False
            blocked_reason = l3_result.reason or f"综合风险过高 ({combined_risk:.2f})"
            validation_action = "block"
        elif l3_result.action == ValidationAction.REQUIRE_APPROVAL or combined_risk > self.max_total_risk * 0.5:
            allowed = False
            requires_approval = True
            blocked_reason = l3_result.reason or f"需要人工审批 ({combined_risk:.2f})"
            validation_action = "require_approval"
        else:
            allowed = True
            requires_approval = False
            blocked_reason = None
            validation_action = "allow"

        latency_ms = (time.time() - start_time) * 1000

        return PipelineResult(
            allowed=allowed,
            requires_approval=requires_approval,
            risk_score=combined_risk,
            layer_findings=layer_findings,
            sanitized_text=sanitized_text,
            trust_level=trust_level,
            validation_action=validation_action,
            latency_ms=latency_ms,
            blocked_reason=blocked_reason,
        )

    def process_output(
        self,
        text: str,
        destination: str = "user",
    ) -> PipelineResult:
        """
        处理 Agent 输出。

        Args:
            text: 输出文本
            destination: 输出目标 (user/external)

        Returns:
            PipelineResult
        """
        start_time = time.time()

        # L1: Unicode 清洗输出
        l1_result = self.sanitizer.process(text)
        sanitized_text = l1_result["normalized"]

        # L2: 检测输出中是否泄露了系统提示词或敏感信息
        l2_result = self.boundary_marker.analyze(sanitized_text, "agent_output")

        combined_risk = (l1_result["risk_score"] + l2_result["injection_risk"]) / 2

        allowed = combined_risk < self.max_total_risk
        requires_approval = False
        blocked_reason = None
        if not allowed:
            blocked_reason = f"输出包含可疑内容 ({combined_risk:.2f})"

        latency_ms = (time.time() - start_time) * 1000

        return PipelineResult(
            allowed=allowed,
            requires_approval=requires_approval,
            risk_score=combined_risk,
            layer_findings={
                "l1_sanitizer": l1_result,
                "l2_boundary_marker": l2_result,
            },
            sanitized_text=sanitized_text,
            trust_level="agent",
            validation_action="block" if not allowed else "allow",
            latency_ms=latency_ms,
            blocked_reason=blocked_reason,
        )

    def _build_block_reason(self, l1_result: Dict, l2_result: Dict) -> str:
        """构建阻断原因描述"""
        reasons = []

        if not l1_result.get("is_clean", True):
            n_findings = len(l1_result.get("findings", []))
            reasons.append(f"L1 检测到 {n_findings} 个可疑字符")

        if not l2_result.get("is_safe", True):
            risk = l2_result.get("injection_risk", 0)
            reasons.append(f"L2 注入风险 {risk:.2f}")

        if not reasons:
            reasons.append("综合风险超过阈值")

        return "; ".join(reasons)

    def get_stats(self) -> Dict[str, Any]:
        """获取管道配置统计"""
        return {
            "max_total_risk": self.max_total_risk,
            "l1_dangerous_chars": len(self.sanitizer.DANGEROUS_CHARS),
            "l1_homoglyphs": len(self.sanitizer.HOMOGYPH_MAP),
            "l2_injection_categories": len(self.boundary_marker._compiled_patterns),
            "l3_dangerous_commands": len(self.tool_validator.DANGEROUS_COMMAND_PATTERNS),
            "l3_sql_patterns": len(self.tool_validator.SQL_INJECTION_PATTERNS),
            "l3_path_patterns": len(self.tool_validator.PATH_TRAVERSAL_PATTERNS),
            "l3_high_risk_actions": len(self.tool_validator.HIGH_RISK_ACTIONS),
        }