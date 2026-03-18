param(
    [string]$SdkRoot = "$env:LOCALAPPDATA\Android\Sdk",
    [string]$AndroidApi = "34",
    [string]$BuildTools = "34.0.0",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Write-Info($msg) {
    Write-Host "[INFO] $msg" -ForegroundColor Cyan
}

function Write-Warn($msg) {
    Write-Host "[WARN] $msg" -ForegroundColor Yellow
}

function Write-Err($msg) {
    Write-Host "[ERROR] $msg" -ForegroundColor Red
}

function Ensure-Command($name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $name"
    }
}

function Run-Step([string]$title, [scriptblock]$action) {
    Write-Info $title
    if ($DryRun) {
        Write-Host "        (dry-run) skipped execution" -ForegroundColor DarkGray
        return
    }
    & $action
}

function Test-WritableDirectory([string]$path) {
    $probe = Join-Path $path ".write_probe_$(Get-Random)"
    try {
        New-Item -ItemType File -Path $probe -Force | Out-Null
        Remove-Item -Path $probe -Force
        return $true
    } catch {
        return $false
    }
}

function Try-Run([scriptblock]$action) {
    try {
        & $action
        return $true
    } catch {
        return $false
    }
}

function Resolve-JavaHome {
    $javaCmd = Get-Command java -ErrorAction SilentlyContinue
    if ($javaCmd -and $javaCmd.Source) {
        $binDir = Split-Path -Parent $javaCmd.Source
        if ($binDir) {
            $javaHomeCandidate = Split-Path -Parent $binDir
            if ($javaHomeCandidate -and (Test-Path (Join-Path $javaHomeCandidate "bin\java.exe"))) {
                return $javaHomeCandidate
            }
        }
    }

    $patterns = @(
        "C:\Program Files\Eclipse Adoptium\jdk-17*",
        "C:\Program Files\Microsoft\jdk-17*",
        "C:\Program Files\Java\jdk-17*"
    )

    foreach ($pattern in $patterns) {
        $dirs = Get-ChildItem -Path $pattern -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending
        foreach ($dir in $dirs) {
            if (Test-Path (Join-Path $dir.FullName "bin\java.exe")) {
                return $dir.FullName
            }
        }
    }

    return $null
}

if ($env:OS -notmatch "Windows_NT") {
    throw "This script is for Windows only."
}

Ensure-Command "conda"
Ensure-Command "python"
Ensure-Command "npm"
Ensure-Command "npx"

$pyExe = (& python -c "import sys; print(sys.executable)").Trim()
$condaBase = Split-Path -Parent $pyExe

if ([string]::IsNullOrWhiteSpace($condaBase) -or -not (Test-Path $condaBase)) {
    throw "Unable to resolve conda base path from python executable."
}
Write-Info "Conda base: $condaBase"

if (-not $DryRun) {
    if (-not (Test-WritableDirectory $condaBase)) {
        throw "Conda base is not writable ($condaBase). Re-run PowerShell as Administrator."
    }
}

Run-Step "Upgrade pip in current Python (conda base expected)" {
    & python -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "pip upgrade failed."
    }
}

Run-Step "Install Python build dependencies (pyinstaller, flask-cors)" {
    & python -m pip install pyinstaller flask-cors
    if ($LASTEXITCODE -ne 0) {
        throw "pip install pyinstaller/flask-cors failed."
    }
}

$javaReady = $false
if (Try-Run { & java -version *> $null }) {
    $javaReady = $true
    Write-Info "Java already available in PATH."
}

if (-not $javaReady) {
    $javaHomeByScan = Resolve-JavaHome
    if ($javaHomeByScan) {
        $javaReady = $true
        Write-Info "Java detected by installation directory scan: $javaHomeByScan"
    }
}

if (-not $javaReady) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Run-Step "Install Java 17 via winget (Temurin)" {
            & winget install EclipseAdoptium.Temurin.17.JDK --accept-package-agreements --accept-source-agreements -e
            if ($LASTEXITCODE -ne 0) {
                $javaHomeFallback = Resolve-JavaHome
                if ($javaHomeFallback) {
                    Write-Warn "winget returned non-zero, but Java installation is detected: $javaHomeFallback"
                } else {
                    throw "winget Java install failed."
                }
            }
        }
    } else {
        throw "Java is still missing and winget is not available for fallback install."
    }
}

$javaHome = Resolve-JavaHome
if (-not $javaHome) {
    throw "Unable to resolve JAVA_HOME after Java install. Re-open terminal and re-run script."
}
$env:JAVA_HOME = $javaHome
if ($env:Path -notlike "*$javaHome\bin*") {
    $env:Path = "$javaHome\bin;$env:Path"
}
Write-Info "JAVA_HOME: $javaHome"

Run-Step "Prepare Android SDK root at $SdkRoot" {
    New-Item -ItemType Directory -Force -Path $SdkRoot | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $SdkRoot "cmdline-tools") | Out-Null
}

$toolsZip = Join-Path $env:TEMP "cmdline-tools-win-latest.zip"
$toolsExtract = Join-Path $env:TEMP "android-cmdline-tools-extract"
$toolsUrl = "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"

