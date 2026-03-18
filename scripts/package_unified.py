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


def has_non_ascii_path(path: Path) -> bool:
    return any(ord(ch) > 127 for ch in str(path))


def choose_android_workspace_dir(target_out_dir: Path, staged_target_dir: Path, packager_cfg: Dict) -> Path:
    configured_root = str(packager_cfg.get("workspace_root", "")).strip()
    if configured_root:
        root = Path(configured_root).expanduser().resolve()
        return root / f"{target_out_dir.name}_{staged_target_dir.name}"

    default_workspace = target_out_dir / "android_workspace"
    if os.name != "nt" or not has_non_ascii_path(default_workspace):
        return default_workspace

    env_root = os.environ.get("ULTIMATE_ANDROID_WORKSPACE_ROOT", "").strip()
    if env_root:
        fallback_root = Path(env_root).expanduser().resolve()
    else:
        local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
        if local_appdata:
            fallback_root = Path(local_appdata) / "UltimateWebBuild" / "android_workspace"
        else:
            fallback_root = Path.home() / "AppData" / "Local" / "UltimateWebBuild" / "android_workspace"
    return fallback_root / f"{target_out_dir.name}_{staged_target_dir.name}"


def get_npm_command() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def get_npx_command() -> str:
    return "npx.cmd" if os.name == "nt" else "npx"


def current_host_target() -> str:
    if os.name == "nt":
        return "windows"
    return "linux"


def is_desktop_target(target: str) -> bool:
    return target in {"windows", "linux"}


def write_desktop_bundle_scripts(
    bundle_dir: Path,
    binary_name: str,
    runtime_env: Dict[str, str],
) -> None:
    runtime_profile = runtime_env.get("BACKEND_RUNTIME_PROFILE", "full")
    third_party_enabled = runtime_env.get("BACKEND_ENABLE_THIRD_PARTY", "true")

    bat = (
        "@echo off\n"
        "setlocal\n"
        f"set BACKEND_RUNTIME_PROFILE={runtime_profile}\n"
        f"set BACKEND_ENABLE_THIRD_PARTY={third_party_enabled}\n"
        "set SCRIPT_DIR=%~dp0\n"
        f"if exist \"%SCRIPT_DIR%bin\\{binary_name}.exe\" (\n"
        f"  \"%SCRIPT_DIR%bin\\{binary_name}.exe\"\n"
        "  exit /b %ERRORLEVEL%\n"
        ")\n"
        "cd /d \"%SCRIPT_DIR%backend_source\"\n"
        "python app.py\n"
    )
    write_text(bundle_dir / "start_backend.bat", bat)

    ps1 = (
        "$ErrorActionPreference = 'Stop'\n"
        "$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path\n"
        f"$env:BACKEND_RUNTIME_PROFILE = \"{runtime_profile}\"\n"
        f"$env:BACKEND_ENABLE_THIRD_PARTY = \"{third_party_enabled}\"\n"
        f"$exePath = Join-Path $scriptDir \"bin/{binary_name}.exe\"\n"
        "if (Test-Path $exePath) {\n"
        "    & $exePath\n"
        "    exit $LASTEXITCODE\n"
        "}\n"
        "$backendSource = Join-Path $scriptDir \"backend_source\"\n"
        "Set-Location $backendSource\n"
        "python app.py\n"
    )
    write_text(bundle_dir / "start_backend.ps1", ps1)

    sh = (
        "#!/usr/bin/env sh\n"
        "set -e\n"
        f"export BACKEND_RUNTIME_PROFILE=\"{runtime_profile}\"\n"
        f"export BACKEND_ENABLE_THIRD_PARTY=\"{third_party_enabled}\"\n"
        "SCRIPT_DIR=\"$(cd \"$(dirname \"$0\")\" && pwd)\"\n"
        f"if [ -x \"$SCRIPT_DIR/bin/{binary_name}\" ]; then\n"
        f"  exec \"$SCRIPT_DIR/bin/{binary_name}\"\n"
        "fi\n"
        "cd \"$SCRIPT_DIR/backend_source\"\n"
        "if command -v python3 >/dev/null 2>&1; then\n"
        "  exec python3 app.py\n"
        "fi\n"
        "exec python app.py\n"
    )
    sh_path = bundle_dir / "start_backend.sh"
    write_text(sh_path, sh)
    try:
        sh_path.chmod(0o755)
    except OSError:
        pass


