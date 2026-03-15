#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR"

echo "=== Stop Services ==="

echo "Stopping backend service..."
pkill -f "python.*app.py" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "Backend service stopped"
else
    echo "No backend process found"
fi

echo "Stopping frontend service..."
pkill -f "npm.*dev|vite" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "Frontend service stopped"
else
    echo "No frontend process found"
fi

echo "=== Services Stopped ==="
