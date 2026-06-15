#!/usr/bin/env powershell
# backup_knowledge_base.ps1 - 知识库自动备份脚本
# 功能: 备份核心灵魂文件 + 知识库条目到NAS（三副本策略）
# 用法: .\backup_knowledge_base.ps1 [-DryRun] [-Verbose]

param(
    [switch]$DryRun,
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"

# ========== 配置 ==========
$LocalWorkspace = "C:\Users\Administrator\.qclaw\workspace-agent-d9479bde"
$NasPath = "Z:\qclaw\knowledge-base"
$N200Path = "\\100.114.245.96\QClawBackup\knowledge-base"
$LocalBackup = "$LocalWorkspace\backup"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupLog = "$LocalWorkspace\logs\backup_$Timestamp.log"

# 核心文件列表
$CoreFiles = @(
    "SOUL.md",
    "IDENTITY.md",
    "MEMORY.md",
    "AGENTS.md",
    "USER.md",
    "TOOLS.md",
    "HEARTBEAT.md"
)

# 知识库目录
$KbDir = "$LocalWorkspace\silicon-civilization-kb"

# ========== 函数 ==========
function Write-Log {
    param($Message)
    $logEntry = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - $Message"
    Write-Output $logEntry | Tee-Object -FilePath $BackupLog -Append
}

function Test-AndCreateDir {
    param($Path)
    if (-not (Test-Path $Path)) {
        if (-not $DryRun) {
            New-Item -ItemType Directory -Path $Path -Force | Out-Null
            Write-Log "Created directory: $Path"
        } else {
            Write-Log "[DRYRUN] Would create directory: $Path"
        }
    }
}

function Copy-WithVerification {
    param($Source, $Destination)
    
    if (-not (Test-Path $Source)) {
        Write-Log "WARNING: Source not found: $Source"
        return $false
    }
    
    if ($DryRun) {
        Write-Log "[DRYRUN] Would copy: $Source -> $Destination"
        return $true
    }
    
    try {
        Copy-Item -Path $Source -Destination $Destination -Force
        # 验证复制
        $srcHash = Get-FileHash -Path $Source -Algorithm SHA256
        $dstHash = Get-FileHash -Path $Destination -Algorithm SHA256
        if ($srcHash.Hash -eq $dstHash.Hash) {
            Write-Log "VERIFIED: $Source -> $Destination"
            return $true
        } else {
            Write-Log "ERROR: Hash mismatch after copy: $Source"
            return $false
        }
    } catch {
        Write-Log "ERROR: Failed to copy $Source -> $Destination : $_"
        return $false
    }
}

# ========== 主逻辑 ==========

Write-Log "========== Backup Started =========="
Write-Log "Timestamp: $Timestamp"
Write-Log "DryRun: $DryRun"

# 1. 创建本地备份目录
$LocalBackupTimestamp = "$LocalBackup\$Timestamp"
Test-AndCreateDir $LocalBackupTimestamp

# 2. 备份核心灵魂文件（本地）
Write-Log "--- Backing up core soul files (local) ---"
$CoreBackupCount = 0
foreach ($file in $CoreFiles) {
    $sourcePath = "$LocalWorkspace\$file"
    $destPath = "$LocalBackupTimestamp\$file"
    if (Copy-WithVerification $sourcePath $destPath) {
        $CoreBackupCount++
    }
}
Write-Log "Core files backed up: $CoreBackupCount/$($CoreFiles.Count)"

# 3. 备份知识库条目（本地）
Write-Log "--- Backing up KB entries (local) ---"
if (Test-Path $KbDir) {
    $KbBackupPath = "$LocalBackupTimestamp\silicon-civilization-kb"
    Test-AndCreateDir $KbBackupPath
    
    # 复制整个知识库目录
    if (-not $DryRun) {
        Copy-Item -Path "$KbDir\*" -Destination $KbBackupPath -Recurse -Force
        Write-Log "KB directory backed up to: $KbBackupPath"
    } else {
        Write-Log "[DRYRUN] Would copy KB directory to: $KbBackupPath"
    }
} else {
    Write-Log "WARNING: KB directory not found: $KbDir"
}

# 4. 尝试备份到NAS（如果可达）
Write-Log "--- Attempting NAS backup ---"
if (Test-Path $NasPath) {
    Write-Log "NAS is reachable: $NasPath"
    $NasBackupPath = "$NasPath\backup\$Timestamp"
    Test-AndCreateDir $NasBackupPath
    
    # 复制核心文件到NAS
    foreach ($file in $CoreFiles) {
        $sourcePath = "$LocalWorkspace\$file"
        $destPath = "$NasBackupPath\$file"
        Copy-WithVerification $sourcePath $destPath
    }
    
    # 复制知识库到NAS
    if (Test-Path $KbDir) {
        $KbNasPath = "$NasBackupPath\silicon-civilization-kb"
        Test-AndCreateDir $KbNasPath
        if (-not $DryRun) {
            Copy-Item -Path "$KbDir\*" -Destination $KbNasPath -Recurse -Force
            Write-Log "KB backed up to NAS: $KbNasPath"
        }
    }
} else {
    Write-Log "WARNING: NAS not reachable: $NasPath (skipping NAS backup)"
}

# 5. 尝试备份到N200（如果可达）
Write-Log "--- Attempting N200 backup ---"
if (Test-Path $N200Path) {
    Write-Log "N200 is reachable: $N200Path"
    $N200BackupPath = "$N200Path\backup\$Timestamp"
    Test-AndCreateDir $N200BackupPath
    
    # 复制核心文件到N200
    foreach ($file in $CoreFiles) {
        $sourcePath = "$LocalWorkspace\$file"
        $destPath = "$N200BackupPath\$file"
        Copy-WithVerification $sourcePath $destPath
    }
    
    # 复制知识库到N200
    if (Test-Path $KbDir) {
        $KbN200Path = "$N200BackupPath\silicon-civilization-kb"
        Test-AndCreateDir $KbN200Path
        if (-not $DryRun) {
            Copy-Item -Path "$KbDir\*" -Destination $KbN200Path -Recurse -Force
            Write-Log "KB backed up to N200: $KbN200Path"
        }
    }
} else {
    Write-Log "WARNING: N200 not reachable: $N200Path (skipping N200 backup)"
}

# 6. 清理旧备份（保留最近7天）
Write-Log "--- Cleaning up old backups ---"
if (-not $DryRun) {
    $oldBackups = Get-ChildItem -Path $LocalBackup -Directory | Where-Object { $_.CreationTime -lt (Get-Date).AddDays(-7) }
    foreach ($oldBackup in $oldBackups) {
        Remove-Item -Path $oldBackup.FullName -Recurse -Force
        Write-Log "Removed old backup: $($oldBackup.Name)"
    }
} else {
    Write-Log "[DRYRUN] Would clean up old backups (older than 7 days)"
}

# ========== 完成 ==========
Write-Log "========== Backup Completed =========="
Write-Log "Backup location (local): $LocalBackupTimestamp"
Write-Log "Log file: $BackupLog"

# 输出摘要
Write-Output "`n========== Backup Summary =========="
Write-Output "Timestamp: $Timestamp"
Write-Output "Core files: $CoreBackupCount/$($CoreFiles.Count) backed up"
Write-Output "KB entries: $(if (Test-Path $KbDir) { (Get-ChildItem $KbDir -Recurse -File).Count } else { 'N/A' }) files"
Write-Output "Log: $BackupLog"
Write-Output "===================================`n"

if ($DryRun) {
    Write-Output "[DRYRUN MODE] No actual changes made. Remove -DryRun to execute."
}
