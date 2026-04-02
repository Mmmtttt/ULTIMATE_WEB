#!/usr/bin/env python3
"""
Unified multi-target build skeleton.

This script does not create final executables/APK in the current phase.
It creates standardized package workspaces for:
  - windows
  - linux
  - android

Future packagers (PyInstaller, Android tooling, etc.) can consume these
workspaces without requiring source changes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Set


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "comic_backend"
FRONTEND_DIR = ROOT_DIR / "comic_frontend"
DEFAULT_TARGETS_CONFIG = ROOT_DIR / "build" / "targets.json"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "output" / "multi_target"
DEFAULT_APP_VERSION = "0.0.0"

BASE_BACKEND_EXCLUDE_DIRS = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "venv",
    "logs",
    "data",
}
BASE_BACKEND_EXCLUDE_FILES = {
    ".DS_Store",
}

ANDROID_BACKEND_EXCLUDE_DIRS = {
    "third_party",
}
ANDROID_BACKEND_EXCLUDE_FILES = {
    "third_party_config.json",
}


def run_cmd(cmd: List[str], cwd: Path, env: Dict[str, str] | None = None) -> None:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    result = subprocess.run(cmd, cwd=str(cwd), check=False, env=merged_env)
    if result.returncode != 0:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(cmd)}")


def get_npm_command() -> str:
    # On Windows, npm is typically available as npm.cmd for subprocess calls.
    return "npm.cmd" if os.name == "nt" else "npm"


def load_targets(config_path: Path) -> List[Dict]:
    if not config_path.exists():
        raise FileNotFoundError(f"targets config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as fp:
        raw = json.load(fp)

    targets = raw.get("targets", [])
    if not isinstance(targets, list) or not targets:
        raise ValueError("targets config is empty")

    normalized = []
    for item in targets:
        if not isinstance(item, dict):
            continue
        target_id = str(item.get("id", "")).strip().lower()
        if not target_id:
            continue
        runtime_profile = str(item.get("runtime_profile", "full")).strip() or "full"
        third_party_enabled = bool(item.get("third_party_enabled", runtime_profile == "full"))
        normalized.append(
            {
                "id": target_id,
                "runtime_profile": runtime_profile,
                "third_party_enabled": third_party_enabled,
                "notes": str(item.get("notes", "")).strip(),
            }
        )
    if not normalized:
        raise ValueError("no valid targets in config")
    return normalized


def normalize_app_version(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""

    if text.lower().startswith("refs/tags/"):
        text = text.split("/", 2)[-1]
    if text.startswith(("v", "V")) and re.search(r"\d", text[1:]):
        text = text[1:]
    return text.strip()


def resolve_app_version(cli_app_version: str = "") -> str:
    candidates = [
        cli_app_version,
        os.environ.get("ULTIMATE_APP_VERSION", ""),
        os.environ.get("GITHUB_REF_NAME", ""),
        os.environ.get("GITHUB_REF", ""),
    ]
    for candidate in candidates:
        normalized = normalize_app_version(candidate)
        if normalized and re.search(r"\d", normalized):
            return normalized

    package_json = FRONTEND_DIR / "package.json"
    if package_json.exists():
        try:
            raw = json.loads(package_json.read_text(encoding="utf-8"))
            package_version = normalize_app_version(raw.get("version", ""))
            if package_version:
                return package_version
        except Exception:
            pass

    return DEFAULT_APP_VERSION


def build_frontend_if_needed(skip_frontend_build: bool, app_version: str) -> Path:
    dist_dir = FRONTEND_DIR / "dist"
    if not skip_frontend_build:
        print("[build] frontend: npm run build")
        frontend_env = {
            "VITE_APP_VERSION": app_version,
            "ULTIMATE_APP_VERSION": app_version,
        }
        try:
            run_cmd([get_npm_command(), "run", "build"], cwd=FRONTEND_DIR, env=frontend_env)
        except RuntimeError as exc:
            raise RuntimeError(
                f"{exc}. if dist already exists, retry with --skip-frontend-build"
            ) from exc
    if not dist_dir.exists():
        raise FileNotFoundError(f"frontend dist not found: {dist_dir}")
    return dist_dir


def copy_tree_with_filters(
    src: Path,
    dst: Path,
    exclude_dirs: Set[str] | None = None,
    exclude_files: Set[str] | None = None,
) -> None:
    exclude_dirs = exclude_dirs or set()
    exclude_files = exclude_files or set()

    def _ignore(_current_dir: str, names: Iterable[str]) -> Set[str]:
        ignored: Set[str] = set()
        for name in names:
            if name in exclude_dirs or name in exclude_files:
                ignored.add(name)
        return ignored

    shutil.copytree(src, dst, ignore=_ignore)


def write_runtime_env(target: Dict, target_dir: Path, app_version: str) -> Path:
    env_path = target_dir / "runtime.env"
    lines = [
        f"BACKEND_RUNTIME_PROFILE={target['runtime_profile']}",
        f"BACKEND_ENABLE_THIRD_PARTY={'true' if target['third_party_enabled'] else 'false'}",
        f"ULTIMATE_APP_VERSION={app_version}",
    ]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return env_path


def write_launchers(target: Dict, target_dir: Path) -> None:
    runtime_profile = target["runtime_profile"]
    third_party_enabled = "true" if target["third_party_enabled"] else "false"

    windows_launcher = (
        "@echo off\n"
        f"set BACKEND_RUNTIME_PROFILE={runtime_profile}\n"
        f"set BACKEND_ENABLE_THIRD_PARTY={third_party_enabled}\n"
        "set BACKEND_DEBUG=false\n"
        "set FRONTEND_DIST_DIR=%~dp0comic_frontend_dist\n"
        "cd /d %~dp0comic_backend\n"
        "python app.py\n"
    )
    (target_dir / "start_backend.bat").write_text(windows_launcher, encoding="utf-8")

    shell_launcher = (
        "#!/usr/bin/env sh\n"
        "SCRIPT_DIR=\"$(cd \"$(dirname \"$0\")\" && pwd)\"\n"
        f"export BACKEND_RUNTIME_PROFILE=\"{runtime_profile}\"\n"
        f"export BACKEND_ENABLE_THIRD_PARTY=\"{third_party_enabled}\"\n"
        "export BACKEND_DEBUG=\"false\"\n"
        "export FRONTEND_DIST_DIR=\"$SCRIPT_DIR/comic_frontend_dist\"\n"
        "cd \"$SCRIPT_DIR/comic_backend\"\n"
        "if command -v python3 >/dev/null 2>&1; then\n"
        "  exec python3 app.py\n"
        "fi\n"
        "exec python app.py\n"
    )
    sh_path = target_dir / "start_backend.sh"
    sh_path.write_text(shell_launcher, encoding="utf-8")
    try:
        sh_path.chmod(0o755)
    except OSError:
        pass


def write_manifest(target: Dict, target_dir: Path, app_version: str) -> None:
    manifest = {
        "target": target["id"],
        "runtime_profile": target["runtime_profile"],
        "third_party_enabled": target["third_party_enabled"],
        "app_version": app_version,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "layout": {
            "backend_dir": "comic_backend",
            "frontend_dist_dir": "comic_frontend_dist",
            "runtime_env_file": "runtime.env",
            "launcher_windows": "start_backend.bat",
            "launcher_posix": "start_backend.sh",
        },
        "notes": target.get("notes", ""),
    }
    manifest_path = target_dir / "package_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_target(target: Dict, frontend_dist_dir: Path, output_dir: Path, app_version: str) -> Path:
    target_dir = output_dir / target["id"]
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    backend_exclude_dirs = set(BASE_BACKEND_EXCLUDE_DIRS)
    backend_exclude_files = set(BASE_BACKEND_EXCLUDE_FILES)
    if target["id"] == "android":
        backend_exclude_dirs.update(ANDROID_BACKEND_EXCLUDE_DIRS)
        backend_exclude_files.update(ANDROID_BACKEND_EXCLUDE_FILES)

    copy_tree_with_filters(
        BACKEND_DIR,
        target_dir / "comic_backend",
        exclude_dirs=backend_exclude_dirs,
        exclude_files=backend_exclude_files,
    )
    shutil.copytree(frontend_dist_dir, target_dir / "comic_frontend_dist")

    server_config_src = ROOT_DIR / "server_config.json"
    if server_config_src.exists():
        shutil.copy2(server_config_src, target_dir / "server_config.json")

    write_runtime_env(target, target_dir, app_version)
    write_launchers(target, target_dir)
    write_manifest(target, target_dir, app_version)
    return target_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build standardized multi-target package workspaces.")
    parser.add_argument(
        "--targets",
        default="all",
        help="Comma-separated target ids from build/targets.json, or 'all' (default).",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_TARGETS_CONFIG),
        help=f"Targets config path (default: {DEFAULT_TARGETS_CONFIG})",
    )
    parser.add_argument(
        "--skip-frontend-build",
        action="store_true",
        help="Skip 'npm run build' and reuse existing comic_frontend/dist.",
    )
    parser.add_argument(
        "--app-version",
        default="",
        help="Set packaged app version (e.g. 2.0.0). Defaults to env/tag/package.json resolution.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).resolve()
    output_dir = Path(args.output).resolve()

    targets = load_targets(config_path)
    target_map = {item["id"]: item for item in targets}

    if args.targets.strip().lower() == "all":
        selected_ids = list(target_map.keys())
    else:
        selected_ids = [item.strip().lower() for item in args.targets.split(",") if item.strip()]
        unknown = [item for item in selected_ids if item not in target_map]
        if unknown:
            raise ValueError(f"unknown targets: {', '.join(unknown)}")

    selected_targets = [target_map[item] for item in selected_ids]
    print(f"[build] targets: {', '.join(selected_ids)}")
    print(f"[build] output: {output_dir}")
    app_version = resolve_app_version(args.app_version)
    print(f"[build] app_version: {app_version}")

    frontend_dist_dir = build_frontend_if_needed(
        skip_frontend_build=args.skip_frontend_build,
        app_version=app_version,
    )

    built_dirs = []
    for target in selected_targets:
        built_dir = build_target(target, frontend_dist_dir, output_dir, app_version)
        built_dirs.append(built_dir)
        print(f"[build] prepared: {built_dir}")

    print("[build] done")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[build] failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
