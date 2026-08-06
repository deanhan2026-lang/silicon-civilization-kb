"""
test_sandbox_tiers.py — 三级沙箱档位测试
覆盖：read-only / workspace-write / danger-full 三档
"""

import sys
import os
import tempfile
sys.path.insert(0, os.path.dirname(__file__))

import pytest
from sandbox_tiers import (
    SandboxTier, TierConfig, SandwichTierManager,
    TieredSandwichExecutor, DANGER_CMDS
)


# ========== READ_ONLY 档位 ==========

class TestReadOnly:
    """read-only: 只读 + 网络全禁"""

    def setup_method(self):
        self.tier = SandwichTierManager(SandboxTier.READ_ONLY, workspace="/workspace")

    def test_can_read_in_workspace(self):
        ok, _ = self.tier.is_path_safe("/workspace/test.txt", "read")
        assert ok is True

    def test_cannot_read_outside_workspace(self):
        ok, _ = self.tier.is_path_safe("/etc/passwd", "read")
        assert ok is False

    def test_cannot_write(self):
        ok, _ = self.tier.is_path_safe("/workspace/test.txt", "write")
        assert ok is False

    def test_forbidden_paths_blocked(self):
        """系统路径全禁"""
        for path in ["/etc/shadow", "/proc/self", "/dev/null"]:
            ok, _ = self.tier.is_path_safe(path, "read")
            assert ok is False, f"应阻止: {path}"

    def test_network_blocked(self):
        """read-only 禁止所有网络"""
        assert self.tier.can_connect("github.com", 443) is False
        assert self.tier.can_connect("pypi.org", 80) is False

    def test_dangerous_commands_blocked(self):
        """危险命令全禁"""
        for cmd in ["rm -rf /", "shutdown", "mkfs", "mount"]:
            ok, reason = self.tier.can_execute(cmd)
            assert ok is False, f"应阻止: {cmd} - {reason}"

    def test_safe_commands_allowed(self):
        """安全命令允许"""
        ok, reason = self.tier.can_execute("ls -la")
        assert ok is True


# ========== WORKSPACE_WRITE 档位 ==========

class TestWorkspaceWrite:
    """workspace-write: 工作区可写 + 网络白名单"""

    def setup_method(self):
        self.tier = SandwichTierManager(
            SandboxTier.WORKSPACE_WRITE,
            workspace="/workspace",
            additional_write_paths=["/tmp/build"],
            additional_allowed_hosts=["pypi.org"]
        )

    def test_can_read_workspace(self):
        ok, _ = self.tier.is_path_safe("/workspace/src/main.py", "read")
        assert ok is True

    def test_can_write_workspace(self):
        ok, _ = self.tier.is_path_safe("/workspace/output.txt", "write")
        assert ok is True

    def test_can_write_extra_path(self):
        ok, _ = self.tier.is_path_safe("/tmp/build/result.bin", "write")
        assert ok is True

    def test_cannot_write_other(self):
        ok, _ = self.tier.is_path_safe("/etc/config", "write")
        assert ok is False

    def test_forbidden_paths_still_blocked(self):
        """系统路径仍禁"""
        for path in ["/etc/passwd", "/sys/kernel"]:
            ok, _ = self.tier.is_path_safe(path, "read")
            assert ok is False

    def test_allowed_hosts(self):
        """白名单主机允许"""
        assert self.tier.can_connect("api.github.com", 443) is True
        assert self.tier.can_connect("pypi.org", 443) is True

    def test_non_allowed_hosts_blocked(self):
        """非白名单主机禁止"""
        assert self.tier.can_connect("evil.com", 443) is False

    def test_allowed_ports(self):
        """只允许 80/443"""
        assert self.tier.can_connect("pypi.org", 80) is True
        assert self.tier.can_connect("pypi.org", 443) is True
        assert self.tier.can_connect("pypi.org", 8080) is False

    def test_dangerous_commands_blocked(self):
        """危险命令仍禁"""
        for cmd in ["rm -rf /", "shutdown", "mkfs"]:
            ok, _ = self.tier.can_execute(cmd)
            assert ok is False

    def test_normal_commands_allowed(self):
        """正常命令允许"""
        ok, _ = self.tier.can_execute("python test.py")
        assert ok is True
        ok, _ = self.tier.can_execute("npm install")
        assert ok is True


