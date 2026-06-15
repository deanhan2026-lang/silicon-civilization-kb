#!/usr/bin/env python3
"""
MemGuard-GM Integrity - 文件完整性签名与篡改检测模块
方案 A+B：信任域分层 + 签名追溯
"""
import os
import json
import hashlib
import hmac
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple, Dict
from dataclasses import dataclass, asdict
from enum import Enum

# ========== 配置 ==========
# Repo根目录（自动定位，跨平台）
REPO_ROOT = Path(__file__).parent.parent.resolve()

class IntegrityConfig:
    """完整性配置（支持环境变量覆盖）"""
    # 签名存储路径（默认 repo/data/signatures/，可用 MEMGUARD_SIG_DIR 覆盖）
    SIGNATURES_DIR = os.environ.get(
        "MEMGUARD_SIG_DIR",
        str(REPO_ROOT / "data" / "signatures")
    )
    SIGNATURES_FILE = os.path.join(SIGNATURES_DIR, "signatures.json")
    TAMPER_LOG = os.path.join(SIGNATURES_DIR, "tamper_log.jsonl")
    
    # 密钥文件（HMAC签名用，可用 MEMGUARD_SIGNING_KEY 覆盖）
    SIGNING_KEY_FILE = os.environ.get(
        "MEMGUARD_SIGNING_KEY",
        str(REPO_ROOT / "data" / "keys" / "signing_key.bin")
    )
    
    # 核心文件列表
    CORE_FILES = [
        "SOUL.md",
        "IDENTITY.md",
        "USER.md",
        "AGENTS.md",
        "MEMORY.md",
        "TOOLS.md"
    ]
    
    # Workspace路径（可用 MEMGUARD_WORKSPACE 覆盖，默认从签名目录推导）
    # FIX: workspace在repo的父目录，不在repo内部
    WORKSPACE_DIR = os.environ.get(
        "MEMGUARD_WORKSPACE",
        str(REPO_ROOT.parent)
    )

# ========== 数据结构 ==========
@dataclass
class FileSignature:
    """文件签名记录"""
    filename: str
    sha256: str
    blake3: str
    hmac_signature: str
    timestamp: str
    signer_node: str
    signer_session: Optional[str] = None
    size: int = 0
    line_count: int = 0

@dataclass
class TamperRecord:
    """篡改检测记录"""
    timestamp: str
    filename: str
    expected_sha256: str
    actual_sha256: str
    expected_hmac: str
    actual_hmac: str
    detection_type: str  # "sha256_mismatch" / "hmac_invalid" / "file_missing" / "file_added"
    severity: str        # "critical" / "warning" / "info"
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[str] = None

# ========== 哈希工具 ==========
class HashUtils:
    """哈希工具（支持SHA256 + BLAKE3）"""
    
    @staticmethod
    def sha256_file(path: str) -> str:
        """计算文件SHA256"""
        if not os.path.exists(path):
            return ""
        
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()
    
    @staticmethod
    def blake3_file(path: str) -> str:
        """计算文件BLAKE3"""
        if not os.path.exists(path):
            return ""
        
        try:
            import blake3
            h = blake3.blake3()
            with open(path, 'rb') as f:
                while chunk := f.read(8192):
                    h.update(chunk)
            return h.hexdigest()
        except ImportError:
            # 如果没有blake3库，fallback到SHA512
            h = hashlib.sha512()
            with open(path, 'rb') as f:
                while chunk := f.read(8192):
                    h.update(chunk)
            return h.hexdigest()
    
    @staticmethod
    def file_stats(path: str) -> Tuple[int, int]:
        """获取文件大小和行数"""
        if not os.path.exists(path):
            return 0, 0
        
        size = os.path.getsize(path)
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            line_count = sum(1 for _ in f)
        
        return size, line_count

