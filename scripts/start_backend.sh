#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="$ROOT_DIR/comic_backend/venv/bin/python"

if [ -f "$VENV_PYTHON" ]; then
    PY_CMD="$VENV_PYTHON"
else
    command_exists() {
        command -v "$1" >/dev/null 2>&1
    }

    get_python_cmd() {
        if command_exists python3; then
            echo "python3"
        elif command_exists python; then
            echo "python"
        else
            echo ""
        fi
    }

    PY_CMD="$(get_python_cmd)"
    if [ -z "$PY_CMD" ]; then
        echo "ERROR: Python not found. Please install Python 3.8+."
        exit 1
    fi
fi

echo "Starting backend service..."
cd "$ROOT_DIR/comic_backend"
"$PY_CMD" app.py
