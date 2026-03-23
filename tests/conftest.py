from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

from tests.shared.test_constants import INTEGRATION_BACKEND_PORT, INTEGRATION_PROFILE, REPO_ROOT
from tests.tools.prepare_test_env import prepare_profile


def _wait_for_backend(base_url: str, timeout_seconds: int = 60) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = requests.get(f"{base_url}/health", timeout=1)
            if response.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(0.5)
    raise TimeoutError(f"Backend did not become ready in {timeout_seconds}s: {base_url}")


@pytest.fixture(scope="session")
def integration_runtime() -> dict:
    prepared = prepare_profile(INTEGRATION_PROFILE, clean=True)

    env = os.environ.copy()
    env.update(
        {
            "SERVER_CONFIG_PATH": prepared["server_config_path"],
            "THIRD_PARTY_CONFIG_PATH": prepared["third_party_config_path"],
            "BACKEND_HOST": "127.0.0.1",
            "BACKEND_PORT": str(INTEGRATION_BACKEND_PORT),
            "BACKEND_DEBUG": "0",
            "BACKEND_ENABLE_THIRD_PARTY": "0",
            "PYTHONUNBUFFERED": "1",
        }
    )

    runtime_root = Path(prepared["runtime_root"])
    backend_log = runtime_root / "backend-integration.log"
    backend_log.parent.mkdir(parents=True, exist_ok=True)
    log_fp = backend_log.open("w", encoding="utf-8")

    backend_app = Path(REPO_ROOT) / "comic_backend" / "app.py"
    process = subprocess.Popen(
        [sys.executable, str(backend_app)],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=log_fp,
        stderr=log_fp,
    )

    base_url = f"http://127.0.0.1:{INTEGRATION_BACKEND_PORT}"
    try:
        _wait_for_backend(base_url=base_url, timeout_seconds=90)
    except Exception:
        process.kill()
        process.wait(timeout=10)
        log_fp.close()
        raise

    try:
        yield {
            "base_url": base_url,
            "runtime_root": runtime_root,
            "data_dir": Path(prepared["data_dir"]),
            "meta_dir": Path(prepared["data_dir"]) / "meta_data",
            "backend_log": backend_log,
        }
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        log_fp.close()
