# MemGuard-GM Windows Task Scheduler 设置脚本
# 创建定时校验任务

$TaskName = "MemGuard-GM-IntegrityCheck"
$ScriptPath = "C:\Users\Administrator\.qclaw\workspace-agent-d9479bde\memguard\scheduler.py"
$WorkingDir = "C:\Users\Administrator\.qclaw\workspace-agent-d9479bde\memguard"
$Description = "MemGuard-GM 记忆完整性定时校验"
$IntervalHours = 4  # 每4小时执行一次

Write-Host "设置 MemGuard-GM 定时校验任务..." -ForegroundColor Cyan

# 检查任务是否已存在
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($existingTask) {
    Write-Host "任务已存在，正在更新..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# 创建触发器 - 每天多次执行
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours $IntervalHours) -RepetitionDuration ([TimeSpan]::MaxValue)

# 创建动作 - 运行Python
$Action = New-ScheduledTaskAction -Execute "python" -Argument "`"$ScriptPath`"" -WorkingDirectory $WorkingDir

# 创建任务设置
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable:$false

# 创建主体 - 使用当前用户
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Limited

# 注册任务
Register-ScheduledTask -TaskName $TaskName -Trigger $Trigger -Action $Action -Settings $Settings -Principal $Principal -Description $Description

Write-Host "✅ 定时任务已创建" -ForegroundColor Green
Write-Host "   任务名称: $TaskName"
Write-Host "   执行间隔: 每$IntervalHours小时"
Write-Host "   脚本路径: $ScriptPath"

# 立即执行一次测试
Write-Host "`n立即执行测试校验..." -ForegroundColor Cyan
Start-ScheduledTask -TaskName $TaskName
Write-Host "测试任务已触发" -ForegroundColor Green
