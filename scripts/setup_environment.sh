#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR"

echo "=== Environment Setup ==="
echo "This script will check and install required dependencies"
echo ""

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

echo -n "Checking Python... "
PY_CMD=$(get_python_cmd)
if [ -n "$PY_CMD" ]; then
    PY_VERSION=$($PY_CMD --version 2>&1)
    echo "OK - $PY_VERSION"
else
    echo "ERROR - Python is not installed"
    echo "Please install Python 3.8 or higher:"
    echo "  Ubuntu/Debian: sudo apt-get install python3 python3-pip"
    echo "  CentOS/RHEL:   sudo yum install python3 python3-pip"
    echo "  Arch Linux:    sudo pacman -S python python-pip"
    echo "  Mac:           brew install python3"
    echo ""
    echo "After installation, run this script again"
    exit 1
fi

PY_MAJOR=$($PY_CMD -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$($PY_CMD -c 'import sys; print(sys.version_info.minor)')
if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 8 ]); then
    echo "ERROR - Python version 3.8 or higher is required"
    exit 1
fi

echo -n "Checking Node.js... "
if command_exists node; then
    NODE_VERSION=$(node --version 2>&1)
    echo "OK - $NODE_VERSION"
else
    echo "ERROR - Node.js is not installed"
    echo "Please install Node.js 16 or higher:"
    echo "  Ubuntu/Debian: curl -fsSL https://deb.nodesource.com/setup_16.x | sudo -E bash - && sudo apt-get install -y nodejs"
    echo "  CentOS/RHEL:   curl -fsSL https://rpm.nodesource.com/setup_16.x | sudo bash - && sudo yum install -y nodejs"
    echo "  Mac:           brew install node"
    echo "  Or use nvm:    https://github.com/nvm-sh/nvm"
    echo ""
    echo "After installation, run this script again"
    exit 1
fi

NODE_MAJOR=$(node -p "process.versions.node.split('.')[0]")
if [ "$NODE_MAJOR" -lt 16 ]; then
    echo "ERROR - Node.js version 16 or higher is required"
    exit 1
fi

echo -n "Checking npm... "
if command_exists npm; then
    NPM_VERSION=$(npm --version 2>&1)
    echo "OK - v$NPM_VERSION"
else
    echo "ERROR - npm is not installed"
    echo "npm comes with Node.js, please reinstall Node.js"
    exit 1
fi

echo ""
echo "=== Installing Dependencies ==="

PIP_CMD=$(get_pip_cmd)
if [ -z "$PIP_CMD" ]; then
    echo "ERROR - pip is not available"
    exit 1
fi
echo "Using pip command: $PIP_CMD"

echo ""
echo "Installing backend dependencies..."
if [ -f "comic_backend/requirements.txt" ]; then
    echo "  Running: $PIP_CMD install -r comic_backend/requirements.txt"
    $PIP_CMD install -r comic_backend/requirements.txt
    if [ $? -eq 0 ]; then
        echo "  OK - Backend dependencies installed"
    else
        echo "  ERROR - Failed to install backend dependencies"
        exit 1
    fi
else
    echo "  ERROR - requirements.txt not found"
    exit 1
fi

echo ""
echo "Installing frontend dependencies..."
if [ -f "comic_frontend/package.json" ]; then
    echo "  Running: npm install"
    cd "comic_frontend"
    npm install
    cd "$ROOT_DIR"
    if [ $? -eq 0 ]; then
        echo "  OK - Frontend dependencies installed"
    else
        echo "  ERROR - Failed to install frontend dependencies"
        exit 1
    fi
else
    echo "  ERROR - package.json not found"
    exit 1
fi

echo ""
echo "=== Setup Complete ==="
echo "You can now start the project with: ./start_project.sh"
echo "Or individually:"
echo "  Backend:  ./scripts/start_backend.sh"
echo "  Frontend: ./scripts/start_frontend.sh"
