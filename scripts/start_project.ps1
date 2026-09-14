# 启动项目脚本
# 先停止已运行的服务，然后启动后端和前端服务

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = $scriptDir

Set-Location $rootDir

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=== Start Project ===" -ForegroundColor Green

# 读取服务器配置，判断后端协议
$backendProtocol = "http"
$backendPort = 5000
$frontendPort = 5173
$configPath = Join-Path $rootDir "server_config.json"
if (Test-Path $configPath) {
    try {
        $config = Get-Content $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($config.backend) {
            $backendPort = [int]$config.backend.port
            if ($config.backend.ssl_enabled -ne $false -and $config.backend.ssl_enabled -ne "false") {
                $backendProtocol = "https"
            }
        }
        if ($config.frontend -and $config.frontend.port) {
            $frontendPort = [int]$config.frontend.port
        }
    } catch {
        Write-Host "Warning: Failed to parse server_config.json, using defaults" -ForegroundColor Yellow
    }
}

# 先停止已运行的服务
Write-Host "Stopping existing services..." -ForegroundColor Cyan
& "$scriptDir\stop_services.ps1"

# 等待一下确保端口释放
Start-Sleep -Seconds 2

# 检查后端依赖
Write-Host "`nChecking backend dependencies..." -ForegroundColor Cyan
if (-not (Test-Path "comic_backend\requirements.txt")) {
    Write-Host "Error: requirements.txt not found" -ForegroundColor Red
    exit 1
}

# 检查前端依赖
Write-Host "Checking frontend dependencies..." -ForegroundColor Cyan
if (-not (Test-Path "comic_frontend\package.json")) {
    Write-Host "Error: package.json not found" -ForegroundColor Red
    exit 1
}

# 启动 Windows 控制中心，由控制中心负责服务生命周期和日志显示
Write-Host "`nStarting Windows control center..." -ForegroundColor Cyan
$launcherPath = Join-Path $rootDir "scripts\windows_launcher.py"
$launcherArgs = '"{0}" --root "{1}" --mode dev --open-browser' -f $launcherPath, $rootDir
$pythonw = Get-Command "pythonw.exe" -ErrorAction SilentlyContinue
if ($pythonw) {
    Start-Process -FilePath $pythonw.Source -ArgumentList $launcherArgs -WorkingDirectory $rootDir -WindowStyle Hidden
} else {
    Start-Process -FilePath "python.exe" -ArgumentList $launcherArgs -WorkingDirectory $rootDir -WindowStyle Hidden
}
Write-Host "Control center started. Closing it will stop the backend and frontend." -ForegroundColor Green
