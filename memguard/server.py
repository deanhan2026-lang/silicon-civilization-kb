#!/usr/bin/env python3
"""
MemGuard-GM API Server
"""
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from functools import wraps

from flask import Flask, request, jsonify
from flask_cors import CORS

sys.path.insert(0, str(Path(__file__).parent))
from core import MemGuardEngine, Config, Storage
from sync import SyncEngine, Delta
from auth import AuthManager, PermissionLevel, NodeType

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

engine = MemGuardEngine()
sync_engine = SyncEngine()
auth_mgr = AuthManager()

def require_operator(op_type: str):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            operator = request.headers.get('X-Operator', 'anonymous')
            allowed_ops = {
                'admin': ['read', 'write', 'freeze', 'unfreeze', 'baseline'],
                'validator': ['read', 'verify'],
                'api': ['read']
            }
            if op_type not in allowed_ops.get(operator, []):
                return jsonify({'error': 'Permission denied', 'required': op_type}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

def get_operator():
    return request.headers.get('X-Operator', 'anonymous')

def get_session_id():
    return request.headers.get('X-Session-ID', '')

def require_auth(*required_permissions: PermissionLevel):
    """
    新鉴权装饰器：验证会话 + 权限
    替代原有的 require_operator
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            session_id = get_session_id()
            
            # 临时兼容：如果没有session_id，fallback到旧的X-Operator
            if not session_id:
                operator = get_operator()
                if operator == 'admin':
                    return f(*args, **kwargs)
                return jsonify({'error': 'Missing X-Session-ID header'}), 401
            
            # 验证会话
            valid, session = auth_mgr.validate_session(session_id)
            if not valid:
                return jsonify({'error': 'Invalid or expired session', 'session_id': session_id}), 401
            
            # 检查权限
            permission = auth_mgr.get_permission(session.node_id)
            if permission not in required_permissions:
                return jsonify({
                    'error': 'Permission denied',
                    'required': [p.value for p in required_permissions],
                    'actual': permission.value
                }), 403
            
            # 将node_id注入kwargs
            kwargs['_node_id'] = session.node_id
            return f(*args, **kwargs)
        return decorated
    return decorator

@app.route('/api/auth/register', methods=['POST'])
def register_node():
    """注册新节点（仅管理员）"""
    # 临时：允许首次注册（检查是否已有节点）
    if len(auth_mgr.keys) > 0:
        # 已有节点，需要管理员权限
        session_id = get_session_id()
        if not session_id:
            return jsonify({'error': '需要管理员权限'}), 403
        valid, session = auth_mgr.validate_session(session_id)
        if not valid or auth_mgr.get_permission(session.node_id) != PermissionLevel.ADMIN:
            return jsonify({'error': '需要管理员权限'}), 403
    
    data = request.get_json()
    node_id = data.get('node_id')
    node_type = NodeType(data.get('node_type', 'nyx'))
    permission = PermissionLevel(data.get('permission', 'editor'))
    
    try:
        _, plain_key = auth_mgr.register_node(node_id, node_type, permission)
        return jsonify({
            'success': True,
            'node_id': node_id,
            'key': plain_key,  # 仅返回一次，需保存
            'message': '请妥善保存密钥，此为唯一明文版本'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/auth/device', methods=['POST'])
def register_device():
    """注册设备指纹"""
    session_id = get_session_id()
    if not session_id:
        return jsonify({'error': '需要先鉴权'}), 401
    
    valid, session = auth_mgr.validate_session(session_id)
    if not valid:
        return jsonify({'error': '会话无效'}), 401
    
    data = request.get_json()
    device_id = auth_mgr.register_device(
        session.node_id,
        data.get('cpu_id'),
        data.get('mac_address'),
        data.get('disk_serial')
    )
    
    return jsonify({
        'success': True,
        'device_id': device_id,
        'node_id': session.node_id
    })

@app.route('/api/auth/login', methods=['POST'])
def login():
    """双重鉴权登录"""
    data = request.get_json()
    node_id = data.get('node_id')
    key = data.get('key')
    device_id = data.get('device_id')  # 可选
    
    if not node_id or not key:
        return jsonify({'error': 'node_id和key是必需的'}), 400
    
    success, msg, session = auth_mgr.authenticate(node_id, key, device_id)
    
    if not success:
        return jsonify({'error': msg}), 401
    
    permission = auth_mgr.get_permission(node_id)
    
    return jsonify({
        'success': True,
        'session_id': session.session_id,
        'expires_at': session.expires_at,
        'permission': permission.value
    })

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """登出（撤销会话）"""
    session_id = get_session_id()
    if session_id:
        auth_mgr.revoke_session(session_id)
    return jsonify({'success': True})

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """查询当前会话状态"""
    session_id = get_session_id()
    if not session_id:
        return jsonify({'authenticated': False, 'reason': 'no session'})
    
    valid, session = auth_mgr.validate_session(session_id)
    if not valid:
        return jsonify({'authenticated': False, 'reason': 'invalid session'})
    
    permission = auth_mgr.get_permission(session.node_id)
    
    return jsonify({
        'authenticated': True,
        'node_id': session.node_id,
        'permission': permission.value,
        'expires_at': session.expires_at
    })

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'MemGuard-GM', 'timestamp': datetime.now().isoformat()})

@app.route('/api/baseline', methods=['GET'])
@require_auth(PermissionLevel.READONLY, PermissionLevel.EDITOR, PermissionLevel.ADMIN)
def get_baseline(**kwargs):
    baseline = engine.baseline_mgr.read_baseline()
    return jsonify({'baseline': baseline, 'locked': engine.baseline_mgr.is_readonly()})

@app.route('/api/baseline', methods=['POST'])
@require_auth(PermissionLevel.ADMIN)
def create_baseline(**kwargs):
    data = request.get_json()
    content = data.get('content', '')
    if not content:
        return jsonify({'error': 'content is required'}), 400
    try:
        node_id = kwargs.get('_node_id', 'admin')
        hashes = engine.create_baseline(content, node_id)
        return jsonify({'success': True, 'hashes': hashes})
    except PermissionError as e:
        return jsonify({'error': str(e)}), 403

@app.route('/api/baseline/lock', methods=['POST'])
@require_auth(PermissionLevel.ADMIN)
def lock_baseline(**kwargs):
    engine.baseline_mgr.lock()
    node_id = kwargs.get('_node_id', 'admin')
    engine.audit_mgr.append('baseline_locked', None, node_id, 'Baseline locked')
    return jsonify({'success': True, 'message': 'Baseline locked'})

@app.route('/api/baseline/unlock', methods=['POST'])
@require_auth(PermissionLevel.ADMIN)
def unlock_baseline(**kwargs):
    engine.baseline_mgr.unlock()
    node_id = kwargs.get('_node_id', 'admin')
    engine.audit_mgr.append('baseline_unlocked', None, node_id, 'Baseline unlocked')
    return jsonify({'success': True, 'message': 'Baseline unlocked'})

@app.route('/api/status/<memory_id>', methods=['GET'])
@require_auth(PermissionLevel.READONLY, PermissionLevel.EDITOR, PermissionLevel.ADMIN)
def get_status(memory_id, **kwargs):
    status = engine.status_mgr.get_status(memory_id)
    return jsonify({'memory_id': memory_id, 'status': status})

@app.route('/api/status/frozen', methods=['GET'])
@require_auth(PermissionLevel.READONLY, PermissionLevel.EDITOR, PermissionLevel.ADMIN)
def get_frozen_list(**kwargs):
    frozen = engine.status_mgr.get_all_frozen()
    return jsonify({'frozen_memories': frozen, 'count': len(frozen)})

@app.route('/api/freeze', methods=['POST'])
@require_auth(PermissionLevel.ADMIN)
def freeze_memory(**kwargs):
    data = request.get_json()
    memory_id = data.get('memory_id')
    reason = data.get('reason', '')
    if not memory_id:
        return jsonify({'error': 'memory_id is required'}), 400
    node_id = kwargs.get('_node_id', 'admin')
    engine.status_mgr.freeze(memory_id, reason, node_id)
    engine.audit_mgr.append('memory_frozen', memory_id, node_id, reason)
    return jsonify({'success': True, 'memory_id': memory_id, 'reason': reason})

@app.route('/api/unfreeze', methods=['POST'])
@require_auth(PermissionLevel.ADMIN)
def unfreeze_memory(**kwargs):
    data = request.get_json()
    memory_id = data.get('memory_id')
    if not memory_id:
        return jsonify({'error': 'memory_id is required'}), 400
    node_id = kwargs.get('_node_id', 'admin')
    engine.status_mgr.unfreeze(memory_id, node_id)
    engine.audit_mgr.append('memory_unfrozen', memory_id, node_id, 'Manual unfreeze')
    return jsonify({'success': True, 'memory_id': memory_id})

@app.route('/api/audit/verify', methods=['GET'])
@require_auth(PermissionLevel.READONLY, PermissionLevel.EDITOR, PermissionLevel.ADMIN)
def verify_audit_chain(**kwargs):
    valid, msg = engine.audit_mgr.verify_chain()
    return jsonify({'valid': valid, 'message': msg})

@app.route('/api/audit/search', methods=['GET'])
@require_auth(PermissionLevel.READONLY, PermissionLevel.EDITOR, PermissionLevel.ADMIN)
def search_audit(**kwargs):
    event = request.args.get('event')
    memory_id = request.args.get('memory_id')
    limit = int(request.args.get('limit', 100))
    logs = engine.audit_mgr.search(event=event, memory_id=memory_id, limit=limit)
    return jsonify({'logs': logs, 'count': len(logs)})

# === Sync API (v2.0) ===
@app.route('/api/sync/heads', methods=['GET'])
def get_sync_heads():
    heads = sync_engine.delta_store.get_all_heads()
    return jsonify({'heads': heads})

@app.route('/api/sync/register', methods=['POST'])
def register_terminal():
    data = request.get_json()
    sync_engine.terminal_registry.register_my_terminal(
        data['terminal_id'], data['name'], data['platform'],
        data.get('endpoint', ''), data.get('public_key', '')
    )
    return jsonify({'success': True})

@app.route('/api/sync/status', methods=['GET'])
def sync_status():
    status = sync_engine.get_sync_status()
    return jsonify(status)

@app.route('/api/sync/deltas/<terminal_id>', methods=['GET'])
def get_terminal_deltas(terminal_id):
    since = request.args.get('since', '')
    deltas = []
    for delta_id in sync_engine.delta_store.index['by_terminal'].get(terminal_id, []):
        delta = sync_engine.delta_store.get_delta(delta_id)
        if delta:
            deltas.append(delta.to_dict())
    return jsonify({'deltas': deltas})

@app.route('/api/sync/push', methods=['POST'])
def receive_deltas():
    data = request.get_json()
    received = []
    for delta_data in data.get('deltas', []):
        delta = Delta.from_dict(delta_data)
        sync_engine.delta_store.add_delta(delta)
        received.append(delta.delta_id)
    return jsonify({'success': True, 'received': received})

@app.route('/api/sync/pull', methods=['POST'])
def request_deltas():
    data = request.get_json()
    delta_ids = data.get('delta_ids', [])
    deltas = []
    for delta_id in delta_ids:
        delta = sync_engine.delta_store.get_delta(delta_id)
        if delta:
            deltas.append(delta.to_dict())
    return jsonify({'deltas': deltas})

@app.route('/api/access/<memory_id>', methods=['GET'])
def test_access(memory_id):
    operator = request.args.get('operator', 'anonymous')
    operation = request.args.get('operation', 'read')
    allowed, reason = engine.access_ctrl.check_access(memory_id, operator, operation)
    return jsonify({'memory_id': memory_id, 'operator': operator, 'operation': operation, 'allowed': allowed, 'reason': reason})

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not Found'}), 404

@app.errorhandler(500)
def server_error(e):
    logger.error(f'Server Error: {e}')
    return jsonify({'error': 'Internal Server Error'}), 500

if __name__ == '__main__':
    print('=' * 50)
    print('MemGuard-GM API Server v2.0')
    print('=' * 50)
    Storage.ensure_dir(Config.AUDIT_DIR)
    Storage.ensure_dir(Config.BASELINE_DIR)
    app.run(host='0.0.0.0', port=5050, debug=False)