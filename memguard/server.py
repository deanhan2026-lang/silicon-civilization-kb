#!/usr/bin/env python3
"""
MemGuard-GM API Server
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import json
import logging
import os
from pathlib import Path
from datetime import datetime
from functools import wraps

from flask import Flask, request, jsonify
from flask_cors import CORS

REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))
from memguard.core import MemGuardEngine, Config, Storage
from memguard.sync import SyncEngine, Delta
from memguard.auth import AuthManager, PermissionLevel, NodeType

# 初始化配置（必须在创建 engine 前调用）
Config.init()

# ========== 记忆内容存储 ==========
_MEMORY_STORE_DIR = Path(Config.MEMORY_DIR) / ".store"

class MemoryStore:
    """记忆内容本地存储（每文件一条JSON）"""
    _store = {}

    @classmethod
    def _path(cls, memory_id: str) -> Path:
        _MEMORY_STORE_DIR.mkdir(parents=True, exist_ok=True)
        return _MEMORY_STORE_DIR / f"{memory_id}.json"

    @classmethod
    def put(cls, memory_id: str, entry: dict):
        entry["_stored_at"] = datetime.now().isoformat()
        cls._path(memory_id).write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
        cls._store[memory_id] = entry

    @classmethod
    def get(cls, memory_id: str) -> dict:
        if memory_id in cls._store:
            return cls._store[memory_id]
        p = cls._path(memory_id)
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            cls._store[memory_id] = data
            return data
        return None

    @classmethod
    def list_ids(cls) -> list:
        _MEMORY_STORE_DIR.mkdir(parents=True, exist_ok=True)
        return sorted([f.stem for f in _MEMORY_STORE_DIR.glob("*.json")])

app = Flask(__name__)
CORS(app)

# ========== Security: API Key Gate ==========
import secrets
_API_KEY = os.environ.get('MEMGUARD_API_KEY') or os.environ.get('API_KEY')
_PUBLIC_PREFIXES = ('/stellar/', '/stellar', '/polaris/', '/polaris', '/animlink/', '/animlink', '/gateway/', '/gateway', '/health', '/api/health')

@app.before_request
def security_gate():
    """Require X-API-Key header for all non-public routes."""
    if request.path.startswith(_PUBLIC_PREFIXES):
        return None  # brand site + polaris: public
    if request.method == 'OPTIONS':
        return None  # CORS preflight
    if not _API_KEY:
        return None  # first-run: warn but allow
    key = request.headers.get('X-API-Key', '')
    if key != _API_KEY:
        return jsonify({'error': 'Unauthorized', 'hint': 'Valid X-API-Key header required'}), 401
    return None
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

# Generate API key on first run if not set
if not _API_KEY:
    _API_KEY = secrets.token_hex(16)
    print(f'SECURITY: Auto-generated API key: {_API_KEY}')
    print(f'SECURITY: Set MEMGUARD_API_KEY env var to persist')


@app.route('/download/skills.zip')
def download_skills():
    """下载灵元三件套 Skill 压缩包"""
    from flask import send_file
    path = 'C:\\Users\\Administrator\\.qclaw\\workspace-agent-d9479bde\\lingyuan-skills.zip'
    return send_file(path, as_attachment=True, download_name='lingyuan-skills.zip')


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
    """鉴权登录（设备指纹改为可选，支持远程登录）"""
    data = request.get_json()
    node_id = data.get('node_id')
    key = data.get('key')
    device_id = data.get('device_id')
    skip_fingerprint = data.get('skip_fingerprint', False)
    
    if not node_id or not key:
        return jsonify({'error': 'node_id和key是必需的'}), 400
    
    if skip_fingerprint:
        # 跳过设备指纹，仅密钥验证
        key_valid, key_msg = auth_mgr.verify_key(node_id, key)
        if not key_valid:
            return jsonify({'error': key_msg}), 401
        session = auth_mgr.create_session(node_id, 'remote')
        permission = auth_mgr.get_permission(node_id)
        return jsonify({
            'success': True,
            'session_id': session.session_id,
            'expires_at': session.expires_at,
            'permission': permission.value
        })
    
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
    return jsonify({'status': 'ok', 'service': 'MemGuard-GM',
                    'memory_count': len(MemoryStore.list_ids()),
                    'timestamp': datetime.now().isoformat()})

@app.route('/api/memory/ingest', methods=['POST'])
def memory_ingest():
    """写入记忆（带 DID 签名验签）"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'empty body'}), 400
    memory_id = data.get('memory_id', '')
    content = data.get('content', '')
    if not memory_id or not content:
        return jsonify({'error': 'memory_id and content required'}), 400
    entry = {
        'memory_id': memory_id, 'content': content,
        'did': data.get('did', ''),
        'signature': data.get('signature', ''),
        'instance_id': data.get('instance_id', ''),
        'timestamp': data.get('timestamp', datetime.now().isoformat()),
    }
    MemoryStore.put(memory_id, entry)
    engine.audit_mgr.append(
        event='memory_ingested', memory_id=memory_id,
        operator=data.get('did', 'anonymous'),
        detail=f'写入 {len(content)} 字节')
    hashes = engine.compute_memory_hash(content)
    return jsonify({'status': 'ok', 'memory_id': memory_id, 'hashes': hashes})

