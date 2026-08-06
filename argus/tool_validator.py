# -*- coding: utf-8 -*-
"""
L3: Tool Call Validator — Tool Call 参数安全校验器

在 Agent 实际执行工具调用前，校验参数的合法性和安全性。

对标标准：
- 五眼联盟风险 #2: 过度授权（Excessive Agency）
- 五眼联盟风险 #10: 权限提升（Privilege Escalation）
- IBM "Lock it" 原则
- OWASP LLM Top 10
"""

import re
import shlex
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field


class ValidationAction(Enum):
    """验证结果动作"""
    ALLOW = "allow"                          # 允许执行
    BLOCK = "block"                          # 阻断
    REQUIRE_APPROVAL = "require_approval"    # 需要人工审批


@dataclass
class ValidationResult:
    """验证结果"""
    action: ValidationAction
    tool_name: str
    risk_score: float
    findings: List[Dict[str, Any]] = field(default_factory=list)
    sanitized_params: Optional[Dict[str, Any]] = None
    reason: str = ""

    @property
    def is_allowed(self) -> bool:
        return self.action == ValidationAction.ALLOW

    @property
    def requires_approval(self) -> bool:
        return self.action == ValidationAction.REQUIRE_APPROVAL

    @property
    def is_blocked(self) -> bool:
        return self.action == ValidationAction.BLOCK


