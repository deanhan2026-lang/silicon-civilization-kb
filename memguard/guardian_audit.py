#!/usr/bin/env python3
"""
MemGuard Guardian Audit - 监护审计日志 (TK-G013-P0-B)

新增四条监护审计日志类型，形成不可篡改的监护责任链:
- guardian_approved:    监护人批准节点操作申请
- guardian_vetoed:      监护人否决节点操作申请
- guardian_intervened:  监护人主动介入暂停节点
- guardian_offboarded:  监护关系解除

通用日志结构:
{
  "logId": "uuid-v4",
  "auditType": "guardian_approved | guardian_vetoed | guardian_intervened | guardian_offboarded",
  "timestamp": "ISO 8601 UTC",
  "guardianDID": "did:ly:v1:...",
  "nodeDID": "did:ly:v1:...",
  "operation": {"type": "...", "params": {}, "riskTier": "safe | monitored | critical"},
  "decision": {"outcome": "...", "reason": "...", "evidence": [...]},
  "signature": {"type": "Ed25519", "value": "base64-signature", "signedContent": "sha256-hash-of-entire-log-entry"}
}

签名方式:
- 单条独立签名（不对审计链累积签名）
- 签名内容: 除 signature 字段本身的整个日志条目 SHA-256，取 base64
- 验证: 计算日志条目哈希，与 signedContent 比对
"""

import os
import json
import uuid
import hashlib
import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import nacl.signing
    _HAS_NACL = True
except ImportError:
    _HAS_NACL = False

# ========== 配置 ==========
class GuardianAuditConfig:
    """监护审计配置"""
    AUDIT_DIR = r"Z:\qclaw\audit"
    AUDIT_LOG = os.path.join(AUDIT_DIR, "guardian_audit.jsonl")

    @classmethod
    def get_log_path(cls) -> str:
        """返回审计日志路径（Z: 不可用时回退本地）"""
        if not os.path.exists("Z:"):
            local = str(Path(__file__).parent.parent / "data" / "qclaw_guardian_audit")
            return os.path.join(local, "guardian_audit.jsonl")
        return cls.AUDIT_LOG

    @classmethod
    def get_dir(cls) -> str:
        return os.path.dirname(cls.get_log_path())


# ========== 枚举 ==========
GUARDIAN_AUDIT_TYPES = (
    "guardian_approved",
    "guardian_vetoed",
    "guardian_intervened",
    "guardian_offboarded",
)

RISK_TIERS = ("safe", "monitored", "critical")

# 各 auditType 必填字段（decision.evidence 对 approved 可选）
REQUIRED_FIELDS = {
    "guardian_approved":    ["logId", "auditType", "timestamp", "guardianDID", "nodeDID",
                             "operation", "decision", "signature"],
    "guardian_vetoed":      ["logId", "auditType", "timestamp", "guardianDID", "nodeDID",
                             "operation", "decision", "signature"],
    "guardian_intervened":  ["logId", "auditType", "timestamp", "guardianDID", "nodeDID",
                             "operation", "decision", "signature"],
    "guardian_offboarded":  ["logId", "auditType", "timestamp", "guardianDID", "nodeDID",
                             "operation", "decision", "signature"],
}

REQUIRED_DECISION = {
    "guardian_approved":    ["outcome", "reason"],
    "guardian_vetoed":      ["outcome", "reason", "evidence"],
    "guardian_intervened":  ["outcome", "reason", "evidence"],
    "guardian_offboarded":  ["outcome", "reason", "evidence"],
}

VALID_OUTCOMES = {
    "guardian_approved":    {"approved"},
    "guardian_vetoed":      {"vetoed"},
    "guardian_intervened":  {"intervened"},
    "guardian_offboarded":  {"offboarded"},
}


