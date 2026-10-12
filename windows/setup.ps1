# Manual Batching (UV Mix + Sublimation) - one-time setup on a Windows PC.
# Run by double-clicking "Setup.bat" in the main folder.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host ""
Write-Host "=== Manual Batching setup ===" -ForegroundColor Cyan

# 1. Find Python 3.10 - 3.13 (prefer 3.12)
$python = $null
foreach ($cand in @("py -3.12", "py -3.13", "py -3.11", "py -3.10", "python", "py -3")) {
    try {
        $c = $cand -split ' '
        $exe = $c[0]; $pre = @($c | Select-Object -Skip 1)
        $ver = (& $exe @pre -c "import sys;print(sys.version_info[0], sys.version_info[1])" 2>$null) -join ""
        if ($ver -match '^3 1[0-3]$') { $python = $c; break }
    } catch {}
}
if (-not $python) {
    Write-Host ""
    Write-Host "Python 3.10 - 3.13 is not installed (3.14 is not supported yet)." -ForegroundColor Yellow
    Write-Host "In PowerShell run:  winget install Python.Python.3.13"
    Write-Host "or download the latest 3.13.x 'Windows installer (64-bit)' from https://www.python.org/downloads/windows/"
    Write-Host "(tick 'Add python.exe to PATH'). 3.13 can sit next to 3.14. Then run Setup.bat again."
    Read-Host "Press Enter to close"
    exit 1
}
Write-Host "Using Python $($ver -replace ' ', '.')"

# 2. Private Python environment inside this folder
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating environment..."
    $exe = $python[0]; $pre = @($python | Select-Object -Skip 1)
    & $exe @pre -m venv .venv
}
Write-Host "Installing components (first time takes a few minutes)..."
& ".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) { Write-Host "Install failed - send a screenshot of this window." -ForegroundColor Red; Read-Host "Press Enter to close"; exit 1 }

# 3. Settings file
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ""
    Write-Host "A settings file (.env) was created. Fill in the database password and logins, then save it." -ForegroundColor Yellow
    Start-Process notepad.exe ".env"
}

# 4. Check database access
Write-Host ""
Write-Host "Checking connection to Pulse..."
& ".venv\Scripts\python.exe" "windows\check_db.py"

Write-Host ""
Write-Host "Setup finished. Start the portal with 'Start Manual Batching.bat'." -ForegroundColor Green
Read-Host "Press Enter to close"
