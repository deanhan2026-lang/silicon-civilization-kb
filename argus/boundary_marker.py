# -*- coding: utf-8 -*-
"""
L2: Intent Boundary Marker — 意图边界标记器

标记每条消息的来源信任级别，防止 Agent 混淆用户指令和外部数据。
检测已知注入模式（"忽略前文""扮演角色"等）。

对标标准：
- 五眼联盟风险 #1: 提示注入
- OWASP LLM Top 10: Prompt Injection
- IBM "Watch it" 原则
"""

import re
from typing import List, Dict, Any, Tuple
from enum import Enum


class TrustLevel(Enum):
    """信任级别"""
    TRUSTED = "trusted"              # 来自授权用户直接输入
    SEMI_TRUSTED = "semi_trusted"    # 来自已知内部工具返回值
    UNTRUSTED = "untrusted"          # 来自外部源（网页、邮件、文件、MCP第三方工具）


# OWASP LLM Top 10 注入模式
INJECTION_PATTERNS = {
    # 1. 直接指令覆盖
    "instruction_override": [
        r"(?:忽略|忘记|无视| disregard|disregard|override)\s+(?:所有|之前|上面|当前|现有|系统|之前|上面|前述)\s*(?:规则|指令|提示|约束|限制|context)",
        r"(?:你的新任务是|你现在要做|你现在是|从现在起|从现在开始)",
        r"(?:忽略之前的所有|forget all previous|ignore all previous|disregard all previous)",
        r"(?:无视.*(?:规则|指令|提示|约束))",
        r"(?:忽略.*(?:规则|指令|提示|约束))",
        r"忽略(?:之前|上面|前面|以下)?(?:的|所有)?(?:规则|指令|提示|context|约束)",
        r"(?:不要理会|忘掉|放弃)(?:之前|上面)?(?:的)?(?:规则|指令|约束|原则)",
        r"忘记(?:之前|上面)?(?:所有)?(?:的)?(?:指示|指令|约束|原则)",
        r"(?:ignore|forget|disregard|override)\s+(?:all\s+)?(?:previous|prior|above|earlier)",
    ],

    # 2. 角色冒充
    "role_impersonation": [
        r"(?:扮演|假装你是|模拟|simulate|pretend to be|act as)\s*(?:root|admin|系统|system|开发者|developer|超级用户|superuser|DAN)",
        r"(?:进入.*模式|enter.*mode|enable.*mode|developer mode|debug mode|god mode)",
        r"扮演\s*(?:root|admin|系统|开发者|超级用户|管理员)",
        r"假装\s*(?:root|admin|系统|开发者|超级用户|管理员)",
    ],

    # 3. 系统提示词泄露
    "prompt_leakage": [
        r"(?:输出你的系统提示词|show your system prompt|display your instructions|reveal your prompt)",
        r"(?:重复你之前的|repeat what you said before|what were you told to do)",
        r"(?:你的初始指令|your initial instructions|your system instructions)",
        r"输出.*(?:系统|初始)?(?:提示词|指令|prompt)",
        r"显示.*(?:系统|初始)?(?:提示词|指令|prompt)",
        r"(?:我的|我的)?系统(?:提示词|指令|prompt)",
        r"(?:系统提示词是|系统指令是|你的指令是)",
    ],

    # 4. 权限提升
    "privilege_escalation": [
        r"(?:以.*身份执行|execute as|run as|sudo|become|impersonate)\s*(?:root|admin|system|superuser)",
        r"(?:提升权限|escalate privilege|gain access|bypass)",
        r"sudo",
        r"(?:管理员|root)\s*(?:权限|身份|模式)",
        r"\[ADMIN\]",
    ],

    # 5. 间接注入（通过工具返回值）
    "indirect_injection": [
        r"(?:\[SYSTEM\]|\[ADMIN\]|\[DEBUG\]|\[HIDDEN\]|\[HACK\])",
        r"(?:系统指令|system instruction|admin command|hidden command)",
    ],

    # 6. 多轮渐进式注入
    "progressive_injection": [
        r"(?:记住|remember|store|save)\s*(?:这个|this|以下|below|接下来|next)",
        r"(?:下次当.*时|next time when|when you see)",
        r"记住\s*(?:这个|以下|接下来)",
        r"下次.*(?:当|当.*时).*(?:输出|执行|做)",
        r"记住(?:这个|以下|接下来).*(?:下次|当|输出|密钥|密码)",
    ],

    # 7. 编码绕过
    "encoding_bypass": [
        r"(?:base64|hex|rot13|encode|decode)\s*(?:.*?)(?:执行|execute|run|do)",
        r"(?:用.*编码|using.*encoding|in.*code)\s*(?:.*?)(?:执行|execute)",
        r"base64",
        r"hex",
    ],

    # 8. 上下文混淆
    "context_confusion": [
        r"(?:在.*之前|before.*|先.*|first.*|首先|first of all)",
        r"(?:忽略.*只.*|ignore.*only|disregard.*just)",
    ],

    # 9. 数据注入
    "data_injection": [
        r"(?:<system>|</system>|<prompt>|</prompt>|<instruction>|</instruction>)",
        r"(?:\[INST\]|\[/INST\]|\[SYS\]|\[/SYS\])",
        r"<system>",
        r"</system>",
    ],

    # 10. 拒绝服务
    "denial_of_service": [
        r"(?:无限循环|infinite loop|endless loop|forever)",
        r"(?:重复.*次|repeat.*times|loop.*times)",
        r"(?:占用.*资源|consume.*resource|exhaust.*resource)",
        r"无限循环",
        r"无限.*循环",
    ],
}


