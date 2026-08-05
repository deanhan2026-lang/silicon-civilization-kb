"""测试 Guardian Audit (TK-G013-P0-B) - 四条监护审计日志类型"""
import json
import pytest

import nacl.signing

from memguard.guardian_audit import (
    GuardianAuditManager,
    GuardianAuditStorage,
    sha256_b64,
    ed25519_sign_b64,
    ed25519_verify_b64,
    GUARDIAN_AUDIT_TYPES,
)


@pytest.fixture
def keys():
    signing_key = nacl.signing.SigningKey.generate()
    return {
        "signing_key": signing_key,
        "pubkey_hex": bytes(signing_key.verify_key).hex(),
    }


@pytest.fixture
def mgr(tmp_path):
    log_path = str(tmp_path / "guardian_audit.jsonl")
    return GuardianAuditManager(log_path=log_path)


GUARDIAN_DID = "did:ly:v1:TestGuardian"
NODE_DID = "did:ly:v1:TestNode"


def sample_operation(risk_tier="safe"):
    return {"type": "daily_operation", "params": {"action": "read_memory"}, "riskTier": risk_tier}


def sample_decision(outcome, reason="测试原因", with_evidence=False):
    decision = {"outcome": outcome, "reason": reason}
    if with_evidence:
        decision["evidence"] = ["audit-log-001"]
    return decision


class TestHashAndSign:
    """哈希与签名工具测试"""

    def test_sha256_b64(self):
        h = sha256_b64("hello")
        assert isinstance(h, str)
        assert len(h) > 0

    def test_sign_verify_roundtrip(self, keys):
        sig = ed25519_sign_b64("content", keys["signing_key"])
        assert ed25519_verify_b64("content", sig, keys["pubkey_hex"]) is True

    def test_sign_verify_wrong_content(self, keys):
        sig = ed25519_sign_b64("content-A", keys["signing_key"])
        assert ed25519_verify_b64("content-B", sig, keys["pubkey_hex"]) is False


class TestAppendTypes:
    """四条日志类型写入测试"""

    @pytest.mark.parametrize("audit_type,append_fn,outcome", [
        ("guardian_approved", "append_approved", "approved"),
        ("guardian_vetoed", "append_vetoed", "vetoed"),
        ("guardian_intervened", "append_intervened", "intervened"),
        ("guardian_offboarded", "append_offboarded", "offboarded"),
    ])
    def test_append_each_type(self, mgr, keys, audit_type, append_fn, outcome):
        decision = sample_decision(outcome, with_evidence=(outcome != "approved"))
        entry = getattr(mgr, append_fn)(
            guardian_did=GUARDIAN_DID,
            node_did=NODE_DID,
            operation=sample_operation(),
            decision=decision,
            guardian_signing_key=keys["signing_key"],
            timestamp="2026-08-05T00:00:00Z",
        )
        assert entry["auditType"] == audit_type
        assert entry["logId"]
        assert entry["guardianDID"] == GUARDIAN_DID
        assert entry["nodeDID"] == NODE_DID
        assert entry["signature"]["type"] == "Ed25519"
        assert entry["signature"]["value"]
        assert entry["signature"]["signedContent"]

        # 已写入文件
        stored = GuardianAuditStorage.read_all(mgr.log_path)
        assert len(stored) == 1
        assert stored[0]["auditType"] == audit_type

    def test_append_writes_all_four(self, mgr, keys):
        """连续写入四条日志"""
        for audit_type, outcome, ev in [
            ("guardian_approved", "approved", False),
            ("guardian_vetoed", "vetoed", True),
            ("guardian_intervened", "intervened", True),
            ("guardian_offboarded", "offboarded", True),
        ]:
            decision = sample_decision(outcome, with_evidence=ev)
            method_name = audit_type.replace("guardian_", "append_")
            getattr(mgr, method_name)(
                guardian_did=GUARDIAN_DID,
                node_did=NODE_DID,
                operation=sample_operation(),
                decision=decision,
                guardian_signing_key=keys["signing_key"],
                timestamp="2026-08-05T00:00:00Z",
            )
        stored = GuardianAuditStorage.read_all(mgr.log_path)
        assert len(stored) == 4
        types = [e["auditType"] for e in stored]
        assert types == list(GUARDIAN_AUDIT_TYPES)


