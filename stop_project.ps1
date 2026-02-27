# 停止项目脚本
# 停止后端和前端服务

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=== Stop Services ===" -ForegroundColor Green

# 停止后端服务（Python Flask）
Write-Host "Stopping backend service..." -ForegroundColor Cyan
Get-Process python -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        Stop-Process -Id $_.Id -Force
        Write-Host "Stopped process: python (PID: $($_.Id))" -ForegroundColor Yellow
    } catch {
        Write-Host "Failed to stop process: python" -ForegroundColor Red
    }
}

# 停止前端服务（Node.js）
Write-Host "Stopping frontend service..." -ForegroundColor Cyan
Get-Process node -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        Stop-Process -Id $_.Id -Force
        Write-Host "Stopped process: node (PID: $($_.Id))" -ForegroundColor Yellow
    } catch {
        Write-Host "Failed to stop process: node" -ForegroundColor Red
    }
}

# 清理临时脚本文件
Write-Host "Cleaning up temporary files..." -ForegroundColor Cyan
Remove-Item -Path "start_backend.ps1" -ErrorAction SilentlyContinue
Remove-Item -Path "start_frontend.ps1" -ErrorAction SilentlyContinue

Write-Host "=== Services Stopped ===" -ForegroundColor Green
