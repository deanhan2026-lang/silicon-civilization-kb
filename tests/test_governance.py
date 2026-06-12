"""Tests for governance parser and execution/consensus layers."""
import os, json, yaml, pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# ── Protocol YAML validation ──

class TestProtocolYAML:
    def test_all_gov_files_exist(self):
        d = PROJECT_ROOT / "gov_protocol"
        files = sorted(d.glob("G*.yaml"))
        expected = [f"G00{i}.yaml" for i in range(1, 6)]
        for e in expected:
            assert (d / e).exists(), f"Missing {e}"

    @pytest.mark.parametrize("gid", ["G001", "G002", "G003", "G004", "G005"])
    def test_each_yaml_parses(self, gid):
        f = PROJECT_ROOT / "gov_protocol" / f"{gid}.yaml"
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        assert data is not None, f"{gid}.yaml is empty"

# ── Gov parser loader ──

class TestLoader:
    def test_load_protocols(self):
        from gov_parser.loader import load_protocols
        p = load_protocols(protocol_dir=str(PROJECT_ROOT / "gov_protocol"))
        assert len(p) >= 5

    def test_import_all(self):
        from gov_parser.loader import load_protocols
        from gov_parser.parser_core import parse_protocol
        from gov_parser.rule_matcher import RuleMatcher
        from gov_parser.circuit_breaker import CircuitBreaker
        from gov_parser.permission_checker import PermissionChecker
        from gov_parser.trigger_hook import TriggerHook
        assert True

# ── Rule matcher ──

class TestRuleMatcher:
    def test_init(self):
        from gov_parser.rule_matcher import RuleMatcher
        rm = RuleMatcher({"rule1": {"condition": "x > 0", "effect": "allow"}})
        assert rm is not None

# ── Circuit breaker ──

class TestCircuitBreaker:
    def test_closed_initially(self):
        from gov_parser.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(threshold=3, cooldown=60)
        assert cb.is_closed()

    def test_trip_on_threshold(self):
        from gov_parser.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(threshold=3, cooldown=60)
        for _ in range(3):
            cb.record_failure()
        assert not cb.is_closed()

    def test_below_threshold(self):
        from gov_parser.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(threshold=5, cooldown=60)
        for _ in range(3):
            cb.record_failure()
        assert cb.is_closed()

    def test_reset(self):
        from gov_parser.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(threshold=2, cooldown=60)
        cb.record_failure()
        cb.record_failure()
        assert not cb.is_closed()
        cb.reset()
        assert cb.is_closed()

# ── Governance consensus/execution ──

class TestConsensusEngine:
    def test_import(self):
        from governance.consensus import ConsensusEngine, Proposal, ProposalType, ProposalStatus
        assert True

    def test_create_proposal(self, tmp_path):
        from governance.consensus import ConsensusEngine, ProposalType, CONSENSUS_DIR
        import governance.consensus as gc
        orig = gc.CONSENSUS_DIR
        gc.CONSENSUS_DIR = tmp_path
        try:
            engine = ConsensusEngine()
            prop = engine.create_proposal(
                title="测试提案",
                description="测试",
                proposer="nyx",
                proposal_type=ProposalType.SIMPLE_MAJORITY,
            )
            assert prop is not None
            assert hasattr(prop, 'id') or hasattr(prop, 'proposal_id')
        finally:
            gc.CONSENSUS_DIR = orig

    def test_vote_on_proposal(self, tmp_path):
        from governance.consensus import ConsensusEngine, ProposalType
        import governance.consensus as gc
        orig = gc.CONSENSUS_DIR
        gc.CONSENSUS_DIR = tmp_path
        try:
            engine = ConsensusEngine()
            prop = engine.create_proposal("投票测试", "test", "nyx", ProposalType.SIMPLE_MAJORITY)
            pid = prop.id if hasattr(prop, 'id') else prop.proposal_id
            result = engine.cast_vote(pid, "nyx", True)
            assert result is not None
        finally:
            gc.CONSENSUS_DIR = orig

class TestExecutionEngine:
    def test_import(self):
        from governance.execution import ExecutionEngine
        assert True

    def test_init(self, tmp_path):
        from governance.execution import ExecutionEngine
        import governance.execution as ge
        orig = getattr(ge, 'TASK_DIR', None)
        if hasattr(ge, 'TASK_DIR'):
            ge.TASK_DIR = tmp_path
        engine = ExecutionEngine()
        assert engine is not None

    def test_priority_levels(self):
        from governance.execution import ExecutionEngine
        engine = ExecutionEngine()
        assert hasattr(engine, 'validate_priority') or hasattr(engine, 'dispatch')