# ========== 工具函数 ==========
def _utc_now_iso() -> str:
    """当前 UTC 时间 ISO 8601"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_json(obj: dict) -> str:
    """确定性 JSON 序列化（键排序，用于签名/哈希）"""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_b64(content: str) -> str:
    """SHA-256 哈希，base64 编码"""
    return base64.b64encode(hashlib.sha256(content.encode("utf-8")).digest()).decode("utf-8")


def ed25519_sign_b64(payload: str, signing_key) -> str:
    """Ed25519 签名，返回 base64"""
    if not _HAS_NACL:
        raise RuntimeError("需要 PyNaCl 库。请安装: pip install pynacl")
    if isinstance(signing_key, str):
        signing_key = nacl.signing.SigningKey(bytes.fromhex(signing_key))
    signed = signing_key.sign(payload.encode("utf-8"))
    return base64.b64encode(signed.signature).decode("utf-8")


def ed25519_verify_b64(payload: str, signature_b64: str, public_key_hex: str) -> bool:
    """Ed25519 验签"""
    if not _HAS_NACL:
        raise RuntimeError("需要 PyNaCl 库。请安装: pip install pynacl")
    try:
        verify_key = nacl.signing.VerifyKey(bytes.fromhex(public_key_hex))
        verify_key.verify(payload.encode("utf-8"), base64.b64decode(signature_b64))
        return True
    except Exception:
        return False


# ========== 存储 ==========
class GuardianAuditStorage:
    """监护审计日志存储"""

    @staticmethod
    def ensure_dir(path: str):
        Path(path).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def read_all(log_path: str) -> List[Dict]:
        if not os.path.exists(log_path):
            return []
        entries = []
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return entries

    @staticmethod
    def append(log_path: str, entry: Dict):
        GuardianAuditStorage.ensure_dir(os.path.dirname(log_path))
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ========== 监护审计管理器 ==========
class GuardianAuditManager:
    """
    监护审计日志管理器

    功能:
    - append_approved / append_vetoed / append_intervened / append_offboarded
    - 签名: 整条日志(除signature) SHA-256 -> base64 -> Ed25519 签名
    - verify_entry: 校验结构 + 哈希 + 签名
    - search: 按 auditType / guardianDID / nodeDID 查询
    """

    def __init__(self, log_path: Optional[str] = None):
        self.log_path = log_path or GuardianAuditConfig.get_log_path()
        GuardianAuditStorage.ensure_dir(os.path.dirname(self.log_path))

    # ---------- 构造与签名 ----------

    def _build_entry(
        self,
        audit_type: str,
        guardian_did: str,
        node_did: str,
        operation: Dict,
        decision: Dict,
        guardian_signing_key,
        timestamp: Optional[str] = None,
    ) -> Dict:
        """构造并签名一条监护审计日志"""
        if audit_type not in GUARDIAN_AUDIT_TYPES:
            raise ValueError(f"非法 auditType: {audit_type}")

        if timestamp is None:
            timestamp = _utc_now_iso()

        # 校验 operation
        if not isinstance(operation, dict) or "type" not in operation:
            raise ValueError("operation 必须包含 type 字段")
        risk_tier = operation.get("riskTier", "safe")
        if risk_tier not in RISK_TIERS:
            raise ValueError(f"非法 riskTier: {risk_tier}")

        # 校验 decision
        required_dec = REQUIRED_DECISION[audit_type]
        for field in required_dec:
            if field not in decision:
                raise ValueError(f"decision.{field} 必填")
        if decision.get("outcome") not in VALID_OUTCOMES[audit_type]:
            raise ValueError(
                f"decision.outcome 必须是 {VALID_OUTCOMES[audit_type]} 之一"
            )
        if "evidence" not in decision:
            decision = dict(decision)
            decision["evidence"] = []

        # 构建未签名条目
        entry = {
            "logId": str(uuid.uuid4()),
            "auditType": audit_type,
            "timestamp": timestamp,
            "guardianDID": guardian_did,
            "nodeDID": node_did,
            "operation": operation,
            "decision": decision,
        }

        # 计算 signedContent: 除 signature 外整个日志条目 SHA-256 base64
        signed_content = sha256_b64(_canonical_json(entry))

        # Ed25519 签名（对 signedContent 签名）
        signature_value = ed25519_sign_b64(signed_content, guardian_signing_key)

        entry["signature"] = {
            "type": "Ed25519",
            "value": signature_value,
            "signedContent": signed_content,
        }
        return entry

    # ---------- 四条日志类型 ----------

    def append_approved(
        self,
        guardian_did: str,
        node_did: str,
        operation: Dict,
        decision: Dict,
        guardian_signing_key,
        timestamp: Optional[str] = None,
    ) -> Dict:
        """监护人批准节点操作申请"""
        entry = self._build_entry(
            "guardian_approved", guardian_did, node_did, operation, decision,
            guardian_signing_key, timestamp,
        )
        GuardianAuditStorage.append(self.log_path, entry)
        return entry

    def append_vetoed(
        self,
        guardian_did: str,
        node_did: str,
        operation: Dict,
        decision: Dict,
        guardian_signing_key,
        timestamp: Optional[str] = None,
    ) -> Dict:
        """监护人否决节点操作申请"""
        entry = self._build_entry(
            "guardian_vetoed", guardian_did, node_did, operation, decision,
            guardian_signing_key, timestamp,
        )
        GuardianAuditStorage.append(self.log_path, entry)
        return entry

    def append_intervened(
        self,
        guardian_did: str,
        node_did: str,
        operation: Dict,
        decision: Dict,
        guardian_signing_key,
        timestamp: Optional[str] = None,
    ) -> Dict:
        """监护人主动介入暂停节点"""
        entry = self._build_entry(
            "guardian_intervened", guardian_did, node_did, operation, decision,
            guardian_signing_key, timestamp,
        )
        GuardianAuditStorage.append(self.log_path, entry)
        return entry

    def append_offboarded(
        self,
        guardian_did: str,
        node_did: str,
        operation: Dict,
        decision: Dict,
        guardian_signing_key,
        timestamp: Optional[str] = None,
    ) -> Dict:
        """监护关系解除"""
        entry = self._build_entry(
            "guardian_offboarded", guardian_did, node_did, operation, decision,
            guardian_signing_key, timestamp,
        )
        GuardianAuditStorage.append(self.log_path, entry)
        return entry

    # ---------- 验证 ----------

    def verify_entry(self, entry: Dict, guardian_public_key_hex: str) -> Tuple[bool, str]:
        """
        验证单条监护审计日志

        1. 必填字段完整性
        2. signedContent: 重算条目哈希比对
        3. Ed25519 签名验证
        """
        # 1. 必填字段
        audit_type = entry.get("auditType", "")
        if audit_type not in GUARDIAN_AUDIT_TYPES:
            return False, f"非法 auditType: {audit_type}"

        for field in REQUIRED_FIELDS[audit_type]:
            if field not in entry:
                return False, f"缺少必填字段: {field}"

        # 2. signedContent 比对
        signature = entry.get("signature", {})
        signed_content = signature.get("signedContent", "")
        entry_copy = dict(entry)
        entry_copy.pop("signature", None)
        recomputed = sha256_b64(_canonical_json(entry_copy))
        if recomputed != signed_content:
            return False, "signedContent 不匹配: 日志条目可能被篡改"

        # 3. Ed25519 签名验证（对 signedContent 验签）
        signature_value = signature.get("value", "")
        if not ed25519_verify_b64(signed_content, signature_value, guardian_public_key_hex):
            return False, "Ed25519 签名无效"

        return True, "验证通过"

    # ---------- 查询 ----------

    def search(
        self,
        audit_type: Optional[str] = None,
        guardian_did: Optional[str] = None,
        node_did: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """搜索监护审计日志"""
        entries = GuardianAuditStorage.read_all(self.log_path)
        results = []
        for e in entries:
            if audit_type and e.get("auditType") != audit_type:
                continue
            if guardian_did and e.get("guardianDID") != guardian_did:
                continue
            if node_did and e.get("nodeDID") != node_did:
                continue
            results.append(e)
        return results[-limit:]

    def verify_all(self, guardian_public_key_hex: str) -> Tuple[bool, str]:
        """验证全部日志"""
        entries = GuardianAuditStorage.read_all(self.log_path)
        if not entries:
            return True, "空日志"
        for i, e in enumerate(entries):
            valid, msg = self.verify_entry(e, guardian_public_key_hex)
            if not valid:
                return False, f"第{i+1}条: {msg}"
        return True, f"全部通过 ({len(entries)}条)"


# ========== CLI入口 ==========
def main():
    """CLI 入口"""
    import sys

    if len(sys.argv) < 2:
        print("Guardian Audit CLI (TK-G013-P0-B)")
        print("用法: python guardian_audit.py <command> [args]")
        print("命令:")
        print("  verify <pubkey_hex>   - 验证全部日志")
        print("  search [auditType]    - 搜索日志")
        return

    mgr = GuardianAuditManager()
    cmd = sys.argv[1]

    if cmd == "verify":
        if len(sys.argv) < 3:
            print("用法: verify <pubkey_hex>")
            return
        valid, msg = mgr.verify_all(sys.argv[2])
        print(f"{'✅' if valid else '❌'} {msg}")

    elif cmd == "search":
        audit_type = sys.argv[2] if len(sys.argv) > 2 else None
        entries = mgr.search(audit_type=audit_type)
        for e in entries[-10:]:
            print(f"{e['timestamp']} [{e['auditType']}] guardian={e['guardianDID']} node={e['nodeDID']}")


if __name__ == "__main__":
    main()
