#!/usr/bin/env python3
"""Run E2E tests with explicit server lifecycle management."""

from __future__ import annotations

import argparse
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

import requests

BOOTSTRAP_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(BOOTSTRAP_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOTSTRAP_REPO_ROOT))

from tests.shared.test_constants import E2E_BACKEND_PORT, E2E_FRONTEND_PORT, E2E_PROFILE, REPO_ROOT
from tests.tools.prepare_test_env import prepare_profile


def _wait_http(url: str, timeout_seconds: int = 120) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=1)
            if response.status_code < 500:
                return
        except requests.RequestException:
            pass
        time.sleep(0.5)
    raise TimeoutError(f"Service not ready: {url}")


def _spawn_process(command: list[str], cwd: Path, env: dict, log_file: Path) -> tuple[subprocess.Popen, object]:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    fp = log_file.open("w", encoding="utf-8")
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        env=env,
        stdout=fp,
        stderr=fp,
        start_new_session=True,
    )
    return process, fp


def _kill_process_tree(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return

    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return

    try:
        os.killpg(process.pid, signal.SIGTERM)
    except Exception:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except Exception:
            process.kill()


def _kill_ports_on_windows(ports: list[int]) -> None:
    if os.name != "nt":
        return
    try:
        output = subprocess.check_output(["netstat", "-ano"], text=True, errors="ignore")
    except Exception:
        return

    pids = set()
    for line in output.splitlines():
        for port in ports:
            pattern = rf":{port}\s+.*LISTENING\s+(\d+)$"
            match = re.search(pattern, line.strip())
            if match:
                pids.add(int(match.group(1)))

    for pid in sorted(pids):
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run E2E tests with managed backend/frontend lifecycle.")
    parser.add_argument(
        "--visual",
        action="store_true",
        help="Enable local visual mode: headed + slowmo(200ms) + PWDEBUG + Playwright UI.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    prepared = prepare_profile(E2E_PROFILE, clean=True)
    runtime_root = Path(prepared["runtime_root"])
    repo_root = Path(REPO_ROOT)

    backend_env = os.environ.copy()
    fake_deps_dir = Path(REPO_ROOT) / "tests" / "shared" / "fake_deps"
    existing_pythonpath = str(backend_env.get("PYTHONPATH", "")).strip()
    backend_env["PYTHONPATH"] = (
        f"{fake_deps_dir}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else str(fake_deps_dir)
    )
    backend_env.update(
        {
            "SERVER_CONFIG_PATH": prepared["server_config_path"],
            "THIRD_PARTY_CONFIG_PATH": prepared["third_party_config_path"],
            "BACKEND_HOST": "127.0.0.1",
            "BACKEND_PORT": str(E2E_BACKEND_PORT),
            "BACKEND_DEBUG": "0",
            "BACKEND_ENABLE_THIRD_PARTY": "0",
            "PYTHONUNBUFFERED": "1",
        }
    )

    frontend_env = os.environ.copy()
    frontend_env.update(
        {
            "VITE_API_BASE_URL": f"http://127.0.0.1:{E2E_BACKEND_PORT}/api",
            "VITE_BACKEND_PORT": str(E2E_BACKEND_PORT),
        }
    )
    playwright_env = os.environ.copy()
    if args.visual:
        playwright_env["PW_HEADED"] = "1"
        playwright_env["PW_SLOWMO"] = "200"
        playwright_env["PWDEBUG"] = "1"

    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    npx_cmd = "npx.cmd" if os.name == "nt" else "npx"

    backend_proc = None
    frontend_proc = None
    backend_fp = None
    frontend_fp = None

    try:
        backend_proc, backend_fp = _spawn_process(
            [sys.executable, str(repo_root / "comic_backend" / "app.py")],
            cwd=repo_root,
            env=backend_env,
            log_file=runtime_root / "backend-e2e.log",
        )
        _wait_http(f"http://127.0.0.1:{E2E_BACKEND_PORT}/health", timeout_seconds=120)

        frontend_proc, frontend_fp = _spawn_process(
            [npm_cmd, "run", "dev", "--", "--host", "127.0.0.1", "--port", str(E2E_FRONTEND_PORT)],
            cwd=repo_root / "comic_frontend",
            env=frontend_env,
            log_file=runtime_root / "frontend-e2e.log",
        )
        _wait_http(f"http://127.0.0.1:{E2E_FRONTEND_PORT}", timeout_seconds=180)

        playwright_cmd = [npx_cmd, "--prefix", "comic_frontend", "playwright", "test", "-c", "tests/playwright.config.js"]
        if args.visual:
            playwright_cmd.append("--ui")

        completed = subprocess.run(playwright_cmd, cwd=str(repo_root), env=playwright_env)
        return int(completed.returncode or 0)
    finally:
        _kill_process_tree(frontend_proc)
        _kill_process_tree(backend_proc)
        _kill_ports_on_windows([E2E_FRONTEND_PORT, E2E_BACKEND_PORT])
        if frontend_fp:
            frontend_fp.close()
        if backend_fp:
            backend_fp.close()


if __name__ == "__main__":
    raise SystemExit(main())