def prepare_desktop_release_bundle(
    target: str,
    target_out_dir: Path,
    staged_target_dir: Path,
    binary_name: str,
    runtime_env: Dict[str, str],
) -> Path:
    bundle_dir = target_out_dir / "release_bundle"
    ensure_clean_dir(bundle_dir)

    backend_src = staged_target_dir / "comic_backend"
    frontend_dist = staged_target_dir / "comic_frontend_dist"

    if backend_src.exists():
        shutil.copytree(backend_src, bundle_dir / "backend_source")
    if frontend_dist.exists():
        shutil.copytree(frontend_dist, bundle_dir / "frontend_dist")

    runtime_env_src = staged_target_dir / "runtime.env"
    if runtime_env_src.exists():
        shutil.copy2(runtime_env_src, bundle_dir / "runtime.env")

    manifest_src = staged_target_dir / "package_manifest.json"
    if manifest_src.exists():
        shutil.copy2(manifest_src, bundle_dir / "stage_manifest.json")

    notes = [
        "# Desktop Release Bundle",
        "",
        f"- target: `{target}`",
        "- `backend_source/`: fallback Python source runtime",
        "- `frontend_dist/`: frontend static assets",
        "- `bin/`: packaged backend executable (if packaging executed successfully)",
        "",
        "Start commands:",
        "- Windows cmd: `start_backend.bat`",
        "- Windows PowerShell: `start_backend.ps1`",
        "- Linux/macOS: `start_backend.sh`",
    ]
    write_text(bundle_dir / "README.md", "\n".join(notes) + "\n")

    (bundle_dir / "bin").mkdir(parents=True, exist_ok=True)
    write_desktop_bundle_scripts(bundle_dir, binary_name=binary_name, runtime_env=runtime_env)
    return bundle_dir


