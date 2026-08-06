"""
test_approval_strategy.py — 四级审批策略测试
覆盖：on-request / on-failure / untrusted / never 四种策略
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pytest
from approval_strategy import (
    ApprovalPolicy, ApprovalConfig, Strategy, RiskAssessment,
    ApprovalAwarePipeline
)


# ========== on-request 策略 ==========

class TestOnRequest:
    """on-request: 模型自主判断"""

    def setup_method(self):
        self.policy = ApprovalPolicy(ApprovalConfig(strategy=Strategy.ON_REQUEST))

    def test_none_risk_auto(self):
        risk = RiskAssessment("none", "只读操作")
        result = self.policy.evaluate("read_file", risk)
        assert result["decision"] == "auto"

    def test_low_risk_auto(self):
        risk = RiskAssessment("low", "网络只读")
        result = self.policy.evaluate("fetch_url", risk)
        assert result["decision"] == "auto"

    def test_medium_risk_approve(self):
        risk = RiskAssessment("medium", "写操作")
        result = self.policy.evaluate("write_file", risk)
        assert result["decision"] == "approve"

    def test_medium_risk_whitelist_auto(self):
        risk = RiskAssessment("medium", "白名单工具")
        result = self.policy.evaluate("read_file", risk)
        assert result["decision"] == "auto"

    def test_high_risk_approve(self):
        risk = RiskAssessment("high", "系统操作")
        result = self.policy.evaluate("bash", risk)
        assert result["decision"] == "approve"

    def test_critical_risk_approve(self):
        risk = RiskAssessment("critical", "系统+网络")
        result = self.policy.evaluate("shell", risk)
        assert result["decision"] == "approve"


# ========== on-failure 策略 ==========

class TestOnFailure:
    """on-failure: 先自动执行，失败3次再升人审"""

    def setup_method(self):
        self.policy = ApprovalPolicy(
            ApprovalConfig(strategy=Strategy.ON_FAILURE, max_failures_before_escalation=3)
        )

    def test_low_risk_auto(self):
        risk = RiskAssessment("low", "低风险")
        result = self.policy.evaluate("fetch_url", risk)
        assert result["decision"] == "auto"
        assert "failures_remaining" in result

    def test_medium_risk_auto(self):
        risk = RiskAssessment("medium", "中风险")
        result = self.policy.evaluate("write_file", risk)
        assert result["decision"] == "auto"

    def test_high_risk_approve(self):
        risk = RiskAssessment("high", "高风险")
        result = self.policy.evaluate("bash", risk)
        assert result["decision"] == "approve"

    def test_critical_risk_approve(self):
        risk = RiskAssessment("critical", "关键风险")
        result = self.policy.evaluate("shell", risk)
        assert result["decision"] == "approve"

    def test_failure_counting(self):
        """记录失败次数，达到阈值后升级"""
        risk = RiskAssessment("low", "低风险")
        tool = "fetch_url"

        # 前3次自动
        for i in range(3):
            result = self.policy.evaluate(tool, risk)
            assert result["decision"] == "auto"
            self.policy.record_failure(tool)

        # 第4次应该升级
        result = self.policy.evaluate(tool, risk)
        assert result["decision"] == "approve"
        assert "失败3次" in result["reason"]

    def test_success_resets_count(self):
        """成功后重置失败计数"""
        risk = RiskAssessment("low", "低风险")
        tool = "fetch_url"

        # 记录2次失败
        self.policy.record_failure(tool)
        self.policy.record_failure(tool)

        # 重置
        self.policy.record_success(tool)

        # 应该还是自动
        result = self.policy.evaluate(tool, risk)
        assert result["decision"] == "auto"
        assert result["failures_remaining"] == 3


# ========== untrusted 策略 ==========

class TestUntrusted:
    """untrusted: 所有非只读都审批"""

    def setup_method(self):
        self.policy = ApprovalPolicy(ApprovalConfig(strategy=Strategy.UNTRUSTED))

    def test_whitelist_auto(self):
        result = self.policy.evaluate("read_file", RiskAssessment("none", "只读"))
        assert result["decision"] == "auto"

    def test_non_whitelist_approve(self):
        result = self.policy.evaluate("write_file", RiskAssessment("medium", "写操作"))
        assert result["decision"] == "approve"

    def test_dangerous_command_block(self):
        result = self.policy.evaluate("rm", RiskAssessment("high", "删除"))
        assert result["decision"] == "block"

    def test_custom_whitelist(self):
        config = ApprovalConfig(
            strategy=Strategy.UNTRUSTED,
            auto_allow_tools=["list_dir"]
        )
        policy = ApprovalPolicy(config)
        result = policy.evaluate("list_dir", RiskAssessment("none", "列表"))
        assert result["decision"] == "auto"


# ========== never 策略 ==========

class TestNever:
    """never: 全自动，CI/CD专用"""

    def setup_method(self):
        self.policy = ApprovalPolicy(ApprovalConfig(strategy=Strategy.NEVER))

    def test_auto_all(self):
        result = self.policy.evaluate("bash", RiskAssessment("high", "系统操作"))
        assert result["decision"] == "auto"

    def test_dangerous_still_block(self):
        """危险命令仍然需要审批"""
        result = self.policy.evaluate("delete", RiskAssessment("critical", "删除"))
        assert result["decision"] == "block"

    def test_custom_always_require(self):
        config = ApprovalConfig(
            strategy=Strategy.NEVER,
            always_require_approval=["shutdown"]
        )
        policy = ApprovalPolicy(config)
        result = policy.evaluate("shutdown", RiskAssessment("critical", "关机"))
        assert result["decision"] == "block"


# ========== 强制审批操作 ==========

class TestAlwaysRequireApproval:
    """危险操作强制审批"""

    def setup_method(self):
        self.policy = ApprovalPolicy()

    def test_rm_blocked(self):
        result = self.policy.evaluate("rm", RiskAssessment("high", "删除"))
        assert result["decision"] == "block"

    def test_delete_blocked(self):
        result = self.policy.evaluate("delete", RiskAssessment("high", "删除"))
        assert result["decision"] == "block"

    def test_drop_blocked(self):
        result = self.policy.evaluate("drop_table", RiskAssessment("critical", "删表"))
        assert result["decision"] == "block"

    def test_truncate_blocked(self):
        result = self.policy.evaluate("truncate", RiskAssessment("high", "截断"))
        assert result["decision"] == "block"

    def test_format_blocked(self):
        result = self.policy.evaluate("format_disk", RiskAssessment("critical", "格式化"))
        assert result["decision"] == "block"

    def test_shutdown_blocked(self):
        result = self.policy.evaluate("shutdown", RiskAssessment("critical", "关机"))
        assert result["decision"] == "block"

    def test_restart_blocked(self):
        result = self.policy.evaluate("restart_service", RiskAssessment("high", "重启"))
        assert result["decision"] == "block"


# ========== 审计回调 ==========

class TestAuditCallback:
    """审批决策回调"""

    def test_callback_fired(self):
        decisions = []
        def on_decision(dec):
            decisions.append(dec)

        config = ApprovalConfig(
            strategy=Strategy.ON_REQUEST,
            on_decision=on_decision
        )
        policy = ApprovalPolicy(config)
        policy.evaluate("read_file", RiskAssessment("none", "只读"))

        assert len(decisions) == 1
        assert decisions[0]["decision"] == "auto"


# ========== Pipeline 集成 ==========

class TestApprovalAwarePipeline:
    """与 Argus Pipeline 集成测试"""

    def test_safe_read_auto(self):
        """安全读操作自动通过"""
        mock_pipeline = type('Mock', (), {'process': lambda self, tc: {"blocked": False}})()
        policy = ApprovalPolicy(ApprovalConfig(strategy=Strategy.ON_REQUEST))
        pipeline = ApprovalAwarePipeline(mock_pipeline, policy)

        result = pipeline.process({"tool": "read_file", "args": {"path": "/test.txt"}})
        assert result["approval_decision"] == "auto"

    def test_write_approve(self):
        """写操作需要审批"""
        mock_pipeline = type('Mock', (), {'process': lambda self, tc: {"blocked": False}})()
        policy = ApprovalPolicy(ApprovalConfig(strategy=Strategy.ON_REQUEST))
        pipeline = ApprovalAwarePipeline(mock_pipeline, policy)

        result = pipeline.process({"tool": "write_file", "args": {"path": "/test.txt"}})
        assert result["approval_decision"] == "approve"

    def test_blocked_pipeline(self):
        """被 pipeline 阻断的不做审批"""
        mock_pipeline = type('Mock', (), {'process': lambda self, tc: {"blocked": True}})()
        policy = ApprovalPolicy(ApprovalConfig(strategy=Strategy.ON_REQUEST))
        pipeline = ApprovalAwarePipeline(mock_pipeline, policy)

        result = pipeline.process({"tool": "rm", "args": {}})
        assert result["blocked"] == True
        assert "approval_decision" not in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
