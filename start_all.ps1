#!/usr/bin/env pwsh
<#
.SYNOPSIS
    灵元星尘科技 | 三产品一键启动脚本
    启动: MemGuard(5050) + Polaris(5052) + MeshIdentity(库/service)

.PARAMETER Mode
    dev: 从本地路径启动（开发调试）
    nas: 从 NAS 路径启动（生产部署）

.PARAMETER DataDir
    自定义数据目录，默认:
    dev  -> Z:\qclaw\
    nas  -> C:\memguard-data\

示例:
    .\start_all.ps1                    # dev 模式
    .\start_all.ps1 -Mode nas          # NAS 部署模式
    .\start_all.ps1 -Mode dev -DataDir D:\my-data\
#>
param(
    [ValidateSet("dev", "nas")]
    [string]$Mode = "dev",
    [string]$DataDir = ""
)

$ErrorActionPreference = "Stop"
$Repo = "C:\Users\Administrator\.qclaw\workspace-agent-d9479bde\silicon-civilization-kb"
$Python = "C:\Program Files\QClaw\v0.2.32.610\resources\python\python.exe"

if (-not $DataDir) {
    $DataDir = if ($Mode -eq "nas") { "C:\memguard-data\" } else { "Z:\qclaw\" }
}

# 确保数据目录
New-Item -ItemType Directory -Path "$DataDir" -Force | Out-Null
New-Item -ItemType Directory -Path "$DataDir\memory" -Force | Out-Null
New-Item -ItemType Directory -Path "$DataDir\did" -Force | Out-Null
New-Item -ItemType Directory -Path "$DataDir\memguard_baseline" -Force | Out-Null
New-Item -ItemType Directory -Path "$DataDir\audit" -Force | Out-Null
New-Item -ItemType Directory -Path "$DataDir\polaris" -Force | Out-Null
New-Item -ItemType Directory -Path "$Repo\data" -Force | Out-Null
Write-Host "=== 数据目录: $DataDir ==="

# 进程管理函数
$script:processes = @{}

function Start-ServiceBg {
    param([string]$Name, [string]$Script, [int]$Port)
    $env:DATA_ROOT = $DataDir
    $env:MEMGUARD_PORT = "$Port"
    $env:POLARIS_PORT = "$Port"
    $log = "$DataDir\logs\$Name.log"
    New-Item -ItemType Directory -Path "$DataDir\logs" -Force | Out-Null

    $p = Start-Process -FilePath $Python -ArgumentList "-X utf8", "`"$Script`"" -NoNewWindow -PassThru -RedirectStandardOutput $log -RedirectStandardError $log
    $script:processes[$Name] = @{Process=$p; Port=$Port; Log=$log}
    Write-Host "[$Name] PID=$($p.Id) Port=$Port Log=$log"
}

# 停止已有进程
if ($script:processes.Count -gt 0 -or (Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Id -ne $pid })) {
    Write-Host "=== 停止已有进程 ==="
    Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Id -ne $pid } | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

# 启动服务
Write-Host "`n=== 启动 MemGuard (5050) ==="
$env:MEMGUARD_PORT = "5050"
$env:MEMGUARD_HOST = "0.0.0.0"
$env:MEMGUARD_DEBUG = "false"
$logMem = "$DataDir\logs\memguard.log"
New-Item -ItemType Directory -Path "$DataDir\logs" -Force | Out-Null
$p1 = Start-Process -FilePath $Python -ArgumentList "-X utf8", "`"$Repo\memguard\server.py`"" -NoNewWindow -PassThru -RedirectStandardOutput $logMem -RedirectStandardError $logMem
Write-Host "[MEMGUARD] PID=$($p1.Id) Port=5050"

Start-Sleep -Seconds 3

Write-Host "`n=== 启动 Polaris (5052) ==="
$logPol = "$DataDir\logs\polaris.log"
$p2 = Start-Process -FilePath $Python -ArgumentList "-X utf8", "`"$Repo\anti_drift\saas_server.py`"" -NoNewWindow -PassThru -RedirectStandardOutput $logPol -RedirectStandardError $logPol
Write-Host "[POLARIS]  PID=$($p2.Id) Port=5052"

Start-Sleep -Seconds 3

# 健康检查
Write-Host "`n=== 健康检查 ==="
try {
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:5050/api/health" -Method GET -UseBasicParsing -ErrorAction Stop
    Write-Host "[MEMGUARD] status=$($h.status) memory_count=$($h.memory_count)" -ForegroundColor Green
} catch {
    Write-Host "[MEMGUARD] 不可达 - 检查日志: $logMem" -ForegroundColor Red
}

try {
    $body = @{email="nyx-demo@wlmhan.local";password="demo123"} | ConvertTo-Json
    $login = Invoke-RestMethod -Uri "http://127.0.0.1:5052/api/v1/auth/login" -Method POST -Body $body -ContentType "application/json" -UseBasicParsing -ErrorAction Stop
    Write-Host "[POLARIS]  登录成功" -ForegroundColor Green
} catch {
    Write-Host "[POLARIS]  不可达 - 检查日志: $logPol" -ForegroundColor Red
}

Write-Host "`n=== 服务状态 ==="
Write-Host "MemGuard API:  http://127.0.0.1:5050/api/health"
Write-Host "Polaris  API:  http://127.0.0.1:5052/api/v1/auth/login"
Write-Host "数据目录:      $DataDir"
Write-Host "PIDs:          MemGuard=$($p1.Id)  Polaris=$($p2.Id)" -ForegroundColor Cyan
Write-Host "`n停止: Get-Process python | Stop-Process -Force" -ForegroundColor Yellow
Write-Host "状态: curl http://127.0.0.1:5050/api/health" -ForegroundColor Yellow
Write-Host "`n=== 启动完毕 ===" -ForegroundColor Green
