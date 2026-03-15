#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR"
SCRIPTS_DIR="$ROOT_DIR/scripts"

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

get_pip_cmd() {
    if command_exists pip3; then
        echo "pip3"
    elif command_exists pip; then
        echo "pip"
    elif command_exists python3; then
        echo "python3 -m pip"
    elif command_exists python; then
        echo "python -m pip"
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

check_dependencies() {
    local pip_cmd="$1"

    if [ -f "comic_backend/requirements.txt" ]; then
        while IFS= read -r pkg; do
            if [[ "$pkg" =~ ^([a-zA-Z0-9_-]+) ]]; then
                pkg_name="${BASH_REMATCH[1]}"
                if ! $pip_cmd show "$pkg_name" > /dev/null 2>&1; then
                    return 1
                fi
            fi
        done < "comic_backend/requirements.txt"
    fi

    if [ -f "comic_frontend/package.json" ] && [ ! -d "comic_frontend/node_modules" ]; then
        return 1
    fi

    return 0
}

PY_CMD="$(get_python_cmd)"
BACKEND_PORT="$(get_server_config_value backend port 5000)"
FRONTEND_PORT="$(get_server_config_value frontend port 5173)"

echo "=== Start Project ==="

echo "Checking dependencies..."
PIP_CMD=$(get_pip_cmd)

if [ -n "$PIP_CMD" ]; then
    if ! check_dependencies "$PIP_CMD"; then
        echo "  Dependencies not found, running setup..."
        bash "$SCRIPTS_DIR/setup_environment.sh"

        if [ $? -ne 0 ]; then
            echo "  ERROR - Failed to install dependencies"
            exit 1
        fi
        echo "  Dependencies installed successfully"
    else
        echo "  Dependencies already installed"
    fi
else
    echo "  Python/pip not found, running setup..."
    bash "$SCRIPTS_DIR/setup_environment.sh"

    if [ $? -ne 0 ]; then
        echo "  ERROR - Failed to install dependencies"
        exit 1
    fi
    echo "  Dependencies installed successfully"
fi

echo ""
echo "Stopping existing services..."
bash "$SCRIPTS_DIR/stop_services.sh"

sleep 2

echo ""
echo "Starting backend service..."
bash "$SCRIPTS_DIR/start_backend.sh" &

echo "Waiting for backend service to start..."
sleep 5

echo "Starting frontend service..."
bash "$SCRIPTS_DIR/start_frontend.sh" &

echo "Waiting for frontend service to start..."
sleep 8

echo ""
echo "=== Services Started ==="
echo "Backend: http://127.0.0.1:${BACKEND_PORT}"
echo "Frontend: http://127.0.0.1:${FRONTEND_PORT}/"
echo ""
echo "To stop services, run: ./scripts/stop_services.sh"
echo "To view status, run: ./scripts/view_status.sh"
