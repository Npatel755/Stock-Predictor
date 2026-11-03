# Starts the TradingView -> paper ledger webhook receiver and an ngrok tunnel.
# Run from the repository root in PowerShell. Leave the window open (or register this
# script with Task Scheduler "At log on" so it survives reboots).
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$port = if ($env:PAPER_WEBHOOK_PORT) { $env:PAPER_WEBHOOK_PORT } else { '8787' }
Start-Process -FilePath '.ethvenv\Scripts\python.exe' -ArgumentList '-m', 'backtesting.paper_webhook', '--port', $port -NoNewWindow
Start-Sleep -Seconds 2
Write-Host "Secret (paste into the TradingView alert JSON):"
Get-Content 'backtesting\artifacts\paper_trading\secret.txt'
if ($env:NGROK_DOMAIN) {
    ngrok http --url=$env:NGROK_DOMAIN $port
} else {
    Write-Host 'Set $env:NGROK_DOMAIN to your free static ngrok domain (dashboard.ngrok.com -> Domains) for a stable webhook URL.'
    ngrok http $port
}
