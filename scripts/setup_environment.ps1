# 环境搭建脚本
# 检测并安装所需环境（Python、Node.js），然后安装项目依赖

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = (Get-Item $scriptDir).Parent.FullName

Set-Location $rootDir

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=== Environment Setup ===" -ForegroundColor Green
Write-Host "This script will check and install required dependencies" -ForegroundColor Cyan
Write-Host ""

function Get-PipCommand {
    $commands = @("pip", "pip3", "py -m pip")
    foreach ($cmd in $commands) {
        try {
            $null = Invoke-Expression "$cmd --version" 2>$null
            if ($LASTEXITCODE -eq 0) {
                return $cmd
            }
        } catch {
        }
    }
    return $null
}

function Get-PythonVersion {
    $commands = @("python", "python3", "py")
    foreach ($cmd in $commands) {
        try {
            $version = Invoke-Expression "$cmd --version" 2>&1
            if ($LASTEXITCODE -eq 0 -and $version -match "Python (\d+)\.(\d+)") {
                return @{
                    Command = $cmd
                    Version = $version
                    Major = [int]$Matches[1]
                    Minor = [int]$Matches[2]
                }
            }
        } catch {
        }
    }
    return $null
}

function Get-NodeVersion {
    try {
        $version = node --version 2>&1
        if ($LASTEXITCODE -eq 0 -and $version -match "v(\d+)") {
            return @{
                Version = $version
                Major = [int]$Matches[1]
            }
        }
    } catch {
    }
    return $null
}

Write-Host "Checking Python..." -ForegroundColor Yellow
$pythonInfo = Get-PythonVersion
if ($pythonInfo) {
    Write-Host "  [OK] Python found: $($pythonInfo.Version)" -ForegroundColor Green
    if ($pythonInfo.Major -lt 3 -or ($pythonInfo.Major -eq 3 -and $pythonInfo.Minor -lt 8)) {
        Write-Host "  [ERROR] Python 3.8 or higher is required" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  [ERROR] Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "  Please install Python 3.8 or higher from: https://www.python.org/downloads/" -ForegroundColor Cyan
    Write-Host "  After installation, restart your terminal and run this script again" -ForegroundColor Cyan
    exit 1
}

Write-Host "Checking Node.js..." -ForegroundColor Yellow
$nodeInfo = Get-NodeVersion
if ($nodeInfo) {
    Write-Host "  [OK] Node.js found: $($nodeInfo.Version)" -ForegroundColor Green
    if ($nodeInfo.Major -lt 16) {
        Write-Host "  [ERROR] Node.js 16 or higher is required" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  [ERROR] Node.js is not installed or not in PATH" -ForegroundColor Red
    Write-Host "  Please install Node.js 16 or higher from: https://nodejs.org/" -ForegroundColor Cyan
    Write-Host "  After installation, restart your terminal and run this script again" -ForegroundColor Cyan
    exit 1
}

Write-Host "Checking npm..." -ForegroundColor Yellow
try {
    $npmVersion = npm --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] npm found: v$npmVersion" -ForegroundColor Green
    }
} catch {
    Write-Host "  [ERROR] npm is not installed" -ForegroundColor Red
    Write-Host "  npm comes with Node.js, please reinstall Node.js" -ForegroundColor Cyan
    exit 1
}

Write-Host ""
Write-Host "=== Installing Dependencies ===" -ForegroundColor Green

$pipCmd = Get-PipCommand
if (-not $pipCmd) {
    Write-Host "  [ERROR] pip is not available" -ForegroundColor Red
    exit 1
}
Write-Host "  Using pip command: $pipCmd" -ForegroundColor Cyan

Write-Host ""
Write-Host "Installing backend dependencies..." -ForegroundColor Yellow
if (Test-Path "comic_backend\requirements.txt") {
    Write-Host "  Running: $pipCmd install -r comic_backend\requirements.txt" -ForegroundColor Cyan
    & $pipCmd install -r comic_backend\requirements.txt
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] Backend dependencies installed" -ForegroundColor Green
    } else {
        Write-Host "  [ERROR] Failed to install backend dependencies" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  [ERROR] requirements.txt not found" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
if (Test-Path "comic_frontend\package.json") {
    Write-Host "  Running: npm install" -ForegroundColor Cyan
    $frontendPath = Join-Path $rootDir "comic_frontend"
    npm install --prefix $frontendPath
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] Frontend dependencies installed" -ForegroundColor Green
    } else {
        Write-Host "  [ERROR] Failed to install frontend dependencies" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  [ERROR] package.json not found" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Green
Write-Host "You can now start the project with: .\start_project.ps1" -ForegroundColor Yellow
Write-Host "Or individually:" -ForegroundColor Yellow
Write-Host "  Backend:  .\scripts\start_backend.ps1" -ForegroundColor Cyan
Write-Host "  Frontend: .\scripts\start_frontend.ps1" -ForegroundColor Cyan
