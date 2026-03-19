param(
    [string]$PackageName = "com.ultimate.web",
    [int]$CaptureSeconds = 12
)

$ErrorActionPreference = "Stop"

function Require-Command([string]$name) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if (-not $cmd) {
        throw "Required command not found: $name"
    }
}

Require-Command "adb"

$root = Split-Path -Parent $PSScriptRoot
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$outDir = Join-Path $root "output\android_diag\$ts"
New-Item -ItemType Directory -Path $outDir -Force | Out-Null

function Save-Text([string]$name, [string]$text) {
    $path = Join-Path $outDir $name
    Set-Content -Path $path -Value $text -Encoding UTF8
}

function Invoke-AdbCapture([string]$argsLine) {
    $oldPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $result = & cmd /c "adb $argsLine" 2>&1
        return ($result -join "`n")
    } finally {
        $ErrorActionPreference = $oldPreference
    }
}

$deviceList = Invoke-AdbCapture "devices"
Save-Text "01_adb_devices.txt" $deviceList

$pkgList = Invoke-AdbCapture "shell pm list packages"
Save-Text "02_all_packages.txt" $pkgList

$pkgExists = $pkgList -match "package:$([regex]::Escape($PackageName))"
if (-not $pkgExists) {
    Save-Text "00_summary.txt" "Package not installed: $PackageName"
    Write-Host "[diag] package not installed: $PackageName"
    Write-Host "[diag] output: $outDir"
    exit 2
}

$pkgInfo = Invoke-AdbCapture "shell dumpsys package $PackageName"
Save-Text "03_package_info.txt" $pkgInfo

# Clear logcat first, then launch app and capture fresh logs.
[void](Invoke-AdbCapture "logcat -c")
[void](Invoke-AdbCapture "shell monkey -p $PackageName -c android.intent.category.LAUNCHER 1")
Start-Sleep -Seconds $CaptureSeconds

$logcat = Invoke-AdbCapture "logcat -d -v time"
Save-Text "04_logcat_full.txt" $logcat

$filtered = (Invoke-AdbCapture "logcat -d -v time") | Select-String -Pattern "UltimateEmbeddedBackend|Chaquopy|Python|Flask|backend|127.0.0.1|cleartext|NetworkSecurityConfig|ConnectException|ECONNREFUSED|Failed to start embedded backend"
Save-Text "05_logcat_filtered.txt" (($filtered | ForEach-Object { $_.Line }) -join "`n")

$runAsFiles = Invoke-AdbCapture "shell run-as $PackageName ls -la files"
Save-Text "06_run_as_files.txt" $runAsFiles

$runAsData = Invoke-AdbCapture "shell run-as $PackageName ls -la files/app_data"
Save-Text "07_run_as_app_data.txt" $runAsData

$bootLog = Invoke-AdbCapture "shell run-as $PackageName cat files/ultimate_backend_boot.log"
Save-Text "08_backend_boot_log.txt" $bootLog

$portHex = "1388"  # 5000 decimal in hex
$tcp = Invoke-AdbCapture "shell cat /proc/net/tcp"
$tcpHit = $tcp | Select-String -Pattern ":$portHex"
Save-Text "09_proc_net_tcp_5000.txt" (($tcpHit | ForEach-Object { $_.Line }) -join "`n")

$summary = @(
    "package=$PackageName",
    "capture_seconds=$CaptureSeconds",
    "output=$outDir",
    "hint=Check 05_logcat_filtered.txt and 08_backend_boot_log.txt first"
) -join "`n"
Save-Text "00_summary.txt" $summary

Write-Host "[diag] done"
Write-Host "[diag] output: $outDir"
