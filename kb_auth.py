#!/usr/bin/env python3
"""
kb_auth.py - 知识库鉴权接口 v1.0
复用 memguard/auth.py 的节点密钥系统
"""
import os
import sys
from pathlib import Path
from typing import Optional, List, Tuple

# 复用 MemGuard 鉴权模块
sys.path.insert(0, str(Path(__file__).parent / "memguard"))
from auth import AuthManager, PermissionLevel, NodeType

# ========== 配置 ==========
class KBAuthConfig:
    """知识库鉴权配置"""
    
    # 知识库根目录
    KB_DIR = str(Path.home() / ".qclaw" / "workspace-agent-d9479bde" / "knowledge-base")
    
    # 权限映射：节点类型 → 可访问的目录
    PERMISSION_MAP = {
        NodeType.COORDINATOR: ["nyx", "shared", "user", "intercom"],  # 全访问
        NodeType.VALIDATOR: ["shared", "user"],  # 只能访问共享区
        NodeType.SENSOR: ["shared"],  # 只读共享区
        NodeType.ACTUATOR: ["shared"],  # 受限写权限
    }
    
    # 特殊权限：destroyer 级别可以删除
    DESTROYER_EXTRA_DIRS = ["nyx", "shared", "user", "intercom"]

# ========== 知识库鉴权管理器 ==========
class KBAuthManager:
    """知识库鉴权管理器"""
    
    def __init__(self):
        self.auth_mgr = AuthManager()
        self.sessions = {}  # session_id -> node_id
    
    def authenticate(self, node_id: str, key: str) -> Tuple[bool, Optional[str]]:
        """
        节点认证
        返回: (是否成功, session_id)
        """
        # 验证节点密钥
        node = self.auth_mgr.keys.get(node_id)
        if not node:
            return False, None
        
        # 计算密钥哈希
        from crypto import hashlib
        key_hash = hashlib.sha256(key.encode('utf-8')).hexdigest()
        
        if key_hash != node.key_hash:
            return False, None
        
        # 创建会话
        import secrets
        session_id = secrets.token_urlsafe(32)
        self.sessions[session_id] = {
            'node_id': node_id,
            'created_at': self.auth_mgr._get_timestamp(),
            'expires_at': self.auth_mgr._get_timestamp(expires_in=86400)  # 24小时
        }
        
        return True, session_id
    
    def validate_session(self, session_id: str) -> Optional[str]:
        """
        验证会话
        返回: node_id (如果有效) 或 None
        """
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        
        # 检查是否过期
        from datetime import datetime
        expires_at = datetime.fromisoformat(session['expires_at'])
        if datetime.now() >= expires_at:
            del self.sessions[session_id]
            return None
        
        return session['node_id']
    
    def check_permission(self, node_id: str, filepath: str, operation: str = 'read') -> bool:
        """
        检查权限
        operation: read / write / delete
        """
        if node_id not in self.auth_mgr.keys:
            return False
        
        node = self.auth_mgr.keys[node_id]
        
        # 获取文件所属目录
        rel_path = os.path.relpath(filepath, KBAuthConfig.KB_DIR)
        top_dir = rel_path.split(os.sep)[0] if os.sep in rel_path else ''
        
        # 检查目录访问权限
        allowed_dirs = KBAuthConfig.PERMISSION_MAP.get(node.node_type, [])
        
        # destroyer 级别有额外权限
        if node.permission_level == PermissionLevel.DESTROYER:
            allowed_dirs = KBAuthConfig.DESTROYER_EXTRA_DIRS
        
        if top_dir not in allowed_dirs:
            return False
        
        # 检查操作权限
        if operation == 'read':
            return True  # 所有有目录访问权限的都可以读
        
        if operation in ['write', 'delete']:
            # 需要至少 editor 权限
            if node.permission_level == PermissionLevel.READONLY:
                return False
            
            # delete 需要 destroyer 权限
            if operation == 'delete' and node.permission_level != PermissionLevel.DESTROYER:
                return False
        
        return True
    
    def get_node_info(self, node_id: str) -> Optional[dict]:
        """获取节点信息"""
        node = self.auth_mgr.keys.get(node_id)
        if not node:
            return None
        
        return {
            'node_id': node.node_id,
            'node_type': node.node_type,
            'permission_level': node.permission_level,
            'created_at': node.created_at,
            'last_active': node.last_active
        }
    
    def logout(self, session_id: str):
        """注销会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

# ========== Flask 装饰器（用于 API 集成）==========
def require_kb_access(operation: str = 'read'):
    """
    知识库访问鉴权装饰器
    用法：
    @require_kb_access('read')
    def get_kb_file(filepath):
        ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 从请求头获取 session_id
            from flask import request, jsonify
            session_id = request.headers.get('X-Session-ID')
            
            if not session_id:
                return jsonify({'error': 'Missing session ID'}), 401
            
            # 验证会话
            mgr = KBAuthManager()
            node_id = mgr.validate_session(session_id)
            
            if not node_id:
                return jsonify({'error': 'Invalid or expired session'}), 401
            
            # 获取文件路径
            filepath = kwargs.get('filepath') or request.args.get('filepath')
            
            if filepath:
                # 检查权限
                if not mgr.check_permission(node_id, filepath, operation):
                    return jsonify({'error': 'Permission denied'}), 403
            
            # 将 node_id 传给函数
            kwargs['_node_id'] = node_id
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

