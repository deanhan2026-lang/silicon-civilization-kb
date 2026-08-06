# -*- coding: utf-8 -*-
"""
P0-2: Permission Resolver — 细粒度权限解析引擎

为每个工具调用定义细粒度权限，而非按 Agent 粗粒度授权。
五眼联盟的核心教训：宽泛的"写入权限"会变成"删除防火墙日志"的通道。

对标标准：
- 五眼联盟风险 #2: 过度授权（Excessive Agency）
- 五眼联盟风险 #10: 权限提升（Privilege Escalation）
- IBM "Lock it" 原则
"""

from enum import Enum
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
import hashlib
import time


class AutonomyLevel(Enum):
    """自主性级别（对标中国三部门三类决策权限边界）"""
    USER_ONLY = 1        # 仅限用户决策：Agent可建议，不可执行
    USER_AUTHORIZED = 2  # 需用户授权：Agent可发起请求，需人类确认
    AGENT_AUTONOMOUS = 3 # Agent自主决策：低风险、高频、边界清晰的操作


@dataclass
class ToolPermission:
    """工具权限定义"""
    tool_name: str
    allowed_actions: List[str] = field(default_factory=list)
    allowed_resources: List[str] = field(default_factory=list)
    rate_limit: int = 100  # 单位时间最大调用次数
    require_approval: bool = False
    max_data_volume: int = 10 * 1024 * 1024  # 默认10MB

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "allowed_actions": self.allowed_actions,
            "allowed_resources": self.allowed_resources,
            "rate_limit": self.rate_limit,
            "require_approval": self.require_approval,
            "max_data_volume": self.max_data_volume,
        }


@dataclass
class AgentCapabilityProfile:
    """Agent 能力画像"""
    agent_did: str
    permissions: Dict[str, ToolPermission] = field(default_factory=dict)
    max_autonomy_level: AutonomyLevel = AutonomyLevel.AGENT_AUTONOMOUS
    restricted_hours: Optional[tuple] = None
    rate_limit_window: int = 60  # 限流时间窗口（秒）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_did": self.agent_did,
            "max_autonomy_level": self.max_autonomy_level.value,
            "restricted_hours": self.restricted_hours,
            "rate_limit_window": self.rate_limit_window,
            "permissions": {k: v.to_dict() for k, v in self.permissions.items()},
        }


@dataclass
class ToolCallRequest:
    """工具调用请求"""
    tool_name: str
    action: str  # GET, POST, DELETE, etc.
    resource: str
    params: Dict[str, Any] = field(default_factory=dict)
    agent_did: str = ""


@dataclass
class PermissionResolution:
    """权限解析结果"""
    allowed: bool
    require_approval: bool
    reason: str
    matched_permission: Optional[ToolPermission] = None
    risk_level: str = "low"


