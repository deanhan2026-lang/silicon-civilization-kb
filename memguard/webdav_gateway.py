# -*- coding: utf-8 -*-
"""
MemGuard WebDAV Gateway
=======================
所有外部节点通过 MemGuard 访问 NAS WebDAV，不再直接持有 anima/animastellar 凭据。

架构：
  外部节点 → POST /api/webdav/auth/login（node_id + key）
           → 获得 session_id
           → GET/POST/PUT/DELETE /api/webdav/path（X-Session-ID 鉴权）
           → MemGuard 权限矩阵检查
           → NAS WebDAV（服务端持有凭据）
           → 返回结果

权限矩阵（G010 档位映射）：
  L1 READONLY  → 只读 shared inbox 自己和公开文档
  L2 EDITOR    → + 写自己的 inbox，读取 mesh 共享文档
  L3 ADMIN     → + 读写 mesh/、archive/、docs/
  核心文件      → 禁止任何外部访问
"""
from flask import Blueprint, request, jsonify
from memguard.auth import AuthManager, PermissionLevel
import requests
import base64

# ========== 配置 ==========
WEBDAV_BLUEPRINT = Blueprint('webdav', __name__, url_prefix='/api/webdav')

NAS_WEBDAV = 'http://100.123.195.10:5005'
NAS_AUTH = ('anima', 'animastellar')  # 仅在 MemGuard 服务端持有
NAS_BASE_PATH = '/qclaw'

# ========== 权限矩阵 ==========
# (permission_level, method, nas_path) → allowed | (reason, status_code)
def check_access(permission: PermissionLevel, method: str, path: str) -> tuple[bool, str]:
    """
    返回 (allowed, reason_or_error_msg)
    """
    # 规范化路径
    path = path.strip('/')
    if path.startswith('qclaw/'):
        path = path[len('qclaw/'):]
    path = '/' + path

    is_write = method in ('PUT', 'POST', 'DELETE', 'MKCOL', 'MOVE')
    is_read = method in ('GET', 'PROPFIND', 'HEAD')

    # ========== 核心灵魂文件：完全禁止外部访问 ==========
    core_files = [
        '/soul.md', '/identity.md', '/memory.md',
        '/AGENTS.md', '/USER.md', '/TOOLS.md', '/HEARTBEAT.md',
        '/MEMORY.md',
    ]
    for cf in core_files:
        if path.endswith(cf) or path == cf:
            return False, 'Access denied: core soul files protected', 403

    # ========== L1 READONLY ==========
    if permission == PermissionLevel.READONLY:
        # 只读：自己的 inbox + 公开文档
        if is_write:
            return False, 'Permission denied: read-only access', 403

        # 允许读：自己的 inbox、ONBOARDING.md、公开文档
        l1_allowed = (
            path.startswith('/mesh/shared/') or
            path.startswith('/mesh/ONBOARDING') or
            path.startswith('/docs/ONBOARDING') or
            '/PROTOCOL.md' in path or
            '/archive/COMMERCIAL/' in path
        )
        if l1_allowed:
            return True, 'OK', 200
        return False, 'Permission denied: path not accessible for L1', 403

    # ========== L2 EDITOR ==========
    if permission == PermissionLevel.EDITOR:
        if is_write:
            # 只能写自己的 inbox
            if '/mesh/shared/' in path:
                # 提取目标节点（path 格式：mesh/shared/{node}/inbox/...）
                parts = path.split('/')
                try:
                    shared_idx = parts.index('shared')
                    target_node = parts[shared_idx + 1]
                    own_inbox = _get_own_node_from_session(request.headers.get('X-Session-ID', ''))
                    if target_node == own_inbox:
                        return True, 'OK', 200
                except (IndexError, ValueError):
                    pass
                return False, 'Permission denied: can only write own inbox', 403
            return False, 'Permission denied: write not allowed for L2', 403

        # 读：所有 shared inbox + 公开文档
        l2_allowed = (
            path.startswith('/mesh/') or
            path.startswith('/docs/') or
            path.startswith('/archive/') or
            path.startswith('/products/')
        )
        if l2_allowed:
            return True, 'OK', 200
        return False, 'Permission denied: path not accessible for L2', 403

    # ========== L3 ADMIN ==========
    if permission == PermissionLevel.ADMIN:
        # 禁止写核心文件（即使 ADMIN 也走白名单）
        if is_write:
            # 禁止写 MEMORY.md 等核心灵魂文件
            for cf in core_files:
                if cf in path:
                    return False, 'Access denied: core soul files protected', 403
        # ADMIN 可读写大部分路径
        admin_allowed = (
            path.startswith('/mesh/') or
            path.startswith('/docs/') or
            path.startswith('/archive/') or
            path.startswith('/products/') or
            path.startswith('/inbox/') or
            path.startswith('/tokens/')
        )
        if admin_allowed:
            return True, 'OK', 200
        return False, 'Permission denied: path not accessible', 403

    return False, 'Unknown permission level', 403


