#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

if ! command -v npm >/dev/null 2>&1; then
    echo "ERROR: npm not found. Please install Node.js and npm."
    exit 1
fi

echo "Starting frontend service..."
cd "$ROOT_DIR/comic_frontend"
npm run dev
