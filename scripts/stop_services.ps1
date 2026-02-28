# 停止服务脚本
# 停止后端和前端服务

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = (Get-Item $scriptDir).Parent.FullName

Set-Location $rootDir

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=== Stop Services ===" -ForegroundColor Green

Write-Host "Stopping backend service..." -ForegroundColor Cyan
Get-Process python -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        Stop-Process -Id $_.Id -Force
        Write-Host "Stopped process: python (PID: $($_.Id))" -ForegroundColor Yellow
    } catch {
        Write-Host "Failed to stop process: python" -ForegroundColor Red
    }
}

Write-Host "Stopping frontend service..." -ForegroundColor Cyan
Get-Process node -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        Stop-Process -Id $_.Id -Force
        Write-Host "Stopped process: node (PID: $($_.Id))" -ForegroundColor Yellow
    } catch {
        Write-Host "Failed to stop process: node" -ForegroundColor Red
    }
}

Write-Host "=== Services Stopped ===" -ForegroundColor Green