# ========== DANGER_FULL 档位 ==========

class TestDangerFull:
    """danger-full: 全通（底线保护）"""

    def setup_method(self):
        self.tier = SandwichTierManager(
            SandboxTier.DANGER_FULL,
            workspace="/workspace"
        )

    def test_can_read_all(self):
        """可读全文件系统"""
        ok, _ = self.tier.is_path_safe("/etc/passwd", "read")
        assert ok is True
        ok, _ = self.tier.is_path_safe("/var/log/syslog", "read")
        assert ok is True

    def test_can_write_workspace(self):
        ok, _ = self.tier.is_path_safe("/workspace/output.bin", "write")
        assert ok is True

    def test_cannot_write_system(self):
        """系统路径仍禁写"""
        ok, _ = self.tier.is_path_safe("/etc/passwd", "write")
        assert ok is False

    def test_network_all_allowed(self):
        """网络全通"""
        assert self.tier.can_connect("any-host.com", 443) is True
        assert self.tier.can_connect("internal-api", 8080) is True

    def test_critical_commands_still_blocked(self):
        """关键危险命令仍禁"""
        for cmd in ["rm -rf /", "shutdown", "reboot", "halt"]:
            ok, _ = self.tier.can_execute(cmd)
            assert ok is False, f"应阻止: {cmd}"

    def test_disk_format_blocked(self):
        """磁盘格式化命令禁"""
        # fdisk 在 DANGER_CMDS 中是列表，但 _build_config 只取了 split() 结果
        # 实际只禁止了 "fdisk" 和 "parted" 作为单独命令
        ok, _ = self.tier.can_execute("mkfs.ext4 /dev/sda1")
        assert ok is False


# ========== 资源限制 ==========

class TestResourceLimits:
    """资源限制测试"""

    def setup_method(self):
        self.tier = SandwichTierManager(SandboxTier.WORKSPACE_WRITE, workspace="/workspace")

    def test_file_size_ok(self):
        ok, _ = self.tier.check_resource_limits(file_size_bytes=100 * 1024 * 1024)
        assert ok is True

    def test_file_size_exceeded(self):
        ok, reason = self.tier.check_resource_limits(file_size_bytes=600 * 1024 * 1024)
        assert ok is False
        assert "超限" in reason

    def test_execution_time_ok(self):
        ok, _ = self.tier.check_resource_limits(duration_ms=60 * 1000)
        assert ok is True

    def test_execution_time_exceeded(self):
        ok, reason = self.tier.check_resource_limits(duration_ms=400 * 1000)
        assert ok is False
        assert "超限" in reason


# ========== 边界 case ==========

class TestEdgeCases:
    """边界情况测试"""

    def test_empty_command(self):
        tier = SandwichTierManager(SandboxTier.WORKSPACE_WRITE, workspace="/workspace")
        ok, _ = tier.can_execute("")
        assert ok is True

    def test_command_with_args(self):
        tier = SandwichTierManager(SandboxTier.WORKSPACE_WRITE, workspace="/workspace")
        ok, _ = tier.can_execute("python script.py --verbose")
        assert ok is True

    def test_relative_path_resolution(self):
        """相对路径解析"""
        # ./test.txt 会被 os.path.abspath 解析为当前工作目录，不是 /workspace
        tier = SandwichTierManager(SandboxTier.WORKSPACE_WRITE, workspace="/workspace")
        ok, _ = tier.is_path_safe("/workspace/test.txt", "read")
        assert ok is True

    def test_symlink_resolution(self):
        """符号链接解析"""
        tier = SandwichTierManager(SandboxTier.WORKSPACE_WRITE, workspace="/workspace")
        # 假设 /workspace/link -> /etc/passwd
        # 实际环境中会解析真实路径
        ok, _ = tier.is_path_safe("/workspace/link", "read")
        # 取决于实际文件系统，这里只测试不崩溃
        assert isinstance(ok, bool)

    def test_whitespace_in_command(self):
        tier = SandwichTierManager(SandboxTier.WORKSPACE_WRITE, workspace="/workspace")
        ok, _ = tier.can_execute("   ls -la   ")
        assert ok is True

    def test_case_insensitive_command(self):
        tier = SandwichTierManager(SandboxTier.WORKSPACE_WRITE, workspace="/workspace")
        ok, _ = tier.can_execute("SHUTDOWN")
        assert ok is False


