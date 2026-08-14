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

# 5. Detect if a USB thermal printer needs root access
echo "[4/5] Checking USB printer access..."
PYTHON_BIN=".venv/bin/python"
NEED_SUDO=0
if $PYTHON_BIN -c "
import sys
from apps.printer.utils import USBPrinter
usb = USBPrinter()
devices = usb.discover()
usb_printers = [d for d in devices if d.get('vid') and d.get('pid')]
if not usb_printers:
    sys.exit(0)
import usb.core
from apps.printer.utils import _get_usb_backend
b = _get_usb_backend()
for d in usb_printers:
    dev = usb.core.find(idVendor=int(d['vid'], 16), idProduct=int(d['pid'], 16), backend=b)
    if dev is not None:
        try:
            if dev.is_kernel_driver_active(0):
                sys.exit(1)
        except Exception:
            sys.exit(1)
sys.exit(0)
" 2>/dev/null; then
    :
else
    echo "    USB printer detected but needs root access — will run with sudo."
    NEED_SUDO=1
fi

# 6. Start server with nohup
echo "[5/5] Starting server on port 8000..."
cd "$(dirname "$0")"
if [ "$NEED_SUDO" = "1" ]; then
    echo "    USB printer needs root access. Enter your sudo password:"
    sudo -v || { echo "    sudo failed — cannot start with root."; exit 1; }
    nohup sudo $PYTHON_BIN -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1 --log-level info > uvicorn.log 2>&1 &
else
    nohup uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1 --log-level info > uvicorn.log 2>&1 &
fi

echo ""
echo "Server started on port 8000. Logs -> uvicorn.log"
echo "Check: curl http://localhost:8000/local/docs"