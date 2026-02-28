#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR"

echo "=== View Service Status ==="

echo "Backend service processes:"
if pgrep -f "python.*app.py" > /dev/null; then
    ps aux | grep -E "python.*app.py" | grep -v grep
else
    echo "No backend processes found"
fi

echo ""
echo "Frontend service processes:"
if pgrep -f "npm.*dev" > /dev/null; then
    ps aux | grep -E "npm.*dev" | grep -v grep
else
    echo "No frontend processes found"
fi

echo ""
echo "Testing service availability:"

if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/health | grep -q "200"; then
    echo "Backend service: OK"
else
    echo "Backend service: ERROR (Not accessible)"
fi

if curl -s -o /dev/null -w "%{http_code}" http://localhost:5173/ | grep -q "200"; then
    echo "Frontend service: OK"
else
    echo "Frontend service: ERROR (Not accessible)"
fi

echo ""
echo "=== Status View Complete ==="
