$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = (Get-Item $scriptDir).Parent.FullName

Set-Location $rootDir

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$pythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        & $cmd --version *> $null
        if ($LASTEXITCODE -eq 0) {
            $pythonCmd = $cmd
            break
        }
    } catch {
    }
}

if (-not $pythonCmd) {
    Write-Host "[build] Python not found" -ForegroundColor Red
    exit 1
}

Write-Host "[build] Running unified multi-target build..." -ForegroundColor Cyan
& $pythonCmd "$scriptDir\build_unified.py" @args
exit $LASTEXITCODE
