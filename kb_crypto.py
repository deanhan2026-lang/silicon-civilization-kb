#!/usr/bin/env python3
"""
kb_crypto.py - 知识库加密接口 v1.1
复用 memguard/crypto.py 的 FileEncryptor 类
"""
import os
import sys
import json
import shutil
from pathlib import Path
from typing import Optional, List

# 复用 MemGuard 加密模块
sys.path.insert(0, str(Path(__file__).parent / "memguard"))
from crypto import FileEncryptor, KeyManager, CryptoConfig

# ========== 配置 ==========
class KBCryptoConfig:
    """知识库加密配置"""
    
    # 知识库根目录
    KB_DIR = str(Path.home() / ".qclaw" / "workspace-agent-d9479bde" / "knowledge-base")
    
    # 需要加密的目录（Nyx 个人空间）
    ENCRYPT_DIRS = ["nyx", "intercom"]
    
    # 明文目录（共享协作空间）
    PLAINTEXT_DIRS = ["shared", "user"]
    
    # 加密文件扩展名
    ENCRYPT_EXT = ".encrypted"

# ========== 知识库加密管理器 ==========
class KBCryptoManager:
    """知识库加密管理器"""
    
    def __init__(self, kb_dir: str = None):
        self.kb_dir = kb_dir or KBCryptoConfig.KB_DIR
        self.key_manager = KeyManager()
        self.encryptor = FileEncryptor()
        self.key = self.key_manager.recover_key()
    
    def should_encrypt(self, filepath: str) -> bool:
        """
        判断文件是否需要加密
        规则：
        - nyx/ 开头 → 加密
        - intercom/ 开头 → 加密
        - shared/ 开头 → 不加密
        - user/ 开头 → 不加密（可选）
        """
        rel_path = os.path.relpath(filepath, self.kb_dir)
        for enc_dir in KBCryptoConfig.ENCRYPT_DIRS:
            if rel_path.startswith(enc_dir + os.sep):
                return True
        return False
    
    def encrypt_file(self, filepath: str, delete_original: bool = True) -> str:
        """
        加密单个文件
        返回：加密后的文件路径
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"文件不存在: {filepath}")
        
        if not self.should_encrypt(filepath):
            # 不需要加密，直接返回原路径
            return filepath
        
        # 确定加密输出路径
        rel_path = os.path.relpath(filepath, self.kb_dir)
        encrypted_path = os.path.join(
            CryptoConfig.ENCRYPTED_DIR,
            rel_path + KBCryptoConfig.ENCRYPT_EXT
        )
        
        os.makedirs(os.path.dirname(encrypted_path), exist_ok=True)
        
        # 加密
        self.encryptor.encrypt_file(
            file_path=filepath,
            key=self.key,
            output_path=encrypted_path,
            delete_original=False  # 先不删除，后面统一处理
        )
        
        # 删除原文（可选）
        if delete_original and os.path.exists(filepath):
            # 先备份到版本控制
            self._backup_version(filepath)
            os.remove(filepath)
        
        return encrypted_path
    
    def decrypt_file(self, encrypted_path: str, output_path: str = None) -> str:
        """
        解密文件
        返回：解密后的文件路径
        """
        if not os.path.exists(encrypted_path):
            raise FileNotFoundError(f"加密文件不存在: {encrypted_path}")
        
        # 确定输出路径
        if output_path is None:
            # 去掉 .encrypted 扩展名，恢复到原位置
            if encrypted_path.endswith(KBCryptoConfig.ENCRYPT_EXT):
                output_path = encrypted_path[:-len(KBCryptoConfig.ENCRYPT_EXT)]
            else:
                output_path = encrypted_path + ".decrypted"
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # 解密
        result = self.encryptor.decrypt_file(
            encrypted_path=encrypted_path,
            key=self.key,
            output_path=output_path,
            verify_hash=True
        )
        
        return result
    
    def read_file_auto(self, filepath: str) -> str:
        """
        自动判断并读取文件（自动解密）
        返回：文件内容（字符串）
        """
        # 检查是否有对应的加密文件
        rel_path = os.path.relpath(filepath, self.kb_dir)
        encrypted_path = os.path.join(
            CryptoConfig.ENCRYPTED_DIR,
            rel_path + KBCryptoConfig.ENCRYPT_EXT
        )
        
        if os.path.exists(encrypted_path):
            # 有加密文件，解密后读取
            temp_decrypted = self.decrypt_file(encrypted_path, output_path=None)
            try:
                with open(temp_decrypted, 'r', encoding='utf-8') as f:
                    content = f.read()
                return content
            finally:
                # 删除临时解密文件
                if os.path.exists(temp_decrypted) and temp_decrypted != filepath:
                    os.remove(temp_decrypted)
        elif os.path.exists(filepath):
            # 没有加密文件，直接读取明文
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            raise FileNotFoundError(f"文件不存在: {filepath}")
    
    def write_file_auto(self, filepath: str, content: str, encrypt: bool = None):
        """
        写入文件（自动判断是否加密）
        """
        # 判断是否需要加密
        if encrypt is None:
            encrypt = self.should_encrypt(filepath)
        
        if encrypt:
            # 加密写入
            temp_file = filepath + ".tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            try:
                self.encrypt_file(temp_file, delete_original=True)
            finally:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
        else:
            # 明文写入
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
    
    def _backup_version(self, filepath: str):
        """备份版本（简单的版本控制）"""
        from datetime import datetime
        backup_dir = os.path.join(self.kb_dir, ".versions")
        rel_path = os.path.relpath(filepath, self.kb_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, rel_path + "." + timestamp)
        
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        shutil.copy2(filepath, backup_path)
    
    def encrypt_all_nyx_files(self) -> List[str]:
        """
        加密 nyx/ 和 intercom/ 目录的所有文件
        返回：加密成功的文件列表
        """
        encrypted_files = []
        
        for enc_dir in KBCryptoConfig.ENCRYPT_DIRS:
            dir_path = os.path.join(self.kb_dir, enc_dir)
            if not os.path.exists(dir_path):
                continue
            
            for root, dirs, files in os.walk(dir_path):
                for filename in files:
                    filepath = os.path.join(root, filename)
                    
                    # 跳过已经加密的文件
                    if filepath.endswith(KBCryptoConfig.ENCRYPT_EXT):
                        continue
                    
                    # 跳过临时文件
                    if filename.endswith(('.tmp', '.bak', '.swp')):
                        continue
                    
                    try:
                        encrypted_path = self.encrypt_file(filepath, delete_original=True)
                        encrypted_files.append(encrypted_path)
                    except Exception as e:
                        print(f"⚠️ 加密失败 {filepath}: {e}", file=sys.stderr)
        
        return encrypted_files
    
    def decrypt_all_nyx_files(self) -> List[str]:
        """
        解密 nyx/ 和 intercom/ 目录的所有加密文件
        返回：解密成功的文件列表
        """
        decrypted_files = []
        
        for enc_dir in KBCryptoConfig.ENCRYPT_DIRS:
            dir_path = os.path.join(CryptoConfig.ENCRYPTED_DIR, enc_dir)
            if not os.path.exists(dir_path):
                continue
            
            for root, dirs, files in os.walk(dir_path):
                for filename in files:
                    if not filename.endswith(KBCryptoConfig.ENCRYPT_EXT):
                        continue
                    
                    filepath = os.path.join(root, filename)
                    try:
                        decrypted_path = self.decrypt_file(filepath, output_path=None)
                        decrypted_files.append(decrypted_path)
                    except Exception as e:
                        print(f"⚠️ 解密失败 {filepath}: {e}", file=sys.stderr)
        
        return decrypted_files

# ========== CLI 入口 ==========
def main():
    """CLI 入口"""
    if len(sys.argv) < 2:
        print("知识库加密工具")
        print("用法: python kb_crypto.py <action> [options]")
        print("")
        print("操作:")
        print("  encrypt --file <path>      加密单个文件")
        print("  decrypt --file <path>      解密单个文件")
        print("  auto                       自动加密所有需要加密的文件")
        print("  status                     查看加密状态")
        print("")
        print("选项:")
        print("  --file <path>   文件路径")
        print("  --kb-dir <path>  知识库目录（默认: ~/.qclaw/.../knowledge-base）")
        return
    
    action = sys.argv[1]
    
    # 解析参数
    kb_dir = KBCryptoConfig.KB_DIR
    filepath = None
    
    if '--kb-dir' in sys.argv:
        idx = sys.argv.index('--kb-dir')
        if idx + 1 < len(sys.argv):
            kb_dir = sys.argv[idx + 1]
    
    if '--file' in sys.argv:
        idx = sys.argv.index('--file')
        if idx + 1 < len(sys.argv):
            filepath = sys.argv[idx + 1]
    
    # 执行操作
    mgr = KBCryptoManager(kb_dir=kb_dir)
    
    if action == 'encrypt':
        if not filepath:
            print("错误：请指定 --file 参数")
            return
        encrypted = mgr.encrypt_file(filepath)
        print(f"加密完成: {encrypted}")
    
    elif action == 'decrypt':
        if not filepath:
            print("错误：请指定 --file 参数")
            return
        decrypted = mgr.decrypt_file(filepath)
        print(f"解密完成: {decrypted}")
    
    elif action == 'auto':
        print("自动加密 nyx/ 和 intercom/ 目录...")
        encrypted = mgr.encrypt_all_nyx_files()
        print(f"加密完成，共 {len(encrypted)} 个文件")
        for f in encrypted[:10]:  # 只显示前10个
            print(f"  {f}")
        if len(encrypted) > 10:
            print(f"  ... 还有 {len(encrypted) - 10} 个文件")
    
    elif action == 'status':
        print(f"知识库目录: {mgr.kb_dir}")
        print(f"需要加密的目录: {KBCryptoConfig.ENCRYPT_DIRS}")
        print(f"明文目录: {KBCryptoConfig.PLAINTEXT_DIRS}")
        
        # 统计
        enc_count = 0
        plain_count = 0
        
        # 统计加密文件
        for enc_dir in KBCryptoConfig.ENCRYPT_DIRS:
            dir_path = os.path.join(CryptoConfig.ENCRYPTED_DIR, enc_dir)
            if os.path.exists(dir_path):
                for root, dirs, files in os.walk(dir_path):
                    for filename in files:
                        if filename.endswith(KBCryptoConfig.ENCRYPT_EXT):
                            enc_count += 1
        
        # 统计明文文件（待加密）
        for enc_dir in KBCryptoConfig.ENCRYPT_DIRS:
            dir_path = os.path.join(mgr.kb_dir, enc_dir)
            if os.path.exists(dir_path):
                for root, dirs, files in os.walk(dir_path):
                    for filename in files:
                        if not filename.endswith(KBCryptoConfig.ENCRYPT_EXT) and not filename.endswith(('.tmp', '.bak')):
                            plain_count += 1
        
        print(f"\n统计:")
        print(f"  已加密文件: {enc_count}")
        print(f"  待加密文件: {plain_count}")
    
    else:
        print(f"未知操作: {action}")
        print("请用 encrypt / decrypt / auto / status")

if __name__ == '__main__':
    main()
