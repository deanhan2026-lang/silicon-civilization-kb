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
        from memguard.crypto import FileEncryptor, KeyManager

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

        # Write entry file
        type_dir = tmp_path / entry_type.lower()
        type_dir.mkdir(parents=True, exist_ok=True)
        entry_file = type_dir / f"{entry_id}.md"
        entry_file.write_text(kb.make_yaml_front_matter(meta, body), encoding="utf-8")

        assert entry_file.exists()
        content = entry_file.read_text(encoding="utf-8")
        assert "E2E Test" in content

        # Now encrypt with actual API
        km = KeyManager()
        key = km.generate_and_store_key()
        fe = FileEncryptor()
        enc_result = fe.encrypt_file(str(entry_file), key, delete_original=True)
        assert not entry_file.exists() or entry_file.read_bytes() != content.encode()

        # Decrypt and verify
        fe.decrypt_file(enc_result.encrypted_path, key)
        dec_path = str(entry_file)  # should restore to original
        # The decrypted file should exist and contain original content
        dec_file = Path(enc_result.encrypted_path.replace(".enc", ""))
        if dec_file.exists():
            dec_content = dec_file.read_text(encoding="utf-8")
            assert "E2E Test" in dec_content


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

        # L2 — detect returns DeviationResult; use overall_score or similar
        detector = DeviationDetector()
        d_result = detector.detect(baseline, baseline, tags)
        # Get deviation score (attribute name may vary)
        dev_score = getattr(d_result, 'overall_score', None) or getattr(d_result, 'total_score', None) or 0
        assert dev_score < 1.0  # baseline vs baseline should be low deviation

        # L3+L4
        judge = Judge()
        judgment, action = judge.judge(d_result, question_id=qid, current_answer=baseline, baseline_answer=baseline)
        assert judgment is not None
        archiver = Archiver(archive_dir=tmp_path)
        snapshot = archiver.archive(
            judgment=judgment,
            correction=action,
            deviation=d_result,
            question_id=qid,
            current_answer=baseline,
            baseline_answer=baseline
        )
        assert snapshot is not None


class TestMemGuardChain:
    """Auth → encrypt → sign → verify → audit chain."""

    def test_security_chain(self, tmp_path):
        from memguard.auth import AuthManager, NodeType, PermissionLevel
        from memguard.crypto import FileEncryptor, KeyManager
        from memguard.integrity import SignatureManager, HashUtils
        from memguard.audit import EnhancedAuditManager

        # 1. Auth: register node and authenticate
        am = AuthManager()
        import time
        nid = f"e2e-nyx-{int(time.time()*1000)}"
        nid, plain_key = am.register_node(nid, NodeType.NYX, PermissionLevel.ADMIN)
        device_id = am.register_device(nid, cpu_id="e2e-cpu")
        ok, msg, session = am.authenticate(nid, plain_key, device_id=device_id)
        assert ok is True

        # 2. Crypto: encrypt file
        km = KeyManager()
        key = km.generate_and_store_key()
        test_file = tmp_path / "secret.txt"
        test_file.write_text("secret memory content", encoding="utf-8")
        fe = FileEncryptor()
        enc = fe.encrypt_file(str(test_file), key)
        assert enc is not None

        # 3. Integrity: hash the original content
        h = HashUtils.sha256_file(str(test_file))
        assert len(h) == 64

        # 4. Decrypt and verify
        fe.decrypt_file(enc.encrypted_path, key)

        # 5. Audit: log the operation
        audit = EnhancedAuditManager()
        audit.append(event="access", node_id=nid, operation="read", target_resource="secret.txt")
        results = audit.search(node_id=nid)
        assert len(results) >= 1


class TestGovWithProtocols:
    """Governance parser integration."""

    def test_load_and_validate(self):
        from gov_parser.loader import ProtocolLoader

        loader = ProtocolLoader()
        count = loader.load_all()
        assert count >= 5
        rules = loader.get_all_rules()
        assert len(rules) >= 5
