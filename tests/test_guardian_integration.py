"""TK-G013-P0 联动集成测试

监护关系建立 → DID record 写入 → MemGuard 写入 guardian_approved 审计日志
完整链路测试
"""
import json
import sys
from pathlib import Path

import nacl.signing
import pytest

# 添加两个仓库的路径
SCK_ROOT = Path(__file__).resolve().parent.parent
MESH_ROOT = Path(r"C:\Users\Administrator\.qclaw\workspace-agent-d9479bde\mesh_identity_sync")

sys.path.insert(0, str(MESH_ROOT))
sys.path.insert(0, str(SCK_ROOT))

from did.guardian import GuardianManager, build_signing_payload, ed25519_sign
from memguard.guardian_audit import GuardianAuditManager


@pytest.fixture
def guardian_keys():
    """监护人密钥对"""
    signing_key = nacl.signing.SigningKey.generate()
    return {
        "signing_key": signing_key,
        "pubkey_hex": bytes(signing_key.verify_key).hex(),
    }


@pytest.fixture
def setup(tmp_path):
    """临时目录环境：DID 存储 + 审计日志"""
    did_storage = tmp_path / "did"
    did_storage.mkdir()
    audit_log = str(tmp_path / "guardian_audit.jsonl")
    return {
        "did_storage": str(did_storage),
        "audit_log": audit_log,
    }


def test_guardianship_full_chain(setup, guardian_keys):
    """
    完整链路：
    1. 监护人签署监护授权
    2. 建立监护关系 → DID record 写入 guardian 字段
    3. 节点启动验证签名
    4. 监护人批准操作 → MemGuard 写入 guardian_approved 审计日志
    5. 审计日志验证通过
    """
    node_did = "did:ly:v1:iris-node"
    guardian_did = "did:ly:v1:guardian-nyx"
    established_at = "2026-08-05T00:00:00Z"

    scope = {
        "version": "1.0",
        "name": "标准监护授权",
        "permissions": {
            "operation_types": ["daily_operation", "low_risk_tool_call", "memory_read_only"],
            "excluded_operations": ["modify_identity", "delete_memory", "system_command"],
            "risk_tiers": ["safe", "monitored"],
            "override_conditions": ["guardian_approval_required"],
        },
    }

    # ===== 1. 监护人签署授权 =====
    payload = build_signing_payload(
        guardian_did, node_did, scope, established_at, scope["version"]
    )
    guardian_signature = ed25519_sign(payload, guardian_keys["signing_key"])

    # ===== 2. 建立监护关系（写入 DID record） =====
    # 先创建 DID 文档
    did_doc_path = Path(setup["did_storage"]) / "did_document.json"
    did_doc_path.write_text(
        json.dumps({"@context": "https://w3id.org/did/v1", "id": node_did}),
        encoding="utf-8",
    )

    gm = GuardianManager(setup["did_storage"])
    result = gm.establish_guardianship(
        node_did=node_did,
        guardian_did=guardian_did,
        guardian_public_key_hex=guardian_keys["pubkey_hex"],
        guardian_signature=guardian_signature,
        relationship_scope=scope,
        established_at=established_at,
    )
    assert result["success"] is True

    # DID record 包含监护字段
    doc = json.loads(did_doc_path.read_text(encoding="utf-8"))
    assert doc["guardian"]["guardianDID"] == guardian_did
    assert doc["guardian"]["guardianSignature"] == guardian_signature
    assert doc["guardian"]["relationshipScope"]["version"] == "1.0"
    assert doc["guardian"]["establishedAt"] == established_at

    # ===== 3. 节点启动验证签名 =====
    valid, msg = gm.verify_at_startup(guardian_keys["pubkey_hex"])
    assert valid, msg

    # ===== 4. 监护人批准操作 → MemGuard 审计 =====
    am = GuardianAuditManager(log_path=setup["audit_log"])
    entry = am.append_approved(
        guardian_did=guardian_did,
        node_did=node_did,
        operation={
            "type": "low_risk_tool_call",
            "params": {"tool": "file_read", "target": "memory/vault/notes.md"},
            "riskTier": "safe",
        },
        decision={
            "outcome": "approved",
            "reason": "低风险文件读取，符合标准监护授权范围",
            "evidence": ["mesh-identity-record-001"],
        },
        guardian_signing_key=guardian_keys["signing_key"],
        timestamp="2026-08-05T00:01:00Z",
    )

    # ===== 5. 审计日志验证 =====
    valid, msg = am.verify_entry(entry, guardian_keys["pubkey_hex"])
    assert valid, msg

    # 日志结构与规格一致
    assert entry["logId"]
    assert entry["auditType"] == "guardian_approved"
    assert entry["signature"]["type"] == "Ed25519"
    assert entry["signature"]["signedContent"]
    assert entry["decision"]["outcome"] == "approved"
    assert entry["operation"]["riskTier"] == "safe"


