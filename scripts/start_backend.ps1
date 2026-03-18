# 启动后端服务脚本

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = (Get-Item $scriptDir).Parent.FullName

Set-Location "$rootDir\comic_backend"

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

if (-not $env:BACKEND_RUNTIME_PROFILE) {
    $env:BACKEND_RUNTIME_PROFILE = "full"
}
if (-not $env:BACKEND_ENABLE_THIRD_PARTY) {
    $env:BACKEND_ENABLE_THIRD_PARTY = "true"
}

Write-Host "Starting backend service..." -ForegroundColor Cyan
python app.py