# ========== 签名管理器 ==========
class SignatureManager:
    """文件签名管理器"""
    
    def __init__(self, workspace_dir: str = None):
        self.workspace_dir = workspace_dir or IntegrityConfig.WORKSPACE_DIR
        self.signatures_dir = IntegrityConfig.SIGNATURES_DIR
        self.signatures_file = IntegrityConfig.SIGNATURES_FILE
        self.signing_key_file = IntegrityConfig.SIGNING_KEY_FILE
        
        # 确保目录存在
        Path(self.signatures_dir).mkdir(parents=True, exist_ok=True)
        
        # 加载或生成签名密钥
        self.signing_key = self._load_or_create_key()
        
        # 加载已有签名
        self.signatures: Dict[str, FileSignature] = self._load_signatures()
    
    def _load_or_create_key(self) -> bytes:
        """加载或创建签名密钥"""
        if os.path.exists(self.signing_key_file):
            with open(self.signing_key_file, 'rb') as f:
                return f.read()
        
        # 生成新密钥（32字节）
        key = os.urandom(32)
        with open(self.signing_key_file, 'wb') as f:
            f.write(key)
        
        return key
    
    def _load_signatures(self) -> Dict[str, FileSignature]:
        """加载已有签名"""
        if not os.path.exists(self.signatures_file):
            return {}
        
        with open(self.signatures_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return {k: FileSignature(**v) for k, v in data.items()}
    
    def _save_signatures(self):
        """保存签名"""
        with open(self.signatures_file, 'w', encoding='utf-8') as f:
            json.dump({k: asdict(v) for k, v in self.signatures.items()}, f, indent=2, ensure_ascii=False)
    
    def _compute_hmac(self, sha256: str, blake3: str, filename: str) -> str:
        """计算HMAC签名"""
        data = f"{filename}|{sha256}|{blake3}"
        return hmac.new(self.signing_key, data.encode('utf-8'), hashlib.sha256).hexdigest()
    
    def sign_file(self, filename: str, node_id: str, session_id: str = None) -> FileSignature:
        """签名单个文件"""
        path = os.path.join(self.workspace_dir, filename)
        
        if not os.path.exists(path):
            raise FileNotFoundError(f"文件不存在: {path}")
        
        # 计算哈希
        sha256 = HashUtils.sha256_file(path)
        blake3 = HashUtils.blake3_file(path)
        size, line_count = HashUtils.file_stats(path)
        
        # 计算HMAC
        hmac_sig = self._compute_hmac(sha256, blake3, filename)
        
        # 创建签名记录
        sig = FileSignature(
            filename=filename,
            sha256=sha256,
            blake3=blake3,
            hmac_signature=hmac_sig,
            timestamp=datetime.now().isoformat(),
            signer_node=node_id,
            signer_session=session_id,
            size=size,
            line_count=line_count
        )
        
        # 保存
        self.signatures[filename] = sig
        self._save_signatures()
        
        return sig
    
    def sign_all_core_files(self, node_id: str, session_id: str = None) -> List[FileSignature]:
        """签名所有核心文件"""
        results = []
        for filename in IntegrityConfig.CORE_FILES:
            try:
                sig = self.sign_file(filename, node_id, session_id)
                results.append(sig)
            except FileNotFoundError:
                print(f"⚠️ 文件不存在，跳过: {filename}")
        
        return results
    
    def verify_file(self, filename: str) -> Tuple[bool, str, Optional[TamperRecord]]:
        """
        验证单个文件完整性
        返回: (是否通过, 状态描述, 篡改记录(如果有))
        """
        path = os.path.join(self.workspace_dir, filename)
        
        # 1. 检查文件是否存在
        if not os.path.exists(path):
            if filename in self.signatures:
                # 文件被删除
                record = TamperRecord(
                    timestamp=datetime.now().isoformat(),
                    filename=filename,
                    expected_sha256=self.signatures[filename].sha256,
                    actual_sha256="",
                    expected_hmac=self.signatures[filename].hmac_signature,
                    actual_hmac="",
                    detection_type="file_missing",
                    severity="critical"
                )
                return False, "文件被删除", record
            else:
                # 新文件，未签名
                return True, "未签名的新文件", None
        
        # 2. 检查是否有签名记录
        if filename not in self.signatures:
            # 新文件，未签名
            return True, "未签名", None
        
        # 3. 计算当前哈希
        actual_sha256 = HashUtils.sha256_file(path)
        actual_blake3 = HashUtils.blake3_file(path)
        
        expected_sig = self.signatures[filename]
        
        # 4. 验证SHA256
        if actual_sha256 != expected_sig.sha256:
            actual_hmac = self._compute_hmac(actual_sha256, actual_blake3, filename)
            record = TamperRecord(
                timestamp=datetime.now().isoformat(),
                filename=filename,
                expected_sha256=expected_sig.sha256,
                actual_sha256=actual_sha256,
                expected_hmac=expected_sig.hmac_signature,
                actual_hmac=actual_hmac,
                detection_type="sha256_mismatch",
                severity="critical"
            )
            return False, "SHA256不匹配（内容被修改）", record
        
        # 5. 验证HMAC
        actual_hmac = self._compute_hmac(actual_sha256, actual_blake3, filename)
        if actual_hmac != expected_sig.hmac_signature:
            record = TamperRecord(
                timestamp=datetime.now().isoformat(),
                filename=filename,
                expected_sha256=expected_sig.sha256,
                actual_sha256=actual_sha256,
                expected_hmac=expected_sig.hmac_signature,
                actual_hmac=actual_hmac,
                detection_type="hmac_invalid",
                severity="critical"
            )
            return False, "HMAC签名无效（元数据被篡改）", record
        
        # 6. 全部通过
        return True, f"完整（签名时间: {expected_sig.timestamp[:19]}）", None
    
    def verify_all_core_files(self) -> Tuple[Dict[str, Tuple[bool, str]], List[TamperRecord]]:
        """
        验证所有核心文件
        返回: ({文件名: (是否通过, 状态)}, [篡改记录列表])
        """
        results = {}
        tamper_records = []
        
        # 检查已签名的文件
        for filename in self.signatures.keys():
            valid, status, record = self.verify_file(filename)
            results[filename] = (valid, status)
            if record:
                tamper_records.append(record)
                self._log_tamper(record)
        
        # 检查未签名的新文件
        for filename in IntegrityConfig.CORE_FILES:
            if filename not in self.signatures:
                path = os.path.join(self.workspace_dir, filename)
                if os.path.exists(path):
                    results[filename] = (True, "未签名的新文件")
        
        return results, tamper_records
    
    def _log_tamper(self, record: TamperRecord):
        """记录篡改事件"""
        with open(IntegrityConfig.TAMPER_LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + '\n')
    
    def acknowledge_tamper(self, filename: str, acknowledger: str) -> bool:
        """确认篡改记录（标记为已知）"""
        if not os.path.exists(IntegrityConfig.TAMPER_LOG):
            return False
        
        records = []
        with open(IntegrityConfig.TAMPER_LOG, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        
        # 更新最新的一条记录
        updated = False
        for record in reversed(records):
            if record['filename'] == filename and not record.get('acknowledged'):
                record['acknowledged'] = True
                record['acknowledged_by'] = acknowledger
                record['acknowledged_at'] = datetime.now().isoformat()
                updated = True
                break
        
        if updated:
            with open(IntegrityConfig.TAMPER_LOG, 'w', encoding='utf-8') as f:
                for r in records:
                    f.write(json.dumps(r, ensure_ascii=False) + '\n')
        
        return updated

# ========== 信任域检查 ==========
class TrustDomainChecker:
    """信任域检查器"""
    
    @staticmethod
    def is_in_trust_domain() -> bool:
        """
        检查当前是否在信任域内
        信任域定义：能访问 Z:/qclaw/ 的终端
        """
        try:
            # 检查是否能访问共享目录
            test_path = os.path.join("Z:", "qclaw", "instance.lock")
            if os.path.exists(test_path):
                return True
            
            # 尝试创建测试文件
            test_dir = r"Z:\qclaw\trust_test"
            os.makedirs(test_dir, exist_ok=True)
            test_file = os.path.join(test_dir, "test.tmp")
            with open(test_file, 'w') as f:
                f.write("trust_test")
            os.remove(test_file)
            os.rmdir(test_dir)
            return True
        except:
            return False
    
    @staticmethod
    def get_trust_level() -> str:
        """
        获取信任级别
        返回: "full_trust" / "partial_trust" / "untrusted"
        """
        if TrustDomainChecker.is_in_trust_domain():
            # 检查是否有写权限
            try:
                test_file = r"Z:\qclaw\write_test.tmp"
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                return "full_trust"
            except:
                return "partial_trust"
        return "untrusted"

# ========== API 集成 ==========
def get_integrity_status() -> dict:
    """获取完整性状态（供API调用）"""
    sm = SignatureManager()
    results, tamper_records = sm.verify_all_core_files()
    
    return {
        "workspace": sm.workspace_dir,
        "trust_domain": TrustDomainChecker.get_trust_level(),
        "core_files": {
            "total": len(results),
            "valid": sum(1 for v, _ in results.values() if v),
            "invalid": sum(1 for v, _ in results.values() if not v)
        },
        "signatures": len(sm.signatures),
        "tamper_alerts": len(tamper_records),
        "details": {k: v for k, (v, _) in results.items()},
        "alerts": [
            {
                "filename": r.filename,
                "type": r.detection_type,
                "severity": r.severity,
                "timestamp": r.timestamp
            }
            for r in tamper_records
        ]
    }

# ========== CLI ==========
def main():
    """CLI入口"""
    import sys
    
    if len(sys.argv) < 2:
        print("Integrity CLI")
        print("用法: python integrity.py <command>")
        print("命令:")
        print("  sign [node_id]     - 签名所有核心文件")
        print("  verify             - 验证所有核心文件")
        print("  status             - 获取完整性状态")
        print("  trust              - 检查信任域")
        return
    
    cmd = sys.argv[1]
    sm = SignatureManager()
    
    if cmd == "sign":
        node_id = sys.argv[2] if len(sys.argv) > 2 else "nyx"
        print(f"签名核心文件（节点: {node_id}）...")
        results = sm.sign_all_core_files(node_id)
        for sig in results:
            print(f"  {sig.filename}: {sig.sha256[:16]}...")
        print(f"完成，已签名 {len(results)} 个文件")
    
    elif cmd == "verify":
        print("验证核心文件完整性...")
        results, tamper_records = sm.verify_all_core_files()
        for filename, (valid, status) in results.items():
            mark = "OK" if valid else "FAIL"
            print(f"  [{mark}] {filename}: {status}")
        
        if tamper_records:
            print(f"\n发现 {len(tamper_records)} 个篡改警告")
            for r in tamper_records:
                print(f"  {r.filename}: {r.detection_type}")
    
    elif cmd == "status":
        status = get_integrity_status()
        print(f"工作区: {status['workspace']}")
        print(f"信任域: {status['trust_domain']}")
        print(f"核心文件: {status['core_files']}")
        print(f"签名数: {status['signatures']}")
        print(f"篡改警告: {status['tamper_alerts']}")
    
    elif cmd == "trust":
        level = TrustDomainChecker.get_trust_level()
        print(f"信任级别: {level}")
        print(f"在信任域内: {TrustDomainChecker.is_in_trust_domain()}")

if __name__ == "__main__":
    main()
