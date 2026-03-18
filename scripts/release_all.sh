#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

if command -v python3 >/dev/null 2>&1; then
  PY_CMD="python3"
elif command -v python >/dev/null 2>&1; then
  PY_CMD="python"
else
  echo "[release] Python not found"
  exit 1
fi

execute_packaging="false"
echo "[release] Running unified release orchestration..."
"$PY_CMD" "$SCRIPT_DIR/release_unified.py" "$@"