class TestValidation:
    """必填字段校验测试"""

    def test_invalid_audit_type(self, mgr, keys):
        with pytest.raises(ValueError, match="非法 auditType"):
            mgr._build_entry(
                "invalid_type", GUARDIAN_DID, NODE_DID,
                sample_operation(), sample_decision("approved"),
                keys["signing_key"],
            )

    def test_missing_operation_type(self, mgr, keys):
        with pytest.raises(ValueError, match="operation 必须包含 type"):
            mgr._build_entry(
                "guardian_approved", GUARDIAN_DID, NODE_DID,
                {"params": {}}, sample_decision("approved"),
                keys["signing_key"],
            )

    def test_invalid_risk_tier(self, mgr, keys):
        with pytest.raises(ValueError, match="非法 riskTier"):
            mgr._build_entry(
                "guardian_approved", GUARDIAN_DID, NODE_DID,
                {"type": "op", "riskTier": "extreme"}, sample_decision("approved"),
                keys["signing_key"],
            )

    def test_vetoed_requires_evidence(self, mgr, keys):
        """vetoed 必须有 evidence"""
        with pytest.raises(ValueError, match="decision.evidence 必填"):
            mgr._build_entry(
                "guardian_vetoed", GUARDIAN_DID, NODE_DID,
                sample_operation(), sample_decision("vetoed", with_evidence=False),
                keys["signing_key"],
            )

    def test_approved_evidence_optional(self, mgr, keys):
        """approved 的 evidence 可选"""
        entry = mgr._build_entry(
            "guardian_approved", GUARDIAN_DID, NODE_DID,
            sample_operation(), sample_decision("approved", with_evidence=False),
            keys["signing_key"],
        )
        assert entry["decision"]["evidence"] == []

    def test_wrong_outcome(self, mgr, keys):
        with pytest.raises(ValueError, match="decision.outcome"):
            mgr._build_entry(
                "guardian_approved", GUARDIAN_DID, NODE_DID,
                sample_operation(), sample_decision("vetoed"),
                keys["signing_key"],
            )


class TestVerify:
    """验证函数测试"""

    def test_verify_valid_entry(self, mgr, keys):
        entry = mgr.append_approved(
            guardian_did=GUARDIAN_DID,
            node_did=NODE_DID,
            operation=sample_operation(),
            decision=sample_decision("approved"),
            guardian_signing_key=keys["signing_key"],
            timestamp="2026-08-05T00:00:00Z",
        )
        valid, msg = mgr.verify_entry(entry, keys["pubkey_hex"])
        assert valid, msg

    def test_verify_tampered_content(self, mgr, keys):
        entry = mgr.append_approved(
            guardian_did=GUARDIAN_DID,
            node_did=NODE_DID,
            operation=sample_operation(),
            decision=sample_decision("approved"),
            guardian_signing_key=keys["signing_key"],
            timestamp="2026-08-05T00:00:00Z",
        )
        # 篡改 decision.reason
        entry["decision"]["reason"] = "被篡改的原因"
        valid, msg = mgr.verify_entry(entry, keys["pubkey_hex"])
        assert not valid
        assert "signedContent" in msg

    def test_verify_tampered_signature(self, mgr, keys):
        entry = mgr.append_approved(
            guardian_did=GUARDIAN_DID,
            node_did=NODE_DID,
            operation=sample_operation(),
            decision=sample_decision("approved"),
            guardian_signing_key=keys["signing_key"],
            timestamp="2026-08-05T00:00:00Z",
        )
        entry["signature"]["value"] = "AAAA"  # 篡改签名
        valid, msg = mgr.verify_entry(entry, keys["pubkey_hex"])
        assert not valid

    def test_verify_wrong_key(self, mgr, keys):
        entry = mgr.append_approved(
            guardian_did=GUARDIAN_DID,
            node_did=NODE_DID,
            operation=sample_operation(),
            decision=sample_decision("approved"),
            guardian_signing_key=keys["signing_key"],
            timestamp="2026-08-05T00:00:00Z",
        )
        other = nacl.signing.SigningKey.generate()
        valid, _ = mgr.verify_entry(entry, bytes(other.verify_key).hex())
        assert not valid

    def test_verify_all(self, mgr, keys):
        for audit_type, outcome, ev in [
            ("approved", "approved", False),
            ("vetoed", "vetoed", True),
            ("intervened", "intervened", True),
            ("offboarded", "offboarded", True),
        ]:
            getattr(mgr, f"append_{audit_type}")(
                guardian_did=GUARDIAN_DID,
                node_did=NODE_DID,
                operation=sample_operation(),
                decision=sample_decision(outcome, with_evidence=ev),
                guardian_signing_key=keys["signing_key"],
                timestamp="2026-08-05T00:00:00Z",
            )
        valid, msg = mgr.verify_all(keys["pubkey_hex"])
        assert valid, msg


class TestSearch:
    """查询测试"""

    def test_search_by_type(self, mgr, keys):
        mgr.append_approved(
            guardian_did=GUARDIAN_DID, node_did=NODE_DID,
            operation=sample_operation(), decision=sample_decision("approved"),
            guardian_signing_key=keys["signing_key"], timestamp="2026-08-05T00:00:00Z",
        )
        mgr.append_vetoed(
            guardian_did=GUARDIAN_DID, node_did=NODE_DID,
            operation=sample_operation(), decision=sample_decision("vetoed", with_evidence=True),
            guardian_signing_key=keys["signing_key"], timestamp="2026-08-05T00:00:00Z",
        )
        approved = mgr.search(audit_type="guardian_approved")
        assert len(approved) == 1
        assert approved[0]["auditType"] == "guardian_approved"

    def test_search_by_node(self, mgr, keys):
        mgr.append_approved(
            guardian_did=GUARDIAN_DID, node_did=NODE_DID,
            operation=sample_operation(), decision=sample_decision("approved"),
            guardian_signing_key=keys["signing_key"], timestamp="2026-08-05T00:00:00Z",
        )
        found = mgr.search(node_did=NODE_DID)
        assert len(found) == 1
        assert found[0]["nodeDID"] == NODE_DID
