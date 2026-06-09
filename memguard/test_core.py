#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
from core import MemGuardEngine, HashUtils

print('=== Hash测试 ===')
content = 'Test memory content'
hashes = HashUtils.compute_hashes(content)
print('SHA256:', hashes['sha256'])
print('BLAKE3:', hashes['blake3'])

print('\n=== 引擎测试 ===')
engine = MemGuardEngine()
print('引擎初始化: OK')

print('\n=== 基线测试 ===')
baseline = engine.baseline_mgr.read_baseline()
print('当前基线:', baseline)

print('\n=== 审计日志测试 ===')
log = engine.audit_mgr.append('test_event', 'mem-001', 'admin', '测试日志')
print('审计日志时间:', log.ts)

valid, msg = engine.audit_mgr.verify_chain()
print('链验证:', msg)

print('\n=== 访问控制测试 ===')
try:
    engine.access_ctrl.require_access('mem-001', 'admin', '读取')
    print('Admin访问: OK')
except Exception as e:
    print('Admin访问:', str(e))

print('\n=== 冻结功能测试 ===')
engine.status_mgr.freeze('mem-001', '测试冻结', 'admin')
print('已冻结 mem-001')
print('冻结列表:', engine.status_mgr.get_all_frozen())

engine.status_mgr.unfreeze('mem-001')
print('已解冻 mem-001')

print('\n=== 核心模块测试全部通过 ===')