def _get_own_node_from_session(session_id: str) -> str:
    """从 session 提取 node_id（供权限判断用）"""
    # 懒加载避免循环导入
    from flask import current_app
    try:
        auth_mgr = current_app.auth_mgr
        valid, session = auth_mgr.validate_session(session_id)
        if valid:
            return session.node_id
    except Exception:
        pass
    return ''


def _forward_to_nas(method: str, nas_path: str, headers: dict = None,
                     data: bytes = None) -> tuple:
    """
    转发请求到 NAS WebDAV
    返回 (status_code, response_body, response_headers)
    """
    url = NAS_WEBDAV + nas_path
    h = dict(headers) if headers else {}
    h.pop('Host', None)
    h.pop('host', None)
    # MemGuard 内部转发，不带 Authorization（NAS 用不到，MemGuard 已在服务端持有凭据）
    h.pop('Authorization', None)

    try:
        if method == 'GET':
            resp = requests.get(url, auth=NAS_AUTH, headers=h, timeout=15)
        elif method == 'POST':
            resp = requests.post(url, auth=NAS_AUTH, headers=h, data=data, timeout=15)
        elif method == 'PUT':
            resp = requests.put(url, auth=NAS_AUTH, headers=h, data=data, timeout=20)
        elif method == 'DELETE':
            resp = requests.delete(url, auth=NAS_AUTH, headers=h, timeout=15)
        elif method == 'PROPFIND':
            resp = requests.request('PROPFIND', url, auth=NAS_AUTH, headers=h, timeout=15)
        elif method == 'MKCOL':
            resp = requests.request('MKCOL', url, auth=NAS_AUTH, headers=h, timeout=15)
        elif method == 'MOVE':
            resp = requests.request('MOVE', url, auth=NAS_AUTH, headers=h, data=data, timeout=15)
        else:
            return 405, b'Method not allowed', {}
        return resp.status_code, resp.content, dict(resp.headers)
    except requests.exceptions.RequestException as e:
        return 502, f'NAS error: {e}'.encode(), {}


# ========== 认证端点 ==========

