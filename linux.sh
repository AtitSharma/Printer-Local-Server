#!/bin/bash
set -e

echo "=== FVR Local Server - Linux setup ==="

# 1. Install system deps (Python + venv + libusb driver for USB printing)
echo "[1/5] Installing system dependencies..."
if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y python3 python3-venv python3-pip libusb-1.0-0
elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y python3 python3-pip libusbx
elif command -v yum >/dev/null 2>&1; then
    sudo yum install -y python3 python3-pip libusbx
elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -Sy --noconfirm python python-pip libusb
else
    echo "Unsupported package manager. Please install python3, pip, and libusb manually."
    exit 1
fi

# 2. Create venv + install python requirements
echo "[2/5] Creating virtual environment and installing Python packages..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements/base.txt

# 3. Copy .env if missing
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "    Created .env from .env.example — edit POS_URL/POS_TOKEN before running."
fi

# 4. Kill any process on port 8000
echo "[3/5] Killing process on port 8000..."
if command -v fuser >/dev/null 2>&1; then
    fuser -k 8000/tcp 2>/dev/null || true
else
    PORT_PID=$(lsof -ti tcp:8000 || true)
    if [ -n "$PORT_PID" ]; then
        kill -9 $PORT_PID 2>/dev/null || true
    fi
fi
echo "    Port 8000 cleared."

# 5. Start server with nohup
echo "[4/5] Starting server on port 8000..."
cd "$(dirname "$0")"
nohup uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1 --log-level info > uvicorn.log 2>&1 &

echo ""
echo "Server started on port 8000. Logs -> uvicorn.log"
echo "Check: curl http://localhost:8000/local/docs"