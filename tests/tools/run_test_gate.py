#!/usr/bin/env python3
"""Run test gate locally: always run integration + E2E, fail if any one fails."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

BOOTSTRAP_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(BOOTSTRAP_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(BOOTSTRAP_REPO_ROOT))

from tests.shared.test_constants import REPO_ROOT
from tests.tools.prepare_test_env import prepare_profile


def _run(cmd: list[str], cwd: Path, log_path: Path) -> int:
    print(f"[test-gate] running: {' '.join(cmd)}")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as fp:
        completed = subprocess.run(cmd, cwd=str(cwd), stdout=fp, stderr=subprocess.STDOUT)
    print(f"[test-gate] log written: {log_path}")
    return int(completed.returncode or 0)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local quality gate tests.")
    parser.add_argument("--skip-integration", action="store_true", help="Skip backend integration tests.")
    parser.add_argument("--skip-e2e", action="store_true", help="Skip frontend E2E tests.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = Path(REPO_ROOT)
    artifact_dir = repo_root / "tests" / ".runtime" / "gate-logs"
    final_code = 0

    if not args.skip_integration:
        prepare_profile("integration", clean=True)
        code = _run(
            [sys.executable, "-m", "pytest", "tests/features", "-m", "integration"],
            cwd=repo_root,
            log_path=artifact_dir / "integration.log",
        )
        if code != 0:
            final_code = code

    if not args.skip_e2e:
        prepare_profile("e2e", clean=True)
        code = _run(
            [sys.executable, "tests/tools/run_e2e.py"],
            cwd=repo_root,
            log_path=artifact_dir / "e2e.log",
        )
        if code != 0:
            final_code = code

    if final_code != 0:
        print("[test-gate] failed. See logs under tests/.runtime/gate-logs/")
    else:
        print("[test-gate] passed.")
    return final_code


if __name__ == "__main__":
    raise SystemExit(main())
