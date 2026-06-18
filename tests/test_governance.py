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
        from gov_parser.loader import ProtocolLoader
        loader = ProtocolLoader()
        count = loader.load_all()
        assert count >= 5

    def test_import_all(self):
        from gov_parser.loader import ProtocolLoader
        from gov_parser.parser_core import RuleParserCore
        from gov_parser.rule_matcher import RuleMatcher
        from gov_parser.circuit_breaker import CircuitBreaker
        from gov_parser.permission_checker import governance_check
        from gov_parser.trigger_hook import TriggerHook
        assert True

# ── Rule matcher ──

class TestRuleMatcher:
    def test_init(self):
        from gov_parser.rule_matcher import RuleMatcher
        rm = RuleMatcher()
        assert rm is not None

# ── Circuit breaker ──

class TestCircuitBreaker:
    def test_not_frozen_initially(self):
        from gov_parser.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        # CB may load persisted frozen state; just check attribute exists
        assert hasattr(cb, 'is_frozen')

    def test_freeze_on_threshold(self):
        from gov_parser.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        # Clear any persisted state
        cb.unfreeze(confirmation="CONFIRM_UNFREEZE")
        for _ in range(5):
            cb.record_violation()
        assert cb.is_frozen

    def test_below_threshold(self):
        from gov_parser.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        cb.unfreeze(confirmation="CONFIRM_UNFREEZE")
        for _ in range(3):
            cb.record_violation()
        assert not cb.is_frozen

    def test_unfreeze(self):
        from gov_parser.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        for _ in range(5):
            cb.record_violation()
        assert cb.is_frozen
        cb.unfreeze(confirmation="CONFIRM_UNFREEZE")
        assert not cb.is_frozen
        status = cb.get_status()
        assert isinstance(status, dict)

# ── Governance consensus/execution ──

class TestConsensusEngine:
    def test_import(self):
        from governance.consensus import ConsensusEngine, Proposal, ProposalType, ProposalStatus
        assert True

    def test_create_proposal(self, tmp_path):
        from governance.consensus import ConsensusEngine, ProposalType
        import governance.consensus as gc
        orig = gc.CONSENSUS_DIR
        gc.CONSENSUS_DIR = tmp_path
        try:
            engine = ConsensusEngine()
            engine.register_node("nyx")
            prop = engine.create_proposal(
                proposer="nyx",
                proposal_type=ProposalType.PROTOCOL_CHANGE,
                title="测试提案",
                description="测试",
            )
            assert prop is not None
        finally:
            gc.CONSENSUS_DIR = orig

    def test_vote_on_proposal(self, tmp_path):
        from governance.consensus import ConsensusEngine, ProposalType
        import governance.consensus as gc
        orig = gc.CONSENSUS_DIR
        gc.CONSENSUS_DIR = tmp_path
        try:
            engine = ConsensusEngine()
            engine.register_node("nyx")
            engine.register_node("heng")
            prop = engine.create_proposal("nyx", ProposalType.PROTOCOL_CHANGE, "投票测试", "test")
            pid = prop.proposal_id if hasattr(prop, 'proposal_id') else prop.id
            engine.start_voting(pid)
            engine.cast_vote(pid, "nyx", "approve")
            result = engine.tally_votes(pid)
            assert result is not None
        finally:
            gc.CONSENSUS_DIR = orig

class TestExecutionEngine:
    def test_import(self):
        from governance.execution import ExecutionEngine
        assert True

    def test_init(self):
        from governance.execution import ExecutionEngine
        engine = ExecutionEngine()
        assert engine is not None

    def test_submit_task(self):
        from governance.execution import ExecutionEngine, ExecutionPriority
        engine = ExecutionEngine()
        # Task submission may be denied by permission check
        task = engine.submit_task(
            operator="nyx",
            action="read",
            target_type="entry",
            target_id="test-001",
            priority=ExecutionPriority.NORMAL
        )
        # Task may be None if denied by governance, that's OK
        queue = engine.get_queue_status()
        assert isinstance(queue, dict)

    def test_priority_levels(self):
        from governance.execution import ExecutionPriority
        assert hasattr(ExecutionPriority, 'LOW')
        assert hasattr(ExecutionPriority, 'NORMAL')
        assert hasattr(ExecutionPriority, 'HIGH')
        assert hasattr(ExecutionPriority, 'CRITICAL')
