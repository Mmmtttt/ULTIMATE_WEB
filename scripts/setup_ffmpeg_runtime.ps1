# 下载并安装本地 FFmpeg 运行时到仓库工具目录

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = (Get-Item $scriptDir).Parent.FullName
$targetDir = Join-Path $rootDir "tools\ffmpeg\windows"
$targetFfmpeg = Join-Path $targetDir "ffmpeg.exe"
$targetFfprobe = Join-Path $targetDir "ffprobe.exe"
$downloadUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=== FFmpeg Runtime Setup ===" -ForegroundColor Green
Write-Host "Target directory: $targetDir" -ForegroundColor Cyan

if (Test-Path $targetFfmpeg) {
    Write-Host "FFmpeg runtime already exists: $targetFfmpeg" -ForegroundColor Yellow
    & $targetFfmpeg -version | Select-Object -First 1
    exit 0
}

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ultimate-ffmpeg-" + [System.Guid]::NewGuid().ToString("N"))
$zipPath = Join-Path $tempRoot "ffmpeg.zip"
$extractDir = Join-Path $tempRoot "extract"

try {
    New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $extractDir -Force | Out-Null

    Write-Host "Downloading FFmpeg archive..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath

    Write-Host "Extracting archive..." -ForegroundColor Cyan
    Expand-Archive -LiteralPath $zipPath -DestinationPath $extractDir -Force

    $ffmpegSource = Get-ChildItem -Path $extractDir -Filter "ffmpeg.exe" -Recurse -ErrorAction Stop | Select-Object -First 1
    if (-not $ffmpegSource) {
        throw "ffmpeg.exe not found in extracted archive"
    }

    $ffprobeSource = Get-ChildItem -Path $extractDir -Filter "ffprobe.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1

    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    Copy-Item -LiteralPath $ffmpegSource.FullName -Destination $targetFfmpeg -Force
    if ($ffprobeSource) {
        Copy-Item -LiteralPath $ffprobeSource.FullName -Destination $targetFfprobe -Force
    }

    Write-Host "FFmpeg runtime installed successfully." -ForegroundColor Green
    & $targetFfmpeg -version | Select-Object -First 1
    Write-Host "You can now restart the backend and use local video thumbnail generation." -ForegroundColor Yellow
} catch {
    Write-Host "Failed to install FFmpeg runtime: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    if (Test-Path $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
