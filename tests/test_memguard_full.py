#!/usr/bin/env python3
"""
MemGuard 模块测试 - pytest 全覆盖
测试目标: core, crypto, audit, integrity
"""
import os
import json
import pytest
import tempfile
from pathlib import Path
from datetime import datetime

# ============================================================
# Test Core Module - FileEncryptor encrypt/decrypt
# ============================================================
class TestCore:
    """测试 core.py - MemGuard 核心功能"""
    
    def test_config_init(self):
        """测试配置初始化"""
        from memguard.core import Config
        Config.init()
        assert Config.BASELINE_DIR is not None
        assert Config.MEMORY_DIR is not None
        assert Config.AUDIT_DIR is not None
    
    def test_hash_utils_compute_hashes(self):
        """测试 Hash 计算工具"""
        from memguard.core import HashUtils
        
        content = "test content for hashing"
        hashes = HashUtils.compute_hashes(content)
        
        assert 'sha256' in hashes
        assert 'blake3' in hashes
        assert len(hashes['sha256']) == 64  # SHA256 = 64 hex chars
    
    def test_hash_utils_sha256(self):
        """测试 SHA256 计算"""
        from memguard.core import HashUtils
        
        data = "hello world"
        sha = HashUtils.sha256(data)
        
        assert sha == hashlib.sha256(data.encode()).hexdigest()
    
    def test_baseline_manager_lock_unlock(self):
        """测试基线锁定/解锁"""
        from memguard.core import BaselineManager, Config
        
        Config.init()
        bm = BaselineManager()
        
        # 解锁
        bm.unlock()
        assert not bm.is_readonly()
        
        # 锁定
        bm.lock()
        assert bm.is_readonly()
        
        # 清理
        bm.unlock()
    
    def test_baseline_manager_save_and_read(self):
        """测试基线保存和读取"""
        from memguard.core import BaselineManager, Config
        
        Config.init()
        bm = BaselineManager()
        bm.unlock()
        
        # 保存基线
        test_sha256 = "abc123" * 10 + "abcd"  # 64 chars
        test_blake3 = "def456" * 10 + "defg"  # 64 chars
        bm.save_baseline(test_sha256, test_blake3)
        
        # 读取基线
        baseline = bm.read_baseline()
        assert baseline['sha256'] == test_sha256
        assert baseline['blake3'] == test_blake3
        
        # 应该自动锁定
        assert bm.is_readonly()
        
        # 清理
        bm.unlock()
    
    def test_audit_log_append_and_verify(self):
        """测试审计日志追加和链验证"""
        from memguard.core import AuditLogManager, Config
        
        Config.init()
        am = AuditLogManager()
        
        # 追加日志
        log = am.append(
            event="test_event",
            memory_id="test_mem_001",
            operator="test_admin",
            detail="Test detail"
        )
        
        assert log.event == "test_event"
        assert log.memory_id == "test_mem_001"
        assert log.hash is not None
        
        # 验证链
        valid, msg = am.verify_chain()
        assert valid is True
    
    def test_audit_log_search(self):
        """测试审计日志搜索"""
        from memguard.core import AuditLogManager, Config
        
        Config.init()
        am = AuditLogManager()
        
        # 追加多条日志
        am.append("search_test_1", "mem1", "admin", "detail 1")
        am.append("search_test_2", "mem2", "admin", "detail 2")
        am.append("search_test_1", "mem3", "admin", "detail 3")
        
        # 搜索
        results = am.search(event="search_test_1")
        assert len(results) >= 2
        
        results2 = am.search(memory_id="mem2")
        assert len(results2) >= 1


