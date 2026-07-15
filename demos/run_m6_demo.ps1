# run_m6_demo.ps1
# Polaris x MeshIdentity M6 Demo 启动脚本
# 用法：.\run_m6_demo.ps1

param(
    [switch]$NoScreenshot,
    [switch]$Verbose
)

$ErrorActionPreference = "Continue"
$DemoRoot = "C:\Users\Administrator\.qclaw\workspace-agent-d9479bde\silicon-civilization-kb\demos"
$DemoScript = Join-Path $DemoRoot "m6_demo.py"
$LogFile = Join-Path $DemoRoot "m6_demo_run_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

# ── 颜色输出 ────────────────────────────────────────────────────────────────
function Write-Step { param($msg) Write-Host "[STEP] $msg" -ForegroundColor Cyan }
function Write-OK   { param($msg) Write-Host "[PASS] $msg" -ForegroundColor Green }
function Write-WARN { param($msg) Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-FAIL { param($msg) Write-Host "[FAIL] $msg" -ForegroundColor Red }
function Write-Info { param($msg) Write-Host "[INFO] $msg" -ForegroundColor Gray }

# ── 头部 ──────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "==============================================================" -ForegroundColor Magenta
Write-Host "  M6 Demo Runner — Polaris x MeshIdentity" -ForegroundColor Magenta
Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Magenta
Write-Host "==============================================================" -ForegroundColor Magenta
Write-Host ""

# ── Step 1: 检查服务状态 ───────────────────────────────────────────────────
Write-Step "检查后端服务状态..."

$services = @(
    @{Port=5050; Name="MemGuard";   Expected="ON"},
    @{Port=5052; Name="Polaris";    Expected="ON"},
    @{Port=5053; Name="AnimaLink";  Expected="ON"}
)

$allOnline = $true
foreach ($svc in $services) {
    $c = New-Object System.Net.Sockets.TcpClient
    try {
        $c.Connect("127.0.0.1", $svc.Port)
        $connected = $c.Connected
    } catch {
        $connected = $false
    } finally { if ($c) { $c.Close() } }

    if ($connected) {
        Write-OK "$($svc.Name) (port $($svc.Port)) — ONLINE"
    } else {
        Write-FAIL "$($svc.Name) (port $($svc.Port)) — OFFLINE"
        $allOnline = $false
    }
}
Write-Host ""

# ── Step 2: 启动 Polaris (如未运行) ───────────────────────────────────────
if (-not $allOnline) {
    Write-Step "启动 Polaris (port 5052)..."
    $polarisPath = "Z:\qclaw\polaris\saas_server.py"
    if (-not (Test-Path $polarisPath)) {
        Write-WARN "Polaris saas_server.py 未找到: $polarisPath"
    } else {
        $proc = Start-Process python -ArgumentList $polarisPath -PassThru -WindowStyle Hidden
        Write-Info "Polaris 进程已启动 (PID: $($proc.Id))"
        Start-Sleep -Seconds 3

        # 再次检查
        $c2 = New-Object System.Net.Sockets.TcpClient
        try {
            $c2.Connect("127.0.0.1", 5052)
            if ($c2.Connected) { Write-OK "Polaris 在线 (port 5052)" }
        } catch { Write-WARN "Polaris 仍未响应" }
        finally { if ($c2) { $c2.Close() } }
    }
    Write-Host ""
}

# ── Step 3: 运行 m6_demo.py ───────────────────────────────────────────────
Write-Step "运行 m6_demo.py..."
Write-Host ""

if (-not (Test-Path $DemoScript)) {
    Write-FAIL "Demo 脚本不存在: $DemoScript"
    exit 1
}

Write-Info "工作目录: $DemoRoot"
Write-Info "日志文件: $LogFile"
Write-Host ""

# 运行 demo，捕获输出
$env:PYTHONIOENCODING = "utf-8"
$pinfo = New-Object System.Diagnostics.ProcessStartInfo
$pinfo.FileName = "python"
$pinfo.Arguments = "`"$DemoScript`""
$pinfo.WorkingDirectory = $DemoRoot
$pinfo.RedirectStandardOutput = $true
$pinfo.RedirectStandardError = $true
$pinfo.UseShellExecute = $false
$pinfo.CreateNoWindow = $true
$pinfo.StandardOutputEncoding = [System.Text.Encoding]::UTF8
$pinfo.StandardErrorEncoding = [System.Text.Encoding]::UTF8

$process = New-Object System.Diagnostics.Process
$process.StartInfo = $pinfo
$process.Start() | Out-Null

$stdout = $process.StandardOutput.ReadToEnd()
$stderr = $process.StandardError.ReadToEnd()
$process.WaitForExit()

$exitCode = $process.ExitCode

# 输出到控制台 + 写日志
$combined = @()
$combined += "=== M6 Demo Run $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="
$combined += ""
$combined += "--- STDOUT ---"
$combined += $stdout -split "`n"
$combined += ""
$combined += "--- STDERR ---"
$combined += $stderr -split "`n"
$combined += ""
$combined += "Exit Code: $exitCode"
$combined | ForEach-Object { $_ | Out-File -FilePath $LogFile -Encoding UTF8 -Append }

if ($stdout) {
    Write-Host "--- m6_demo stdout ---" -ForegroundColor White
    Write-Host $stdout
}
if ($stderr) {
    Write-Host "--- m6_demo stderr ---" -ForegroundColor DarkYellow
    Write-Host $stderr
}

if ($exitCode -eq 0) {
    Write-OK "m6_demo.py 成功完成 (exit 0)"
} else {
    Write-FAIL "m6_demo.py 异常退出 (exit $exitCode)"
}

Write-Host ""

# ── Step 4: AnimaLink 可视化截图 ──────────────────────────────────────────
if (-not $NoScreenshot) {
    Write-Step "AnimaLink 可视化截图..."

    # 尝试 Edge Screenshot MCP 或直接调用 screenshot
    try {
        # 使用 OpenClaw browser 截图
        $screenDir = Join-Path $DemoRoot "screenshots"
        if (-not (Test-Path $screenDir)) { New-Item -ItemType Directory -Path $screenDir | Out-Null }

        $ts = Get-Date -Format 'yyyyMMdd_HHmmss'
        $outFile = Join-Path $screenDir "m6_animlink_$ts.png"

        # 检查 Edge 是否在跑 CDP
        $cdpPort = 9334
        $c3 = New-Object System.Net.Sockets.TcpClient
        $cdpOnline = $false
        try {
            $c3.Connect("127.0.0.1", $cdpPort)
            $cdpOnline = $c3.Connected
        } catch { }
        finally { if ($c3) { $c3.Close() } }

        if ($cdpOnline) {
            Write-Info "CDP port $cdpPort 在线，尝试截图..."
            # 用 curl 触发 CDP screenshot
            $cdpUrl = "http://127.0.0.1:$cdpPort/json"
            try {
                $tabs = Invoke-RestMethod $cdpUrl -TimeoutSec 3
                $firstTab = $tabs[0]
                if ($firstTab) {
                    $shotUrl = "http://127.0.0.1:$cdpPort$(($firstTab).webSocketDebuggerUrl -replace 'ws://[^/]+','')/screenshot"
                    Write-Info "截图目标: $($firstTab.title // $firstTab.url)"
                }
            } catch {
                Write-WARN "无法获取 CDP tab 列表"
            }
        } else {
            Write-WARN "CDP port $cdpPort 不可用，跳过截图"
        }
    } catch {
        Write-WARN "截图失败: $_"
    }
}

Write-Host ""

# ── Step 5: 汇总 ───────────────────────────────────────────────────────────
Write-Host "==============================================================" -ForegroundColor Magenta
Write-Host "  Demo 执行摘要" -ForegroundColor Magenta
Write-Host "==============================================================" -ForegroundColor Magenta
Write-Host ""
Write-Host "  Demo 脚本   : $DemoScript"
Write-Host "  退出码     : $exitCode"
Write-Host "  日志文件   : $LogFile"
Write-Host "  服务状态   : MemGuard=$(if((Test-NetConnection 127.0.0.1 -Port 5050 -InformationLevel Quiet -WarningAction SilentlyContinue) {'ON'}) ELSE {'OFF'}) | Polaris=$(if((Test-NetConnection 127.0.0.1 -Port 5052 -InformationLevel Quiet -WarningAction SilentlyContinue) {'ON'}) ELSE {'OFF'}) | AnimaLink=$(if((Test-NetConnection 127.0.0.1 -Port 5053 -InformationLevel Quiet -WarningAction SilentlyContinue) {'ON'}) ELSE {'OFF'})"
Write-Host ""
Write-Host "==============================================================" -ForegroundColor Magenta

exit $exitCode
