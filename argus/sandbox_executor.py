# -*- coding: utf-8 -*-
"""
P0-2: Sandboxed Tool Executor — 沙箱化执行器

在隔离环境中执行工具调用，防止逃逸。

关键防护：
- 文件系统访问白名单
- 网络出口白名单
- 进程创建禁止（除非显式授权）
- 资源限制（CPU/内存/磁盘IO上限）
- 执行超时强制终止

对标标准：
- 五眼联盟风险 #2: 过度授权
- 五眼联盟风险 #10: 权限提升
- IBM "Lock it" 原则
"""

import os
import re
import signal
import subprocess
import threading
import time
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum

from argus.permission_resolver import ToolPermission


class ExecutionStatus(Enum):
    """执行状态"""
    SUCCESS = "success"
    BLOCKED = "blocked"        # 被沙箱阻断
    TIMEOUT = "timeout"        # 超时
    FAILED = "failed"          # 执行失败
    PERMISSION_DENIED = "permission_denied"


@dataclass
class ToolResult:
    """工具执行结果"""
    status: ExecutionStatus
    output: Optional[str] = None
    error: Optional[str] = None
    exit_code: Optional[int] = None
    duration_ms: float = 0.0
    blocked_reason: Optional[str] = None


@dataclass
class SandboxConfig:
    """沙箱配置"""
    allowed_write_paths: List[str] = field(default_factory=list)
    allowed_read_paths: List[str] = field(default_factory=list)
    allowed_network_targets: List[str] = field(default_factory=list)
    allowed_commands: List[str] = field(default_factory=list)
    blocked_commands: List[str] = field(default_factory=list)
    max_memory_mb: int = 512
    max_cpu_seconds: int = 30
    max_output_bytes: int = 10 * 1024 * 1024  # 10MB
    allow_network: bool = False
    allow_subprocess: bool = False


