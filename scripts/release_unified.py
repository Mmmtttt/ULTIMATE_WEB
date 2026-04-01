#!/usr/bin/env python3
"""
Unified release orchestrator:
  1) build staged multi-target workspaces
  2) package staged workspaces
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT_DIR / "scripts"
BUILD_SCRIPT = SCRIPTS_DIR / "build_unified.py"
PACKAGE_SCRIPT = SCRIPTS_DIR / "package_unified.py"


def run_cmd(cmd: List[str]) -> int:
    process = subprocess.run(cmd, cwd=str(ROOT_DIR), check=False)
    return process.returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run build_unified + package_unified in one command.")
    parser.add_argument("--targets", default="all", help="Comma-separated targets or 'all'.")
    parser.add_argument("--build-output", default="output/multi_target", help="Staged build output directory.")
    parser.add_argument("--package-output", default="output/packages", help="Packaging output directory.")
    parser.add_argument("--targets-config", default="build/targets.json", help="Path to targets config.")
    parser.add_argument("--packagers-config", default="build/packagers.json", help="Path to packagers config.")
    parser.add_argument("--skip-frontend-build", action="store_true", help="Skip frontend build in stage-1.")
    parser.add_argument("--execute", action="store_true", help="Execute packager commands when available.")
    parser.add_argument(
        "--app-version",
        default="",
        help="Set packaged app version (e.g. 2.0.0). If empty, build script auto-resolves from env/tag/package.json.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    build_cmd = [
        sys.executable,
        str(BUILD_SCRIPT),
        "--targets",
        args.targets,
        "--output",
        args.build_output,
        "--config",
        args.targets_config,
    ]
    if str(args.app_version or "").strip():
        build_cmd.extend(["--app-version", str(args.app_version).strip()])
    if args.skip_frontend_build:
        build_cmd.append("--skip-frontend-build")

    print("[release] step 1/2: build staged workspaces")
    build_code = run_cmd(build_cmd)
    if build_code != 0:
        return build_code

    package_cmd = [
        sys.executable,
        str(PACKAGE_SCRIPT),
        "--targets",
        args.targets,
        "--staged",
        args.build_output,
        "--output",
        args.package_output,
        "--targets-config",
        args.targets_config,
        "--packagers-config",
        args.packagers_config,
    ]
    if args.execute:
        package_cmd.append("--execute")

    print("[release] step 2/2: package orchestration")
    return run_cmd(package_cmd)


if __name__ == "__main__":
    raise SystemExit(main())
