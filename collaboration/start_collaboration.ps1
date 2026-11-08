# Launch script for Devin-Antigravity Collaboration Bridge Daemon
param(
    [switch]$Mock,
    [int]$Interval = 10
)

$VENV_PYTHON = Join-Path $PSScriptRoot "..\quant_trading_bot\.venv\Scripts\python.exe"
if (-not (Test-Path $VENV_PYTHON)) {
    $VENV_PYTHON = "python"
}

$DAEMON_SCRIPT = Join-Path $PSScriptRoot "bridge_daemon.py"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   AUTONOMOUS DEVIN - ANTIGRAVITY COLLABORATION BRIDGE   " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

if ($env:DEVIN_API_KEY) {
    Write-Host "[AUTH] DEVIN_API_KEY is detected in environment." -ForegroundColor Green
} else {
    Write-Host "[AUTH] DEVIN_API_KEY is not set. Running in Local Queue/Simulation mode." -ForegroundColor Yellow
    Write-Host "       Set DEVIN_API_KEY to enable live REST API dispatch to Devin." -ForegroundColor Yellow
}

$Arguments = @($DAEMON_SCRIPT, "--interval", $Interval)
if ($Mock -or (-not $env:DEVIN_API_KEY)) {
    $Arguments += "--mock"
}

Write-Host "[LAUNCH] Starting background daemon..." -ForegroundColor White
& $VENV_PYTHON @Arguments
