# Manual Batching (UV Mix + Sublimation) - start the portal on this PC (http://localhost:8765).
# Run by double-clicking "Start Manual Batching.bat" in the main folder. Keep the window open while working.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Not set up yet - run Setup.bat first." -ForegroundColor Yellow
    Read-Host "Press Enter to close"; exit 1
}
if (-not (Test-Path ".env")) {
    Write-Host "Settings file .env is missing - run Setup.bat first." -ForegroundColor Yellow
    Read-Host "Press Enter to close"; exit 1
}

# Load settings from .env into this window's environment
Get-Content ".env" | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $k, $v = $line.Split("=", 2)
        [Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim().Trim('"'), "Process")
    }
}
# Local use: plain http, so cookies must not require https
[Environment]::SetEnvironmentVariable("COOKIE_SECURE", "0", "Process")
if (-not $env:SECRET_KEY) {
    [Environment]::SetEnvironmentVariable("SECRET_KEY", [guid]::NewGuid().ToString() + [guid]::NewGuid().ToString(), "Process")
}

$port = 8765
Write-Host ""
Write-Host "=== Manual Batching is running ===" -ForegroundColor Green
Write-Host "Open: http://localhost:$port   (opening your browser now)"
Write-Host "Keep this window open. Close it to stop the portal."
Write-Host "Batches are saved in: $Root\data\runs"
Write-Host ""

Start-Job -ScriptBlock { param($p) Start-Sleep -Seconds 3; Start-Process "http://localhost:$p" } -ArgumentList $port | Out-Null
& ".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port $port
