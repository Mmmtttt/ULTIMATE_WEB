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

run_backend=true
run_frontend=true

if [ $# -gt 0 ]; then
    if [ "$1" = "-backend" ] || [ "$1" = "--backend" ]; then
        run_backend=true
        run_frontend=false
    elif [ "$1" = "-frontend" ] || [ "$1" = "--frontend" ]; then
        run_backend=false
        run_frontend=true
    fi
fi

echo "=== Run Tests ==="

if [ "$run_backend" = true ]; then
    echo ""
    echo "=== Backend API Tests ==="

    if [ -z "$PY_CMD" ]; then
        echo "Python not found, cannot run backend tests"
        exit 1
    fi

    echo -n "Checking backend service... "
    if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${BACKEND_PORT}/health" | grep -q "200"; then
        echo "OK"
    else
        echo "Not running, starting..."
        bash "$SCRIPT_DIR/start_backend.sh" &
        sleep 5
    fi

    echo "Running backend API tests..."
    cd "$ROOT_DIR/tests"
    "$PY_CMD" test_api.py

    if [ $? -eq 0 ]; then
        echo "Backend tests passed"
    else
        echo "Backend tests failed"
    fi
fi

if [ "$run_frontend" = true ]; then
    echo ""
    echo "=== Frontend E2E Tests ==="

    echo -n "Checking frontend dependencies... "
    if [ -d "$ROOT_DIR/comic_frontend/node_modules" ]; then
        echo "OK"
    else
        echo "Not installed, installing..."
        bash "$SCRIPT_DIR/setup_environment.sh"
    fi

    echo "Running frontend E2E tests with Playwright..."
    cd "$ROOT_DIR"
    npx playwright test --config=tests/playwright.config.js

    if [ $? -eq 0 ]; then
        echo "Frontend tests passed"
    else
        echo "Frontend tests failed"
    fi
fi

cd "$ROOT_DIR"

echo ""
echo "=== Tests Complete ==="
echo "Usage: "
echo "  ./scripts/run_tests.sh            # Run all tests"
echo "  ./scripts/run_tests.sh -backend   # Run backend tests only"
echo "  ./scripts/run_tests.sh -frontend  # Run frontend tests only"
