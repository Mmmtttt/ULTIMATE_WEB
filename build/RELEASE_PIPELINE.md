# Unified 3-Platform Release Pipeline

This repository now supports a single CI workflow that produces:

- Android APK
- Windows executable bundle
- Linux executable bundle

## One-click trigger

Use GitHub Actions workflow:

- Workflow file: `.github/workflows/release-three-platforms.yml`
- Trigger: `workflow_dispatch` (manual click) or push tag like `v1.2.3`

## What each CI job does

1. Build staged workspace with `scripts/build_unified.py`
2. Package target with `scripts/package_unified.py --execute`
3. Verify target status in `packaging_summary.json` is `built`
4. Upload target artifact (`ultimate-windows`, `ultimate-linux`, `ultimate-android`)
5. Collect all artifacts into `ultimate-release-bundle` with SHA256 manifest

## Local command (single host target)

For local smoke builds on current host:

```bash
python scripts/release_unified.py --targets windows --execute
python scripts/release_unified.py --targets linux --execute
python scripts/release_unified.py --targets android --execute
```

Note: desktop builds must run on matching host OS. Android build requires JDK 21 + Android SDK.
On Windows non-ASCII repo paths, Android packaging auto-stages in `%LOCALAPPDATA%\UltimateWebBuild\android_workspace`.

## Windows local packaging (venv only)

Use this helper on Windows to package from a clean local `venv` (no conda dependency):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/release_windows_local_venv.ps1
```

Optional arguments:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/release_windows_local_venv.ps1 `
  -VenvDir .venv-packaging-win `
  -BuildOutput output/local_stage `
  -PackageOutput output/local_packages
```

This script is only for local packaging and does not change GitHub Actions workflow behavior.
