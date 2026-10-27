﻿﻿﻿﻿﻿# 停止服务脚本
# 只停止本项目相关的服务进程（按端口监听 + 命令行特征匹配），
# 不会影响系统里其它无关的 python / node 进程

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = (Get-Item $scriptDir).Parent.FullName

Set-Location $rootDir

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=== Stop Services ===" -ForegroundColor Green

# 读取端口配置
$ports = @()
$configPath = Join-Path $rootDir "server_config.json"
if (Test-Path $configPath) {
    try {
        $config = Get-Content $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($config.backend -and $config.backend.port) { $ports += [int]$config.backend.port }
        if ($config.frontend -and $config.frontend.port) { $ports += [int]$config.frontend.port }
        if ($config.auth -and $config.auth.private_port) { $ports += [int]$config.auth.private_port }
        if ($config.auth -and $config.auth.normal_port) { $ports += [int]$config.auth.normal_port }
    } catch {
        Write-Host "Warning: Failed to parse server_config.json" -ForegroundColor Yellow
    }
}

# 收集目标 PID
$targetPids = New-Object System.Collections.Generic.HashSet[int]

# 1) 占用项目端口的监听进程
foreach ($port in ($ports | Sort-Object -Unique)) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.OwningProcess -gt 0) {
            [void]$targetPids.Add([int]$_.OwningProcess)
        }
    }
}

# 2) 命令行包含本项目特征的 python/node 进程（兜底：防止端口配置改动后漏杀）
Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe' OR Name='node.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
    $cmd = $_.CommandLine
    if (-not $cmd) { return }
    if ($cmd -like "*app.py*" -or
        $cmd -like "*comic_backend*" -or
        $cmd -like "*comic_frontend*" -or
        $cmd -like "*windows_launcher.py*") {
        [void]$targetPids.Add([int]$_.ProcessId)
    }
}

if ($targetPids.Count -eq 0) {
    Write-Host "No project services found running." -ForegroundColor Gray
    Write-Host "=== Services Stopped ===" -ForegroundColor Green
    exit 0
}

# 树杀目标进程（/T 会连同 esbuild 等子进程一起结束）
$stopped = 0
foreach ($procId in ($targetPids | Sort-Object)) {
    if ($procId -eq $PID) { continue }
    $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if (-not $proc) { continue }
    $procName = $proc.ProcessName
    taskkill /PID $procId /T /F | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Stopped process: $procName (PID: $procId)" -ForegroundColor Yellow
        $stopped++
    } else {
        Write-Host "Failed to stop process: $procName (PID: $procId)（可能需要管理员权限）" -ForegroundColor Red
    }
}

Write-Host "Stopped $stopped process(es)." -ForegroundColor Cyan
Write-Host "=== Services Stopped ===" -ForegroundColor Green
