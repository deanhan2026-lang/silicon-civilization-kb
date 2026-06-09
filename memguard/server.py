#!/usr/bin/env python3
"""
MemGuard-GM API Server
提供REST API用于管理记忆完整性系统
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

# Flask配置
app = Flask(__name__)
CORS(app)

# 日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 引擎实例
engine = MemGuardEngine()

# ========== 权限装饰器 ==========
def require_operator(op_type: str):
    """验证操作者权限"""
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
                return jsonify({'error': '权限不足', 'required': op_type}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

def get_operator():
    return request.headers.get('X-Operator', 'anonymous')

# ========== 健康检查 ==========
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'MemGuard-GM', 'timestamp': datetime.now().isoformat()})

# ========== 基线管理 ==========
@app.route('/api/baseline', methods=['GET'])
@require_operator('read')
def get_baseline():
    baseline = engine.baseline_mgr.read_baseline()
    return jsonify({
        'baseline': baseline,
        'locked': engine.baseline_mgr.is_readonly()
    })

@app.route('/api/baseline', methods=['POST'])
@require_operator('baseline')
def create_baseline():
    """创建/更新基线（需要Admin）"""
    data = request.get_json()
    content = data.get('content', '')
    
    if not content:
        return jsonify({'error': 'content不能为空'}), 400
    
    try:
        hashes = engine.create_baseline(content, get_operator())
        return jsonify({'success': True, 'hashes': hashes})
    except PermissionError as e:
        return jsonify({'error': str(e)}), 403

@app.route('/api/baseline/lock', methods=['POST'])
@require_operator('baseline')
def lock_baseline():
    engine.baseline_mgr.lock()
    engine.audit_mgr.append('baseline_locked', None, get_operator(), '基线锁定')
    return jsonify({'success': True, 'message': '基线已锁定'})

@app.route('/api/baseline/unlock', methods=['POST'])
@require_operator('baseline')
def unlock_baseline():
    engine.baseline_mgr.unlock()
    engine.audit_mgr.append('baseline_unlocked', None, get_operator(), '基线解锁')
    return jsonify({'success': True, 'message': '基线已解锁（警告）'})

# ========== 完整性校验 ==========
@app.route('/api/verify/<memory_id>', methods=['GET'])
@require_operator('verify')
def verify_memory(memory_id):
    """校验单条记忆"""
    # 实际场景中需要从存储读取记忆内容
    # 这里简化处理
    valid, msg = engine.verify_memory(memory_id, '')
    return jsonify({
        'memory_id': memory_id,
        'valid': valid,
        'message': msg
    })

@app.route('/api/verify/all', methods=['POST'])
@require_operator('verify')
def verify_all():
    """执行全量校验"""
    # 调用校验器
    from scheduler import IntegrityChecker
    checker = IntegrityChecker()
    results = checker.run_check()
    return jsonify({
        'timestamp': datetime.now().isoformat(),
        'results': {
            'total': sum(len(v) for v in results.values()),
            'ok': len(results['ok']),
            'mismatch': len(results['mismatch']),
            'errors': len(results['error'])
        }
    })

# ========== 记忆状态管理 ==========
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
        return jsonify({'error': 'memory_id不能为空'}), 400
    
    engine.status_mgr.freeze(memory_id, reason, get_operator())
    engine.audit_mgr.append('memory_frozen', memory_id, get_operator(), reason)
    
    return jsonify({'success': True, 'memory_id': memory_id, 'reason': reason})

@app.route('/api/unfreeze', methods=['POST'])
@require_operator('freeze')
def unfreeze_memory():
    data = request.get_json()
    memory_id = data.get('memory_id')
    
    if not memory_id:
        return jsonify({'error': 'memory_id不能为空'}), 400
    
    engine.status_mgr.unfreeze(memory_id, get_operator())
    engine.audit_mgr.append('memory_unfrozen', memory_id, get_operator(), '手动解冻')
    
    return jsonify({'success': True, 'memory_id': memory_id})

# ========== 审计日志 ==========
@app.route('/api/audit/verify', methods=['GET'])
@require_operator('read')
def verify_audit_chain():
    valid, msg = engine.audit_mgr.verify_chain()
    return jsonify({
        'valid': valid,
        'message': msg
    })

@app.route('/api/audit/search', methods=['GET'])
@require_operator('read')
def search_audit():
    event = request.args.get('event')
    memory_id = request.args.get('memory_id')
    limit = int(request.args.get('limit', 100))
    
    logs = engine.audit_mgr.search(event=event, memory_id=memory_id, limit=limit)
    return jsonify({'logs': logs, 'count': len(logs)})

# ========== 访问控制测试 ==========
@app.route('/api/access/<memory_id>', methods=['GET'])
def test_access(memory_id):
    operator = request.args.get('operator', 'anonymous')
    operation = request.args.get('operation', 'read')
    
    allowed, reason = engine.access_ctrl.check_access(memory_id, operator, operation)
    return jsonify({
        'memory_id': memory_id,
        'operator': operator,
        'operation': operation,
        'allowed': allowed,
        'reason': reason
    })

# ========== 错误处理 ==========
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not Found'}), 404

@app.errorhandler(500)
def server_error(e):
    logger.error(f'Server Error: {e}')
    return jsonify({'error': 'Internal Server Error'}), 500


if __name__ == '__main__':
    print('=' * 50)
    print('MemGuard-GM API Server')
    print('=' * 50)
    print('Endpoints:')
    print('  GET  /api/health          - 健康检查')
    print('  GET  /api/baseline        - 读取基线')
    print('  POST /api/baseline        - 创建基线')
    print('  POST /api/baseline/lock   - 锁定基线')
    print('  GET  /api/status/<id>     - 查看状态')
    print('  GET  /api/status/frozen   - 冻结列表')
    print('  POST /api/freeze          - 冻结记忆')
    print('  POST /api/unfreeze        - 解冻记忆')
    print('  GET  /api/audit/verify    - 验证审计链')
    print('  GET  /api/audit/search    - 搜索审计')
    print()
    print('Header: X-Operator: admin|validator|api|anonymous')
    print('=' * 50)
    
    # 确保目录存在
    Storage.ensure_dir(Config.AUDIT_DIR)
    Storage.ensure_dir(Config.BASELINE_DIR)
    
    app.run(host='0.0.0.0', port=5050, debug=False)