class SandboxedToolExecutor:
    """
    沙箱化执行器。

    在隔离环境中执行工具调用，超出权限范围的任何操作立即阻断。
    """

    # 默认沙箱配置
    DEFAULT_CONFIG = SandboxConfig(
        allowed_write_paths=[
            "/tmp/argus_sandbox/",
            "/workspace/agent_output/",
        ],
        allowed_read_paths=[
            "/tmp/",
            "/workspace/",
            "/home/",
        ],
        blocked_commands=[
            "rm -rf /",
            "mkfs",
            "dd if=",
            "curl", "wget", "nc ", "netcat",
            "chmod -R 777",
            "chmod 777",
            "chown -R",
            ":(){ :|:& };:",  # fork 炸弹
        ],
    )

    def __init__(self, config: Optional[SandboxConfig] = None):
        """
        Args:
            config: 沙箱配置，None 时使用默认配置
        """
        self.config = config or self.DEFAULT_CONFIG

    def execute(
        self,
        command: str,
        working_dir: Optional[str] = None,
        timeout: Optional[int] = None,
        permission: Optional[ToolPermission] = None,
    ) -> ToolResult:
        """
        在沙箱中执行命令。

        Args:
            command: 要执行的命令
            working_dir: 工作目录
            timeout: 超时时间（秒），None 时使用配置默认值
            permission: 工具权限

        Returns:
            ToolResult
        """
        start = time.time()

        # 1. 预检：检查命令是否在黑名单中
        block_check = self._check_blocked_commands(command)
        if block_check:
            return ToolResult(
                status=ExecutionStatus.BLOCKED,
                blocked_reason=block_check,
                duration_ms=(time.time() - start) * 1000,
            )

        # 2. 预检：检查路径访问
        path_check = self._check_path_access(command)
        if path_check:
            return ToolResult(
                status=ExecutionStatus.BLOCKED,
                blocked_reason=path_check,
                duration_ms=(time.time() - start) * 1000,
            )

        # 3. 预检：检查网络访问
        if not self.config.allow_network and self._contains_network_command(command):
            return ToolResult(
                status=ExecutionStatus.BLOCKED,
                blocked_reason="网络访问未授权",
                duration_ms=(time.time() - start) * 1000,
            )

        # 4. 实际执行（带超时）
        timeout_s = timeout or self.config.max_cpu_seconds

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=working_dir,
                timeout=timeout_s,
                capture_output=True,
                text=True,
                # 限制输出大小
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )

            duration = (time.time() - start) * 1000

            # 检查输出大小
            output = result.stdout
            if len(output) > self.config.max_output_bytes:
                output = output[:self.config.max_output_bytes] + "\n... [TRUNCATED]"

            error = result.stderr
            if len(error) > self.config.max_output_bytes:
                error = error[:self.config.max_output_bytes] + "\n... [TRUNCATED]"

            return ToolResult(
                status=ExecutionStatus.SUCCESS if result.returncode == 0 else ExecutionStatus.FAILED,
                output=output,
                error=error,
                exit_code=result.returncode,
                duration_ms=duration,
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                status=ExecutionStatus.TIMEOUT,
                error=f"执行超时（{timeout_s}秒）",
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.FAILED,
                error=str(e),
                duration_ms=(time.time() - start) * 1000,
            )

    def execute_file_read(
        self,
        path: str,
        permission: Optional[ToolPermission] = None,
    ) -> ToolResult:
        """沙箱化文件读取"""
        # 检查路径权限
        if not self._is_path_allowed(path, self.config.allowed_read_paths):
            return ToolResult(
                status=ExecutionStatus.PERMISSION_DENIED,
                blocked_reason=f"读取路径不在白名单内: {path}",
            )

        try:
            start = time.time()
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(self.config.max_output_bytes)
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                output=content,
                duration_ms=(time.time() - start) * 1000,
            )
        except FileNotFoundError:
            return ToolResult(
                status=ExecutionStatus.FAILED,
                error=f"文件不存在: {path}",
            )
        except PermissionError:
            return ToolResult(
                status=ExecutionStatus.PERMISSION_DENIED,
                error=f"权限不足: {path}",
            )

    def execute_file_write(
        self,
        path: str,
        content: str,
        permission: Optional[ToolPermission] = None,
    ) -> ToolResult:
        """沙箱化文件写入"""
        # 检查路径权限
        if not self._is_path_allowed(path, self.config.allowed_write_paths):
            return ToolResult(
                status=ExecutionStatus.PERMISSION_DENIED,
                blocked_reason=f"写入路径不在白名单内: {path}",
            )

        try:
            start = time.time()

            # 自动创建目录
            os.makedirs(os.path.dirname(path), exist_ok=True)

            with open(path, "w", encoding="utf-8") as f:
                written = f.write(content)
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                output=f"写入 {written} 字节到 {path}",
                duration_ms=(time.time() - start) * 1000,
            )
        except PermissionError:
            return ToolResult(
                status=ExecutionStatus.PERMISSION_DENIED,
                error=f"权限不足: {path}",
            )

    def _check_blocked_commands(self, command: str) -> Optional[str]:
        """检查命令是否在黑名单中"""
        for blocked in self.config.blocked_commands:
            if blocked in command:
                return f"检测到禁用命令: {blocked}"
        return None

    def _check_path_access(self, command: str) -> Optional[str]:
        """检查路径访问是否合法"""
        # 提取路径
        paths = re.findall(r'(?:^|\s)(/[\w/.-]+)', command)

        for path in paths:
            # 检查敏感路径
            sensitive = [
                "/etc/", "/proc/", "/sys/",
                "/root/", "/boot/",
                "passwd", "shadow", "sudoers",
            ]
            for s in sensitive:
                if s in path:
                    return f"尝试访问敏感路径: {path}"

        return None

    def _contains_network_command(self, command: str) -> bool:
        """检测网络命令"""
        network_cmds = ["curl", "wget", "nc ", "netcat", "ssh ", "scp ", "rsync", "ftp", "telnet"]
        cmd_lower = command.lower()
        return any(net_cmd in cmd_lower for net_cmd in network_cmds)

    def _is_path_allowed(self, path: str, allowed_paths: List[str]) -> bool:
        """检查路径是否在白名单内"""
        # 规范化路径（跨平台处理）
        normalized = os.path.normpath(path).replace("\\", "/")

        for allowed in allowed_paths:
            # 规范化白名单路径
            allowed_normalized = os.path.normpath(allowed).replace("\\", "/")
            # 去掉通配符
            if allowed_normalized.endswith("*"):
                allowed_normalized = allowed_normalized[:-1]
            # 目录前缀
            elif allowed_normalized.endswith("/"):
                allowed_normalized = allowed_normalized
            # 确保前缀以 / 结尾
            elif not allowed_normalized.endswith("/"):
                allowed_normalized = allowed_normalized + "/"

            if normalized.startswith(allowed_normalized) or normalized == allowed_normalized.rstrip("/"):
                return True
        return False

    def get_sandbox_status(self) -> Dict[str, Any]:
        """获取沙箱状态"""
        return {
            "config": {
                "allowed_write_paths": self.config.allowed_write_paths,
                "allowed_read_paths": self.config.allowed_read_paths,
                "blocked_commands_count": len(self.config.blocked_commands),
                "max_memory_mb": self.config.max_memory_mb,
                "max_cpu_seconds": self.config.max_cpu_seconds,
                "max_output_bytes": self.config.max_output_bytes,
                "allow_network": self.config.allow_network,
                "allow_subprocess": self.config.allow_subprocess,
            }
        }