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

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

engine = MemGuardEngine()
sync_engine = SyncEngine()

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

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'MemGuard-GM', 'timestamp': datetime.now().isoformat()})

@app.route('/api/baseline', methods=['GET'])
@require_operator('read')
def get_baseline():
    baseline = engine.baseline_mgr.read_baseline()
    return jsonify({'baseline': baseline, 'locked': engine.baseline_mgr.is_readonly()})

@app.route('/api/baseline', methods=['POST'])
@require_operator('baseline')
def create_baseline():
    data = request.get_json()
    content = data.get('content', '')
    if not content:
        return jsonify({'error': 'content is required'}), 400
    try:
        hashes = engine.create_baseline(content, get_operator())
        return jsonify({'success': True, 'hashes': hashes})
    except PermissionError as e:
        return jsonify({'error': str(e)}), 403

@app.route('/api/baseline/lock', methods=['POST'])
@require_operator('baseline')
def lock_baseline():
    engine.baseline_mgr.lock()
    engine.audit_mgr.append('baseline_locked', None, get_operator(), 'Baseline locked')
    return jsonify({'success': True, 'message': 'Baseline locked'})

@app.route('/api/baseline/unlock', methods=['POST'])
@require_operator('baseline')
def unlock_baseline():
    engine.baseline_mgr.unlock()
    engine.audit_mgr.append('baseline_unlocked', None, get_operator(), 'Baseline unlocked')
    return jsonify({'success': True, 'message': 'Baseline unlocked'})

@app.route('/api/status/<memory_id>', methods=['GET'])
@require_operator('read')
def get_status(memory_id):
    status = engine.status_mgr.get_status(memory_id)
    return jsonify({'memory_id': memory_id, 'status': status})

@app.route('/api/status/frozen', methods=['GET'])
@require_operator('read')
def get_frozen_list():
    frozen = engine.status_mgr.get_all_frozen()
    return jsonify({'frozen_memories': frozen, 'count': len(frozen)})

@app.route('/api/freeze', methods=['POST'])
@require_operator('freeze')
def freeze_memory():
    data = request.get_json()
    memory_id = data.get('memory_id')
    reason = data.get('reason', '')
    if not memory_id:
        return jsonify({'error': 'memory_id is required'}), 400
    engine.status_mgr.freeze(memory_id, reason, get_operator())
    engine.audit_mgr.append('memory_frozen', memory_id, get_operator(), reason)
    return jsonify({'success': True, 'memory_id': memory_id, 'reason': reason})

@app.route('/api/unfreeze', methods=['POST'])
@require_operator('freeze')
def unfreeze_memory():
    data = request.get_json()
    memory_id = data.get('memory_id')
    if not memory_id:
        return jsonify({'error': 'memory_id is required'}), 400
    engine.status_mgr.unfreeze(memory_id, get_operator())
    engine.audit_mgr.append('memory_unfrozen', memory_id, get_operator(), 'Manual unfreeze')
    return jsonify({'success': True, 'memory_id': memory_id})

@app.route('/api/audit/verify', methods=['GET'])
@require_operator('read')
def verify_audit_chain():
    valid, msg = engine.audit_mgr.verify_chain()
    return jsonify({'valid': valid, 'message': msg})

@app.route('/api/audit/search', methods=['GET'])
@require_operator('read')
def search_audit():
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