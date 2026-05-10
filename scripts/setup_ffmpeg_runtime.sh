#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== FFmpeg Runtime Setup ==="

if command -v ffmpeg >/dev/null 2>&1; then
    echo "FFmpeg runtime already available: $(command -v ffmpeg)"
    ffmpeg -version | head -n1
    exit 0
fi

if command -v apt-get >/dev/null 2>&1; then
    echo "Installing FFmpeg via apt-get..."
    sudo apt-get update
    sudo apt-get install -y --no-install-recommends ffmpeg
    echo "FFmpeg runtime installed successfully."
    ffmpeg -version | head -n1
    exit 0
fi

echo "ERROR: ffmpeg not found and no supported package manager provisioning is configured."
echo "Please install ffmpeg manually, or place it under:"
echo "  $ROOT_DIR/tools/ffmpeg/linux/ffmpeg"
exit 1
