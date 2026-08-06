# -*- coding: utf-8 -*-
"""
P0-2: JIT Privilege Manager — 即时授权管理器

即时授权：默认最小权限，需要时临时提升，操作完成后立即回收。
对标 IBM "lock it" 的临时授权原则。

对标标准：
- IBM "Lock it" 原则（最小权限+隔离+临时授权）
- 五眼联盟风险 #2: 过度授权
"""

import uuid
import time
import threading
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from enum import Enum

from argus.permission_resolver import ToolPermission


class ElevationStatus(Enum):
    """权限提升状态"""
    PENDING = "pending"          # 等待审批
    APPROVED = "approved"        # 已批准
    ACTIVE = "active"            # 生效中
    EXPIRED = "expired"          # 已过期
    REVOKED = "revoked"          # 已撤销
    REJECTED = "rejected"        # 已拒绝


@dataclass
class ElevationToken:
    """权限提升令牌"""
    token_id: str
    agent_did: str
    permission: ToolPermission
    reason: str
    created_at: float
    expires_at: float
    status: ElevationStatus = ElevationStatus.PENDING
    approved_by: Optional[str] = None
    revoked_at: Optional[float] = None
    revoked_reason: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "token_id": self.token_id,
            "agent_did": self.agent_did,
            "permission": self.permission.to_dict(),
            "reason": self.reason,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "status": self.status.value,
            "approved_by": self.approved_by,
            "revoked_at": self.revoked_at,
            "revoked_reason": self.revoked_reason,
        }


class JITPrivilegeManager:
    """
    即时授权管理器。

    工作流程：
    1. Agent 请求权限提升
    2. 记录原因到审计日志
    3. 如果 require_approval=True → 进入人审队列
    4. 签发有时效的 ElevationToken
    5. TTL 到期自动撤销
    """

    def __init__(self, default_ttl: int = 300):
        """
        Args:
            default_ttl: 默认权限有效期（秒）
        """
        self.default_ttl = default_ttl
        self.tokens: Dict[str, ElevationToken] = {}
        self.lock = threading.RLock()

    def request_elevation(
        self,
        agent_did: str,
        required_permission: ToolPermission,
        reason: str,
        ttl_seconds: Optional[int] = None,
    ) -> ElevationToken:
        """
        请求权限提升。

        Args:
            agent_did: Agent DID
            required_permission: 所需权限
            reason: 提升原因（用于审计）
            ttl_seconds: 自定义有效期

        Returns:
            ElevationToken: 提升令牌
        """
        with self.lock:
            ttl = ttl_seconds or self.default_ttl
            now = time.time()

            token = ElevationToken(
                token_id=f"elev_{uuid.uuid4().hex[:12]}",
                agent_did=agent_did,
                permission=required_permission,
                reason=reason,
                created_at=now,
                expires_at=now + ttl,
                status=ElevationStatus.PENDING if required_permission.require_approval else ElevationStatus.ACTIVE,
            )

            self.tokens[token.token_id] = token
            return token

    def approve(self, token_id: str, approved_by: str = "system") -> Optional[ElevationToken]:
        """
        批准权限提升请求。

        Args:
            token_id: 令牌 ID
            approved_by: 审批人

        Returns:
            ElevationToken: 更新后的令牌
        """
        with self.lock:
            token = self.tokens.get(token_id)
            if not token:
                return None

            # 只处理 PENDING 状态的令牌
            if token.status != ElevationStatus.PENDING:
                return token

            token.status = ElevationStatus.ACTIVE
            token.approved_by = approved_by
            return token

    def reject(self, token_id: str, reason: str = "rejected by approver") -> Optional[ElevationToken]:
        """
        拒绝权限提升请求。

        Args:
            token_id: 令牌 ID
            reason: 拒绝原因

        Returns:
            ElevationToken: 更新后的令牌
        """
        with self.lock:
            token = self.tokens.get(token_id)
            if not token:
                return None

            token.status = ElevationStatus.REJECTED
            token.revoked_reason = reason
            token.revoked_at = time.time()
            return token

    def revoke(self, token_id: str, reason: str = "manually revoked") -> Optional[ElevationToken]:
        """
        立即撤销权限提升（用于检测到异常行为时）。

        Args:
            token_id: 令牌 ID
            reason: 撤销原因

        Returns:
            ElevationToken: 更新后的令牌
        """
        with self.lock:
            token = self.tokens.get(token_id)
            if not token:
                return None

            token.status = ElevationStatus.REVOKED
            token.revoked_at = time.time()
            token.revoked_reason = reason
            return token

    def check_valid(self, token_id: str) -> bool:
        """
        检查令牌是否有效（未过期、未撤销）。

        Args:
            token_id: 令牌 ID

        Returns:
            bool: 是否有效
        """
        with self.lock:
            token = self.tokens.get(token_id)
            if not token:
                return False

            # 自动清理过期令牌
            if token.status == ElevationStatus.ACTIVE and time.time() > token.expires_at:
                token.status = ElevationStatus.EXPIRED
                token.revoked_at = time.time()
                token.revoked_reason = "TTL expired"

            return token.status == ElevationStatus.ACTIVE

    def cleanup_expired(self) -> int:
        """
        清理过期令牌。

        Returns:
            int: 清理数量
        """
        with self.lock:
            now = time.time()
            expired_ids = []

            for token_id, token in self.tokens.items():
                if token.status == ElevationStatus.ACTIVE and now > token.expires_at:
                    token.status = ElevationStatus.EXPIRED
                    token.revoked_at = now
                    token.revoked_reason = "TTL expired"
                    expired_ids.append(token_id)

            return len(expired_ids)

    def get_token(self, token_id: str) -> Optional[ElevationToken]:
        """获取令牌"""
        return self.tokens.get(token_id)

    def list_tokens(
        self,
        agent_did: Optional[str] = None,
        status: Optional[ElevationStatus] = None,
    ) -> List[ElevationToken]:
        """列出令牌"""
        with self.lock:
            tokens = list(self.tokens.values())

            if agent_did:
                tokens = [t for t in tokens if t.agent_did == agent_did]

            if status:
                tokens = [t for t in tokens if t.status == status]

            return tokens

    def revoke_all_for_agent(self, agent_did: str, reason: str = "agent isolated") -> int:
        """
        撤销指定 Agent 的所有令牌（用于隔离沦陷 Agent）。

        Args:
            agent_did: Agent DID
            reason: 撤销原因

        Returns:
            int: 撤销数量
        """
        with self.lock:
            count = 0
            for token in self.tokens.values():
                if token.agent_did == agent_did and token.status == ElevationStatus.ACTIVE:
                    token.status = ElevationStatus.REVOKED
                    token.revoked_at = time.time()
                    token.revoked_reason = reason
                    count += 1
            return count