def write_pyinstaller_scripts(
    out_dir: Path,
    staged_target_dir: Path,
    target: str,
    binary_name: str,
    entry: str,
    runtime_env: Dict[str, str],
) -> List[str]:
    dist_dir = out_dir / "dist"
    work_dir = out_dir / "build"
    spec_dir = out_dir / "spec"
    cmd = [
        "python",
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        binary_name,
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(work_dir),
        "--specpath",
        str(spec_dir),
        entry,
    ]

    ps1 = (
        "$ErrorActionPreference = 'Stop'\n"
        "param(\n"
        f"    [string]$StagedDir = \"{staged_target_dir}\"\n"
        ")\n"
        "Set-Location $StagedDir\n"
        f"$env:BACKEND_RUNTIME_PROFILE = \"{runtime_env.get('BACKEND_RUNTIME_PROFILE', 'full')}\"\n"
        f"$env:BACKEND_ENABLE_THIRD_PARTY = \"{runtime_env.get('BACKEND_ENABLE_THIRD_PARTY', 'true')}\"\n"
        + " ".join([f"\"{part}\"" if " " in part else part for part in cmd])
        + "\n"
    )
    write_text(out_dir / "run_pyinstaller.ps1", ps1)

    sh = (
        "#!/usr/bin/env sh\n"
        "set -e\n"
        "STAGED_DIR=\"${1:-"
        + str(staged_target_dir).replace("\\", "/")
        + "}\"\n"
        "cd \"$STAGED_DIR\"\n"
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
        target=target,
        binary_name=binary_name,
        entry=entry,
        runtime_env=runtime_env,
    )
    bundle_dir = prepare_desktop_release_bundle(
        target=target,
        target_out_dir=target_out_dir,
        staged_target_dir=staged_target_dir,
        binary_name=binary_name,
        runtime_env=runtime_env,
    )

    if not execute:
        return PackageResult(
            target=target,
            status="prepared",
            message="pyinstaller scripts generated; desktop release bundle prepared (execution skipped)",
            output_dir=str(target_out_dir),
            command=cmd,
        )

    host_target = current_host_target()
    if target != host_target:
        return PackageResult(
            target=target,
            status="blocked",
            message=f"packaging host mismatch: current host is {host_target}, target is {target}",
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
    dist_dir = target_out_dir / "dist"
    built_binary = dist_dir / binary_name
    if target == "windows":
        built_binary = built_binary.with_suffix(".exe")
    if built_binary.exists():
        shutil.copy2(built_binary, bundle_dir / "bin" / built_binary.name)

    return PackageResult(
        target=target,
        status="built",
        message="pyinstaller build completed and desktop release bundle updated",
        output_dir=str(target_out_dir),
        command=cmd,
    )


def write_android_capacitor_plan(
    target_out_dir: Path,
    staged_target_dir: Path,
    packager_cfg: Dict,
) -> Tuple[List[List[str]], Path, str]:
    app_id = str(packager_cfg.get("app_id", "com.ultimate.web")).strip()
    app_name = str(packager_cfg.get("app_name", "UltimateWeb")).strip()
    staged_web_dir_name = str(packager_cfg.get("web_dir", "comic_frontend_dist")).strip() or "comic_frontend_dist"
    workspace_web_dir_name = str(packager_cfg.get("workspace_web_dir", "web")).strip() or "web"
    gradle_task = str(packager_cfg.get("gradle_task", "assembleDebug")).strip() or "assembleDebug"
    apk_relative_path = str(
        packager_cfg.get(
            "apk_relative_path",
            "android/app/build/outputs/apk/debug/app-debug.apk",
        )
    ).strip() or "android/app/build/outputs/apk/debug/app-debug.apk"

    workspace_dir = choose_android_workspace_dir(target_out_dir, staged_target_dir, packager_cfg)
    ensure_clean_dir(workspace_dir)

    staged_web_dir = staged_target_dir / staged_web_dir_name
    if not staged_web_dir.exists():
        raise FileNotFoundError(f"android staged web dir not found: {staged_web_dir}")
    shutil.copytree(staged_web_dir, workspace_dir / workspace_web_dir_name)

    staged_backend_dir = staged_target_dir / "comic_backend"
    if staged_backend_dir.exists():
        shutil.copytree(staged_backend_dir, workspace_dir / workspace_web_dir_name / "backend_source")

    runtime_env = staged_target_dir / "runtime.env"
    if runtime_env.exists():
        shutil.copy2(runtime_env, workspace_dir / workspace_web_dir_name / "runtime.env")

    package_json = {
        "name": "ultimate-android-shell",
        "private": True,
        "version": "1.0.0",
        "description": "Android shell build workspace for Ultimate Web",
    }
    write_text(
        workspace_dir / "package.json",
        json.dumps(package_json, ensure_ascii=False, indent=2) + "\n",
    )

    core_ver = str(packager_cfg.get("capacitor_core_version", "latest")).strip().lower()
    cli_ver = str(packager_cfg.get("capacitor_cli_version", "latest")).strip().lower()
    android_ver = str(packager_cfg.get("capacitor_android_version", "latest")).strip().lower()

    def cap_dep(name: str, version_text: str) -> str:
        if not version_text or version_text == "latest":
            return name
        return f"{name}@{version_text}"

    npm_cmd = get_npm_command()
    npx_cmd = get_npx_command()
    commands: List[List[str]] = [
        [
            npm_cmd,
            "install",
            "--no-fund",
            "--no-audit",
            cap_dep("@capacitor/core", core_ver),
            cap_dep("@capacitor/cli", cli_ver),
            cap_dep("@capacitor/android", android_ver),
        ],
        [npx_cmd, "cap", "init", app_name, app_id, "--web-dir", workspace_web_dir_name],
        [npx_cmd, "cap", "add", "android"],
        [npx_cmd, "cap", "sync", "android"],
    ]

    gradle_cmd = ["./gradlew", gradle_task]
    if os.name == "nt":
        # Execute batch wrapper through cmd on Windows for reliable process launching.
        gradle_cmd = ["cmd", "/c", "gradlew.bat", gradle_task]
    commands.append(gradle_cmd)

    pretty_commands = []
    for cmd in commands:
        pretty_commands.append(" ".join([f"\"{part}\"" if " " in part else part for part in cmd]))

    plan = [
        "# Android Packaging Plan",
        "",
        "The Android package can be built from this prepared workspace:",
        f"`{workspace_dir}`",
        "",
        "Command sequence:",
    ]
    for idx, cmd in enumerate(pretty_commands, start=1):
        plan.append(f"{idx}. `{cmd}`")
    plan.append("")
    plan.append("Notes:")
    plan.append(f"- source staged web dir: `{staged_web_dir_name}`")
    plan.append(f"- workspace web dir: `{workspace_web_dir_name}`")
    plan.append(f"- workspace dir: `{workspace_dir}`")
    plan.append(f"- expected APK path in workspace: `{apk_relative_path}`")
    plan.append("- ensure Android SDK, Java, and Gradle are available in environment.")
    write_text(target_out_dir / "android_packaging_plan.md", "\n".join(plan) + "\n")

    ps1_lines: List[str] = [
        "$ErrorActionPreference = 'Stop'",
        f"Set-Location \"{workspace_dir}\"",
    ]
    for cmd in pretty_commands:
        ps1_lines.append(cmd)
    write_text(target_out_dir / "run_capacitor.ps1", "\n".join(ps1_lines) + "\n")

    sh_lines: List[str] = [
        "#!/usr/bin/env sh",
        "set -e",
        f"cd \"{str(workspace_dir).replace('\\', '/')}\"",
    ]
    sh_lines.extend(pretty_commands)
    sh_path = target_out_dir / "run_capacitor.sh"
    write_text(sh_path, "\n".join(sh_lines) + "\n")
    try:
        sh_path.chmod(0o755)
    except OSError:
        pass
    return commands, workspace_dir, apk_relative_path


def package_android(
    target: str,
    staged_target_dir: Path,
    packager_cfg: Dict,
    target_out_dir: Path,
    execute: bool,
) -> PackageResult:
    commands, workspace_dir, apk_relative_path = write_android_capacitor_plan(
        target_out_dir,
        staged_target_dir,
        packager_cfg,
    )

    if not execute:
        return PackageResult(
            target=target,
            status="prepared",
            message="android packaging workspace and scripts generated",
            output_dir=str(target_out_dir),
            command=[item for cmd in commands for item in cmd],
        )

    logs: List[str] = []
    for idx, cmd in enumerate(commands, start=1):
        cwd = workspace_dir
        if idx == len(commands):
            cwd = workspace_dir / "android"
            if not cwd.exists():
                return PackageResult(
                    target=target,
                    status="failed",
                    message=f"android project directory missing before gradle step: {cwd}",
                    output_dir=str(target_out_dir),
                    command=cmd,
                )
        try:
            code, output = run_cmd(cmd, cwd=cwd)
        except FileNotFoundError:
            log_path = target_out_dir / "android_build.log"
            logs.append(f"$ {' '.join(cmd)}\n[launcher-error] executable not found in PATH or cwd\n")
            write_text(log_path, "\n".join(logs))
            return PackageResult(
                target=target,
                status="failed",
                message=f"android build failed at step {idx}: command not found ({cmd[0]}); see {log_path}",
                output_dir=str(target_out_dir),
                command=cmd,
            )
        logs.append(f"$ {' '.join(cmd)}\n{output}\n")
        if code != 0:
            log_path = target_out_dir / "android_build.log"
            write_text(log_path, "\n".join(logs))
            return PackageResult(
                target=target,
                status="failed",
                message=f"android build failed at step {idx} with code {code}; see {log_path}",
                output_dir=str(target_out_dir),
                command=cmd,
            )

    expected_apk = workspace_dir / apk_relative_path
    if not expected_apk.exists():
        candidates = sorted((workspace_dir / "android").glob("app/build/outputs/apk/**/*.apk"))
        if candidates:
            expected_apk = candidates[-1]

    if not expected_apk.exists():
        log_path = target_out_dir / "android_build.log"
        write_text(log_path, "\n".join(logs))
        return PackageResult(
            target=target,
            status="failed",
            message=f"android build completed but APK not found; see {log_path}",
            output_dir=str(target_out_dir),
            command=["apk_lookup", apk_relative_path],
        )

    apk_out_dir = target_out_dir / "apk"
    apk_out_dir.mkdir(parents=True, exist_ok=True)
    apk_target = apk_out_dir / expected_apk.name
    shutil.copy2(expected_apk, apk_target)

    log_path = target_out_dir / "android_build.log"
    write_text(log_path, "\n".join(logs))
    return PackageResult(
        target=target,
        status="built",
        message=f"android APK built: {apk_target}",
        output_dir=str(target_out_dir),
        command=[str(apk_target)],
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
