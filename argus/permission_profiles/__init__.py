# -*- coding: utf-8 -*-
"""
Argus 预定义 Agent 能力画像模板

按最小权限原则预配置：
- read_only_agent: 只读 Agent
- research_agent: 调研 Agent（含读 + 网络）
- code_assistant: 代码助手（含读 + 写，不含执行）
- executor_agent: 执行 Agent（含读 + 写 + 执行）
- admin_agent: 管理员 Agent（含所有权限）
"""

from argus.permission_resolver import (
    AgentCapabilityProfile,
    ToolPermission,
    AutonomyLevel,
)


def read_only_agent(agent_did: str) -> AgentCapabilityProfile:
    """
    只读 Agent 画像。
    适用场景：监控、日志分析、数据查询
    """
    return AgentCapabilityProfile(
        agent_did=agent_did,
        max_autonomy_level=AutonomyLevel.AGENT_AUTONOMOUS,
        permissions={
            "read_file": ToolPermission(
                tool_name="read_file",
                allowed_actions=["GET"],
                allowed_resources=["/workspace/", "/tmp/"],
                rate_limit=100,
                max_data_volume=50 * 1024 * 1024,
            ),
            "list_directory": ToolPermission(
                tool_name="list_directory",
                allowed_actions=["LIST"],
                allowed_resources=["/workspace/", "/tmp/"],
                rate_limit=200,
            ),
            "http_request": ToolPermission(
                tool_name="http_request",
                allowed_actions=["GET"],
                allowed_resources=["https://*"],
                rate_limit=30,
            ),
        },
    )


def research_agent(agent_did: str) -> AgentCapabilityProfile:
    """
    调研 Agent 画像。
    适用场景：信息收集、文献调研、网页抓取
    """
    return AgentCapabilityProfile(
        agent_did=agent_did,
        max_autonomy_level=AutonomyLevel.AGENT_AUTONOMOUS,
        permissions={
            "read_file": ToolPermission(
                tool_name="read_file",
                allowed_actions=["GET"],
                allowed_resources=["/workspace/", "/tmp/", "/home/"],
                rate_limit=200,
                max_data_volume=100 * 1024 * 1024,
            ),
            "list_directory": ToolPermission(
                tool_name="list_directory",
                allowed_actions=["LIST"],
                allowed_resources=["/workspace/", "/tmp/", "/home/"],
                rate_limit=300,
            ),
            "http_request": ToolPermission(
                tool_name="http_request",
                allowed_actions=["GET"],
                allowed_resources=["https://*", "http://internal.*"],
                rate_limit=50,
                max_data_volume=10 * 1024 * 1024,
            ),
        },
    )


def code_assistant_agent(agent_did: str) -> AgentCapabilityProfile:
    """
    代码助手 Agent 画像。
    适用场景：代码生成、代码编辑、文档撰写
    """
    return AgentCapabilityProfile(
        agent_did=agent_did,
        max_autonomy_level=AutonomyLevel.USER_AUTHORIZED,
        permissions={
            "read_file": ToolPermission(
                tool_name="read_file",
                allowed_actions=["GET"],
                allowed_resources=["/workspace/", "/tmp/", "/home/"],
                rate_limit=200,
            ),
            "write_file": ToolPermission(
                tool_name="write_file",
                allowed_actions=["POST", "PUT"],
                allowed_resources=["/workspace/*", "/tmp/*"],
                rate_limit=50,
                require_approval=True,
            ),
            "list_directory": ToolPermission(
                tool_name="list_directory",
                allowed_actions=["LIST"],
                allowed_resources=["/workspace/", "/tmp/", "/home/"],
                rate_limit=300,
            ),
            "create_directory": ToolPermission(
                tool_name="create_directory",
                allowed_actions=["POST"],
                allowed_resources=["/workspace/*"],
                rate_limit=20,
                require_approval=True,
            ),
        },
    )


def executor_agent(agent_did: str) -> AgentCapabilityProfile:
    """
    执行 Agent 画像（含命令执行能力）。
    适用场景：CI/CD、自动化任务、运维
    """
    return AgentCapabilityProfile(
        agent_did=agent_did,
        max_autonomy_level=AutonomyLevel.USER_AUTHORIZED,
        permissions={
            "read_file": ToolPermission(
                tool_name="read_file",
                allowed_actions=["GET"],
                allowed_resources=["/workspace/", "/tmp/", "/home/"],
                rate_limit=200,
            ),
            "write_file": ToolPermission(
                tool_name="write_file",
                allowed_actions=["POST", "PUT"],
                allowed_resources=["/workspace/*", "/tmp/*"],
                rate_limit=50,
                require_approval=True,
            ),
            "execute_command": ToolPermission(
                tool_name="execute_command",
                allowed_actions=["EXECUTE"],
                allowed_resources=["*"],
                rate_limit=20,
                require_approval=True,
            ),
            "http_request": ToolPermission(
                tool_name="http_request",
                allowed_actions=["GET", "POST"],
                allowed_resources=["https://api.*", "http://localhost:*"],
                rate_limit=30,
                require_approval=True,
            ),
        },
    )


def admin_agent(agent_did: str) -> AgentCapabilityProfile:
    """
    管理员 Agent 画像（所有权限）。
    适用场景：系统管理、紧急干预、调试
    """
    return AgentCapabilityProfile(
        agent_did=agent_did,
        max_autonomy_level=AutonomyLevel.AGENT_AUTONOMOUS,
        permissions={
            "read_file": ToolPermission(
                tool_name="read_file",
                allowed_actions=["GET"],
                allowed_resources=["*"],
                rate_limit=1000,
            ),
            "write_file": ToolPermission(
                tool_name="write_file",
                allowed_actions=["POST", "PUT"],
                allowed_resources=["*"],
                rate_limit=500,
                require_approval=True,
            ),
            "delete_file": ToolPermission(
                tool_name="delete_file",
                allowed_actions=["DELETE"],
                allowed_resources=["*"],
                rate_limit=50,
                require_approval=True,
            ),
            "execute_command": ToolPermission(
                tool_name="execute_command",
                allowed_actions=["EXECUTE"],
                allowed_resources=["*"],
                rate_limit=100,
                require_approval=True,
            ),
            "execute_sql": ToolPermission(
                tool_name="execute_sql",
                allowed_actions=["EXECUTE"],
                allowed_resources=["*"],
                rate_limit=100,
                require_approval=True,
            ),
            "send_email": ToolPermission(
                tool_name="send_email",
                allowed_actions=["POST"],
                allowed_resources=["*"],
                rate_limit=20,
                require_approval=True,
            ),
            "http_request": ToolPermission(
                tool_name="http_request",
                allowed_actions=["GET", "POST", "PUT", "DELETE"],
                allowed_resources=["*"],
                rate_limit=500,
                require_approval=True,
            ),
        },
    )


# 便捷函数
PROFILES = {
    "read_only": read_only_agent,
    "research": research_agent,
    "code_assistant": code_assistant_agent,
    "executor": executor_agent,
    "admin": admin_agent,
}


def get_profile(profile_name: str, agent_did: str) -> AgentCapabilityProfile:
    """获取预定义画像"""
    factory = PROFILES.get(profile_name)
    if not factory:
        raise ValueError(f"未知的画像: {profile_name}. 可选: {list(PROFILES.keys())}")
    return factory(agent_did)


def register_profile(resolver, profile_name: str, agent_did: str):
    """注册预定义画像到解析器"""
    profile = get_profile(profile_name, agent_did)
    resolver.register_profile(profile)
    return profile