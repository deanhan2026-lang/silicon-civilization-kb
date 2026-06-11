# MemGuard-GM 核心灵魂文件解密脚本
# 放在 workspace 根目录，Agent 启动时自动运行
# v2.5 - 环境变量配置版（OpenCode优化合并）

param(
    [switch]$Force,
    [switch]$Quiet
)

$workspace = "C:\Users\Administrator\.qclaw\workspace-agent-d9479bde"
$coreFiles = @("SOUL.md", "IDENTITY.md", "USER.md", "AGENTS.md", "MEMORY.md", "TOOLS.md")

# 设置环境变量（被 integrity.py 读取）
$env:MEMGUARD_WORKSPACE = $workspace
$env:PYTHONIOENCODING = "utf-8"

if (-not $Quiet) { Write-Host "MemGuard: 检查核心灵魂文件状态..." -ForegroundColor Cyan }

# 检查哪些文件缺失
$missing = @()
foreach ($f in $coreFiles) {
    $path = Join-Path $workspace $f
    if (-not (Test-Path $path)) { $missing += $f }
}

if ($missing.Count -eq 0) {
    if (-not $Quiet) { Write-Host "MemGuard: 所有核心文件正常 ✅" -ForegroundColor Green }
    exit 0
}

if (-not $Quiet) { Write-Host "MemGuard: 检测到 $($missing.Count) 个文件加密/缺失，正在恢复..." -ForegroundColor Yellow }

try {
    cd "C:\Users\Administrator\.qclaw\workspace-agent-d9479bde\silicon-civilization-kb\memguard"
    python -c @"
from crypto import CoreFileProtector, KeyManager
workspace = r'$workspace'
km = KeyManager()
key = km.recover_key()
protector = CoreFileProtector(workspace)
protector.key = key
protector.decrypt_all_core_files()
print('OK')
"@ 2>&1 | Out-Null

    if (-not $Quiet) { Write-Host "MemGuard: 核心文件已恢复 ✅" -ForegroundColor Green }
} catch {
    if (-not $Quiet) { Write-Host "MemGuard: 恢复失败 ❌ $($_.Exception.Message)" -ForegroundColor Red }
    exit 1
}
