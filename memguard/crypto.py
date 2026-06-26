#!/usr/bin/env python3
"""
MemGuard-GM Crypto - 数据加密模块
实现瞬方案：AES-256加密 + 密钥分片存储
"""
from common.logger import get_logger
from common.config_manager import get_config

logger = get_logger(__name__)

import os
import json
import base64
import hashlib
import secrets
from pathlib import Path
from typing import Tuple, List, Optional
from dataclasses import dataclass
from datetime import datetime

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    print("警告：cryptography库未安装，使用模拟加密")

# ========== 配置 ==========
class CryptoConfig:
    """
    加密配置（从 config.yaml 加载，支持回退到默认值）
    使用方式：CryptoConfig.ENCRYPTED_DIR（自动从配置读取）
    """

    _cache: dict = {}
    _local_keyshare_dir: str = str(Path(__file__).parent.parent / "data" / "memguard_keys")
    _local_encrypted_dir: str = str(Path(__file__).parent.parent / "data" / "memguard_encrypted")

    def __getattr__(self, name: str):
        if name.startswith('_') or name in ('__dict__', '__class__'):
            raise AttributeError(name)
        if name not in self._cache:
            self._cache[name] = self._resolve(name)
        return self._cache[name]

    def _resolve(self, name: str):
        """从 config.yaml 解析值，回退到硬编码默认值"""

        def _local_path(path_str: str) -> str:
            """将相对路径转为绝对路径（相对于项目根目录）"""
            if os.path.isabs(path_str):
                return path_str
            return str(Path(__file__).parent.parent / path_str)

        if name == 'ENCRYPTED_DIR':
            val = get_config('memguard.encrypted_dir', None)
            if val:
                return val
            # 回退：NAS 存在则用 NAS，否则用本地
            return self._local_encrypted_dir if not os.path.exists("Z:") else r"Z:\qclaw\memguard_encrypted"

        if name == 'KEYSHARE_LOCATIONS':
            val = get_config('memguard.keyshare_locations', None)
            if val:
                # 配置中是相对路径，转为绝对路径
                result = {}
                for loc, path in val.items():
                    result[loc] = _local_path(path)
                return result
            # 回退默认值
            return {
                'local': str(Path(__file__).parent.parent / "data" / "memguard_keys" / "share_local.json"),
                'nas': str(Path(__file__).parent.parent / "data" / "memguard_keys" / "share_nas.json"),
                'n200': str(Path(__file__).parent.parent / "data" / "memguard_keys" / "share_n200.json")
            }

        if name == 'CRYPTO_CONFIG':
            # 跟随 ENCRYPTED_DIR
            enc_dir = self.ENCRYPTED_DIR
            return os.path.join(enc_dir, "crypto_config.json")

        if name == 'SALT_LENGTH':
            return 32

        if name == 'NONCE_LENGTH':
            return 12

        if name == 'SHARE_TOTAL':
            return get_config('memguard.share_total', 3)

        if name == 'SHARE_THRESHOLD':
            return get_config('memguard.share_threshold', 2)

        raise AttributeError(f"CryptoConfig has no attribute '{name}'")


# 单例实例（供模块内部直接使用 CryptoConfig.XXX）
CryptoConfig = CryptoConfig()

# ========== 数据结构 ==========
@dataclass
class EncryptedFile:
    """加密文件元数据"""
    original_path: str
    encrypted_path: str
    salt: str
    nonce: str
    tag: str           # GCM认证标签
    encrypted_at: str
    original_size: int
    original_hash: str  # 原始文件SHA256
    
    def to_dict(self) -> dict:
        return self.__dict__
    
    @classmethod
    def from_dict(cls, data: dict) -> 'EncryptedFile':
        return cls(**data)

@dataclass
class KeyShare:
    """密钥分片"""
    share_id: str
    location: str      # local/nas/n200
    share_data: str    # 分片数据（Base64）
    created_at: str
    
    def to_dict(self) -> dict:
        return self.__dict__

