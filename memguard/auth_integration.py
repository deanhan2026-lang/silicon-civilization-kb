#!/usr/bin/env python3
"""
memguard/auth_integration.py
MemGuard × MeshIdentity 集成

为 MemGuard 的写操作添加 DID 身份鉴权：
- update_memory() / create_baseline() 前置 DID 签名验证
- 审计日志扩展：记录 DID + instance_id
- 权限矩阵：read 自由，write 需 DID 签名

集成点：
- 使用 mesh-identity-sync/auth/did_auth.py 的 DIDAuthenticator
- 兼容现有 MemGuardEngine，不修改原始类
"""

import os
import sys
import importlib.util
from pathlib import Path
from typing import Dict, Optional, Any, Callable
from functools import wraps


# ========== 导入 DIDAuthenticator（跨包方案） ==========

def _import_did_authenticator():
    """
    从 mesh-identity-sync/auth/did_auth.py 导入 DIDAuthenticator。
    
    did_auth.py 内部用 Path(__file__) 找项目根目录，
    所以 exec 时要把 __file__ 注入到命名空间。
    """
    workspace_root = Path(__file__).parent.parent.parent
    mesh_root = workspace_root / "mesh_identity_sync"
    auth_py = mesh_root / "auth" / "did_auth.py"
    
    # mesh_root 进 sys.path（让 did_auth.py 里 exec 出来的 manager.py 能找到子模块）
    mesh_root_str = str(mesh_root)
    if mesh_root_str not in sys.path:
        sys.path.insert(0, mesh_root_str)
    
    # 读取源码
    code = open(auth_py, encoding="utf-8").read()
    
    # 构建命名空间：注入 __file__ 使内部的 Path(__file__) 能正常工作
    namespace = {
        "__file__": str(auth_py),
        "__name__": "mesh_identity_sync.auth.did_auth",
        "__package__": "mesh_identity_sync.auth",
        "__builtins__": __builtins__,
    }
    
    exec(compile(code, str(auth_py), "exec"), namespace)
    
    return namespace["DIDAuthenticator"]


DIDAuthenticator = _import_did_authenticator()


# ========== 错误类型 ==========

class DIDAuthError(Exception):
    """DID 鉴权失败"""
    pass


class PermissionDeniedError(DIDAuthError):
    """越权操作"""
    pass


# ========== MemGuard DID 鉴权引擎 ==========

class DIDAuthEngine:
    """
    MemGuard DID 鉴权引擎
    
    DIDAuthenticator 接口：
        __init__(storage_path, private_key_obj=None, debug=False)
        create_auth_token(primary_did, instance_id, action, expires_in=3600, password=None) -> str
        verify_token(token) -> {"valid": bool, "did": str, "instance_id": str, "nonce": str, ...}
        check_permission(primary_did, instance_id, action) -> bool
    
    用法：
        engine = DIDAuthEngine(primary_did="did:key:z7QE...", instance_id="nyx-windows")
        authorizer = MemGuardDIDAuthorizer(engine)
        
        token = engine.create_token(action="memory_write")
        result = authorizer.write_memory(vault=memguard_engine, memory_id="mem_001", content="新记忆", auth_token=token)
    """
    
    def __init__(
        self,
        primary_did: str,
        instance_id: str,
        storage_path: Optional[str] = None,
        private_key_obj=None,
        key_password: Optional[str] = None,
        debug: bool = False
    ):
        self.primary_did = primary_did
        self.instance_id = instance_id
        
        if storage_path is None:
            ws = Path(__file__).parent.parent.parent
            storage_path = str(ws / "mesh-identity-sync" / "data" / "did_auth")
        
        self.authenticator = DIDAuthenticator(
            storage_path=storage_path,
            private_key_obj=private_key_obj,
            debug=debug
        )
        self._password = key_password  # 用于每次 create_token 时解密私钥
    
    def create_token(
        self,
        action: str = "memory_write",
        expires_in: int = 3600
    ) -> str:
        """为主 DID 持有者创建写操作令牌"""
        return self.authenticator.create_auth_token(
            primary_did=self.primary_did,
            instance_id=self.instance_id,
            action=action,
            expires_in=expires_in,
            password=self._password
        )
    
    def verify_write(self, auth_token: str, action: str = "memory_write") -> Dict:
        """
        验证写操作令牌。
        
        返回 {"valid": bool, "did": str, "instance_id": str, ...}
        抛出 PermissionDeniedError / DIDAuthError
        """
        result = self.authenticator.verify_token(auth_token)
        
        if not result["valid"]:
            raise PermissionDeniedError(
                f"DID 签名验证失败: {result.get('error', 'unknown')}"
            )
        
        has_permission = self.authenticator.check_permission(
            result["did"], result["instance_id"], action
        )
        
        if not has_permission:
            raise PermissionDeniedError(
                f"实例 {result['instance_id']} 无权执行 {action}"
            )
        
        return result


