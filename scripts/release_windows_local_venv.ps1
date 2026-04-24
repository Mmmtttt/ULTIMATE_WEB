param(
    [string]$PythonExe = "python",
    [string]$VenvDir = ".venv-packaging-win",
    [string]$BuildOutput = "output/local_stage",
    [string]$PackageOutput = "output/local_packages",
    [switch]$SkipFrontendBuild
)

$ErrorActionPreference = "Stop"

function Write-Info([string]$Message) {
    Write-Host "[windows-local-venv] $Message" -ForegroundColor Cyan
}

function Assert-CommandExists([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

Assert-CommandExists $PythonExe
Assert-CommandExists "npm"

$venvPath = Join-Path $repoRoot $VenvDir
if (-not (Test-Path $venvPath)) {
    Write-Info "Create venv: $venvPath"
    & $PythonExe -m venv $venvPath
}

$venvPython = Join-Path $venvPath "Scripts/python.exe"
if (-not (Test-Path $venvPython)) {
    throw "venv python not found: $venvPython"
}

Write-Info "Install Python build dependencies into venv"
& $venvPython -m pip install --upgrade pip setuptools wheel
& $venvPython -m pip install -r "comic_backend/requirements.txt" pyinstaller
$pluginPackagingReqFile = Join-Path $repoRoot ".plugin_packaging_requirements.txt"
& $venvPython "scripts/export_plugin_packaging_requirements.py" "--output" $pluginPackagingReqFile
if ((Test-Path $pluginPackagingReqFile) -and ((Get-Item $pluginPackagingReqFile).Length -gt 0)) {
    & $venvPython -m pip install -r $pluginPackagingReqFile
}

if (-not $SkipFrontendBuild) {
    Write-Info "Install and build frontend"
    Push-Location "comic_frontend"
    if (Test-Path "package-lock.json") {
        npm ci --no-audit --no-fund
    } else {
        npm install --no-audit --no-fund
    }
    npm run build
    Pop-Location
}

$releaseArgs = @(
    "scripts/release_unified.py",
    "--targets", "windows",
    "--execute",
    "--build-output", $BuildOutput,
    "--package-output", $PackageOutput
)
if ($SkipFrontendBuild) {
    $releaseArgs += "--skip-frontend-build"
}

Write-Info ("Run release pipeline: " + ($releaseArgs -join " "))
& $venvPython @releaseArgs
if ($LASTEXITCODE -ne 0) {
    throw "Windows local venv packaging failed with code $LASTEXITCODE"
}

Write-Info "Done."
Write-Info "Package output: $PackageOutput/windows"
