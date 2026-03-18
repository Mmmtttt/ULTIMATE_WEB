#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify packaging_summary.json contains expected target status.")
    parser.add_argument("--summary", required=True, help="Path to packaging_summary.json.")
    parser.add_argument("--target", required=True, help="Target id to check (windows/linux/android).")
    parser.add_argument("--require-status", default="built", help="Required status for the target (default: built).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary_path = Path(args.summary).resolve()
    if not summary_path.exists():
        print(f"[verify] summary not found: {summary_path}", file=sys.stderr)
        return 1

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    results = payload.get("results", [])
    target = str(args.target).strip().lower()
    required_status = str(args.require_status).strip().lower()

    matched = None
    for item in results:
        if str(item.get("target", "")).strip().lower() == target:
            matched = item
            break

    if not matched:
        print(f"[verify] target not found in summary: {target}", file=sys.stderr)
        return 1

    actual_status = str(matched.get("status", "")).strip().lower()
    if actual_status != required_status:
        msg = str(matched.get("message", "")).strip()
        print(
            f"[verify] status mismatch for {target}: expected={required_status}, actual={actual_status}, message={msg}",
            file=sys.stderr,
        )
        return 1

    print(f"[verify] ok: {target} status={actual_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
