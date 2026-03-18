#!/usr/bin/env python3
"""
Unified packaging orchestrator on top of staged multi-target workspaces.

Expected staged input layout (from scripts/build_unified.py):
  output/multi_target/<target>/
    comic_backend/
    comic_frontend_dist/
    runtime.env
    package_manifest.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_STAGED_DIR = ROOT_DIR / "output" / "multi_target"
DEFAULT_PACKAGES_DIR = ROOT_DIR / "output" / "packages"
DEFAULT_TARGETS_CONFIG = ROOT_DIR / "build" / "targets.json"
DEFAULT_PACKAGERS_CONFIG = ROOT_DIR / "build" / "packagers.json"


@dataclass
class PackageResult:
    target: str
    status: str
    message: str
    output_dir: str
    command: Optional[List[str]] = None


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"config not found: {path}")
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def parse_runtime_env(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        values[key.strip()] = val.strip()
    return values


def run_cmd(cmd: List[str], cwd: Path, env: Optional[Dict[str, str]] = None) -> Tuple[int, str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    process = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=merged_env,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (process.stdout or "") + (process.stderr or "")
    return process.returncode, output


def is_pyinstaller_available() -> bool:
    return importlib.util.find_spec("PyInstaller") is not None


def ensure_clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def select_targets(targets: List[str], requested: str) -> List[str]:
    available = [item.strip().lower() for item in targets if item.strip()]
    if requested.strip().lower() == "all":
        return available
    selected = [item.strip().lower() for item in requested.split(",") if item.strip()]
    unknown = [item for item in selected if item not in available]
    if unknown:
        raise ValueError(f"unknown targets: {', '.join(unknown)}")
    return selected


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_pyinstaller_scripts(
    out_dir: Path,
    staged_target_dir: Path,
    binary_name: str,
    entry: str,
    runtime_env: Dict[str, str],
) -> List[str]:
    cmd = ["python", "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--name", binary_name, entry]

    ps1 = (
        "$ErrorActionPreference = 'Stop'\n"
        f"Set-Location \"{staged_target_dir}\"\n"
        f"$env:BACKEND_RUNTIME_PROFILE = \"{runtime_env.get('BACKEND_RUNTIME_PROFILE', 'full')}\"\n"
        f"$env:BACKEND_ENABLE_THIRD_PARTY = \"{runtime_env.get('BACKEND_ENABLE_THIRD_PARTY', 'true')}\"\n"
        + " ".join([f"\"{part}\"" if " " in part else part for part in cmd])
        + "\n"
    )
    write_text(out_dir / "run_pyinstaller.ps1", ps1)

    sh = (
        "#!/usr/bin/env sh\n"
        "set -e\n"
        f"cd \"{staged_target_dir}\"\n"
        f"export BACKEND_RUNTIME_PROFILE=\"{runtime_env.get('BACKEND_RUNTIME_PROFILE', 'full')}\"\n"
        f"export BACKEND_ENABLE_THIRD_PARTY=\"{runtime_env.get('BACKEND_ENABLE_THIRD_PARTY', 'true')}\"\n"
        + " ".join(cmd)
        + "\n"
    )
    sh_path = out_dir / "run_pyinstaller.sh"
    write_text(sh_path, sh)
    try:
        sh_path.chmod(0o755)
    except OSError:
        pass
    return cmd


def package_pyinstaller(
    target: str,
    staged_target_dir: Path,
    packager_cfg: Dict,
    target_out_dir: Path,
    execute: bool,
) -> PackageResult:
    runtime_env = parse_runtime_env(staged_target_dir / "runtime.env")
    binary_name = str(packager_cfg.get("binary_name", f"ultimate_backend_{target}")).strip()
    entry = str(packager_cfg.get("entry", "comic_backend/app.py")).strip()

    cmd = write_pyinstaller_scripts(
        out_dir=target_out_dir,
        staged_target_dir=staged_target_dir,
        binary_name=binary_name,
        entry=entry,
        runtime_env=runtime_env,
    )

    if not execute:
        return PackageResult(
            target=target,
            status="prepared",
            message="pyinstaller scripts generated (execution skipped)",
            output_dir=str(target_out_dir),
            command=cmd,
        )

    if not is_pyinstaller_available():
        return PackageResult(
            target=target,
            status="blocked",
            message="PyInstaller not installed in current Python environment",
            output_dir=str(target_out_dir),
            command=cmd,
        )

    code, output = run_cmd(cmd, cwd=staged_target_dir, env=runtime_env)
    build_log = target_out_dir / "pyinstaller.log"
    write_text(build_log, output)
    if code != 0:
        return PackageResult(
            target=target,
            status="failed",
            message=f"pyinstaller failed with code {code}; see {build_log}",
            output_dir=str(target_out_dir),
            command=cmd,
        )
    return PackageResult(
        target=target,
        status="built",
        message="pyinstaller build completed",
        output_dir=str(target_out_dir),
        command=cmd,
    )


def write_android_capacitor_plan(
    target_out_dir: Path,
    staged_target_dir: Path,
    packager_cfg: Dict,
) -> List[str]:
    app_id = str(packager_cfg.get("app_id", "com.ultimate.web")).strip()
    app_name = str(packager_cfg.get("app_name", "UltimateWeb")).strip()
    web_dir = str(packager_cfg.get("web_dir", "comic_frontend_dist")).strip()
    android_project_dir = str(packager_cfg.get("android_project_dir", "android_app")).strip()

    commands = [
        "npm install @capacitor/core @capacitor/cli @capacitor/android",
        f"npx cap init {app_name} {app_id}",
        f"npx cap add android",
        f"npx cap copy android --web-dir {web_dir}",
        "npx cap sync android",
        "npx cap open android"
    ]

    plan = [
        "# Android Packaging Plan",
        "",
        "This project currently generates packaging workspace only.",
        "Run the following commands in the staged target directory:",
        f"`{staged_target_dir}`",
        "",
    ]
    for idx, cmd in enumerate(commands, start=1):
        plan.append(f"{idx}. `{cmd}`")
    plan.append("")
    plan.append("Notes:")
    plan.append(f"- staged web assets directory: `{web_dir}`")
    plan.append(f"- suggested Android project directory: `{android_project_dir}`")
    plan.append("- ensure Android SDK, Java, and Gradle are configured before running.")
    write_text(target_out_dir / "android_packaging_plan.md", "\n".join(plan) + "\n")

    ps1_lines = [
        "$ErrorActionPreference = 'Stop'",
        f"Set-Location \"{staged_target_dir}\"",
    ] + commands
    write_text(target_out_dir / "run_capacitor.ps1", "\n".join(ps1_lines) + "\n")

    sh_lines = [
        "#!/usr/bin/env sh",
        "set -e",
        f"cd \"{staged_target_dir}\"",
    ] + commands
    sh_path = target_out_dir / "run_capacitor.sh"
    write_text(sh_path, "\n".join(sh_lines) + "\n")
    try:
        sh_path.chmod(0o755)
    except OSError:
        pass
    return commands


def package_android(
    target: str,
    staged_target_dir: Path,
    packager_cfg: Dict,
    target_out_dir: Path,
    execute: bool,
) -> PackageResult:
    commands = write_android_capacitor_plan(target_out_dir, staged_target_dir, packager_cfg)
    if execute:
        return PackageResult(
            target=target,
            status="prepared",
            message="android packaging scripts generated; execute manually with SDK environment",
            output_dir=str(target_out_dir),
            command=commands,
        )
    return PackageResult(
        target=target,
        status="prepared",
        message="android packaging plan generated",
        output_dir=str(target_out_dir),
        command=commands,
    )


def write_summary(results: List[PackageResult], output_dir: Path) -> Path:
    payload = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "host_platform": platform.platform(),
        "results": [
            {
                "target": item.target,
                "status": item.status,
                "message": item.message,
                "output_dir": item.output_dir,
                "command": item.command or [],
            }
            for item in results
        ],
    }
    summary_path = output_dir / "packaging_summary.json"
    write_text(summary_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return summary_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare/execute package commands for multi-target staged workspaces.")
    parser.add_argument("--targets", default="all", help="Comma-separated targets or 'all'.")
    parser.add_argument("--staged", default=str(DEFAULT_STAGED_DIR), help="Staged workspaces root.")
    parser.add_argument("--output", default=str(DEFAULT_PACKAGES_DIR), help="Packaging output root.")
    parser.add_argument("--targets-config", default=str(DEFAULT_TARGETS_CONFIG), help="Path to build/targets.json.")
    parser.add_argument("--packagers-config", default=str(DEFAULT_PACKAGERS_CONFIG), help="Path to build/packagers.json.")
    parser.add_argument("--execute", action="store_true", help="Execute packaging commands when possible.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    staged_root = Path(args.staged).resolve()
    output_root = Path(args.output).resolve()
    targets_cfg = load_json(Path(args.targets_config).resolve())
    packagers_cfg = load_json(Path(args.packagers_config).resolve())

    available_targets = [str(item.get("id", "")).strip().lower() for item in targets_cfg.get("targets", []) if str(item.get("id", "")).strip()]
    selected_targets = select_targets(available_targets, args.targets)

    packagers = packagers_cfg.get("packagers", {})
    if not isinstance(packagers, dict):
        raise ValueError("invalid packagers config")

    print(f"[package] targets: {', '.join(selected_targets)}")
    print(f"[package] staged root: {staged_root}")
    print(f"[package] output root: {output_root}")

    results: List[PackageResult] = []
    for target in selected_targets:
        staged_target_dir = staged_root / target
        target_out_dir = output_root / target
        ensure_clean_dir(target_out_dir)

        if not staged_target_dir.exists():
            results.append(
                PackageResult(
                    target=target,
                    status="blocked",
                    message=f"staged target directory not found: {staged_target_dir}",
                    output_dir=str(target_out_dir),
                )
            )
            continue

        packager_cfg = packagers.get(target, {})
        packager_type = str(packager_cfg.get("type", "")).strip().lower()
        if packager_type == "pyinstaller":
            result = package_pyinstaller(target, staged_target_dir, packager_cfg, target_out_dir, execute=args.execute)
        elif packager_type == "capacitor":
            result = package_android(target, staged_target_dir, packager_cfg, target_out_dir, execute=args.execute)
        else:
            result = PackageResult(
                target=target,
                status="blocked",
                message=f"unsupported packager type: {packager_type or 'empty'}",
                output_dir=str(target_out_dir),
            )

        results.append(result)
        print(f"[package] {target}: {result.status} - {result.message}")

    summary_path = write_summary(results, output_root)
    print(f"[package] summary: {summary_path}")

    has_failed = any(item.status in {"failed"} for item in results)
    return 1 if has_failed else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[package] failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
