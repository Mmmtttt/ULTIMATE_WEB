# 查看服务状态脚本
# 查看后端和前端服务的运行状态

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = (Get-Item $scriptDir).Parent.FullName

Set-Location $rootDir

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=== View Service Status ===" -ForegroundColor Green

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

Write-Host "Backend service processes:" -ForegroundColor Cyan
$backendProcesses = Get-Process python -ErrorAction SilentlyContinue
if ($backendProcesses) {
    $backendProcesses | Format-Table Id, ProcessName, CPU, WorkingSet -AutoSize
} else {
    Write-Host "No backend processes found" -ForegroundColor Yellow
}

Write-Host "" -ForegroundColor Green
Write-Host "Frontend service processes:" -ForegroundColor Cyan
$frontendProcesses = Get-Process node -ErrorAction SilentlyContinue
if ($frontendProcesses) {
    $frontendProcesses | Format-Table Id, ProcessName, CPU, WorkingSet -AutoSize
} else {
    Write-Host "No frontend processes found" -ForegroundColor Yellow
}

Write-Host "" -ForegroundColor Green
Write-Host "Testing service availability:" -ForegroundColor Cyan

# 后端健康检查（支持 HTTPS 自签名证书）
$backendUrl = "$backendProtocol`://127.0.0.1:$backendPort/health"
try {
    if ($backendProtocol -eq "https") {
        # 忽略自签名证书验证
        $callback = { return $true }
        [System.Net.ServicePointManager]::ServerCertificateValidationCallback = $callback
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
    }
    $backendResponse = Invoke-WebRequest -Uri $backendUrl -TimeoutSec 3 -UseBasicParsing
    if ($backendResponse.StatusCode -eq 200) {
        Write-Host "Backend service: OK ($backendUrl, Status: $($backendResponse.StatusCode))" -ForegroundColor Green
    } else {
        Write-Host "Backend service: ERROR ($backendUrl, Status: $($backendResponse.StatusCode))" -ForegroundColor Red
    }
} catch {
    Write-Host "Backend service: ERROR ($backendUrl, Not accessible)" -ForegroundColor Red
} finally {
    # 恢复证书验证
    [System.Net.ServicePointManager]::ServerCertificateValidationCallback = $null
}

# 前端健康检查
$frontendUrl = "$backendProtocol`://localhost:$frontendPort/"
try {
    if ($backendProtocol -eq "https") {
        $callback = { return $true }
        [System.Net.ServicePointManager]::ServerCertificateValidationCallback = $callback
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
    }
    $frontendResponse = Invoke-WebRequest -Uri $frontendUrl -TimeoutSec 3 -UseBasicParsing
    if ($frontendResponse.StatusCode -eq 200) {
        Write-Host "Frontend service: OK ($frontendUrl, Status: $($frontendResponse.StatusCode))" -ForegroundColor Green
    } else {
        Write-Host "Frontend service: ERROR ($frontendUrl, Status: $($frontendResponse.StatusCode))" -ForegroundColor Red
    }
} catch {
    Write-Host "Frontend service: ERROR ($frontendUrl, Not accessible)" -ForegroundColor Red
} finally {
    [System.Net.ServicePointManager]::ServerCertificateValidationCallback = $null
}

Write-Host "" -ForegroundColor Green
Write-Host "=== Status View Complete ===" -ForegroundColor Green