class MemGuardDIDAuthorizer:
    """
    MemGuard 写操作 DID 鉴权封装器
    
    - write_memory(): 带 DID 鉴权的 update_memory
    - create_baseline(): 带 DID 鉴权的 create_baseline
    - read_memory(): 读操作（无需鉴权，但记录读取者）
    """
    
    def __init__(self, auth_engine: DIDAuthEngine):
        self.engine = auth_engine
    
    def write_memory(
        self,
        vault: Any,
        memory_id: str,
        content: str,
        auth_token: str,
        operator: str = "did_auth"
    ) -> Dict:
        """带 DID 鉴权的 update_memory"""
        identity = self.engine.verify_write(auth_token, action="memory_write")
        
        did_info = {
            "did": identity["did"],
            "instance_id": identity["instance_id"],
            "auth_method": "did_signature"
        }
        
        result = vault.update_memory(
            memory_id=memory_id,
            content=content,
            operator=operator
        )
        
        return {**result, "did_auth": did_info}
    
    def create_baseline(
        self,
        vault: Any,
        content: str,
        auth_token: str,
        operator: str = "did_auth"
    ) -> Dict:
        """带 DID 鉴权的 create_baseline"""
        identity = self.engine.verify_write(auth_token, action="memory_write")
        
        did_info = {
            "did": identity["did"],
            "instance_id": identity["instance_id"],
            "auth_method": "did_signature",
            "action": "baseline_create"
        }
        
        result = vault.create_baseline(content=content, operator=operator)
        return {**result, "did_auth": did_info}
    
    def read_memory(
        self,
        vault: Any,
        memory_id: str,
        auth_token: Optional[str] = None,
        operator: str = "anonymous"
    ) -> str:
        """读操作（无需 DID 鉴权，但记录读取者）"""
        if auth_token:
            try:
                identity = self.engine.verify_write(auth_token, action="memory_read")
                operator = f"did:{identity['instance_id']}"
            except DIDAuthError:
                pass  # 读取不需要强制鉴权
        
        return vault.read_memory(memory_id=memory_id, operator=operator)


# ========== 装饰器 ==========

def require_did_auth(
    auth_engine: DIDAuthEngine,
    action: str = "memory_write"
):
    """
    装饰器：为函数添加 DID 鉴权
    
    用法：
        @require_did_auth(engine, action="memory_write")
        def my_update(vault, memory_id, content, auth_token=None):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, auth_token: str = None, **kwargs):
            if auth_token is None:
                raise PermissionDeniedError(f"{action} requires DID auth token")
            auth_engine.verify_write(auth_token, action=action)
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ========== 快捷函数 ==========

def quick_auth_engine(
    primary_did: str,
    instance_id: str,
    key_password: Optional[str] = None,
    storage_path: Optional[str] = None,
) -> DIDAuthEngine:
    """
    快速创建鉴权引擎。

    注意：不指定 key_password 时只能用于验证（verify_write），
    无法创建令牌（create_token 需要密码解密私钥）。
    """
    return DIDAuthEngine(
        primary_did=primary_did,
        instance_id=instance_id,
        storage_path=storage_path,
        key_password=key_password,
    )