Run-Step "Download Android cmdline-tools from Google" {
    Invoke-WebRequest -Uri $toolsUrl -OutFile $toolsZip
}

Run-Step "Extract Android cmdline-tools archive" {
    if (Test-Path $toolsExtract) {
        Remove-Item -Path $toolsExtract -Recurse -Force
    }
    Expand-Archive -Path $toolsZip -DestinationPath $toolsExtract -Force
}

Run-Step "Install cmdline-tools into SDK root" {
    $sourceDir = Join-Path $toolsExtract "cmdline-tools"
    if (Test-Path (Join-Path $sourceDir "cmdline-tools")) {
        $sourceDir = Join-Path $sourceDir "cmdline-tools"
    }
    if (-not (Test-Path $sourceDir)) {
        throw "cmdline-tools source directory not found after extraction: $sourceDir"
    }

    $latestDir = Join-Path $SdkRoot "cmdline-tools\latest"
    if (Test-Path $latestDir) {
        Remove-Item -Path $latestDir -Recurse -Force
    }
    Copy-Item -Path $sourceDir -Destination $latestDir -Recurse -Force
}

$sdkManager = Join-Path $SdkRoot "cmdline-tools\latest\bin\sdkmanager.bat"
$adbPath = Join-Path $SdkRoot "platform-tools\adb.exe"

if (-not $DryRun) {
    if (-not (Test-Path $sdkManager)) {
        throw "sdkmanager not found at expected path: $sdkManager"
    }
}

$env:ANDROID_SDK_ROOT = $SdkRoot
$env:ANDROID_HOME = $SdkRoot
$condaJavaBin = Join-Path $condaBase "Library\bin"
if (Test-Path $condaJavaBin) {
    $env:Path = "$SdkRoot\cmdline-tools\latest\bin;$SdkRoot\platform-tools;$condaJavaBin;$env:Path"
} else {
    $env:Path = "$SdkRoot\cmdline-tools\latest\bin;$SdkRoot\platform-tools;$env:Path"
}

Run-Step "Accept Android SDK licenses" {
    cmd /c "(for /l %i in (1,1,200) do @echo y)|""$sdkManager"" --sdk_root=""$SdkRoot"" --licenses"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to accept Android SDK licenses."
    }
}

Run-Step "Install Android SDK packages (platform-tools, android-$AndroidApi, build-tools;$BuildTools)" {
    & $sdkManager "--sdk_root=$SdkRoot" "platform-tools" "platforms;android-$AndroidApi" "build-tools;$BuildTools"
    if ($LASTEXITCODE -ne 0) {
        throw "sdkmanager package install failed."
    }
}

Run-Step "Write conda base activation scripts for Android SDK env vars" {
    $activateDir = Join-Path $condaBase "etc\conda\activate.d"
    New-Item -ItemType Directory -Force -Path $activateDir | Out-Null

    $batPath = Join-Path $activateDir "android_sdk_env.bat"
    $ps1Path = Join-Path $activateDir "android_sdk_env.ps1"

    $batLines = @(
        "@echo off",
        "set ""JAVA_HOME=$javaHome""",
        "set ""PATH=%JAVA_HOME%\bin;%PATH%""",
        "set ""ANDROID_SDK_ROOT=$SdkRoot""",
        "set ""ANDROID_HOME=%ANDROID_SDK_ROOT%""",
        "set ""PATH=%ANDROID_SDK_ROOT%\cmdline-tools\latest\bin;%ANDROID_SDK_ROOT%\platform-tools;%PATH%"""
    )
    Set-Content -Path $batPath -Value $batLines -Encoding Ascii

    $ps1Lines = @(
        '$env:JAVA_HOME = "' + $javaHome + '"',
        '$javaBin = Join-Path $env:JAVA_HOME "bin"',
        'if ($env:Path -notlike "*$javaBin*") { $env:Path = "$javaBin;$env:Path" }',
        '$env:ANDROID_SDK_ROOT = "' + $SdkRoot + '"',
        '$env:ANDROID_HOME = $env:ANDROID_SDK_ROOT',
        '$androidBins = @(',
        '  (Join-Path $env:ANDROID_SDK_ROOT "cmdline-tools\latest\bin"),',
        '  (Join-Path $env:ANDROID_SDK_ROOT "platform-tools")',
        ')',
        'foreach ($bin in $androidBins) {',
        '  if ($env:Path -notlike "*$bin*") { $env:Path = "$bin;$env:Path" }',
        '}'
    )
    Set-Content -Path $ps1Path -Value $ps1Lines -Encoding Ascii
}

if (-not $DryRun) {
    Write-Info "Verification started..."

    Write-Host "python: " -NoNewline
    & python --version

    Write-Host "py modules: " -NoNewline
    & python -c "import importlib.util; print('PyInstaller=', bool(importlib.util.find_spec('PyInstaller')), 'flask_cors=', bool(importlib.util.find_spec('flask_cors')))"

    Write-Host "java: "
    & java -version

    Write-Host "sdkmanager: " -NoNewline
    & $sdkManager --version

    Write-Host "adb: " -NoNewline
    & $adbPath --version
}

Write-Info "Done. Re-open terminal and run: conda activate base"
Write-Info "Then verify: java -version, sdkmanager --version, adb --version"
