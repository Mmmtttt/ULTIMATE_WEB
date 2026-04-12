# Unified 3-Platform Release Pipeline

This repository now supports a single CI workflow that produces:

- Android APK
- Windows executable bundle
- Linux executable bundle
- Docker image published to DockerHub

## One-click trigger

Use GitHub Actions workflow:

- Workflow file: `.github/workflows/release-three-platforms.yml`
- Trigger: `workflow_dispatch` (manual click) or push tag like `v1.2.3`
- Optional manual input: `app_version`

## What each CI job does

1. Resolve one shared `APP_VERSION` for the whole workflow
2. Build staged workspace with `scripts/build_unified.py`
3. Package target with `scripts/package_unified.py --execute`
4. Verify target status in `packaging_summary.json` is `built`
5. Upload target artifact (`ultimate-windows`, `ultimate-linux`, `ultimate-android`)
6. Collect all artifacts into `ultimate-release-bundle` with SHA256 manifest
7. Build and push Docker image to DockerHub with the same version tag

## Docker publish notes

The Docker publish step uses the same `APP_VERSION` as Windows/Linux/Android packages.

Example:

- Git tag `v1.2.3`
- Desktop bundle version `1.2.3`
- Android `versionName` `1.2.3`
- Docker image tag `1.2.3`

On tag-triggered releases, the workflow also pushes `latest`.

Required GitHub secrets and variables:

- Secret `DOCKERHUB_USERNAME`
- Secret `DOCKERHUB_TOKEN`
- Optional variable `DOCKERHUB_IMAGE`

If `DOCKERHUB_IMAGE` is not set, the workflow defaults to:

- `${DOCKERHUB_USERNAME}/ultimate-web`

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
