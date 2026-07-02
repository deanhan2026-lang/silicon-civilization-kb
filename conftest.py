"""
conftest.py - pytest 全局配置

确保 mesh_identity_sync 和 silicon-civilization-kb 都可以被导入。
"""
import sys
from pathlib import Path

# conftest.py 位于 silicon-civilization-kb/
WORKSPACE_ROOT = Path(__file__).parent  # silicon-civilization-kb
WORKSPACE_ROOT = WORKSPACE_ROOT.parent   # workspace-agent-d9479bde
SCIK_DIR = Path(__file__).parent        # silicon-civilization-kb

# 加入父目录，让 Python 能找到 mesh_identity_sync
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

# 也加入 silicon-civilization-kb 本身（供 memguard 等子包导入）
if str(SCIK_DIR) not in sys.path:
    sys.path.insert(0, str(SCIK_DIR))