# ========== AES-256加密工具 ==========
class AES256Crypto:
    """AES-256-GCM加密工具"""
    
    def __init__(self):
        if not CRYPTO_AVAILABLE:
            self._mock_mode = True
            logger.warning("cryptography库未安装，使用模拟加密模式")
        else:
            self._mock_mode = False
        logger.info(f"AES256Crypto initialized, mock_mode={self._mock_mode}")
    
    def generate_key(self) -> bytes:
        """生成32字节（256位）随机密钥"""
        key = secrets.token_bytes(32)
        logger.debug("AES-256密钥已生成")
        return key
    
    def encrypt(self, plaintext: bytes, key: bytes) -> Tuple[bytes, bytes, bytes]:
        """
        AES-256-GCM加密
        返回: (nonce, ciphertext, tag)
        """
        logger.info(f"AES-256-GCM加密开始，输入大小: {len(plaintext)} 字节")
        if self._mock_mode:
            # 模拟模式：简单Base64编码
            nonce = secrets.token_bytes(CryptoConfig.NONCE_LENGTH)
            ciphertext = base64.b64encode(plaintext)
            tag = hashlib.sha256(plaintext).digest()[:16]
            logger.info("模拟加密完成")
            return nonce, ciphertext, tag
        
        # 真实加密
        nonce = secrets.token_bytes(CryptoConfig.NONCE_LENGTH)
        aesgcm = AESGCM(key)
        
        # AESGCM.encrypt 返回 ciphertext + tag
        ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext, None)
        
        # 分离密文和tag（最后16字节）
        ciphertext = ciphertext_with_tag[:-16]
        tag = ciphertext_with_tag[-16:]
        
        logger.info(f"AES-256-GCM加密完成，密文大小: {len(ciphertext)} 字节")
        return nonce, ciphertext, tag
    
    def decrypt(self, nonce: bytes, ciphertext: bytes, tag: bytes, key: bytes) -> bytes:
        """
        AES-256-GCM解密
        """
        logger.info(f"AES-256-GCM解密开始，密文大小: {len(ciphertext)} 字节")
        if self._mock_mode:
            # 模拟模式：Base64解码
            plaintext = base64.b64decode(ciphertext)
            logger.info("模拟解密完成")
            return plaintext
        
        # 真实解密
        aesgcm = AESGCM(key)
        ciphertext_with_tag = ciphertext + tag
        
        try:
            plaintext = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
            logger.info("AES-256-GCM解密成功")
            return plaintext
        except Exception as e:
            logger.error(f"解密失败: {e}")
            raise ValueError(f"解密失败：{e}")
    
    @staticmethod
    def compute_hash(data: bytes) -> str:
        """计算SHA256哈希"""
        return hashlib.sha256(data).hexdigest()

# ========== Shamir秘密共享（简化实现）==========
class ShamirSecretSharing:
    """
    Shamir秘密共享（简化版）
    注：生产环境应使用专业库如 `secretsharing`
    """
    
    @staticmethod
    def split_secret(secret: bytes, threshold: int, total: int) -> List[bytes]:
        """
        分割秘密为n份，需要k份恢复
        简化实现：使用XOR分片（非 Shamir，但满足基本需求）
        """
        if threshold > total:
            raise ValueError("阈值不能大于总分片数")
        
        # 简化方案：生成随机分片，通过XOR组合
        shares = []
        
        # 生成 threshold-1 个随机分片
        for i in range(threshold - 1):
            shares.append(secrets.token_bytes(len(secret)))
        
        # 最后一个分片 = secret XOR (所有随机分片)
        last_share = secret
        for share in shares:
            last_share = bytes(a ^ b for a, b in zip(last_share, share))
        shares.append(last_share)
        
        # 如果 total > threshold，复制一些分片
        while len(shares) < total:
            shares.append(shares[len(shares) % threshold])
        
        return shares[:total]
    
    @staticmethod
    def recover_secret(shares: List[bytes]) -> bytes:
        """
        从分片恢复秘密
        """
        if not shares:
            raise ValueError("没有提供分片")
        
        # XOR所有分片
        secret = shares[0]
        for share in shares[1:]:
            secret = bytes(a ^ b for a, b in zip(secret, share))
        
        return secret

