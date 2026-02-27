# 启动项目脚本
# 同时启动后端和前端服务

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=== Start Project ===" -ForegroundColor Green

# 检查后端依赖
Write-Host "Checking backend dependencies..." -ForegroundColor Cyan
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

# 获取项目根目录的绝对路径
$rootPath = Get-Location
$backendPath = Join-Path $rootPath "comic_backend"
$frontendPath = Join-Path $rootPath "comic_frontend"

# 启动后端服务
Write-Host "Starting backend service..." -ForegroundColor Cyan
$backendScript = @"
cd "$backendPath"
python app.py
"@
$backendScript | Out-File -FilePath "start_backend.ps1" -Encoding UTF8
Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-File", "start_backend.ps1" -WorkingDirectory $rootPath

# 等待后端服务启动
Write-Host "Waiting for backend service to start..." -ForegroundColor Cyan
Start-Sleep -Seconds 5

# 启动前端服务
Write-Host "Starting frontend service..." -ForegroundColor Cyan
$frontendScript = @"
cd "$frontendPath"
npm run dev
"@
$frontendScript | Out-File -FilePath "start_frontend.ps1" -Encoding UTF8
Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-File", "start_frontend.ps1" -WorkingDirectory $rootPath

# 等待前端服务启动
Write-Host "Waiting for frontend service to start..." -ForegroundColor Cyan
Start-Sleep -Seconds 8

# 显示服务状态
Write-Host "=== Services Started ===" -ForegroundColor Green
Write-Host "Backend: http://127.0.0.1:5000" -ForegroundColor Yellow
Write-Host "Frontend: http://localhost:5173/" -ForegroundColor Yellow
Write-Host "" -ForegroundColor Green
Write-Host "To stop services, run: .\stop_project.ps1" -ForegroundColor Yellow
Write-Host "To view logs, run: .\view_logs.ps1" -ForegroundColor Yellow