class PermissionResolver:
    """
    细粒度权限解析引擎。

    接收入站的 DIDAuth Token，解析为具体权限。
    工作流程：
    1. 验证 Agent DID
    2. 查询 Agent 能力画像
    3. 检查工具+操作+资源三元组是否在权限列表内
    4. 检查速率限制
    5. 返回权限结果
    """

    def __init__(self):
        self.profiles: Dict[str, AgentCapabilityProfile] = {}
        self.rate_counters: Dict[str, List[float]] = {}  # agent_did:tool_name -> [timestamps]

    def register_profile(self, profile: AgentCapabilityProfile):
        """注册 Agent 能力画像"""
        self.profiles[profile.agent_did] = profile

    def resolve(self, request: ToolCallRequest) -> PermissionResolution:
        """
        解析 Tool Call 请求的权限。

        Args:
            request: 工具调用请求

        Returns:
            PermissionResolution: 权限解析结果
        """
        # 1. 查找 Agent 能力画像
        profile = self.profiles.get(request.agent_did)
        if not profile:
            return PermissionResolution(
                allowed=False,
                require_approval=False,
                reason=f"Agent 未注册: {request.agent_did}",
                risk_level="high",
            )

        # 2. 查找工具权限
        tool_perm = profile.permissions.get(request.tool_name)
        if not tool_perm:
            return PermissionResolution(
                allowed=False,
                require_approval=False,
                reason=f"Agent 无权访问工具: {request.tool_name}",
                risk_level="high",
            )

        # 3. 检查操作是否允许
        if tool_perm.allowed_actions and request.action not in tool_perm.allowed_actions:
            return PermissionResolution(
                allowed=False,
                require_approval=False,
                reason=f"操作 {request.action} 不在允许列表内",
                risk_level="high",
                matched_permission=tool_perm,
            )

        # 4. 检查资源是否允许
        if tool_perm.allowed_resources and not self._is_resource_allowed(request.resource, tool_perm.allowed_resources):
            return PermissionResolution(
                allowed=False,
                require_approval=False,
                reason=f"资源 {request.resource} 不在允许列表内",
                risk_level="high",
                matched_permission=tool_perm,
            )

        # 5. 检查速率限制
        if not self._check_rate_limit(request.agent_did, request.tool_name, tool_perm.rate_limit, profile.rate_limit_window):
            return PermissionResolution(
                allowed=False,
                require_approval=False,
                reason=f"超过速率限制 ({tool_perm.rate_limit}/窗口)",
                risk_level="medium",
                matched_permission=tool_perm,
            )

        # 6. 检查受限时段
        if profile.restricted_hours and self._is_in_restricted_hours(profile.restricted_hours):
            return PermissionResolution(
                allowed=False,
                require_approval=True,
                reason=f"受限时段操作: {profile.restricted_hours}",
                risk_level="medium",
                matched_permission=tool_perm,
            )

        # 通过
        return PermissionResolution(
            allowed=True,
            require_approval=tool_perm.require_approval,
            reason="通过权限校验",
            matched_permission=tool_perm,
            risk_level="low",
        )

    def _is_resource_allowed(self, resource: str, allowed: List[str]) -> bool:
        """
        检查资源是否在白名单内。

        支持：
        - 精确匹配：pattern == resource
        - 通配符 *：匹配所有资源
        - 前缀通配符 pattern*：匹配以 pattern 开头的资源
        - 目录前缀（以 / 结尾）：匹配该目录下的所有资源
        """
        for pattern in allowed:
            if pattern == "*":
                return True
            if pattern == resource:
                return True
            if pattern.endswith("*") and resource.startswith(pattern[:-1]):
                return True
            # 目录前缀（以 / 结尾）匹配子路径
            if pattern.endswith("/") and resource.startswith(pattern):
                return True
        return False

    def _check_rate_limit(self, agent_did: str, tool_name: str, limit: int, window: int) -> bool:
        """检查速率限制"""
        key = f"{agent_did}:{tool_name}"
        now = time.time()

        # 清理过期记录
        if key in self.rate_counters:
            self.rate_counters[key] = [t for t in self.rate_counters[key] if now - t < window]

        # 计数
        if key not in self.rate_counters:
            self.rate_counters[key] = []

        if len(self.rate_counters[key]) >= limit:
            return False

        self.rate_counters[key].append(now)
        return True

    def _is_in_restricted_hours(self, restricted: tuple) -> bool:
        """
        检查当前是否在受限时段内。

        Args:
            restricted: (start_hour, end_hour) 元组

        Returns:
            bool
        """
        current_hour = time.localtime().tm_hour
        start, end = restricted
        if start <= end:
            return start <= current_hour < end
        else:
            # 跨午夜的情况
            return current_hour >= start or current_hour < end

    def get_agent_permissions(self, agent_did: str) -> Optional[Dict[str, Any]]:
        """获取 Agent 权限摘要"""
        profile = self.profiles.get(agent_did)
        if not profile:
            return None
        return profile.to_dict()

    def list_agents(self) -> List[str]:
        """列出所有已注册 Agent"""
        return list(self.profiles.keys())