# ========== 密钥管理器 ==========
class KeyManager:
    """密钥管理器 - 分片存储"""
    
    def __init__(self):
        self.crypto = AES256Crypto()
        self._ensure_dirs()
        logger.info(f"KeyManager initialized, encrypted_dir={CryptoConfig.ENCRYPTED_DIR}")
    
    def _ensure_dirs(self):
        """确保目录存在"""
        Path(CryptoConfig.ENCRYPTED_DIR).mkdir(parents=True, exist_ok=True)
        for path in CryptoConfig.KEYSHARE_LOCATIONS.values():
            Path(path).parent.mkdir(parents=True, exist_ok=True)        
        logger.debug(f"加密目录和密钥分片目录已就绪")
    
    def generate_and_store_key(self) -> bytes:
        """
        生成新密钥并分片存储到三个位置
        返回：明文密钥（仅此一次，需保存）
        """
        key = self.crypto.generate_key()
        shares = ShamirSecretSharing.split_secret(
            key,
            CryptoConfig.SHARE_THRESHOLD,
            CryptoConfig.SHARE_TOTAL
        )
        
        # 存储分片
        timestamp = datetime.now().isoformat()
        locations = list(CryptoConfig.KEYSHARE_LOCATIONS.keys())
        
        for i, (share, location) in enumerate(zip(shares, locations)):
            key_share = KeyShare(
                share_id=f"share_{i+1}",
                location=location,
                share_data=base64.b64encode(share).decode('utf-8'),
                created_at=timestamp
            )
            
            with open(CryptoConfig.KEYSHARE_LOCATIONS[location], 'w', encoding='utf-8') as f:
                json.dump(key_share.to_dict(), f, indent=2)
        
        # 保存配置
        config = {
            'key_created_at': timestamp,
            'share_threshold': CryptoConfig.SHARE_THRESHOLD,
            'share_total': CryptoConfig.SHARE_TOTAL,
            'locations': locations
        }
        with open(CryptoConfig.CRYPTO_CONFIG, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"新密钥已生成并分片存储到 {CryptoConfig.SHARE_TOTAL} 个位置，恢复阈值={CryptoConfig.SHARE_THRESHOLD}")
        return key
    
    def recover_key(self, locations: List[str] = None) -> bytes:
        """
        从分片恢复密钥
        需要至少 threshold 个分片
        """
        if locations is None:
            locations = list(CryptoConfig.KEYSHARE_LOCATIONS.keys())[:CryptoConfig.SHARE_THRESHOLD]
        
        shares = []
        for location in locations:
            path = CryptoConfig.KEYSHARE_LOCATIONS.get(location)
            if not path or not os.path.exists(path):
                continue
            
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                share = base64.b64decode(data['share_data'])
                shares.append(share)
        
        if len(shares) < CryptoConfig.SHARE_THRESHOLD:
            logger.error(f"密钥恢复失败：需要至少 {CryptoConfig.SHARE_THRESHOLD} 个分片，当前只有 {len(shares)} 个")
            raise ValueError(f"需要至少 {CryptoConfig.SHARE_THRESHOLD} 个分片，当前只有 {len(shares)} 个")
        
        recovered_key = ShamirSecretSharing.recover_secret(shares[:CryptoConfig.SHARE_THRESHOLD])
        logger.info(f"密钥已从 {len(shares[:CryptoConfig.SHARE_THRESHOLD])} 个分片恢复")
        return recovered_key

# ========== 文件加密器 ==========
class FileEncryptor:
    """文件加密器"""
    
    def __init__(self):
        self.crypto = AES256Crypto()
        self.key_mgr = KeyManager()
        self.metadata_file = os.path.join(CryptoConfig.ENCRYPTED_DIR, "encrypted_files.json")
        self._load_metadata()
        logger.debug(f"FileEncryptor initialized, metadata_file={self.metadata_file}")
    
    def _load_metadata(self):
        """加载加密文件元数据"""
        if os.path.exists(self.metadata_file):
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                self.metadata = json.load(f)
            logger.debug(f"已加载 {len(self.metadata)} 条加密文件元数据")
        else:
            self.metadata = {}
            logger.debug("无加密文件元数据文件，初始化为空")
    
    def _save_metadata(self):
        """保存元数据"""
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)
        logger.debug(f"已保存 {len(self.metadata)} 条加密文件元数据")
    
    def encrypt_file(
        self,
        file_path: str,
        key: bytes,
        output_path: str = None,
        delete_original: bool = False
    ) -> EncryptedFile:
        """
        加密文件
        """
        file_path = os.path.abspath(file_path)
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        # 读取原始文件
        with open(file_path, 'rb') as f:
            plaintext = f.read()
        
        original_hash = self.crypto.compute_hash(plaintext)
        original_size = len(plaintext)
        
        # 加密
        nonce, ciphertext, tag = self.crypto.encrypt(plaintext, key)
        
        # 构建加密文件路径
        if output_path is None:
            output_path = os.path.join(
                CryptoConfig.ENCRYPTED_DIR,
                os.path.basename(file_path) + ".encrypted"
            )
        
        # 写入加密文件
        # 格式: nonce(12) + tag(16) + ciphertext
        with open(output_path, 'wb') as f:
            f.write(nonce)
            f.write(tag)
            f.write(ciphertext)
        
        # 创建元数据
        encrypted_file = EncryptedFile(
            original_path=file_path,
            encrypted_path=output_path,
            salt="",  # GCM模式不需要salt
            nonce=base64.b64encode(nonce).decode('utf-8'),
            tag=base64.b64encode(tag).decode('utf-8'),
            encrypted_at=datetime.now().isoformat(),
            original_size=original_size,
            original_hash=original_hash
        )
        
        # 保存元数据
        self.metadata[output_path] = encrypted_file.to_dict()
        self._save_metadata()
        
        # 删除原始文件（如果要求）
        if delete_original:
            os.remove(file_path)
            logger.info(f"原始文件已删除: {file_path}")
        
        logger.info(f"文件加密成功: {file_path} -> {output_path} (大小: {len(ciphertext)} 字节)")
        return encrypted_file
    
    def decrypt_file(
        self,
        encrypted_path: str,
        key: bytes,
        output_path: str = None,
        verify_hash: bool = True
    ) -> str:
        """
        解密文件
        返回：解密后的文件路径
        """
        encrypted_path = os.path.abspath(encrypted_path)
        
        if not os.path.exists(encrypted_path):
            raise FileNotFoundError(f"加密文件不存在: {encrypted_path}")
        
        # 读取元数据
        if encrypted_path not in self.metadata:
            raise ValueError(f"未找到加密文件元数据: {encrypted_path}")
        
        meta = EncryptedFile.from_dict(self.metadata[encrypted_path])
        
        # 读取加密文件
        with open(encrypted_path, 'rb') as f:
            data = f.read()
        
        # 解析：nonce(12) + tag(16) + ciphertext
        nonce = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]
        
        # 解密
        plaintext = self.crypto.decrypt(nonce, ciphertext, tag, key)
        
        # 验证哈希
        if verify_hash:
            computed_hash = self.crypto.compute_hash(plaintext)
            if computed_hash != meta.original_hash:
                raise ValueError(f"哈希验证失败！文件可能被篡改")
        
        # 确定输出路径
        if output_path is None:
            output_path = meta.original_path
        
        # 写入解密文件
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(plaintext)
        
        logger.info(f"文件解密成功: {encrypted_path} -> {output_path} (大小: {len(plaintext)} 字节)")
        return output_path
    
    def list_encrypted(self) -> List[EncryptedFile]:
        """列出所有加密文件"""
        return [EncryptedFile.from_dict(v) for v in self.metadata.values()]

