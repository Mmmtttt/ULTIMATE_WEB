#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR"

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

get_server_config_value() {
    local section="$1"
    local key="$2"
    local default_value="$3"
    local config_file="$ROOT_DIR/server_config.json"

    if [ -f "$config_file" ] && [ -n "$PY_CMD" ]; then
        "$PY_CMD" - "$config_file" "$section" "$key" "$default_value" <<'PY'
import json, sys
config_file, section, key, default_value = sys.argv[1:]
try:
    with open(config_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    value = data.get(section, {}).get(key, default_value)
    print(value)
except Exception:
    print(default_value)
PY
    else
        echo "$default_value"
    fi
}

PY_CMD="$(get_python_cmd)"
BACKEND_PORT="$(get_server_config_value backend port 5000)"
FRONTEND_PORT="$(get_server_config_value frontend port 5173)"

echo "=== View Service Status ==="

echo "Backend service processes:"
if pgrep -f "python.*app.py" > /dev/null; then
    ps aux | grep -E "python.*app.py" | grep -v grep
else
    echo "No backend processes found"
fi

echo ""
echo "Frontend service processes:"
if pgrep -f "npm.*dev|vite" > /dev/null; then
    ps aux | grep -E "npm.*dev|vite" | grep -v grep
else
    echo "No frontend processes found"
fi

echo ""
echo "Testing service availability:"

if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${BACKEND_PORT}/health" | grep -q "200"; then
    echo "Backend service: OK (port ${BACKEND_PORT})"
else
    echo "Backend service: ERROR (Not accessible on port ${BACKEND_PORT})"
fi

if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${FRONTEND_PORT}/" | grep -q "200"; then
    echo "Frontend service: OK (port ${FRONTEND_PORT})"
else
    echo "Frontend service: ERROR (Not accessible on port ${FRONTEND_PORT})"
fi

echo ""
echo "=== Status View Complete ==="