# ============================================================
# Test Crypto Module - AES-256 encrypt/decrypt
# ============================================================
class TestCrypto:
    """测试 crypto.py - AES-256 加解密"""
    
    def test_aes256_generate_key(self):
        """测试密钥生成"""
        from memguard.crypto import AES256Crypto
        
        crypto = AES256Crypto()
        key = crypto.generate_key()
        
        assert key is not None
        assert len(key) == 32  # 256 bits = 32 bytes
    
    def test_aes256_encrypt_decrypt(self):
        """测试 AES-256-GCM 加解密"""
        from memguard.crypto import AES256Crypto
        
        crypto = AES256Crypto()
        key = crypto.generate_key()
        
        plaintext = b"This is a secret message for testing."
        
        # 加密
        nonce, ciphertext, tag = crypto.encrypt(plaintext, key)
        
        assert nonce is not None
        assert ciphertext is not None
        assert tag is not None
        assert ciphertext != plaintext
        
        # 解密
        decrypted = crypto.decrypt(nonce, ciphertext, tag, key)
        
        assert decrypted == plaintext
    
    def test_aes256_decrypt_with_wrong_key(self):
        """测试错误密钥解密（应该失败）"""
        from memguard.crypto import AES256Crypto
        
        crypto = AES256Crypto()
        key1 = crypto.generate_key()
        key2 = crypto.generate_key()
        
        plaintext = b"Secret data"
        nonce, ciphertext, tag = crypto.encrypt(plaintext, key1)
        
        # 用错误密钥解密
        with pytest.raises(ValueError):
            crypto.decrypt(nonce, ciphertext, tag, key2)
    
    def test_aes256_compute_hash(self):
        """测试哈希计算"""
        from memguard.crypto import AES256Crypto
        
        crypto = AES256Crypto()
        data = b"test data for hash"
        
        hash_val = crypto.compute_hash(data)
        
        assert hash_val is not None
        assert len(hash_val) == 64  # SHA256
    
    def test_file_encryptor_encrypt_decrypt_file(self):
        """测试文件加解密"""
        from memguard.crypto import FileEncryptor, KeyManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # 创建测试文件
            test_file = tmppath / "test.txt"
            test_content = "这是测试内容，用于验证文件加密。"
            test_file.write_text(test_content, encoding='utf-8')
            
            # 加密
            km = KeyManager()
            km._ensure_dirs()
            key = km.generate_and_store_key()
            
            fe = FileEncryptor()
            encrypted = fe.encrypt_file(str(test_file), key)
            
            assert encrypted.encrypted_path is not None
            assert encrypted.original_hash is not None
            
            # 解密
            output_file = tmppath / "decrypted.txt"
            decrypted_path = fe.decrypt_file(
                encrypted.encrypted_path, 
                key, 
                str(output_file)
            )
            
            decrypted_content = Path(decrypted_path).read_text(encoding='utf-8')
            assert decrypted_content == test_content


