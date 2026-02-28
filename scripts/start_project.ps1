# 启动项目脚本
# 先停止已运行的服务，然后启动后端和前端服务

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = $scriptDir

Set-Location $rootDir

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=== Start Project ===" -ForegroundColor Green

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

# 启动后端服务
Write-Host "`nStarting backend service..." -ForegroundColor Cyan
$backendPath = Join-Path $rootDir "comic_backend"
Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-Command", "cd '$backendPath'; python app.py" -WorkingDirectory $backendPath

# 等待后端服务启动
Write-Host "Waiting for backend service to start..." -ForegroundColor Cyan
Start-Sleep -Seconds 5

# 启动前端服务
Write-Host "Starting frontend service..." -ForegroundColor Cyan
$frontendPath = Join-Path $rootDir "comic_frontend"
Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-Command", "cd '$frontendPath'; npm run dev" -WorkingDirectory $frontendPath

# 等待前端服务启动
Write-Host "Waiting for frontend service to start..." -ForegroundColor Cyan
Start-Sleep -Seconds 8

# 显示服务状态
Write-Host "`n=== Services Started ===" -ForegroundColor Green
Write-Host "Backend: http://127.0.0.1:5000" -ForegroundColor Yellow
Write-Host "Frontend: http://localhost:5173/" -ForegroundColor Yellow
Write-Host "" -ForegroundColor Green
Write-Host "To stop services, run: .\scripts\stop_services.ps1" -ForegroundColor Yellow
Write-Host "To view status, run: .\scripts\view_status.ps1" -ForegroundColor Yellow