@WEBDAV_BLUEPRINT.route('/auth/login', methods=['POST'])
def webdav_login():
    """
    新节点登录 WebDAV Gateway
    请求体：{ "node_id": "...", "key": "..." }
    返回：{ "session_id": "...", "permission": "readonly|editor|admin", "expires_at": "..." }
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'body required'}), 400

    node_id = data.get('node_id', '').strip()
    key = data.get('key', '')

    if not node_id or not key:
        return jsonify({'error': 'node_id and key required'}), 400

    from flask import current_app
    auth_mgr = current_app.auth_mgr

    # webdav_login 验证密钥并创建会话（不验证设备指纹）
    try:
        success, msg, session = auth_mgr.webdav_login(node_id, key)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        # 写入错误日志
        try:
            with open(r'C:\Users\Administrator\.qclaw\workspace-agent-d9479bde\temp_webdav_error.log', 'a') as f:
                f.write(f'webdav_login error: {e}\n{tb}\n')
        except Exception:
            pass
        return jsonify({'error': f'auth error: {e}', 'detail': str(e)[:200]}), 500

    if not success:
        return jsonify({'error': msg}), 401

    # 获取权限
    permission = auth_mgr.get_permission(node_id)
    permission_value = permission.value if permission else 'readonly'

    return jsonify({
        'success': True,
        'session_id': session.session_id,
        'permission': permission_value,
        'node_id': node_id,
        'expires_at': session.expires_at,
        'webdav_base': '/api/webdav',
        'message': 'session_id 即 WebDAV token，请妥善保存'
    })


@WEBDAV_BLUEPRINT.route('/auth/logout', methods=['POST'])
def webdav_logout():
    """登出 WebDAV 会话"""
    session_id = request.headers.get('X-Session-ID', '')
    if session_id:
        try:
            from flask import current_app
            auth_mgr = current_app.auth_mgr
            auth_mgr.revoke_session(session_id)
        except Exception:
            pass
    return jsonify({'success': True})


# ========== 权限查询端点 ==========

@WEBDAV_BLUEPRINT.route('/permissions', methods=['GET'])
def webdav_permissions():
    """查询当前 session 的 WebDAV 权限"""
    session_id = request.headers.get('X-Session-ID', '')
    from flask import current_app
    auth_mgr = current_app.auth_mgr

    if not session_id:
        return jsonify({'error': 'X-Session-ID required'}), 401

    valid, session = auth_mgr.validate_session(session_id)
    if not valid:
        return jsonify({'error': 'invalid or expired session'}), 401

    permission = auth_mgr.get_permission(session.node_id)

    # 构建权限说明
    tier_map = {
        PermissionLevel.READONLY: 'L1 Guest',
        PermissionLevel.EDITOR: 'L2 Observer',
        PermissionLevel.ADMIN: 'L3 Trusted',
    }

    return jsonify({
        'node_id': session.node_id,
        'permission': permission.value,
        'tier': tier_map.get(permission, 'unknown'),
        'expires_at': session.expires_at,
        'allowed_paths': _get_allowed_paths(permission),
    })


def _get_allowed_paths(permission: PermissionLevel) -> dict:
    """返回各权限级别的允许路径说明"""
    base = {
        'readonly': ['只读: /mesh/shared/{自身节点}/inbox/', '只读: /mesh/ONBOARDING.md', '只读: /docs/ONBOARDING.md'],
        'editor': [
            '读写: /mesh/shared/{自身节点}/inbox/',
            '只读: /mesh/shared/*/inbox/',
            '只读: /mesh/PROTOCOL.md',
            '只读: /archive/COMMERCIAL/',
            '只读: /docs/',
        ],
        'admin': [
            '读写: /mesh/ (核心子目录除外)',
            '读写: /archive/',
            '读写: /docs/',
            '读写: /inbox/',
            '只读: /products/',
            '禁止: 所有核心灵魂文件',
        ]
    }
    return base.get(permission.value, [])


# ========== 核心 WebDAV 代理端点 ==========

def _authenticate_request():
    """鉴权中间件：检查 session 并返回 (node_id, permission, error_response)
    成功: (node_id, permission, None)  失败: (None, None, jsonify_response_with_status)"""
    session_id = request.headers.get('X-Session-ID', '')
    if not session_id:
        return None, None, (jsonify({'error': 'X-Session-ID header required'}), 401)

    from flask import current_app
    auth_mgr = current_app.auth_mgr
    valid, session = auth_mgr.validate_session(session_id)
    if not valid:
        return None, None, (jsonify({'error': 'invalid or expired session'}), 401)

    permission = auth_mgr.get_permission(session.node_id)
    if not permission:
        return None, None, (jsonify({'error': 'permission not found'}), 403)

    return session.node_id, permission, None


@WEBDAV_BLUEPRINT.route('/<path:nas_path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'MKCOL', 'MOVE'])
@WEBDAV_BLUEPRINT.route('/<path:nas_path>', methods=['PROPFIND', 'HEAD'])
def webdav_proxy(nas_path: str):
    """
    WebDAV 代理核心端点
    所有外部请求在这里鉴权 + 权限检查 + 转发到 NAS WebDAV
    """
    node_id, permission, error = _authenticate_request()
    if error:
        resp, code = error
        return resp, code

    method = request.method
    path = '/' + nas_path.lstrip('/')

    # 权限检查
    allowed, reason_or_msg, denied_code = check_access(permission, method, path)
    if not allowed:
        return jsonify({
            'error': 'Permission denied',
            'reason': reason_or_msg,
            'path': path,
            'permission': permission.value,
            'hint': 'Login at POST /api/webdav/auth/login'
        }), denied_code

    # 转发到 NAS
    headers = dict(request.headers)
    data = request.get_data() if method in ('PUT', 'POST', 'MOVE') else None

    status_code, body, resp_headers = _forward_to_nas(method, path, headers, data)

    # 返回结果（保持 WebDAV 原生响应格式）
    from flask import make_response
    response = make_response((body, status_code, resp_headers))
    return response


# ========== 信息端点 ==========

@WEBDAV_BLUEPRINT.route('/info', methods=['GET'])
def webdav_info():
    """网关信息（公开）"""
    return jsonify({
        'service': 'MemGuard WebDAV Gateway',
        'version': '1.0',
        'description': 'Secure WebDAV access to AnimaLink NAS',
        'auth_endpoint': 'POST /api/webdav/auth/login',
        'permissions_endpoint': 'GET /api/webdav/permissions',
        'example': {
            'step1': 'POST /api/webdav/auth/login body: {"node_id":"xxx","key":"xxx"}',
            'step2': 'GET /api/webdav/mesh/shared/nyx-windows/inbox/ headers: {"X-Session-ID": "<session_id>"}',
        }
    })