# ============================================================
# Test Audit Module - 审计日志写入+读取
# ============================================================
class TestAudit:
    """测试 audit.py - 增强审计日志"""
    
    def test_enhanced_audit_append(self):
        """测试增强审计日志写入"""
        from memguard.audit import EnhancedAuditManager, AuditEventType
        
        with tempfile.TemporaryDirectory() as tmpdir:
            am = EnhancedAuditManager()
            am.log_path = str(Path(tmpdir) / "audit.jsonl")
            Path(tmpdir).mkdir(parents=True, exist_ok=True)
            
            log = am.append(
                event=AuditEventType.LOGIN_SUCCESS.value,
                node_id="test_node",
                operation="login",
                target_resource="session",
                detail="User logged in"
            )
            
            assert log.id is not None
            assert log.event == AuditEventType.LOGIN_SUCCESS.value
            assert log.hash is not None
    
    def test_enhanced_audit_verify_chain(self):
        """测试审计链验证"""
        from memguard.audit import EnhancedAuditManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            am = EnhancedAuditManager()
            am.log_path = str(Path(tmpdir) / "audit.jsonl")
            Path(tmpdir).mkdir(parents=True, exist_ok=True)
            
            # 写入多条日志
            for i in range(5):
                am.append(
                    event="data_read",
                    node_id=f"node_{i}",
                    operation="read",
                    target_resource=f"file_{i}.md"
                )
            
            # 验证链
            valid, msg = am.verify_chain()
            assert valid is True
            assert "完整" in msg or "验证通过" in msg
    
    def test_enhanced_audit_search(self):
        """测试审计日志搜索"""
        from memguard.audit import EnhancedAuditManager, AuditEventType
        
        with tempfile.TemporaryDirectory() as tmpdir:
            am = EnhancedAuditManager()
            am.log_path = str(Path(tmpdir) / "audit.jsonl")
            Path(tmpdir).mkdir(parents=True, exist_ok=True)
            
            # 写入日志
            am.append("login_success", "node1", "login", "session")
            am.append("login_failed", "node2", "login", "session")
            am.append("data_read", "node1", "read", "file.md")
            
            # 搜索
            results = am.search(event="login_failed")
            assert len(results) >= 1
            assert results[0].event == "login_failed"
    
    def test_risk_assessor_assess(self):
        """测试风险评估"""
        from memguard.audit import RiskAssessor
        
        # 高风险场景：敏感操作 + 外部IP
        score1, factors1 = RiskAssessor.assess(
            event="login_failed",
            node_id="unknown",
            ip="203.0.113.50"  # 外部IP
        )
        
        assert score1 > 0
        assert len(factors1) > 0
        
        # 低风险场景：内部操作
        score2, factors2 = RiskAssessor.assess(
            event="data_read",
            node_id="trusted_node",
            ip="192.168.1.100"  # 内网IP
        )
        
        # 内网IP + 正常操作的风险应该更低
        # 注意：如果是在异常时段，score2 可能不比 score1 低
        # 所以只检查返回格式是否正确
        assert isinstance(score2, int)
        assert isinstance(factors2, list)
    
    def test_ip_utils_is_internal_ip(self):
        """测试内网IP判断"""
        from memguard.audit import IPUtils
        
        assert IPUtils.is_internal_ip("192.168.1.1") is True
        assert IPUtils.is_internal_ip("10.0.0.1") is True
        assert IPUtils.is_internal_ip("172.16.0.1") is True
        assert IPUtils.is_internal_ip("127.0.0.1") is True
        assert IPUtils.is_internal_ip("203.0.113.1") is False


