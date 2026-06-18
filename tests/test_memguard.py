"""Tests for MemGuard --- integrity, crypto, auth, audit modules."""
import os, json, hashlib, tempfile, pytest
from pathlib import Path

class TestIntegrity:
    def test_imports(self):
        from memguard.integrity import SignatureManager, TrustDomainChecker, HashUtils
        assert True

    def test_hash_utils(self, tmp_path):
        from memguard.integrity import HashUtils
        f = tmp_path / "hash_test.txt"
        f.write_bytes(b"hello")
        h = HashUtils.sha256_file(str(f))
        assert len(h) == 64

    # Note: sign/verify tests use tmp_path which triggers Python 3.14 tempfile fd bug
    # These are tested in test_memguard_full.py with file-based approach


class TestCrypto:
    def test_imports(self):
        from memguard.crypto import FileEncryptor, KeyManager, AES256Crypto
        assert True

    def test_encrypt_decrypt_file(self, tmp_path):
        from memguard.crypto import FileEncryptor, KeyManager
        km = KeyManager()
        key = km.generate_and_store_key()
        fe = FileEncryptor()
        original = "中文加密内容测试。"
        f = tmp_path / "secret.txt"
        f.write_text(original, encoding="utf-8")
        enc = fe.encrypt_file(str(f), key)
        assert enc is not None
        fe.decrypt_file(enc.encrypted_path, key)
        dec = (tmp_path / "secret.txt").read_text(encoding="utf-8")
        assert dec == original

    def test_key_manager(self):
        from memguard.crypto import KeyManager
        km = KeyManager()
        key = km.generate_and_store_key()
        assert key is not None
        assert isinstance(key, bytes)

    def test_key_recovery(self):
        from memguard.crypto import KeyManager
        km = KeyManager()
        key1 = km.generate_and_store_key()
        key2 = km.recover_key()
        assert key1 == key2

    def test_list_encrypted_empty(self):
        from memguard.crypto import FileEncryptor
        fe = FileEncryptor()
        result = fe.list_encrypted()
        assert isinstance(result, list)


class TestAuth:
    def test_imports(self):
        from memguard.auth import AuthManager, PermissionLevel, NodeKey
        assert True

    def test_register_and_authenticate(self):
        from memguard.auth import AuthManager, NodeType, PermissionLevel
        am = AuthManager()
        node_id = f"test-auth-{id(self)}"
        nid, plain_key = am.register_node(
            node_id, NodeType.NYX, PermissionLevel.ADMIN
        )
        # Register device first (authenticate requires device verification)
        device_id = am.register_device(nid, cpu_id="test-cpu", mac_address="00:00:00:00:00:01")
        # Then authenticate
        ok, msg, session = am.authenticate(nid, plain_key, device_id=device_id)
        assert ok is True, f"authenticate failed: {msg}"

    def test_authenticate_wrong_key(self):
        from memguard.auth import AuthManager, NodeType, PermissionLevel
        am = AuthManager()
        nid = f"test-nyx2-{id(self)}"
        am.register_node(nid, NodeType.NYX, PermissionLevel.ADMIN)
        ok, msg, session = am.authenticate(nid, "wrongkey")
        assert ok is False

    def test_node_key_creation(self):
        from memguard.auth import NodeKey
        nk = NodeKey(
            node_id="test-node",
            node_type="core",
            key_hash="abc123",
            salt="salt123",
            permission_level="admin",
            created_at="2026-01-01T00:00:00"
        )
        assert nk.node_id == "test-node"
        assert nk.permission_level == "admin"

    def test_verify_key(self):
        from memguard.auth import AuthManager, NodeType, PermissionLevel
        am = AuthManager()
        nid = f"test-verify-{id(self)}"
        node_id, plain_key = am.register_node(
            nid, NodeType.NYX, PermissionLevel.ADMIN
        )
        ok, msg = am.verify_key(node_id, plain_key)
        assert ok is True


class TestAudit:
    def test_imports(self):
        from memguard.audit import EnhancedAuditManager, RiskAssessor
        assert True

    def test_append_and_search(self):
        from memguard.audit import EnhancedAuditManager
        am = EnhancedAuditManager()
        am.append(event="access", node_id="nyx", operation="read", target_resource="test.md")
        results = am.search(event="access")
        assert len(results) >= 1

    def test_verify_chain(self):
        from memguard.audit import EnhancedAuditManager
        am = EnhancedAuditManager()
        am.append(event="access", node_id="nyx", operation="read", target_resource="test.md")
        ok, msg = am.verify_chain()
        assert ok is True

    def test_risk_assessor(self):
        from memguard.audit import RiskAssessor
        ra = RiskAssessor()
        risk_level, reasons = ra.assess(event="crypto_failure", node_id="unknown", ip="1.2.3.4")
        assert isinstance(risk_level, int)
        assert isinstance(reasons, list)

    def test_get_stats(self):
        from memguard.audit import EnhancedAuditManager
        am = EnhancedAuditManager()
        am.append(event="access", node_id="nyx", operation="read", target_resource="test.md")
        stats = am.get_stats()
        assert isinstance(stats, dict)
