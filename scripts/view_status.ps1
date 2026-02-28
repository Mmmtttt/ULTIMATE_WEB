# 查看服务状态脚本
# 查看后端和前端服务的运行状态

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = (Get-Item $scriptDir).Parent.FullName

Set-Location $rootDir

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=== View Service Status ===" -ForegroundColor Green

Write-Host "Backend service processes:" -ForegroundColor Cyan
$backendProcesses = Get-Process python -ErrorAction SilentlyContinue
if ($backendProcesses) {
    $backendProcesses | Format-Table Id, ProcessName, CPU, WorkingSet -AutoSize
} else {
    Write-Host "No backend processes found" -ForegroundColor Yellow
}

Write-Host "" -ForegroundColor Green
Write-Host "Frontend service processes:" -ForegroundColor Cyan
$frontendProcesses = Get-Process node -ErrorAction SilentlyContinue
if ($frontendProcesses) {
    $frontendProcesses | Format-Table Id, ProcessName, CPU, WorkingSet -AutoSize
} else {
    Write-Host "No frontend processes found" -ForegroundColor Yellow
}

Write-Host "" -ForegroundColor Green
Write-Host "Testing service availability:" -ForegroundColor Cyan

try {
    $backendResponse = Invoke-WebRequest -Uri "http://127.0.0.1:5000/health" -TimeoutSec 3 -UseBasicParsing
    if ($backendResponse.StatusCode -eq 200) {
        Write-Host "Backend service: OK (Status: $($backendResponse.StatusCode))" -ForegroundColor Green
    } else {
        Write-Host "Backend service: ERROR (Status: $($backendResponse.StatusCode))" -ForegroundColor Red
    }
} catch {
    Write-Host "Backend service: ERROR (Not accessible)" -ForegroundColor Red
}

try {
    $frontendResponse = Invoke-WebRequest -Uri "http://localhost:5173/" -TimeoutSec 3 -UseBasicParsing
    if ($frontendResponse.StatusCode -eq 200) {
        Write-Host "Frontend service: OK (Status: $($frontendResponse.StatusCode))" -ForegroundColor Green
    } else {
        Write-Host "Frontend service: ERROR (Status: $($frontendResponse.StatusCode))" -ForegroundColor Red
    }
} catch {
    Write-Host "Frontend service: ERROR (Not accessible)" -ForegroundColor Red
}

Write-Host "" -ForegroundColor Green
Write-Host "=== Status View Complete ===" -ForegroundColor Green