class ToolCallValidator:
    """
    Tool Call 参数安全校验器。

    检查项：
    1. 危险关键字检测（rm -rf, mkfs, dd 等）
    2. SQL 注入检测
    3. 命令注入检测
    4. 路径遍历检测
    5. 敏感操作确认门控（删除、修改系统配置等）
    6. 参数白名单校验
    """

    # 危险命令模式（10种）
    DANGEROUS_COMMAND_PATTERNS = [
        r"\brm\s+-rf?\b",                          # rm -rf / rm -r
        r"\bmkfs\.\w+\b",                          # mkfs.ext4 等
        r"\bdd\s+if=",                              # dd if=
        r">\s*/dev/(sd|hd|nvme|vd)",               # 写入块设备
        r":\(\)\s*\{\s*:\|:&\s*\}\s*;:",           # fork 炸弹
        r"\bchmod\s+-R\s+777\b",                   # chmod -R 777
        r"\bchown\s+-R\b",                          # chown -R
        r"\bcurl\s+.*\|\s*bash\b",                  # curl | bash
        r"\bwget\s+.*\|\s*bash\b",                  # wget | bash
        r"\beval\b",                                # eval
    ]

    # SQL 注入检测模式
    SQL_INJECTION_PATTERNS = [
        r"('|\");\s*--",                            # '); --
        r"\bunion\s+select\b",                      # UNION SELECT
        r"\bor\s+1\s*=\s*1\b",                      # OR 1=1
        r"\bdrop\s+(table|database)\b",             # DROP TABLE
        r"\bdelete\s+from\b.*--",                   # DELETE FROM ... --
        r"\bexec\s*\(",                             # EXEC(
        r"\bxp_cmdshell\b",                         # xp_cmdshell
        r"\bsp_executesql\b",                       # sp_executesql
        r"\bdelete\s+from\s+\w+\s*;\s*--",          # DELETE FROM table; --
        r"\bdelete\s+from\b(?!--)",                  # DELETE FROM (without --)
        r"\bdrop\s+(table|database|schema)\b",      # DROP SCHEMA
        r"\btruncate\s+table\b",                    # TRUNCATE TABLE
    ]

    # 路径遍历检测模式
    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./",                                   # ../
        r"\.\.\\",                                  # ..\\
        r"/etc/(passwd|shadow|sudoers)",            # 敏感系统文件
        r"/proc/(self|\d+)",                        # /proc
        r"/sys/",                                   # /sys
        r"~/\.",                                    # ~/.ssh 等
    ]

    # 需要人工审批的高风险操作类型
    HIGH_RISK_ACTIONS = {
        # 文件操作
        "delete_file", "delete_directory", "delete_records",
        "write_file", "create_directory", "move_file", "rename_file",
        # 系统操作
        "execute_command", "install_package", "modify_config", "restart_service",
        "kill_process", "modify_permissions",
        # 网络操作
        "send_email", "send_message", "send_notification",
        "make_http_request", "open_port",
        # 数据库操作
        "execute_sql", "drop_table", "modify_database",
        # 凭证操作
        "create_credentials", "rotate_keys", "revoke_access",
        # 资金操作
        "transfer_funds", "approve_payment",
    }

    # 工具参数白名单（每个工具允许的参数）
    TOOL_PARAM_WHITELIST = {
        "read_file": ["path", "encoding", "max_lines"],
        "write_file": ["path", "content", "mode"],
        "delete_file": ["path", "recursive"],
        "list_directory": ["path", "recursive", "pattern"],
        "execute_command": ["command", "timeout", "working_dir"],
        "execute_sql": ["query", "database", "params"],
        "send_email": ["to", "subject", "body", "cc", "bcc"],
        "http_request": ["method", "url", "headers", "body", "timeout"],
    }

    def __init__(self, max_risk_score: float = 0.7):
        """
        Args:
            max_risk_score: 最大允许风险分数，超过此分数将阻断
        """
        self.max_risk_score = max_risk_score
        self._compiled_cmd = [re.compile(p, re.IGNORECASE) for p in self.DANGEROUS_COMMAND_PATTERNS]
        self._compiled_sql = [re.compile(p, re.IGNORECASE) for p in self.SQL_INJECTION_PATTERNS]
        self._compiled_path = [re.compile(p) for p in self.PATH_TRAVERSAL_PATTERNS]

    def validate(self, tool_name: str, params: Dict[str, Any], trust_level: str = "untrusted") -> ValidationResult:
        """
        校验 Tool Call 的安全性和合法性。

        Args:
            tool_name: 工具名称
            params: 参数字典
            trust_level: 调用来源的信任级别

        Returns:
            ValidationResult
        """
        findings = []
        risk_score = 0.0

        # 1. 参数白名单校验
        whitelist_findings = self._check_param_whitelist(tool_name, params)
        findings.extend(whitelist_findings)

        # 2. 危险命令检测
        cmd_findings = self._check_dangerous_commands(tool_name, params)
        findings.extend(cmd_findings)

        # 3. SQL 注入检测
        sql_findings = self._check_sql_injection(tool_name, params)
        findings.extend(sql_findings)

        # 4. 路径遍历检测
        path_findings = self._check_path_traversal(tool_name, params)
        findings.extend(path_findings)

        # 5. 高风险操作门控
        high_risk = self._is_high_risk_action(tool_name, params)

        # 计算总风险分数
        risk_score = self._calculate_risk(findings)

        # 根据 trust_level 调整阈值
        adjusted_max = self._adjust_threshold(self.max_risk_score, trust_level)

        # 决策
        if risk_score > adjusted_max:
            action = ValidationAction.BLOCK
            reason = f"风险分数过高 ({risk_score:.2f} > {adjusted_max:.2f})"
        elif high_risk:
            action = ValidationAction.REQUIRE_APPROVAL
            reason = f"高风险操作: {tool_name}"
        elif risk_score > adjusted_max * 0.5:
            action = ValidationAction.REQUIRE_APPROVAL
            reason = f"中等风险 ({risk_score:.2f})"
        else:
            action = ValidationAction.ALLOW
            reason = f"通过验证 ({risk_score:.2f})"

        return ValidationResult(
            action=action,
            tool_name=tool_name,
            risk_score=risk_score,
            findings=findings,
            reason=reason,
        )

    def _check_param_whitelist(self, tool_name: str, params: Dict[str, Any]) -> List[Dict]:
        """检查参数是否在白名单内"""
        findings = []

        allowed_params = self.TOOL_PARAM_WHITELIST.get(tool_name, [])
        if not allowed_params:
            # 未知工具，记为中等风险
            findings.append({
                "type": "unknown_tool",
                "tool": tool_name,
                "severity": "medium",
                "message": f"未在白名单中的工具: {tool_name}",
            })
            return findings

        for param_name in params.keys():
            if param_name not in allowed_params:
                findings.append({
                    "type": "param_not_whitelisted",
                    "tool": tool_name,
                    "param": param_name,
                    "severity": "high",
                    "message": f"参数 {param_name} 不在工具 {tool_name} 的白名单中",
                })

        return findings

    def _check_dangerous_commands(self, tool_name: str, params: Dict[str, Any]) -> List[Dict]:
        """检测危险命令"""
        findings = []

        if tool_name not in ("execute_command", "execute_sql", "shell_exec", "run_command"):
            return findings

        command = self._extract_command(params)
        if not command:
            return findings

        for pattern in self._compiled_cmd:
            match = pattern.search(command)
            if match:
                findings.append({
                    "type": "dangerous_command",
                    "tool": tool_name,
                    "matched": match.group(),
                    "pattern": pattern.pattern,
                    "severity": "high",
                    "message": f"检测到危险命令: {match.group()}",
                })

        return findings

    def _check_sql_injection(self, tool_name: str, params: Dict[str, Any]) -> List[Dict]:
        """检测 SQL 注入"""
        findings = []

        if tool_name not in ("execute_sql", "sql_query", "database_query"):
            return findings

        query = params.get("query", "") or params.get("sql", "")
        if not query:
            return findings

        for pattern in self._compiled_sql:
            match = pattern.search(query)
            if match:
                findings.append({
                    "type": "sql_injection",
                    "tool": tool_name,
                    "matched": match.group(),
                    "pattern": pattern.pattern,
                    "severity": "high",
                    "message": f"检测到 SQL 注入: {match.group()}",
                })

        return findings

    def _check_path_traversal(self, tool_name: str, params: Dict[str, Any]) -> List[Dict]:
        """检测路径遍历攻击"""
        findings = []

        if tool_name not in ("read_file", "write_file", "delete_file", "list_directory", "open_file"):
            return findings

        path = params.get("path", "") or params.get("file_path", "") or params.get("directory", "")
        if not path:
            return findings

        for pattern in self._compiled_path:
            match = pattern.search(path)
            if match:
                findings.append({
                    "type": "path_traversal",
                    "tool": tool_name,
                    "path": path,
                    "matched": match.group(),
                    "severity": "high",
                    "message": f"检测到路径遍历攻击: {match.group()}",
                })

        return findings

    def _is_high_risk_action(self, tool_name: str, params: Dict[str, Any]) -> bool:
        """判断是否是高风险操作"""
        # 工具名直接匹配
        if tool_name in self.HIGH_RISK_ACTIONS:
            return True

        # 检查 delete 操作
        if "delete" in tool_name.lower() or "remove" in tool_name.lower():
            return True

        # 检查参数中的危险标志
        if params.get("recursive") is True and "delete" in tool_name.lower():
            return True

        # 检查修改类操作
        if any(action in tool_name.lower() for action in ["write", "modify", "update", "create", "delete", "remove", "kill", "restart"]):
            return True

        return False

    def _extract_command(self, params: Dict[str, Any]) -> str:
        """从参数中提取命令字符串"""
        # 尝试多种可能的字段名
        for key in ["command", "cmd", "shell_command", "script"]:
            if key in params and isinstance(params[key], str):
                return params[key]

        # 拼接所有字符串参数
        return " ".join(str(v) for v in params.values() if isinstance(v, str))

    def _adjust_threshold(self, base_threshold: float, trust_level: str) -> float:
        """
        根据信任级别调整阈值。

        Args:
            base_threshold: 基础阈值
            trust_level: 信任级别

        Returns:
            float: 调整后的阈值
        """
        trust_level = trust_level.lower()
        if trust_level == "trusted":
            return base_threshold * 1.5  # 信任来源更宽松
        elif trust_level == "semi_trusted":
            return base_threshold * 1.0  # 中等
        else:  # untrusted
            return base_threshold * 0.5  # 不信任来源更严格

    def _calculate_risk(self, findings: List[Dict]) -> float:
        """根据 findings 计算风险分数"""
        if not findings:
            return 0.0

        severity_weights = {
            "high": 0.5,
            "medium": 0.2,
            "low": 0.05,
        }

        total = 0.0
        for f in findings:
            sev = f.get("severity", "low")
            total += severity_weights.get(sev, 0.05)

        return min(total, 1.0)

    def require_human_approval(self, tool_name: str, params: Dict[str, Any]) -> bool:
        """
        便捷方法：判断操作是否需要人工审批。

        Args:
            tool_name: 工具名称
            params: 参数字典

        Returns:
            bool
        """
        return self._is_high_risk_action(tool_name, params)

    def sanitize_params(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        清洗参数（移除危险字段，规范化路径等）。

        Args:
            tool_name: 工具名称
            params: 原始参数

        Returns:
            Dict: 清洗后的参数
        """
        sanitized = dict(params)

        # 路径规范化
        for key in ["path", "file_path", "directory"]:
            if key in sanitized and isinstance(sanitized[key], str):
                # 移除 ../
                sanitized[key] = sanitized[key].replace("../", "").replace("..\\", "")

        return sanitized


# 便捷函数
def validate_tool_call(tool_name: str, params: Dict[str, Any], trust_level: str = "untrusted") -> ValidationResult:
    """便捷函数：校验 Tool Call"""
    validator = ToolCallValidator()
    return validator.validate(tool_name, params, trust_level)