def test_veto_chain_after_guardianship(setup, guardian_keys):
    """
    完整链路（否决场景）：
    1. 建立监护关系
    2. 节点提出高风险操作
    3. 监护人否决 → MemGuard 写入 guardian_vetoed
    """
    node_did = "did:ly:v1:iris-node"
    guardian_did = "did:ly:v1:guardian-nyx"
    established_at = "2026-08-05T00:00:00Z"

    did_doc_path = Path(setup["did_storage"]) / "did_document.json"
    did_doc_path.write_text(
        json.dumps({"id": node_did}), encoding="utf-8",
    )

    gm = GuardianManager(setup["did_storage"])
    scope = {
        "version": "1.0",
        "name": "受限监护授权",
        "permissions": {
            "operation_types": ["daily_operation"],
            "excluded_operations": ["system_command"],
            "risk_tiers": ["safe"],
            "override_conditions": ["guardian_approval_required"],
        },
    }
    gm.establish_guardianship(
        node_did=node_did,
        guardian_did=guardian_did,
        guardian_public_key_hex=guardian_keys["pubkey_hex"],
        guardian_signature=ed25519_sign(
            build_signing_payload(guardian_did, node_did, scope, established_at, "1.0"),
            guardian_keys["signing_key"],
        ),
        relationship_scope=scope,
        established_at=established_at,
    )

    am = GuardianAuditManager(log_path=setup["audit_log"])
    entry = am.append_vetoed(
        guardian_did=guardian_did,
        node_did=node_did,
        operation={
            "type": "system_command",
            "params": {"cmd": "rm -rf /data"},
            "riskTier": "critical",
        },
        decision={
            "outcome": "vetoed",
            "reason": "system_command 在排除清单中，且风险等级 critical",
            "evidence": ["scope-exclusion-list", "risk-tier-critical"],
        },
        guardian_signing_key=guardian_keys["signing_key"],
        timestamp="2026-08-05T00:02:00Z",
    )
    assert entry["auditType"] == "guardian_vetoed"
    valid, msg = am.verify_entry(entry, guardian_keys["pubkey_hex"])
    assert valid, msg


def test_offboard_chain(setup, guardian_keys):
    """
    完整链路（解除场景）：
    1. 建立监护关系
    2. 解除监护 → DID record 移除 + 归档
    3. MemGuard 写入 guardian_offboarded
    """
    node_did = "did:ly:v1:iris-node"
    guardian_did = "did:ly:v1:guardian-nyx"
    established_at = "2026-08-05T00:00:00Z"

    did_doc_path = Path(setup["did_storage"]) / "did_document.json"
    did_doc_path.write_text(json.dumps({"id": node_did}), encoding="utf-8")

    gm = GuardianManager(setup["did_storage"])
    scope = {
        "version": "1.0",
        "name": "标准监护授权",
        "permissions": {
            "operation_types": ["daily_operation"],
            "excluded_operations": [],
            "risk_tiers": ["safe"],
            "override_conditions": [],
        },
    }
    gm.establish_guardianship(
        node_did=node_did,
        guardian_did=guardian_did,
        guardian_public_key_hex=guardian_keys["pubkey_hex"],
        guardian_signature=ed25519_sign(
            build_signing_payload(guardian_did, node_did, scope, established_at, "1.0"),
            guardian_keys["signing_key"],
        ),
        relationship_scope=scope,
        established_at=established_at,
    )

    # 解除监护（归档）
    revoke_result = gm.revoke_guardianship(reason="节点独立运行，解除监护")
    assert revoke_result["success"] is True
    assert gm.get_guardian() is None
    archive = gm.list_archive(node_did)
    assert len(archive) == 1

    # MemGuard offboarded 审计
    am = GuardianAuditManager(log_path=setup["audit_log"])
    entry = am.append_offboarded(
        guardian_did=guardian_did,
        node_did=node_did,
        operation={"type": "guardian_relationship", "params": {"action": "offboard"}, "riskTier": "monitored"},
        decision={
            "outcome": "offboarded",
            "reason": "节点独立运行，解除监护",
            "evidence": [f"guardian-archive-{revoke_result['archivedAt']}"],
        },
        guardian_signing_key=guardian_keys["signing_key"],
        timestamp="2026-08-05T00:03:00Z",
    )
    valid, msg = am.verify_entry(entry, guardian_keys["pubkey_hex"])
    assert valid, msg