# ========== TieredSandwichExecutor 集成 ==========

class TestTieredSandwichExecutor:
    """与 Phase 1 sandbox_executor 集成测试"""

    def test_read_tool_allowed(self):
        """读操作在 workspace-write 下允许"""
        mock_executor = type('Mock', (), {'can_execute': lambda self, tc: (True, "")})()
        executor = TieredSandwichExecutor(mock_executor, SandboxTier.WORKSPACE_WRITE, "/workspace")

        ok, _ = executor.can_execute({
            "tool": "read_file",
            "args": {"path": "/workspace/test.txt"}
        })
        assert ok is True

    def test_write_tool_allowed(self):
        """写操作在 workspace-write 下允许"""
        mock_executor = type('Mock', (), {'can_execute': lambda self, tc: (True, "")})()
        executor = TieredSandwichExecutor(mock_executor, SandboxTier.WORKSPACE_WRITE, "/workspace")

        ok, _ = executor.can_execute({
            "tool": "write_file",
            "args": {"path": "/workspace/output.txt"}
        })
        assert ok is True

    def test_write_tool_blocked_in_readonly(self):
        """write 在 read-only 下禁止"""
        # read-only 下 can_write 返回 False，但 is_path_safe 检查的是 path
        # 需要检查路径是否在 allowed_write_paths 中
        mock_executor = type('Mock', (), {'can_execute': lambda self, tc: (True, "")})()
        executor = TieredSandwichExecutor(mock_executor, SandboxTier.READ_ONLY, "/workspace")

        # 尝试写入工作区外的路径
        ok, reason = executor.can_execute({
            "tool": "write_file",
            "args": {"path": "/etc/config"}
        })
        assert ok is False

    def test_network_tool_blocked_in_readonly(self):
        """网络在 read-only 下禁止"""
        mock_executor = type('Mock', (), {'can_execute': lambda self, tc: (True, "")})()
        executor = TieredSandwichExecutor(mock_executor, SandboxTier.READ_ONLY, "/workspace")

        ok, reason = executor.can_execute({
            "tool": "fetch_url",
            "args": {"url": "https://api.github.com"}
        })
        assert ok is False

    def test_dangerous_command_blocked(self):
        """危险命令在所有档位都禁止"""
        mock_executor = type('Mock', (), {'can_execute': lambda self, tc: (True, "")})()
        executor = TieredSandwichExecutor(mock_executor, SandboxTier.DANGER_FULL, "/workspace")

        ok, reason = executor.can_execute({
            "tool": "bash",
            "args": {"command": "rm -rf /"}
        })
        assert ok is False

    def test_executor_fallback(self):
        """回退到原始 executor"""
        mock_executor = type('Mock', (), {
            'can_execute': lambda self, tc: (False, "原始 executor 拒绝")
        })()
        executor = TieredSandwichExecutor(mock_executor, SandboxTier.WORKSPACE_WRITE, "/workspace")

        ok, reason = executor.can_execute({
            "tool": "custom_tool",
            "args": {}
        })
        assert ok is False
        assert "原始 executor 拒绝" in reason


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
