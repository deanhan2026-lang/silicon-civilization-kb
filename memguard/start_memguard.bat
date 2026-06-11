@echo off
REM MemGuard-GM 一键部署启动脚本
REM 用法: 双击运行 或 命令行执行
REM v2.5 - 环境变量配置版（OpenCode优化合并）

set MG_DIR=C:\Users\Administrator\.qclaw\workspace-agent-d9479bde\silicon-civilization-kb\memguard

REM 设置环境变量（被 integrity.py 的 IntegrityConfig 读取）
set MEMGUARD_WORKSPACE=C:\Users\Administrator\.qclaw\workspace-agent-d9479bde
set MEMGUARD_SIG_DIR=%MG_DIR%\..\data\signatures
set PYTHONIOENCODING=utf-8

echo ============================================
echo  MemGuard-GM v2.5 启动脚本
echo ============================================
echo.

REM 1. 创建数据目录
echo [0/4] 确保数据目录存在...
if not exist "%MG_DIR%\..\data\keys" mkdir "%MG_DIR%\..\data\keys"
if not exist "%MG_DIR%\..\data\signatures" mkdir "%MG_DIR%\..\data\signatures"
echo   ✅ 目录已就绪

REM 2. 启动API服务
echo [1/4] 启动MemGuard API服务...
start "MemGuard Server" /B python "%MG_DIR%\server.py"

REM 等待3秒启动
timeout /t 3 /nobreak >nul

REM 3. 验证服务
echo [2/4] 验证服务状态...
python -c "import requests; r=requests.get('http://localhost:5050/api/health'); print(f'  Status: {r.json()[\"status\"]}')" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo  ❌ 服务启动失败，请检查端口5050
    pause
    exit /b 1
)

REM 4. 验证核心文件完整性
echo [3/4] 验证核心文件完整性...
python -c "
from integrity import SignatureManager, TrustDomainChecker
sm = SignatureManager()
results, tamper_records = sm.verify_all_core_files()
td = TrustDomainChecker.get_trust_level()
print(f'  信任域: {td}')
print(f'  文件: {len(results)} 个验证')
print(f'  异常: {len(tamper_records)} 个')
" 2>&1

REM 5. 检查鉴权状态
echo [4/4] 检查系统状态...
python -c "
import requests
r = requests.get('http://localhost:5050/api/auth/status', headers={'X-Session-ID': ''}).json()
print(f'  认证: {\"已配置\" if r.get(\"authenticated\") else \"待登录\"}')
r = requests.get('http://localhost:5050/api/baseline').json()
print(f'  基线: {\"已锁定\" if r.get(\"locked\") else \"未锁定\"}')
" 2>nul

echo.
echo ============================================
echo  MemGuard-GM v2.5 已启动
echo  API: http://localhost:5050
echo  Health: http://localhost:5050/api/health
echo  Workspace: %MEMGUARD_WORKSPACE%
echo ============================================
pause
