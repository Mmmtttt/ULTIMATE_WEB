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

Note: desktop builds must run on matching host OS. Android build requires Java + Android SDK.
