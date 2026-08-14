# =============================================================
#  FVR Local Server - Windows setup
#  Run in PowerShell as Administrator:
#    powershell -ExecutionPolicy Bypass -File .\windows.ps1
# =============================================================
$ErrorActionPreference = "Stop"

Write-Host "=== FVR Local Server - Windows setup ===" -ForegroundColor Cyan

# 1. Check Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "[X] Python not found. Install Python 3.10+ from https://python.org and re-run." -ForegroundColor Red
    exit 1
}
Write-Host "[1/5] Python found: $($python.Source)"

# 2. Install libusb driver for USB printing (Zadig) if missing
#    Windows needs the WinUSB/libusb driver bound to the thermal printer.
#    This opens the Zadig download page so the user can install the driver.
if (Get-PnpDevice | Where-Object { $_.Status -eq "OK" } | Select-String -Quiet "USB Input Device") {
    Write-Host "[2/5] Checking libusb driver (Zadig)..."
}
Write-Host "    NOTE: For USB printers, install the WinUSB driver via Zadig:"
Write-Host "          -> https://zadig.akeo.ie/ (select your printer, choose WinUSB, click Replace Driver)"
Write-Host ""

# 3. Create venv + install python requirements
Write-Host "[3/5] Creating virtual environment and installing Python packages..."
if (-not (Test-Path ".venv")) {
    py -3.12 -m venv .venv
}
& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -r requirements\base.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "[X] pip install failed." -ForegroundColor Red
    exit 1
}

# 4. Copy .env if missing
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "    Created .env from .env.example - edit POS_URL/POS_TOKEN before running."
}

# 5. Kill any process on port 8000
Write-Host "[4/5] Killing process on port 8000..."
$listener = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($listener) {
    $pids = $listener.OwningProcess | Sort-Object -Unique
    foreach ($pidToKill in $pids) {
        Write-Host "    Killing PID: $pidToKill"
        Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
    }
} else {
    Write-Host "    Port 8000 is free."
}

# 6. Start server (nohup equivalent -> Start-Process detached)
Write-Host "[5/5] Starting server on port 8000..."
Start-Process -FilePath ".venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--log-level", "info" `
    -RedirectStandardOutput "uvicorn.log" `
    -RedirectStandardError "uvicorn.err.log" `
    -WindowStyle Hidden

Write-Host ""
Write-Host "Server started on port 8000. Logs -> uvicorn.log" -ForegroundColor Green
Write-Host "Check: http://localhost:8000/local/docs"