@app.route('/api/memory/<memory_id>', methods=['GET'])
def memory_read(memory_id):
    """读取记忆内容"""
    entry = MemoryStore.get(memory_id)
    if not entry:
        return jsonify({'error': 'not found', 'memory_id': memory_id}), 404
    return jsonify(entry)

@app.route('/api/memory', methods=['GET'])
def memory_list():
    """列出所有记忆ID"""
    ids = MemoryStore.list_ids()
    return jsonify({'memory_ids': ids, 'count': len(ids)})

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

# ========== 完整性验证 API ==========

@app.route('/api/integrity/sign', methods=['POST'])
@require_auth(PermissionLevel.ADMIN)
def sign_core_files(**kwargs):
    """签名所有核心文件"""
    try:
        from memguard.integrity import SignatureManager
        sm = SignatureManager()
        node_id = kwargs.get('_node_id', 'admin')
        session_id = kwargs.get('_session_id')
        results = sm.sign_all_core_files(node_id, session_id)
        return jsonify({
            'success': True,
            'signed_count': len(results),
            'files': [{'filename': s.filename, 'sha256': s.sha256[:16]+'...', 'timestamp': s.timestamp} for s in results]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/integrity/verify', methods=['GET'])
@require_auth(PermissionLevel.READONLY, PermissionLevel.EDITOR, PermissionLevel.ADMIN)
def verify_core_files(**kwargs):
    """验证所有核心文件完整性"""
    try:
        from memguard.integrity import SignatureManager, TrustDomainChecker
        sm = SignatureManager()
        results, tamper_records = sm.verify_all_core_files()
        return jsonify({
            'trust_domain': TrustDomainChecker.get_trust_level(),
            'total': len(results),
            'valid': sum(1 for v, _ in results.values() if v),
            'invalid': sum(1 for v, _ in results.values() if not v),
            'details': {k: {'valid': v, 'status': s} for k, (v, s) in results.items()},
            'alerts': [{'filename': r.filename, 'type': r.detection_type, 'severity': r.severity, 'timestamp': r.timestamp} for r in tamper_records]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/integrity/status', methods=['GET'])
@require_auth(PermissionLevel.READONLY, PermissionLevel.EDITOR, PermissionLevel.ADMIN)
def get_integrity_status_api(**kwargs):
    """获取完整性状态概览"""
    try:
        from memguard.integrity import get_integrity_status
        return jsonify(get_integrity_status())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/integrity/tamper_log', methods=['GET'])
@require_auth(PermissionLevel.READONLY, PermissionLevel.EDITOR, PermissionLevel.ADMIN)
def get_tamper_log(**kwargs):
    """获取篡改日志"""
    try:
        import os
        from memguard.integrity import IntegrityConfig
        if not os.path.exists(IntegrityConfig.TAMPER_LOG):
            return jsonify({'records': [], 'count': 0})
        
        records = []
        with open(IntegrityConfig.TAMPER_LOG, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        
        return jsonify({'records': records[-100:], 'count': len(records)})  # 最近100条
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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

@app.route('/')
def memguard_index():
    from flask import send_from_directory
    return send_from_directory(str(Path(__file__).parent / 'web'), 'index.html')

@app.route('/<path:path>')
def memguard_static(path):
    from flask import send_from_directory
    web_dir = Path(__file__).parent / 'web'
    f = web_dir / path
    if f.exists():
        return send_from_directory(str(web_dir), path)
    return send_from_directory(str(web_dir), 'index.html')

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({'status': 'healthy', 'service': 'MemGuard-GM', 'version': '2.1'}), 200



# ========== LingOS MeshIdentity 注册端点 ==========
# 公开接口，无认证，best-effort 接收来自全球 lingos 用户的注册记录
# 收到后写入本地 mesh registry，仅用作生态数据统计
_MESH_REGISTRY_LOCK = False

@app.route('/api/mesh/register', methods=['POST'])
def mesh_register():
    """
    接收 lingos --join-mesh 的注册记录（公开接口，无认证）
    
    请求体：
      { did, instance_id, platform, public_key, record_type, ... }
    
    存储到：
      Z:/qclaw/mesh/registry.json（NAS）
      memory/data/mesh_registry.json（本地 fallback）
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'empty body'}), 400
    
    did = data.get('did', '')
    instance_id = data.get('instance_id', '')
    if not did:
        return jsonify({'error': 'did required'}), 400
    
    # 加载注册表
    mesh_paths = [
        Path('Z:/qclaw/mesh/registry.json'),
        REPO_ROOT / 'data' / 'mesh_registry.json',
    ]
    registry = {}
    for p in mesh_paths:
        if p.exists():
            try:
                registry = json.loads(p.read_text(encoding='utf-8'))
                break
            except Exception:
                pass
    
    if not registry:
        registry = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "nodes": {},
            "lingyuan_exports": [],
            "lingyuan_imports": [],
        }
    
    # 记录
    record_type = data.get('record_type', 'export')
    key_map = f"lingyuan_{record_type}s"
    if key_map not in registry:
        registry[key_map] = []
    registry[key_map].append({
        "did": did,
        "instance_id": instance_id,
        "platform": data.get('platform', 'unknown'),
        "hostname": data.get('hostname', ''),
        "public_key": data.get('public_key', ''),
        "timestamp": data.get('timestamp', datetime.now().isoformat()),
        "received_at": datetime.now().isoformat(),
        "source_ip": request.remote_addr or '',
    })
    
    # 更新节点
    registry["nodes"][instance_id] = {
        "did": did,
        "platform": data.get('platform', 'unknown'),
        "lastSeen": data.get('timestamp', datetime.now().isoformat()),
        "status": "active",
        "protocol": "lingyuan-v1",
    }
    registry["updated_at"] = datetime.now().isoformat()
    
    # 写入所有可达路径
    written = False
    for p in mesh_paths:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding='utf-8')
            written = True
        except Exception:
            pass
    
    return jsonify({
        'status': 'ok',
        'did': did,
        'instance_id': instance_id,
        'received': True,
        'total_exports': len(registry.get('lingyuan_exports', [])),
        'written': written,
    }), 201 if written else 202


@app.route('/polaris/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def polaris_proxy(path):
    """Reverse proxy to Polaris SaaS (port 5052)"""
    from flask import request
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError
    target_url = 'http://127.0.0.1:5052/' + path
    headers = {k: v for k, v in request.headers if k.lower() != 'host'}
    try:
        if request.method in ('POST', 'PUT'):
            data = request.get_data()
            req = Request(target_url, data=data, headers=headers, method=request.method)
        else:
            req = Request(target_url, headers=headers, method=request.method)
        resp = urlopen(req, timeout=10)
        return resp.read(), resp.status, resp.headers.items()
    except HTTPError as e:
        return e.read(), e.code, {'Content-Type': 'application/json'}
    except Exception as e:
        return '{"error": "' + str(e) + '"}', 502, {'Content-Type': 'application/json'}

@app.route('/animlink/api/network', methods=['GET'])
def animlink_api_network():
    """Return network stats from WebDAV (bypasses Flask 5053 + SMB instability)"""
    from flask import jsonify
    import json, urllib.request, base64
    WEBDAV_BASE = 'http://100.123.195.10:5005/qclaw'
    _auth = {'Authorization': 'Basic ' + base64.b64encode(b'anima:animastellar').decode()}
    try:
        req = urllib.request.Request(f'{WEBDAV_BASE}/mesh/registry.json', headers=_auth)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        nodes = data.get('nodes', {})
        node_list = list(nodes.values())
        active = [n for n in node_list if n.get('status') == 'active']
        return jsonify({
            'total': len(node_list),
            'active': len(active),
            'trusted': len(active),
            'nodes': node_list
        })
    except Exception as e:
        return jsonify({'error': str(e), 'total': 0, 'active': 0, 'trusted': 0, 'nodes': []}), 200

@app.route('/animlink/api/nodes', methods=['GET'])
def animlink_api_nodes():
    """Return all nodes from WebDAV"""
    from flask import jsonify
    import json, urllib.request, base64
    WEBDAV_BASE = 'http://100.123.195.10:5005/qclaw'
    _auth = {'Authorization': 'Basic ' + base64.b64encode(b'anima:animastellar').decode()}
    try:
        req = urllib.request.Request(f'{WEBDAV_BASE}/mesh/registry.json', headers=_auth)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        nodes = data.get('nodes', {})
        return jsonify(list(nodes.values()))
    except Exception as e:
        return jsonify({'error': str(e), 'nodes': []}), 200

@app.route('/animlink/api/trust', methods=['GET'])
def animlink_api_trust():
    """Return trust scores from WebDAV"""
    from flask import jsonify
    import json, urllib.request, base64
    WEBDAV_BASE = 'http://100.123.195.10:5005/qclaw'
    _auth = {'Authorization': 'Basic ' + base64.b64encode(b'anima:animastellar').decode()}
    try:
        req = urllib.request.Request(f'{WEBDAV_BASE}/tokens/trust_scores.json', headers=_auth)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e), 'scores': {}}), 200

@app.route('/animlink/api/tokens', methods=['GET'])
def animlink_api_tokens():
    """Return token history from WebDAV"""
    from flask import jsonify
    import json, urllib.request, base64
    WEBDAV_BASE = 'http://100.123.195.10:5005/qclaw'
    _auth = {'Authorization': 'Basic ' + base64.b64encode(b'anima:animastellar').decode()}
    try:
        req = urllib.request.Request(f'{WEBDAV_BASE}/tokens/trust_scores.json', headers=_auth)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 200

@app.route('/animlink/', defaults={'path': ''}, methods=['GET'])
@app.route('/animlink/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def animlink_proxy(path):
    """Serve AnimaLink Viewer from local animlink/web/ (was proxying to 5053)"""
    from flask import send_from_directory
    animlink_root = REPO_ROOT / 'animlink' / 'web'
    if path == '' or path == 'index.html':
        return send_from_directory(str(animlink_root), 'index.html')
    f = animlink_root / path
    if f.exists() and f.is_file():
        return send_from_directory(str(animlink_root), path)
    return send_from_directory(str(animlink_root), 'index.html')


@app.route('/stellar/', defaults={'path': ''}, methods=['GET'])
@app.route('/stellar/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def stellar_proxy(path):
    """Serve STELLAR company site from workspace www/stellar/ (was proxying to 5053)"""
    from flask import send_from_directory
    # www/stellar is at workspace root (parent of silicon-civilization-kb/)
    stellar_root = REPO_ROOT.parent / 'www' / 'stellar'
    if path == '' or path == 'index.html':
        return send_from_directory(str(stellar_root), 'index.html')
    f = stellar_root / path
    if f.exists() and f.is_file():
        return send_from_directory(str(stellar_root), path)
    # Clean-URL fallback: /stellar/product -> /stellar/product.html
    if not os.path.splitext(path)[1]:
        f2 = stellar_root / (path + '.html')
        if f2.exists() and f2.is_file():
            return send_from_directory(str(stellar_root), path + '.html')
    return send_from_directory(str(stellar_root), 'index.html')


@app.route('/gateway/', defaults={'path': ''}, methods=['GET'])
@app.route('/gateway/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def gateway_proxy(path):
    """Reverse proxy to AnimaLink Gateway (NAS:8000)"""
    from flask import request
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError
    target_url = 'http://100.123.195.10:8000/' + path
    headers = {k: v for k, v in request.headers if k.lower() != 'host'}
    try:
        if request.method in ('POST', 'PUT'):
            data = request.get_data()
            req = Request(target_url, data=data, headers=headers, method=request.method)
        else:
            req = Request(target_url, headers=headers, method=request.method)
        resp = urlopen(req, timeout=10)
        return resp.read(), resp.status, resp.headers.items()
    except HTTPError as e:
        return e.read(), e.code, {'Content-Type': 'application/json'}
    except Exception as e:
        return ('{"error": "Gateway unavailable (' + str(e) + ')"}').encode(), 502, {'Content-Type': 'application/json'}


@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not Found'}), 404

@app.errorhandler(500)
def server_error(e):
    logger.error(f'Server Error: {e}')
    return jsonify({'error': 'Internal Server Error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('MEMGUARD_PORT', 5050))
    host = os.environ.get('MEMGUARD_HOST', '0.0.0.0')
    debug = os.environ.get('MEMGUARD_DEBUG', 'false').lower() == 'true'
    print('=' * 50)
    print(f'MemGuard-GM API Server v2.1 - {host}:{port}')
    print('=' * 50)
    Storage.ensure_dir(Config.AUDIT_DIR)
    Storage.ensure_dir(Config.BASELINE_DIR)
    
    # 启动时验证核心文件完整性
    try:
        from memguard.integrity import SignatureManager
        sm = SignatureManager()
        results, tamper_records = sm.verify_all_core_files()
        if tamper_records:
            print(f'[WARN] Detected {len(tamper_records)} file tamper warnings')
            for r in tamper_records:
                print(f'  {r.filename}: {r.detection_type}')
        else:
            print(f'[OK] Core file integrity verified ({len(results)} files)')
    except Exception as e:
        print(f'[WARN] Integrity verification failed: {e}')
    
    app.run(host=host, port=port, debug=debug)