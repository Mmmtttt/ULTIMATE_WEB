#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


DEFAULT_APP_VERSION = "0.0.0"


def normalize_app_version(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""

    if text.lower().startswith("refs/tags/"):
        text = text.split("/", 2)[-1]
    if text.startswith(("v", "V")) and re.search(r"\d", text[1:]):
        text = text[1:]
    return text.strip()


def has_numeric_version(raw: str) -> bool:
    normalized = normalize_app_version(raw)
    return bool(normalized and re.search(r"\d", normalized))


def load_package_version(package_json_path: Path) -> str:
    if not package_json_path.exists():
        return ""
    try:
        payload = json.loads(package_json_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    return normalize_app_version(str(payload.get("version", "")))


def resolve_release_app_version(
    raw_version: str = "",
    package_version: str = "",
    run_number: str | int = "0",
) -> str:
    normalized_raw = normalize_app_version(raw_version)
    if has_numeric_version(normalized_raw):
        return normalized_raw

    normalized_package = normalize_app_version(package_version)
    if has_numeric_version(normalized_package) and normalized_package != DEFAULT_APP_VERSION:
        return normalized_package

    return f"0.0.{str(run_number or '0').strip() or '0'}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve Ultimate Web release version.")
    parser.add_argument("--raw-version", default="", help="Preferred raw version string, usually from tag or manual input.")
    parser.add_argument("--package-json", default="", help="Optional package.json path used as fallback.")
    parser.add_argument("--run-number", default="0", help="GitHub run number fallback suffix.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    package_version = load_package_version(Path(args.package_json)) if str(args.package_json or "").strip() else ""
    resolved = resolve_release_app_version(
        raw_version=args.raw_version,
        package_version=package_version,
        run_number=args.run_number,
    )
    print(resolved)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