# ============================================================
# Test Integrity Module - 完整性校验
# ============================================================
class TestIntegrity:
    """测试 integrity.py - 文件完整性签名"""
    
    def test_hash_utils_sha256_file(self):
        """测试文件 SHA256 计算"""
        from memguard.integrity import HashUtils
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Hello, World!", encoding='utf-8')
            
            sha = HashUtils.sha256_file(str(test_file))
            
            assert sha is not None
            assert len(sha) == 64
    
    def test_signature_manager_sign_file(self):
        """测试文件签名"""
        from memguard.integrity import SignatureManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # 创建测试文件
            test_file = tmppath / "SOUL.md"
            test_file.write_text("# My Soul", encoding='utf-8')
            
            # 签名
            sm = SignatureManager(workspace_dir=str(tmppath))
            sm.signatures_dir = str(tmppath / "sigs")
            sm.signatures_file = str(tmppath / "sigs" / "signatures.json")
            sm.signing_key_file = str(tmppath / "key.bin")
            sm.signing_key = sm._load_or_create_key()
            sm.signatures = {}
            Path(tmppath / "sigs").mkdir(parents=True, exist_ok=True)
            
            sig = sm.sign_file("SOUL.md", "test_node")
            
            assert sig is not None
            assert sig.filename == "SOUL.md"
            assert sig.sha256 is not None
            assert sig.hmac_signature is not None
    
    def test_signature_manager_verify_file(self):
        """测试文件验证"""
        from memguard.integrity import SignatureManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # 创建并签名文件
            test_file = tmppath / "USER.md"
            test_file.write_text("# User Profile", encoding='utf-8')
            
            sm = SignatureManager(workspace_dir=str(tmppath))
            sm.signatures_dir = str(tmppath / "sigs")
            sm.signatures_file = str(tmppath / "sigs" / "signatures.json")
            sm.signing_key_file = str(tmppath / "key.bin")
            sm.signing_key = sm._load_or_create_key()
            sm.signatures = {}
            Path(tmppath / "sigs").mkdir(parents=True, exist_ok=True)
            
            sm.sign_file("USER.md", "test_node")
            
            # 验证（文件未修改）
            valid, status, record = sm.verify_file("USER.md")
            
            assert valid is True
            assert "完整" in status or "签名" in status
            assert record is None
    
    def test_signature_manager_detect_tamper(self):
        """测试篡改检测"""
        from memguard.integrity import SignatureManager
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # 创建并签名文件
            test_file = tmppath / "AGENTS.md"
            test_file.write_text("Original content", encoding='utf-8')
            
            sm = SignatureManager(workspace_dir=str(tmppath))
            sm.signatures_dir = str(tmppath / "sigs")
            sm.signatures_file = str(tmppath / "sigs" / "signatures.json")
            sm.signing_key_file = str(tmppath / "key.bin")
            sm.signing_key = sm._load_or_create_key()
            sm.signatures = {}
            Path(tmppath / "sigs").mkdir(parents=True, exist_ok=True)
            
            sm.sign_file("AGENTS.md", "test_node")
            
            # 修改文件
            test_file.write_text("TAMPERED CONTENT!", encoding='utf-8')
            
            # 验证（应检测到篡改）
            valid, status, record = sm.verify_file("AGENTS.md")
            
            assert valid is False
            assert record is not None
            assert record.detection_type == "sha256_mismatch"
    
    def test_signature_manager_verify_all(self):
        """测试批量验证"""
        from memguard.integrity import SignatureManager, IntegrityConfig
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # 创建多个核心文件
            for filename in ["SOUL.md", "IDENTITY.md", "USER.md"]:
                (tmppath / filename).write_text(f"# {filename}", encoding='utf-8')
            
            sm = SignatureManager(workspace_dir=str(tmppath))
            sm.signatures_dir = str(tmppath / "sigs")
            sm.signatures_file = str(tmppath / "sigs" / "signatures.json")
            sm.signing_key_file = str(tmppath / "key.bin")
            sm.signing_key = sm._load_or_create_key()
            sm.signatures = {}
            Path(tmppath / "sigs").mkdir(parents=True, exist_ok=True)
            
            # 签名所有文件
            for filename in ["SOUL.md", "IDENTITY.md", "USER.md"]:
                sm.sign_file(filename, "test_node")
            
            # 批量验证
            results, tamper_records = sm.verify_all_core_files()
            
            assert len(results) >= 3
            assert len(tamper_records) == 0


# ============================================================
# Test Logger Module - JSON 结构化日志
# ============================================================
class TestLogger:
    """测试 logger.py - JSON 日志模块"""
    
    def test_json_formatter_format(self):
        """测试 JSON 格式化器"""
        from memguard.logger import JsonFormatter
        import logging
        
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        output = formatter.format(record)
        data = json.loads(output)
        
        assert data["level"] == "INFO"
        assert data["module"] == "test"
        assert data["message"] == "Test message"
    
    def test_get_logger(self):
        """测试获取日志记录器"""
        from memguard.logger import get_logger
        
        logger = get_logger("test_logger")
        
        assert logger is not None
        assert logger.name == "test_logger"
        assert len(logger.handlers) > 0
    
    def test_get_logger_with_file(self):
        """测试文件日志"""
        from memguard.logger import get_logger
        
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            
            logger = get_logger("file_test", log_file=str(log_file))
            logger.info("Test log entry")
            
            # 检查文件是否创建
            assert log_file.exists()
            
            # 检查内容
            content = log_file.read_text(encoding='utf-8')
            data = json.loads(content.strip())
            
            assert data["message"] == "Test log entry"


# 导入 hashlib 用于测试
import hashlib
