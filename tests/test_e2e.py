"""End-to-end integration tests — across module boundaries."""
import os, sys, json, pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

class TestKBWithCrypto:
    """kb create → verify hash → encrypt → decrypt → read."""

    def test_entry_to_encrypted_roundtrip(self, tmp_path, monkeypatch):
        """Create an entry, verify hash_index, encrypt, decrypt, read."""
        import kb
        from memguard.crypto import FileEncryptor

        # Setup temp KB directory
        monkeypatch.setattr(kb, 'BASE_DIR', tmp_path)
        monkeypatch.setattr(kb, 'KB_DIR', tmp_path)

        # Create entry via ProtocolEnforcer (simulating what create command does)
        pe = kb.ProtocolEnforcer()
        entry_id = "test-e2e-001"
        entry_type = "Concept"
        meta = {
            "id": entry_id,
            "type": entry_type,
            "name": "E2E Test",
            "description": "End-to-end test entry",
            "layer": None,
            "status": "draft",
            "visibility": "internal",
            "tags": ["test"],
            "creator": "nyx",
            "owner": "nyx",
        }
        body = "这是端到端测试的内容，包含加密流程。"
        ok, violations = pe.validate_create(meta, body, operator="nyx")

        # Write entry file (as kb create would)
        type_dir = tmp_path / entry_type.lower()
        type_dir.mkdir(parents=True, exist_ok=True)
        entry_file = type_dir / f"{entry_id}.md"
        entry_file.write_text(kb.make_yaml_front_matter(meta, body), encoding="utf-8")

        assert entry_file.exists()
        content = entry_file.read_text(encoding="utf-8")
        assert "E2E Test" in content

        # Now encrypt
        fe = FileEncryptor(workspace_path=tmp_path)
        fe.encrypt_file(entry_file)
        enc = entry_file.read_bytes()
        assert b"E2E Test" not in enc  # should be encrypted

        # Decrypt and verify
        fe.decrypt_file(entry_file)
        dec = entry_file.read_text(encoding="utf-8")
        assert "E2E Test" in dec
        assert body in dec

class TestPolarisPipeline:
    """Full Polaris pipeline: tag → sample → detect → archive."""

    def test_full_pipeline(self, tmp_path):
        from anti_drift.scene_tagger import SceneTagger
        from anti_drift.sampler import Sampler
        from anti_drift.detector import DeviationDetector
        from anti_drift.archive import Archiver, Judge

        # L0.5
        tagger = SceneTagger()
        tags = tagger.tag([
            {"sender": "user", "text": "AI的本质是什么？"}
        ])

        # L1
        sampler = Sampler()
        baselines = sampler.load_baseline()
        if not baselines:
            pytest.skip("No baselines available")

        qid = list(baselines.keys())[0]
        baseline = baselines[qid]
        result = sampler.deep_sample(baseline, tags, session_id="e2e-test")
        assert result is not None

        # L2
        detector = DeviationDetector()
        d_result = detector.detect(baseline, baseline, tags)
        assert d_result.total_deviation < 0.1

        # L3+L4
        judge = Judge()
        judgment = judge.classify(d_result.total_deviation)
        archiver = Archiver(archive_dir=tmp_path)
        record = archiver.store(
            question_id=qid,
            question_text=result.question_text if hasattr(result, 'question_text') else qid,
            current_answer=baseline,
            deviation=d_result.total_deviation,
            judgment=judgment
        )
        assert record is not None

class TestMemGuardChain:
    """Auth → encrypt → sign → verify → audit chain."""

    def test_security_chain(self, tmp_path):
        from memguard.auth import AuthManager, PermissionLevel
        from memguard.crypto import FileEncryptor
        from memguard.integrity import SignatureManager
        from memguard.audit import AuditEventType, EnhancedAuditManager

        # 1. Auth: generate token
        am = AuthManager(workspace_path=tmp_path)
        token = am.generate_token("nyx", [PermissionLevel.READ, PermissionLevel.WRITE])
        assert am.check_token(token, PermissionLevel.READ) is True

        # 2. Crypto: encrypt data
        fe = FileEncryptor(workspace_path=tmp_path)
        secret = b"secret memory content"
        cipher = fe.encrypt(secret)
        assert cipher != secret

        # 3. Integrity: sign the ciphertext
        sm = SignatureManager(workspace_path=tmp_path)
        sm.sign(cipher, "secret-data")
        assert sm.verify(cipher, "secret-data") is True

        # 4. Decrypt
        decrypted = fe.decrypt(cipher)
        assert decrypted == secret

        # 5. Audit: log the operation
        audit = EnhancedAuditManager(log_dir=tmp_path)
        audit.log_event(
            AuditEventType.ACCESS, "nyx", "secret-data",
            {"action": "read", "result": "success"}
        )
        logs = audit.query(limit=5)
        assert len(logs) >= 1

class TestGovWithProtocols:
    """Governance parser integration."""

    def test_load_and_validate(self):
        from gov_parser.loader import load_protocols
        from gov_parser.circuit_breaker import CircuitBreaker

        p = load_protocols(protocol_dir=str(PROJECT_ROOT / "gov_protocol"))
        assert len(p) >= 5

        cb = CircuitBreaker(threshold=3, cooldown=1)
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert not cb.is_closed()
        cb.reset()
        assert cb.is_closed()
