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

$localFfmpeg = Join-Path $rootDir "tools\ffmpeg\windows\ffmpeg.exe"
if ((-not $env:ULTIMATE_FFMPEG_PATH) -and (Test-Path $localFfmpeg)) {
    $env:ULTIMATE_FFMPEG_PATH = $localFfmpeg
    Write-Host "Using local FFmpeg runtime: $localFfmpeg" -ForegroundColor DarkCyan
}

Write-Host "Starting backend service..." -ForegroundColor Cyan
python app.py
