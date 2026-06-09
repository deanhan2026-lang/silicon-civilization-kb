#!/usr/bin/env python3
"""创建测试补丁"""
import sys
sys.path.insert(0, 'C:\\Users\\Administrator\\.qclaw\\workspace-agent-d9479bde\\memguard')
from sync import SyncEngine

engine = SyncEngine()

# 创建增量补丁
d1 = engine.create_delta('memory-main', 'create', '这是主要记忆文件的内容', 'nyx-windows')
print(f'Delta 1: {d1.delta_id}')

d2 = engine.create_delta('memory-today', 'create', '2026-06-09的工作记录', 'nyx-windows')
print(f'Delta 2: {d2.delta_id}')

d3 = engine.create_delta('memory-main', 'update', '更新了主要记忆文件', 'nyx-windows')
print(f'Delta 3: {d3.delta_id} (更新)')

# 查看链头
heads = engine.delta_store.get_all_heads()
print(f'\nChain heads: {heads}')

# 查看状态
status = engine.get_sync_status()
print(f'\nSync status:')
print(f'  Terminal: {status["my_terminal"]["name"]}')
print(f'  Deltas: {status["delta_count"]}')

# 通过API验证
import requests
resp = requests.get('http://localhost:5050/api/sync/heads')
print(f'\nAPI heads: {resp.json()}')
