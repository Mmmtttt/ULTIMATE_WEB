#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from package_unified import collect_pyinstaller_plugin_metadata


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export plugin-declared PyInstaller build requirements."
    )
    parser.add_argument(
        "--backend-dir",
        default="comic_backend",
        help="Backend source root that contains the third_party directory.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional output file path. Prints to stdout when omitted.",
    )
    args = parser.parse_args()

    backend_dir = Path(args.backend_dir).resolve()
    requirements = collect_pyinstaller_plugin_metadata(backend_dir).get("pip_requirements", [])
    content = "\n".join(requirements).strip()
    if content:
        content += "\n"

    output_path = str(args.output or "").strip()
    if output_path:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
