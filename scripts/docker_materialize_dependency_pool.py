from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def requirement_name(value: str) -> str:
    return re.split(
        r"\s*(?:\[|==|>=|<=|~=|!=|>|<|=|;)",
        str(value or ""),
        maxsplit=1,
    )[0].strip().lower().replace("_", "-")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pool_path", type=Path)
    parser.add_argument("dependency_root", type=Path)
    parser.add_argument("manifest_path", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.pool_path.read_text(encoding="utf-8"))
    requirements = [
        str(item).strip()
        for item in (payload.get("pools") or {}).get("external") or []
        if str(item).strip()
    ]
    if not requirements:
        raise ValueError("external resident dependency pool is empty")

    args.dependency_root.mkdir(parents=True, exist_ok=True)
    subprocess.check_call([
        sys.executable,
        "-m",
        "pip",
        "install",
        "--no-cache-dir",
        "--target",
        str(args.dependency_root),
        *requirements,
    ])

    manifest = {
        "version": 1,
        "platform": "external",
        "dependency_root": str(args.dependency_root),
        "requirements": requirements,
        "requirement_names": sorted({requirement_name(item) for item in requirements}),
    }
    args.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