# ========== CLI 入口 ==========
def main():
    """CLI 入口"""
    if len(sys.argv) < 2:
        print("知识库鉴权工具")
        print("用法: python kb_auth.py <command> [options]")
        print("")
        print("命令:")
        print("  login <node_id> <key>      登录获取 session_id")
        print("  verify <session_id>          验证会话")
        print("  check <session_id> <filepath> <op>  检查文件访问权限")
        print("  info <node_id>              查看节点信息")
        print("  logout <session_id>         注销会话")
        return
    
    cmd = sys.argv[1]
    mgr = KBAuthManager()
    
    if cmd == 'login':
        if len(sys.argv) < 4:
            print("用法: python kb_auth.py login <node_id> <key>")
            return
        node_id = sys.argv[2]
        key = sys.argv[3]
        success, session_id = mgr.authenticate(node_id, key)
        if success:
            print(f"登录成功！")
            print(f"Session ID: {session_id}")
        else:
            print(f"登录失败：密钥错误")
    
    elif cmd == 'verify':
        if len(sys.argv) < 3:
            print("用法: python kb_auth.py verify <session_id>")
            return
        session_id = sys.argv[2]
        node_id = mgr.validate_session(session_id)
        if node_id:
            print(f"会话有效，节点: {node_id}")
        else:
            print(f"会话无效或已过期")
    
    elif cmd == 'check':
        if len(sys.argv) < 5:
            print("用法: python kb_auth.py check <session_id> <filepath> <op>")
            print("  op: read / write / delete")
            return
        session_id = sys.argv[2]
        filepath = sys.argv[3]
        operation = sys.argv[4]
        node_id = mgr.validate_session(session_id)
        if not node_id:
            print(f"会话无效")
            return
        has_permission = mgr.check_permission(node_id, filepath, operation)
        if has_permission:
            print(f"权限检查通过：{node_id} 可以 {operation} {filepath}")
        else:
            print(f"权限检查失败：{node_id} 不能 {operation} {filepath}")
    
    elif cmd == 'info':
        if len(sys.argv) < 3:
            print("用法: python kb_auth.py info <node_id>")
            return
        node_id = sys.argv[2]
        info = mgr.get_node_info(node_id)
        if info:
            print(f"节点信息：")
            for k, v in info.items():
                print(f"  {k}: {v}")
        else:
            print(f"节点不存在：{node_id}")
    
    elif cmd == 'logout':
        if len(sys.argv) < 3:
            print("用法: python kb_auth.py logout <session_id>")
            return
        session_id = sys.argv[2]
        if mgr.logout(session_id):
            print(f"注销成功")
        else:
            print(f"会话不存在")
    
    else:
        print(f"未知命令：{cmd}")

if __name__ == '__main__':
    # 导入 wraps
    from functools import wraps
    main()
