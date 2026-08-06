# sandbox_tiers.py - 增量沙箱档位（借鉴 Codex workspace-write 设计）
from dataclasses import dataclass, field
from enum import Enum
from typing import Set, List, Optional
import os

class SandboxTier(Enum):
    READ_ONLY = "read-only"
    WORKSPACE_WRITE = "workspace-write"
    DANGER_FULL = "danger-full"

@dataclass
class TierConfig:
    tier: SandboxTier
    allowed_read_paths: List[str] = field(default_factory=list)
    allowed_write_paths: List[str] = field(default_factory=list)
    forbidden_paths: Set[str] = field(default_factory=lambda: {
        "/etc/passwd", "/etc/shadow", "/etc/sudoers",
        "/etc/ssh", "/boot", "/sys", "/proc", "/dev"
    })
    allowed_hosts: List[str] = field(default_factory=list)
    allowed_ports: List[int] = field(default_factory=lambda: [80, 443])
    block_all_outbound: bool = False
    allowed_commands: List[str] = field(default_factory=list)
    forbidden_commands: Set[str] = field(default_factory=set)
    max_file_size_mb: int = 500
    max_execution_seconds: int = 300
    max_processes: int = 10

DANGER_CMDS = {
    "remove_recursive": ["rm", "-rf", "/"],
    "make_filesystem": "mkfs",
    "disk_zero": ["dd", "if=/dev/zero"],
    "mount_ops": ["mount", "umount"],
    "power_ops": ["shutdown", "reboot", "halt", "poweroff"],
    "perm_change": ["chmod", "-R", "/"],
    "process_kill": ["kill", "-9"],
    "disk_format": ["fdisk", "parted"],
}

class SandwichTierManager:
    """沙箱档位管理器"""
    def __init__(self, tier: SandboxTier = SandboxTier.WORKSPACE_WRITE,
                 workspace: str = ".", additional_write_paths=None,
                 additional_allowed_hosts=None):
        self.tier = tier
        self.workspace = os.path.abspath(workspace)
        extra_w = additional_write_paths or []
        extra_h = additional_allowed_hosts or []
        self.config = self._build_config(tier, extra_w, extra_h)

    def _build_config(self, tier, extra_write, extra_hosts):
        cfg = TierConfig(tier=tier)
        if tier == SandboxTier.READ_ONLY:
            cfg.allowed_read_paths = [self.workspace]
            cfg.allowed_write_paths = []
            cfg.block_all_outbound = True
            cfg.forbidden_commands = {
                "rm", "mv", "cp", "dd",
            } | set(DANGER_CMDS["power_ops"]) | {"chmod", "chown"} | \
            {"curl", "wget", "nc", "ncat", "socat"}
            cfg.forbidden_commands.update(DANGER_CMDS["make_filesystem"].split())
            cfg.forbidden_commands.update(DANGER_CMDS["mount_ops"])
        elif tier == SandboxTier.WORKSPACE_WRITE:
            cfg.allowed_read_paths = [self.workspace]
            cfg.allowed_write_paths = [self.workspace] + extra_write
            cfg.allowed_hosts = ["api.github.com", "pypi.org"] + extra_hosts
            cfg.forbidden_commands = {
                "rm -rf /",
            } | set(DANGER_CMDS["power_ops"])
            cfg.forbidden_commands.update(DANGER_CMDS["make_filesystem"].split())
            cfg.forbidden_commands.update(DANGER_CMDS["mount_ops"])
        elif tier == SandboxTier.DANGER_FULL:
            cfg.allowed_read_paths = ["/"]
            cfg.allowed_write_paths = [self.workspace]
            cfg.allowed_hosts = ["*"]
            cfg.forbidden_commands = {
                "rm -rf /",
            } | set(DANGER_CMDS["power_ops"])
            cfg.forbidden_commands.update(DANGER_CMDS["make_filesystem"].split())
            cfg.forbidden_commands.update(DANGER_CMDS["mount_ops"])
        return cfg

    def can_read(self, path):
        abs_path = os.path.abspath(os.path.realpath(path))
        for fb in self.config.forbidden_paths:
            if abs_path.startswith(fb): return False
        for al in self.config.allowed_read_paths:
            if abs_path.startswith(os.path.abspath(al)): return True
        return False

    def can_write(self, path):
        if self.tier == SandboxTier.READ_ONLY: return False
        abs_path = os.path.abspath(os.path.realpath(path))
        for fb in self.config.forbidden_paths:
            if abs_path.startswith(fb): return False
        for al in self.config.allowed_write_paths:
            if abs_path.startswith(os.path.abspath(al)): return True
        return False

    def is_path_safe(self, path, operation="read"):
        if operation == "read":
            ok = self.can_read(path)
            return (ok, "" if ok else f"路径 '{path}' 不在可读范围内")
        ok = self.can_write(path)
        return (ok, "" if ok else f"路径 '{path}' 不可写（{self.tier.value}模式）")

    def can_connect(self, host, port=443):
        if self.config.block_all_outbound: return False
        if "*" in self.config.allowed_hosts: return True
        for al in self.config.allowed_hosts:
            if host == al or host.endswith("." + al.lstrip("*")):
                return port in self.config.allowed_ports
        return False

    def can_execute(self, command):
        cmd_lower = command.strip().lower()
        for fb in self.config.forbidden_commands:
            if fb.lower() in cmd_lower:
                return (False, f"禁止执行: '{fb}'")
        if self.config.allowed_commands:
            cmd_base = cmd_lower.split()[0] if cmd_lower.split() else ""
            if cmd_base not in self.config.allowed_commands:
                return (False, f"'{cmd_base}' 不在白名单中")
        return (True, "")

    def check_resource_limits(self, file_size_bytes=0, duration_ms=0):
        size_mb = file_size_bytes / (1024 * 1024)
        if size_mb > self.config.max_file_size_mb:
            return (False, f"文件 {size_mb:.1f}MB 超限 {self.config.max_file_size_mb}MB")
        if duration_ms / 1000 > self.config.max_execution_seconds:
            return (False, f"执行超限 {self.config.max_execution_seconds}s")
        return (True, "")

class TieredSandwichExecutor:
    """包装 Phase 1 sandbox_executor，注入档位感知"""
    def __init__(self, original_executor, tier: SandboxTier, workspace: str = "."):
        self._original = original_executor
        self.tier_mgr = SandwichTierManager(tier, workspace)

    def can_execute(self, tool_call):
        args = tool_call.get("args", {})
        for key in ("path", "file", "filepath", "dest", "destination"):
            if key in args:
                op = "write" if tool_call.get("tool") in ("write", "create_file", "edit_file") else "read"
                ok, reason = self.tier_mgr.is_path_safe(str(args[key]), op)
                if not ok: return (False, reason)
        for key in ("command", "cmd", "shell"):
            if key in args:
                ok, reason = self.tier_mgr.can_execute(str(args[key]))
                if not ok: return (False, reason)
        for key in ("url", "host", "endpoint"):
            if key in args:
                url = str(args[key])
                host = url.split("://")[-1].split("/")[0].split(":")[0] if "://" in url else url.split("/")[0].split(":")[0]
                port = int(url.split(":")[-1].split("/")[0]) if ":" in url.split("://")[-1] else 443
                if not self.tier_mgr.can_connect(host, port):
                    return (False, f"无网络权限连接 {host}:{port}")
        if hasattr(self._original, 'can_execute'):
            return self._original.can_execute(tool_call)
        return (True, "")
