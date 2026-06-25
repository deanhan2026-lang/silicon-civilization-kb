@echo off
set MEMGUARD_WORKSPACE=C:\Users\Administrator\.qclaw\workspace-agent-d9479bde
set MEMGUARD_SIG_DIR=C:\Users\Administrator\.qclaw\workspace-agent-d9479bde\silicon-civilization-kb\data\signatures
set PYTHONIOENCODING=utf-8

cd /d "C:\Users\Administrator\.qclaw\workspace-agent-d9479bde\silicon-civilization-kb\memguard"
start "MemGuard" /B python server.py
