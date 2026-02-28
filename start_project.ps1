# 启动项目脚本
# 检测并安装依赖，然后停止已运行的服务，最后启动后端和前端服务

$rootDir = $PWD.Path
$scriptsDir = Join-Path $rootDir "scripts"

Set-Location $rootDir

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

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

function Test-DependenciesInstalled {
    param($pipCmd)

    if (Test-Path "comic_backend\requirements.txt") {
        $requiredPackages = Get-Content "comic_backend\requirements.txt"
        foreach ($pkg in $requiredPackages) {
            if ($pkg -match "^([a-zA-Z0-9_-]+)") {
                $pkgName = $Matches[1]
                $result = & $pipCmd show $pkgName 2>$null
                if ($LASTEXITCODE -ne 0) {
                    return $false
                }
            }
        }
    }

    if (Test-Path "comic_frontend\package-lock.json") {
        if (-not (Test-Path "comic_frontend\node_modules")) {
            return $false
        }
    }

    if (Test-Path "comic_frontend\package.json") {
        if (-not (Test-Path "comic_frontend\node_modules")) {
            return $false
        }
    }

    return $true
}

Write-Host "=== Start Project ===" -ForegroundColor Green

Write-Host "Checking dependencies..." -ForegroundColor Yellow
$pipCmd = Get-PipCommand

if ($pipCmd) {
    $depsInstalled = Test-DependenciesInstalled -pipCmd $pipCmd

    if (-not $depsInstalled) {
        Write-Host "  Dependencies not found, running setup..." -ForegroundColor Yellow
        & "$scriptsDir\setup_environment.ps1"

        if ($LASTEXITCODE -ne 0) {
            Write-Host "  [ERROR] Failed to install dependencies" -ForegroundColor Red
            exit 1
        }
        Write-Host "  Dependencies installed successfully" -ForegroundColor Green
    } else {
        Write-Host "  Dependencies already installed" -ForegroundColor Green
    }
} else {
    Write-Host "  Python/pip not found, running setup..." -ForegroundColor Yellow
    & "$scriptsDir\setup_environment.ps1"

    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [ERROR] Failed to install dependencies" -ForegroundColor Red
        exit 1
    }
    Write-Host "  Dependencies installed successfully" -ForegroundColor Green
}

Write-Host "" -ForegroundColor Green
Write-Host "Stopping existing services..." -ForegroundColor Cyan
& "$scriptsDir\stop_services.ps1"

Start-Sleep -Seconds 2

Write-Host "" -ForegroundColor Green
Write-Host "Starting backend service..." -ForegroundColor Cyan
$backendPath = Join-Path $rootDir "comic_backend"
Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "cd /d `"$backendPath`" && python app.py"

Write-Host "Waiting for backend service to start..." -ForegroundColor Cyan
Start-Sleep -Seconds 5

Write-Host "Starting frontend service..." -ForegroundColor Cyan
$frontendPath = Join-Path $rootDir "comic_frontend"
Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "cd /d `"$frontendPath`" && npm run dev"

Write-Host "Waiting for frontend service to start..." -ForegroundColor Cyan
Start-Sleep -Seconds 8

Write-Host "" -ForegroundColor Green
Write-Host "=== Services Started ===" -ForegroundColor Green
Write-Host "Backend: http://127.0.0.1:5000" -ForegroundColor Yellow
Write-Host "Frontend: http://localhost:5173/" -ForegroundColor Yellow
Write-Host "" -ForegroundColor Green
Write-Host "To stop services, run: .\scripts\stop_services.ps1" -ForegroundColor Yellow
Write-Host "To view status, run: .\scripts\view_status.ps1" -ForegroundColor Yellow
