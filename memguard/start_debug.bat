@echo off
set MEMGUARD_WORKSPACE=C:\Users\Administrator\.qclaw\workspace-agent-d9479bde
set MEMGUARD_SIG_DIR=C:\Users\Administrator\.qclaw\workspace-agent-d9479bde\silicon-civilization-kb\data\signatures
set PYTHONIOENCODING=utf-8

cd /d "C:\Users\Administrator\.qclaw\workspace-agent-d9479bde\silicon-civilization-kb\memguard"

echo Starting MemGuard with env:
echo   MEMGUARD_WORKSPACE=%MEMGUARD_WORKSPACE%
echo   MEMGUARD_SIG_DIR=%MEMGUARD_SIG_DIR%
echo   PYTHONIOENCODING=%PYTHONIOENCODING%
echo.

python server.py > memguard_stdout.log 2>&1
