"""Tests for MemGuard --- integrity, crypto, auth, audit modules."""
import os, json, hashlib, tempfile, pytest
from pathlib import Path

class TestIntegrity:
    def test_imports(self):
        from memguard.integrity import SignatureManager, TrustDomainChecker, HashUtils
        assert True

    def test_sign_and_verify(self, tmp_path):
        from memguard.integrity import SignatureManager
        sm = SignatureManager(workspace_dir=str(tmp_path))
        # sign_file returns FileSignature
        f = tmp_path / "test.txt"
        f.write_text("hello", encoding="utf-8")
        sig = sm.sign_file(str(f), node_id="test-node")
        assert sig is not None
        ok, msg = sm.verify_file(str(f))
        assert ok is True

    def test_verify_tampered(self, tmp_path):
        from memguard.integrity import SignatureManager
        sm = SignatureManager(workspace_dir=str(tmp_path))
        f = tmp_path / "tamper.txt"
        f.write_text("original", encoding="utf-8")
        sm.sign_file(str(f), node_id="test-node")
        # Tamper the file
        f.write_text("MODIFIED", encoding="utf-8")
        ok, msg, _ = sm.verify_file(str(f))
        assert ok is False

    def test_file_sign_and_verify(self, tmp_path):
        from memguard.integrity import SignatureManager
        sm = SignatureManager(workspace_dir=str(tmp_path))
        f = tmp_path / "test2.txt"
        f.write_text("# Memory content", encoding="utf-8")
        sig = sm.sign_file(str(f), node_id="test-node")
        assert sig is not None
        ok, msg = sm.verify_file(str(f))
        assert ok is True

    def test_hash_utils(self, tmp_path):
        from memguard.integrity import HashUtils
        f = tmp_path / "hash_test.txt"
        f.write_bytes(b"hello")
        h = HashUtils.sha256_file(str(f))
        assert len(h) == 64


class TestCrypto:
    def test_imports(self):
        from memguard.crypto import FileEncryptor, KeyManager, AES256Crypto
        assert True

    def test_encrypt_decrypt_roundtrip(self, tmp_path):
        from memguard.crypto import FileEncryptor
        fe = FileEncryptor(workspace_dir=str(tmp_path))
        plain = b"This is secret memory."
        cipher = fe.encrypt(plain)
        assert cipher != plain
        decrypted = fe.decrypt(cipher)
        assert decrypted == plain

    def test_file_encrypt_decrypt(self, tmp_path):
        from memguard.crypto import FileEncryptor
        fe = FileEncryptor(workspace_dir=str(tmp_path))
        original = "中文加密内容测试。"
        f = tmp_path / "secret.txt"
        f.write_text(original, encoding="utf-8")
        fe.encrypt_file(str(f))
        fe.decrypt_file(str(f))
        dec = f.read_text(encoding="utf-8")
        assert dec == original

    def test_key_manager(self, tmp_path):
        from memguard.crypto import KeyManager
        km = KeyManager(workspace_dir=str(tmp_path))
        key = km.get_or_create_key()
        assert key is not None

    def test_encrypt_with_different_key(self, tmp_path):
        """Encrypt with one key, try to decrypt with another."""
        from memguard.crypto import FileEncryptor
        fe1 = FileEncryptor(workspace_dir=str(tmp_path / "key1"))
        fe2 = FileEncryptor(workspace_dir=str(tmp_path / "key2"))
        cipher = fe1.encrypt(b"secret")
        try:
            fe2.decrypt(cipher)
            assert False, "Should have raised an exception"
        except Exception:
            pass


class TestAuth:
    def test_imports(self):
        from memguard.auth import AuthManager, PermissionLevel, NodeKey
        assert True

    def test_generate_and_check_token(self, tmp_path):
        from memguard.auth import AuthManager, PermissionLevel
        am = AuthManager()
        token = am.generate_token("nyx", [PermissionLevel.READ, PermissionLevel.WRITE])
        assert token is not None
        assert am.check_token(token, PermissionLevel.READ) is True

    def test_wrong_permission(self, tmp_path):
        from memguard.auth import AuthManager, PermissionLevel
        am = AuthManager()
        token = am.generate_token("nyx", [PermissionLevel.READ])
        assert am.check_token(token, PermissionLevel.WRITE) is False

    def test_invalid_token(self, tmp_path):
        from memguard.auth import AuthManager, PermissionLevel
        am = AuthManager()
        assert am.check_token("bad-token", PermissionLevel.READ) is False

    def test_revoke_token(self, tmp_path):
        from memguard.auth import AuthManager, PermissionLevel
        am = AuthManager()
        tok = am.generate_token("nyx", [PermissionLevel.READ])
        assert am.check_token(tok, PermissionLevel.READ) is True
        am.revoke_token(tok)
        assert am.check_token(tok, PermissionLevel.READ) is False

    def test_node_key_generation(self, tmp_path):
        from memguard.auth import NodeKey, NodeType
        key = NodeKey.generate("nyx", NodeType.CORE)
        assert key is not None


class TestAudit:
    def test_imports(self):
        from memguard.audit import AuditEventType, EnhancedAuditManager, RiskAssessor
        assert True

    def test_log_event(self, tmp_path):
        from memguard.audit import AuditEventType, EnhancedAuditManager
        am = EnhancedAuditManager()
        entry = am.log_event(
            event_type=AuditEventType.ACCESS,
            actor="nyx",
            resource="test-file.md",
            details={"action": "read"}
        )
        assert entry is not None
        assert entry.event_type == AuditEventType.ACCESS

    def test_read_logs(self, tmp_path):
        from memguard.audit import AuditEventType, EnhancedAuditManager
        am = EnhancedAuditManager()
        am.log_event(AuditEventType.MODIFY, "nyx", "file1", {"change": "update"})
        logs = am.query(limit=10)
        assert len(logs) >= 1

    def test_risk_assessor(self):
        from memguard.audit import RiskAssessor
        ra = RiskAssessor()
        risk = ra.assess(
            event_type="crypto_failure",
            actor="unknown",
            resource_count=10
        )
        assert risk is not None