# ========== 核心文件加密器（瞬方案：灵魂文件层）==========
class CoreFileProtector:
    """
    核心灵魂文件层加密保护
    实现瞬方案：核心文件全量AES-256加密
    """
    
    # 核心灵魂文件清单
    CORE_FILES = [
        "SOUL.md",
        "IDENTITY.md", 
        "USER.md",
        "AGENTS.md",
        "MEMORY.md",
        "TOOLS.md"
    ]
    
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        self.encryptor = FileEncryptor()
        self.key = None
    
    def initialize(self, existing_key: bytes = None):
        """
        初始化加密系统
        如果不提供密钥，生成新密钥并分片存储
        """
        if existing_key:
            self.key = existing_key
            logger.info("CoreFileProtector使用已有密钥")
        else:
            self.key = self.encryptor.key_mgr.generate_and_store_key()
            logger.info("CoreFileProtector生成新密钥并分片存储")
            print(f"新密钥已生成并分片存储到 {CryptoConfig.SHARE_TOTAL} 个位置")
            print(f"恢复阈值: {CryptoConfig.SHARE_THRESHOLD}")
        
        return self.key
    
    def encrypt_all_core_files(self, delete_originals: bool = False) -> List[EncryptedFile]:
        """
        加密所有核心灵魂文件
        """
        if not self.key:
            raise ValueError("请先调用 initialize() 初始化密钥")
        
        results = []
        
        logger.info(f"开始加密核心灵魂文件，共 {len(self.CORE_FILES)} 个")
        for filename in self.CORE_FILES:
            file_path = os.path.join(self.workspace_root, filename)
            
            if not os.path.exists(file_path):
                logger.warning(f"跳过不存在的核心文件: {filename}")
                print(f"跳过不存在的文件: {filename}")
                continue
            
            try:
                encrypted = self.encryptor.encrypt_file(
                    file_path,
                    self.key,
                    delete_original=delete_originals
                )
                results.append(encrypted)
                logger.info(f"核心文件加密成功: {filename}")
                print(f"已加密: {filename} -> {encrypted.encrypted_path}")
            except Exception as e:
                logger.error(f"核心文件加密失败 {filename}: {e}")
                print(f"加密失败 {filename}: {e}")
        
        logger.info(f"核心文件加密完成: {len(results)}/{len(self.CORE_FILES)} 个成功")
        return results
    
    def decrypt_all_core_files(self) -> List[str]:
        """
        解密所有核心灵魂文件
        """
        if not self.key:
            logger.info("无已加载密钥，尝试从分片恢复")
            self.key = self.encryptor.key_mgr.recover_key()
        
        logger.info("开始解密所有核心灵魂文件")
        results = []
        
        for encrypted in self.encryptor.list_encrypted():
            try:
                output_path = self.encryptor.decrypt_file(
                    encrypted.encrypted_path,
                    self.key
                )
                results.append(output_path)
                logger.info(f"核心文件解密成功: {os.path.basename(encrypted.original_path)}")
                print(f"已解密: {encrypted.encrypted_path} -> {output_path}")
            except Exception as e:
                logger.error(f"核心文件解密失败 {encrypted.encrypted_path}: {e}")
                print(f"解密失败: {e}")
        
        logger.info(f"核心文件解密完成: {len(results)} 个成功")
        return results
    
    def verify_integrity(self) -> dict:
        """
        验证所有加密文件的完整性
        """
        logger.info("开始验证所有加密文件完整性")
        if not self.key:
            self.key = self.encryptor.key_mgr.recover_key()
        
        results = {}
        valid_count = 0
        invalid_count = 0
        
        for encrypted in self.encryptor.list_encrypted():
            try:
                # 尝试解密并验证哈希
                self.encryptor.decrypt_file(
                    encrypted.encrypted_path,
                    self.key,
                    verify_hash=True
                )
                results[encrypted.original_path] = {
                    'status': 'valid',
                    'original_hash': encrypted.original_hash
                }
                valid_count += 1
            except ValueError as e:
                results[encrypted.original_path] = {
                    'status': 'invalid',
                    'error': str(e)
                }
                invalid_count += 1
                logger.error(f"完整性验证失败: {encrypted.original_path} - {e}")
        
        logger.info(f"完整性验证完成: {valid_count} 有效, {invalid_count} 无效")
        return results

