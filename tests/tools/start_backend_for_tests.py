#!/usr/bin/env python3
"""Prepare an isolated runtime and exec backend app for Playwright webServer."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BOOTSTRAP_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(BOOTSTRAP_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOTSTRAP_REPO_ROOT))

from tests.shared.test_constants import REPO_ROOT
from tests.tools.prepare_test_env import prepare_profile


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start backend with isolated test profile.")
    parser.add_argument("--profile", default="e2e", help="Runtime profile name.")
    parser.add_argument("--host", default="127.0.0.1", help="Backend host.")
    parser.add_argument("--port", type=int, default=5010, help="Backend port.")
    parser.add_argument("--enable-third-party", action="store_true", help="Enable third-party adapters.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    prepared = prepare_profile(args.profile, clean=True)

    backend_app = Path(REPO_ROOT) / "comic_backend" / "app.py"
    if not backend_app.exists():
        raise FileNotFoundError(f"Backend app not found: {backend_app}")

    env = os.environ.copy()
    env.update(
        {
            "SERVER_CONFIG_PATH": prepared["server_config_path"],
            "THIRD_PARTY_CONFIG_PATH": prepared["third_party_config_path"],
            "BACKEND_HOST": args.host,
            "BACKEND_PORT": str(args.port),
            "BACKEND_DEBUG": "0",
            "BACKEND_ENABLE_THIRD_PARTY": "1" if args.enable_third_party else "0",
            "PYTHONUNBUFFERED": "1",
        }
    )

    os.execvpe(sys.executable, [sys.executable, str(backend_app)], env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
