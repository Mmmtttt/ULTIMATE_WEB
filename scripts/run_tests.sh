#!/bin/bash
# 运行测试脚本
# 执行后端API测试和前端E2E测试

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR"

cd "$ROOT_DIR"

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

# 运行后端测试
if [ "$run_backend" = true ]; then
    echo ""
    echo "=== Backend API Tests ==="

    echo -n "Checking backend service... "
    if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/health | grep -q "200"; then
        echo "OK"
    else
        echo "Not running, starting..."
        bash "$SCRIPT_DIR/start_backend.sh" &
        sleep 5
    fi

    echo "Running backend API tests..."
    cd "$ROOT_DIR/tests"
    python test_api.py

    if [ $? -eq 0 ]; then
        echo "Backend tests passed"
    else
        echo "Backend tests failed"
    fi
fi

# 运行前端测试
if [ "$run_frontend" = true ]; then
    echo ""
    echo "=== Frontend E2E Tests ==="

    echo -n "Checking frontend dependencies... "
    if [ -d "comic_frontend/node_modules" ]; then
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
echo "  ./scripts/run_tests.sh           # Run all tests"
echo "  ./scripts/run_tests.sh -backend # Run backend tests only"
echo "  ./scripts/run_tests.sh -frontend # Run frontend tests only"
