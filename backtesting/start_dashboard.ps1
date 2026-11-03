$ErrorActionPreference = 'Stop'
$taskRepository = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$taskPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    $taskPython = Join-Path $taskRepository '.ethvenv/Scripts/python.exe'
}
if (-not (Test-Path -LiteralPath $taskPython)) {
    throw 'Create backtesting/.venv and install backtesting/requirements.txt first. See backtesting/README.md.'
}
Push-Location -LiteralPath $taskRepository
try {
    & $taskPython -m streamlit run (Join-Path $PSScriptRoot 'dashboard.py') --server.address 127.0.0.1 --browser.gatherUsageStats false
} finally {
    Pop-Location
}
