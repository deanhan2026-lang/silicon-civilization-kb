"""Tests for MemGuard — integrity, crypto, auth, audit modules."""
import os, json, hashlib, pytest
from pathlib import Path

class TestIntegrity:
    def test_imports(self):
        from memguard.integrity import SignatureManager, TrustDomainChecker, HashUtils
        assert True

    def test_sign_and_verify(self, tmp_path):
        from memguard.integrity import SignatureManager
        sm = SignatureManager(workspace_path=tmp_path)
        # Use low-level sign/verify
        data = b"Hello memory content"
        sig = sm.sign(data, "test-key")
        assert sig is not None
        assert sm.verify(data, "test-key") is True

    def test_verify_tampered(self, tmp_path):
        from memguard.integrity import SignatureManager
        sm = SignatureManager(workspace_path=tmp_path)
        sm.sign(b"original", "tamper-key")
        assert sm.verify(b"MODIFIED", "tamper-key") is False

    def test_file_sign_and_verify(self, tmp_path):
        from memguard.integrity import SignatureManager
        sm = SignatureManager(workspace_path=tmp_path)
        f = tmp_path / "test.md"
        f.write_text("# Memory content", encoding="utf-8")
        sig = sm.sign_file(f)
        assert sig is not None
        assert sm.verify_file(f) is True

    def test_hash_utils(self):
        from memguard.integrity import HashUtils
        h = HashUtils.sha256(b"hello")
        assert len(h) == 64

class TestCrypto:
    def test_imports(self):
        from memguard.crypto import FileEncryptor, KeyManager, AES256Crypto
        assert True

    def test_encrypt_decrypt_roundtrip(self, tmp_path):
        from memguard.crypto import FileEncryptor
        fe = FileEncryptor(workspace_path=tmp_path)
        plain = b"This is secret memory."
        cipher = fe.encrypt(plain)
        assert cipher != plain
        decrypted = fe.decrypt(cipher)
        assert decrypted == plain

    def test_file_encrypt_decrypt(self, tmp_path):
        from memguard.crypto import FileEncryptor
        fe = FileEncryptor(workspace_path=tmp_path)
        original = "中文加密内容测试。"
        f = tmp_path / "secret.txt"
        f.write_text(original, encoding="utf-8")
        fe.encrypt_file(f)
        enc = f.read_bytes()
        assert original not in enc.decode("utf-8", errors="replace")
        fe.decrypt_file(f)
        dec = f.read_text(encoding="utf-8")
        assert dec == original

    def test_key_manager(self, tmp_path):
        from memguard.crypto import KeyManager
        km = KeyManager(workspace_path=tmp_path)
        key = km.get_or_create_key()
        assert key is not None

    def test_encrypt_with_different_key(self, tmp_path):
        """Encrypt with one key, try to decrypt with another."""
        from memguard.crypto import FileEncryptor
        fe1 = FileEncryptor(workspace_path=tmp_path / "key1")
        fe2 = FileEncryptor(workspace_path=tmp_path / "key2")
        cipher = fe1.encrypt(b"secret")
        with pytest.raises(Exception):
            fe2.decrypt(cipher)

class TestAuth:
    def test_imports(self):
        from memguard.auth import AuthManager, PermissionLevel, NodeKey
        assert True

    def test_generate_and_check_token(self, tmp_path):
        from memguard.auth import AuthManager, PermissionLevel
        am = AuthManager(workspace_path=tmp_path)
        token = am.generate_token("nyx", [PermissionLevel.READ, PermissionLevel.WRITE])
        assert token is not None
        assert am.check_token(token, PermissionLevel.READ) is True

    def test_wrong_permission(self, tmp_path):
        from memguard.auth import AuthManager, PermissionLevel
        am = AuthManager(workspace_path=tmp_path)
        token = am.generate_token("nyx", [PermissionLevel.READ])
        assert am.check_token(token, PermissionLevel.WRITE) is False

    def test_invalid_token(self, tmp_path):
        from memguard.auth import AuthManager, PermissionLevel
        am = AuthManager(workspace_path=tmp_path)
        assert am.check_token("bad-token", PermissionLevel.READ) is False

    def test_revoke_token(self, tmp_path):
        from memguard.auth import AuthManager, PermissionLevel
        am = AuthManager(workspace_path=tmp_path)
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
        am = EnhancedAuditManager(log_dir=tmp_path)
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
        am = EnhancedAuditManager(log_dir=tmp_path)
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