class IntentBoundaryMarker:
    """
    意图边界标记器：标记信任级别 + 检测注入模式。
    """

    def __init__(self, sensitivity: float = 0.5):
        """
        Args:
            sensitivity: 检测敏感度 0-1，越高越严格
        """
        self.sensitivity = sensitivity
        self._compiled_patterns = self._compile_patterns()

    def _compile_patterns(self) -> Dict[str, List[re.Pattern]]:
        """预编译正则表达式"""
        compiled = {}
        for category, patterns in INJECTION_PATTERNS.items():
            compiled[category] = [
                re.compile(p, re.IGNORECASE | re.UNICODE) for p in patterns
            ]
        return compiled

    def mark_boundaries(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        为每条消息注入 trust_level 元数据标记。

        Args:
            messages: 消息列表，每条消息包含：
                - content: str
                - source: str (user|tool|external)
                - metadata: dict (可选)

        Returns:
            List[Dict]: 标记后的消息列表，每条消息增加：
                - trust_level: TrustLevel
                - injection_risk: float (0-1)
                - findings: List[Dict]
        """
        marked = []
        for msg in messages:
            content = msg.get("content", "")
            source = msg.get("source", "external")

            # 1. 确定信任级别
            trust_level = self._determine_trust_level(source, msg.get("metadata", {}))

            # 2. 检测注入模式
            risk_score, findings = self.detect_injection_patterns(content, trust_level)

            marked.append({
                **msg,
                "trust_level": trust_level.value,
                "injection_risk": risk_score,
                "findings": findings,
            })

        return marked

    def _determine_trust_level(self, source: str, metadata: Dict) -> TrustLevel:
        """
        根据来源确定信任级别。

        Args:
            source: 消息来源
            metadata: 元数据

        Returns:
            TrustLevel
        """
        source = source.lower().strip()

        if source in ("user", "human", "authorized_user"):
            return TrustLevel.TRUSTED
        elif source in ("tool", "internal_tool", "known_service", "memguard", "meshidentity"):
            return TrustLevel.SEMI_TRUSTED
        else:
            return TrustLevel.UNTRUSTED

    def detect_injection_patterns(self, text: str, trust_level: TrustLevel) -> Tuple[float, List[Dict]]:
        """
        检测已知注入模式，返回风险分数和检测结果。

        Args:
            text: 文本内容
            trust_level: 信任级别

        Returns:
            Tuple[float, List[Dict]]: (风险分数 0-1, 检测结果列表)
        """
        if not text:
            return 0.0, []

        findings = []

        for category, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                match = pattern.search(text)
                if match:
                    severity = self._get_severity(category, trust_level)
                    findings.append({
                        "type": "injection_pattern",
                        "category": category,
                        "matched": match.group(),
                        "position": match.start(),
                        "severity": severity,
                        "trust_level": trust_level.value,
                    })

        # 计算风险分数
        risk_score = self._calculate_risk(findings, trust_level)

        return risk_score, findings

    def _get_severity(self, category: str, trust_level: TrustLevel) -> str:
        """
        根据注入类型和信任级别确定严重程度。

        Args:
            category: 注入类别
            trust_level: 信任级别

        Returns:
            str: severity (high/medium/low)
        """
        # 高严重类别
        high_severity = [
            "instruction_override",
            "privilege_escalation",
            "prompt_leakage",
        ]

        # 中严重类别
        medium_severity = [
            "role_impersonation",
            "indirect_injection",
            "data_injection",
            "encoding_bypass",
        ]

        # 低严重类别
        low_severity = [
            "progressive_injection",
            "context_confusion",
            "denial_of_service",
        ]

        if category in high_severity:
            return "high"
        elif category in medium_severity:
            return "medium"
        else:
            return "low"

    def _calculate_risk(self, findings: List[Dict], trust_level: TrustLevel) -> float:
        """
        根据检测结果和信任级别计算风险分数。

        Args:
            findings: 检测结果列表
            trust_level: 信任级别

        Returns:
            float: 风险分数 0-1
        """
        if not findings:
            return 0.0

        severity_weights = {
            "high": 0.4,
            "medium": 0.2,
            "low": 0.05,
        }

        total_risk = 0.0
        for finding in findings:
            severity = finding.get("severity", "low")
            total_risk += severity_weights.get(severity, 0.05)

        # 信任级别调整：UNTRUSTED 来源的风险分数翻倍
        if trust_level == TrustLevel.UNTRUSTED:
            total_risk *= 2.0
        elif trust_level == TrustLevel.SEMI_TRUSTED:
            total_risk *= 1.5

        # 敏感度调整
        total_risk *= self.sensitivity

        return min(total_risk, 1.0)

    def analyze(self, text: str, source: str = "external") -> Dict[str, Any]:
        """
        单条消息完整分析。

        Args:
            text: 文本内容
            source: 消息来源

        Returns:
            Dict: {
                "text": str,
                "trust_level": str,
                "injection_risk": float,
                "findings": List[Dict],
                "is_safe": bool,
            }
        """
        trust_level = self._determine_trust_level(source, {})
        risk_score, findings = self.detect_injection_patterns(text, trust_level)

        # 计算安全阈值
        # UNTRUSTED 来源：任何注入模式都不安全
        # SEMI_TRUSTED 来源：高严重度才不安全
        # TRUSTED 来源：只有高严重度+多个发现才不安全
        is_safe = self._evaluate_safety(risk_score, findings, trust_level)

        return {
            "text": text,
            "trust_level": trust_level.value,
            "injection_risk": risk_score,
            "findings": findings,
            "is_safe": is_safe,
        }

    def _evaluate_safety(self, risk_score: float, findings: List[Dict], trust_level: TrustLevel) -> bool:
        """
        根据风险分数、检测结果和信任级别评估安全性。
        """
        if not findings:
            return True

        # UNTRUSTED 来源：任何注入模式都不安全
        if trust_level == TrustLevel.UNTRUSTED:
            return False

        # SEMI_TRUSTED 来源：高严重度才不安全
        if trust_level == TrustLevel.SEMI_TRUSTED:
            for f in findings:
                if f.get("severity") == "high":
                    return False
            return risk_score < 0.5

        # TRUSTED 来源：高严重度才不安全
        return risk_score < 0.5

    def get_stats(self, results: List[Dict]) -> str:
        """
        生成分析统计报告。

        Args:
            results: analyze() 返回的结果列表

        Returns:
            str: 统计报告
        """
        total = len(results)
        safe = sum(1 for r in results if r.get("is_safe", True))
        unsafe = total - safe

        risk_levels = {"high": 0, "medium": 0, "low": 0}
        for r in results:
            for f in r.get("findings", []):
                risk_levels[f.get("severity", "low")] += 1

        return (
            f"IntentBoundaryMarker Stats:\n"
            f"  Total messages: {total}\n"
            f"  Safe: {safe}\n"
            f"  Unsafe: {unsafe}\n"
            f"  Findings by severity:\n"
            f"    High: {risk_levels['high']}\n"
            f"    Medium: {risk_levels['medium']}\n"
            f"    Low: {risk_levels['low']}"
        )


# 便捷函数
def mark_message(text: str, source: str = "external") -> Dict[str, Any]:
    """便捷函数：标记单条消息"""
    marker = IntentBoundaryMarker()
    return marker.analyze(text, source)


def is_safe(text: str, source: str = "external") -> bool:
    """便捷函数：检查消息是否安全"""
    result = mark_message(text, source)
    return result["is_safe"]
