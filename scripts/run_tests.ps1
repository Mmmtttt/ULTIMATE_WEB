# 运行测试脚本
# 执行后端API测试和前端E2E测试

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = (Get-Item $scriptDir).Parent.FullName

Set-Location $rootDir

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=== Run Tests ===" -ForegroundColor Green

$runBackend = $true
$runFrontend = $true

if ($args.Count -gt 0) {
    $runBackend = $args -contains "-backend" -or $args -contains "-all"
    $runFrontend = $args -contains "-frontend" -or $args -contains "-all"
}

$scriptsDir = Join-Path $rootDir "scripts"

# 运行后端测试
if ($runBackend) {
    Write-Host "`n=== Backend API Tests ===" -ForegroundColor Cyan

    Write-Host "Checking backend service..." -ForegroundColor Yellow
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:5000/health" -TimeoutSec 3 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Host "Backend service is running" -ForegroundColor Green
        }
    } catch {
        Write-Host "Backend service is not running. Starting it..." -ForegroundColor Yellow
        & "$scriptsDir\start_backend.ps1"
        Start-Sleep -Seconds 5
    }

    Write-Host "Running backend API tests..." -ForegroundColor Yellow
    Set-Location "$rootDir\tests"
    python test_api.py

    if ($LASTEXITCODE -eq 0) {
        Write-Host "Backend tests passed" -ForegroundColor Green
    } else {
        Write-Host "Backend tests failed" -ForegroundColor Red
    }
}

# 运行前端测试
if ($runFrontend) {
    Write-Host "`n=== Frontend E2E Tests ===" -ForegroundColor Cyan

    Write-Host "Checking frontend dependencies..." -ForegroundColor Yellow
    if (-not (Test-Path "comic_frontend\node_modules")) {
        Write-Host "Frontend dependencies not installed. Installing..." -ForegroundColor Yellow
        & "$scriptsDir\setup_environment.ps1"
    }

    Write-Host "Running frontend E2E tests with Playwright..." -ForegroundColor Yellow
    Set-Location "$rootDir"
    npx playwright test --config=tests/playwright.config.js

    if ($LASTEXITCODE -eq 0) {
        Write-Host "Frontend tests passed" -ForegroundColor Green
    } else {
        Write-Host "Frontend tests failed" -ForegroundColor Red
    }
}

Set-Location $rootDir

Write-Host "`n=== Tests Complete ===" -ForegroundColor Green
Write-Host "Usage: " -ForegroundColor Cyan
Write-Host "  .\scripts\run_tests.ps1           # Run all tests" -ForegroundColor Yellow
Write-Host "  .\scripts\run_tests.ps1 -backend # Run backend tests only" -ForegroundColor Yellow
Write-Host "  .\scripts\run_tests.ps1 -frontend # Run frontend tests only" -ForegroundColor Yellow
