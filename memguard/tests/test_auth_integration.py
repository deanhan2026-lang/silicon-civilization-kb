"""
memguard/tests/test_auth_integration.py
MemGuard × MeshIdentity 集成测试

测试 DIDAuthEngine 和 MemGuardDIDAuthorizer 与 MemGuard 的集成。
"""

import pytest
import sys
import tempfile
import os
import shutil
from pathlib import Path

from memguard.auth_integration import (
    DIDAuthEngine,
    MemGuardDIDAuthorizer,
    quick_auth_engine,
    DIDAuthError,
    PermissionDeniedError,
)
# DIDAuthenticator 也直接从 mesh_identity_sync 导入（绕过 auth_integration 的 exec 缓存问题）
from mesh_identity_sync.auth.did_auth import DIDAuthenticator


@pytest.fixture
def test_storage():
    """测试用临时存储目录"""
    path = tempfile.mkdtemp(prefix="memguard_did_test_")
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def did_setup(test_storage):
    """
    生成主 DID 并注册两个实例。
    返回 (primary_did, password, storage_path)
    """
    auth = DIDAuthenticator(storage_path=test_storage)
    multi = auth._multi_instance_manager

    result = multi.generate_primary_did(password="test_password_123", force=True)
    primary_did = result["did"]

    multi.register_instance(primary_did, "nyx-windows", "QClaw (Windows)")
    multi.register_instance(primary_did, "nyx-mac", "QClaw (macOS)")

    return {
        "primary_did": primary_did,
        "password": "test_password_123",
        "storage_path": test_storage,
    }


@pytest.fixture
def auth_engine(did_setup):
    """已设置的 DIDAuthEngine（nyx-windows 身份）"""
    return DIDAuthEngine(
        primary_did=did_setup["primary_did"],
        instance_id="nyx-windows",
        storage_path=did_setup["storage_path"],
        key_password=did_setup["password"],
    )


@pytest.fixture
def authorizer(auth_engine):
    """MemGuardDIDAuthorizer 封装"""
    return MemGuardDIDAuthorizer(auth_engine)


class TestDIDAuthEngine:
    """DIDAuthEngine 核心功能测试"""

    def test_create_token_memory_write(self, auth_engine):
        """注册实例可以创建 memory_write 令牌"""
        token = auth_engine.create_token(action="memory_write", expires_in=3600)
        assert token is not None
        assert len(token.split(".")) == 3

    def test_create_token_memory_read(self, auth_engine):
        """任意实例（包括未注册）可创建 memory_read 令牌"""
        token = auth_engine.create_token(action="memory_read", expires_in=3600)
        assert token is not None
        assert len(token.split(".")) == 3

    def test_verify_write_valid_token(self, auth_engine):
        """有效令牌验证通过"""
        token = auth_engine.create_token(action="memory_write")
        result = auth_engine.verify_write(token, action="memory_write")

        assert result["valid"] is True
        assert result["instance_id"] == "nyx-windows"
        assert "did" in result

    def test_verify_write_invalid_token(self, auth_engine):
        """无效令牌抛出 PermissionDeniedError"""
        with pytest.raises(PermissionDeniedError):
            auth_engine.verify_write("invalid.token.here", action="memory_write")

    def test_unregistered_instance_cannot_write(self, did_setup):
        """未注册实例无法创建 memory_write 令牌（抛出 ValueError）"""
        unregistered_engine = DIDAuthEngine(
            primary_did=did_setup["primary_did"],
            instance_id="unknown-instance",
            storage_path=did_setup["storage_path"],
            key_password=did_setup["password"],
        )
        with pytest.raises(ValueError):  # did_auth.py 抛出 ValueError
            unregistered_engine.create_token(action="memory_write")

    def test_unregistered_can_read(self, did_setup):
        """未注册实例可以创建 memory_read 令牌"""
        unregistered_engine = DIDAuthEngine(
            primary_did=did_setup["primary_did"],
            instance_id="random-person",
            storage_path=did_setup["storage_path"],
            key_password=did_setup["password"],
        )
        token = unregistered_engine.create_token(action="memory_read")
        result = unregistered_engine.verify_write(token, action="memory_read")
        assert result["valid"] is True

    def test_instance_id_in_token(self, auth_engine):
        """令牌中包含正确的 instance_id"""
        token = auth_engine.create_token(action="memory_write")
        result = auth_engine.verify_write(token, action="memory_write")
        assert result["instance_id"] == "nyx-windows"


class TestMemGuardDIDAuthorizer:
    """MemGuardDIDAuthorizer 集成测试（带 mock MemGuardEngine）"""

    def test_write_memory_requires_valid_token(self, authorizer):
        """write_memory 需要有效令牌"""
        token = authorizer.engine.create_token(action="memory_write")

        # Mock vault
        class MockVault:
            def __init__(self):
                self.audit = []

            def update_memory(self, memory_id, content, operator):
                self.audit.append({"action": "update", "memory_id": memory_id})
                return {"memory_id": memory_id, "sha256": "abc123"}

        vault = MockVault()
        result = authorizer.write_memory(
            vault=vault,
            memory_id="mem_001",
            content="测试内容",
            auth_token=token,
        )

        assert "did_auth" in result
        assert result["did_auth"]["instance_id"] == "nyx-windows"
        assert result["did_auth"]["auth_method"] == "did_signature"
        assert result["did_auth"]["did"] == authorizer.engine.primary_did
        assert len(vault.audit) == 1

    def test_write_memory_rejects_invalid_token(self, authorizer):
        """无效令牌拒绝写操作"""
        class MockVault:
            def update_memory(self, memory_id, content, operator):
                return {}

        vault = MockVault()
        with pytest.raises(PermissionDeniedError):
            authorizer.write_memory(
                vault=vault,
                memory_id="mem_001",
                content="未授权写入",
                auth_token="bad_token",
            )

    def test_read_memory_no_token_required(self, authorizer):
        """读操作不强制要求令牌"""
        class MockVault:
            def read_memory(self, memory_id, operator):
                return "记忆内容"

        vault = MockVault()
        content = authorizer.read_memory(vault=vault, memory_id="mem_001")
        assert content == "记忆内容"

    def test_read_memory_records_did_when_provided(self, authorizer):
        """读操作有令牌时记录 DID"""
        token = authorizer.engine.create_token(action="memory_read")

        class MockVault:
            def __init__(self):
                self.last_operator = None

            def read_memory(self, memory_id, operator):
                self.last_operator = operator
                return "记忆内容"

        vault = MockVault()
        content = authorizer.read_memory(
            vault=vault,
            memory_id="mem_001",
            auth_token=token,
        )
        assert content == "记忆内容"
        assert "nyx-windows" in vault.last_operator


class TestQuickAuthEngine:
    """快捷工厂函数测试"""

    def test_quick_auth_engine_creates_valid_engine(self, did_setup):
        """quick_auth_engine 创建有效的引擎（需传入完整参数）"""
        engine = quick_auth_engine(
            primary_did=did_setup["primary_did"],
            instance_id="nyx-windows",
            key_password=did_setup["password"],
            storage_path=did_setup["storage_path"],
        )
        assert isinstance(engine, DIDAuthEngine)
        assert engine.primary_did == did_setup["primary_did"]
        assert engine.instance_id == "nyx-windows"

        token = engine.create_token(action="memory_read")
        assert token is not None