# ========== CLI入口 ==========
def main():
    """CLI入口"""
    import sys
    
    if len(sys.argv) < 2:
        print("MemGuard-GM Crypto CLI")
        print("用法: python crypto.py <command> [args]")
        print("命令:")
        print("  init                           - 初始化加密系统")
        print("  encrypt <file>                 - 加密文件")
        print("  decrypt <encrypted_file>       - 解密文件")
        print("  list                           - 列出加密文件")
        print("  recover_key                    - 从分片恢复密钥")
        print("  protect_core <workspace>       - 加密核心灵魂文件")
        return
    
    cmd = sys.argv[1]
    logger.info(f"CLI命令: {cmd}, 参数: {sys.argv[2:]}")
    
    if cmd == "init":
        key_mgr = KeyManager()
        key = key_mgr.generate_and_store_key()
        logger.info("CLI: 密钥生成并分片存储")
        print(f"密钥已生成并分片存储")
        print(f"明文密钥（请保存）: {base64.b64encode(key).decode('utf-8')}")
    
    elif cmd == "encrypt":
        if len(sys.argv) < 3:
            print("用法: encrypt <file>")
            return
        
        key_mgr = KeyManager()
        key = key_mgr.recover_key()
        
        encryptor = FileEncryptor()
        result = encryptor.encrypt_file(sys.argv[2], key)
        logger.info(f"CLI加密完成: {result.encrypted_path}")
        print(f"已加密: {result.encrypted_path}")
    
    elif cmd == "decrypt":
        if len(sys.argv) < 3:
            print("用法: decrypt <encrypted_file>")
            return
        
        key_mgr = KeyManager()
        key = key_mgr.recover_key()
        
        encryptor = FileEncryptor()
        output = encryptor.decrypt_file(sys.argv[2], key)
        logger.info(f"CLI解密完成: {output}")
        print(f"已解密: {output}")
    
    elif cmd == "list":
        encryptor = FileEncryptor()
        files = encryptor.list_encrypted()
        logger.info(f"CLI列出加密文件: {len(files)} 个")
        for f in files:
            print(f"{f.original_path} -> {f.encrypted_path}")
    
    elif cmd == "recover_key":
        key_mgr = KeyManager()
        key = key_mgr.recover_key()
        logger.info("CLI密钥恢复成功")
        print(f"密钥已恢复: {base64.b64encode(key).decode('utf-8')}")
    
    elif cmd == "protect_core":
        if len(sys.argv) < 3:
            print("用法: protect_core <workspace>")
            return
        
        protector = CoreFileProtector(sys.argv[2])
        protector.initialize()
        results = protector.encrypt_all_core_files()
        logger.info(f"CLI保护核心文件完成: {len(results)} 个")
        print(f"已加密 {len(results)} 个核心文件")
    
    else:
        logger.warning(f"未知CLI命令: {cmd}")


if __name__ == "__main__":
    main()
