param([switch]$Stop)
$bridgeScript = Join-Path $PSScriptRoot 'codex_history_bridge.py'
$bridgePython = Join-Path $PSScriptRoot '..\quant_trading_bot\.venv\Scripts\python.exe'
$bridgePidFile = Join-Path $PSScriptRoot 'codex_history_process.json'
if (Test-Path -LiteralPath $bridgePidFile) {
    $bridgeState = Get-Content -LiteralPath $bridgePidFile -Raw | ConvertFrom-Json
    $bridgeProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($bridgeState.pid)" -ErrorAction SilentlyContinue
    if ($bridgeProcess -and $bridgeProcess.CommandLine -like '*codex_history_bridge.py*--watch*') {
        if ($Stop) {
            Stop-Process -Id $bridgeState.pid
            Write-Output 'Codex history refresh stopped; saved mirrors preserved.'
        } else {
            Write-Output "Codex history refresh is already running (PID $($bridgeState.pid))."
        }
        exit 0
    }
}
if ($Stop) { Write-Output 'Codex history refresh is not running.'; exit 0 }
if (-not (Test-Path -LiteralPath $bridgePython)) { throw 'Project Python runtime is missing.' }
$bridgeArgs = @('"' + $bridgeScript + '"', '--watch', '--interval', '5')
$bridgeProcess = Start-Process -FilePath $bridgePython -ArgumentList $bridgeArgs -WindowStyle Hidden -PassThru -WorkingDirectory $PSScriptRoot -RedirectStandardOutput (Join-Path $PSScriptRoot 'codex_history.stdout.log') -RedirectStandardError (Join-Path $PSScriptRoot 'codex_history.stderr.log')
@{pid=$bridgeProcess.Id; started_at=(Get-Date).ToUniversalTime().ToString('o'); interval_seconds=5} | ConvertTo-Json | Set-Content -LiteralPath $bridgePidFile -Encoding UTF8
Write-Output "Codex history refresh started (PID $($bridgeProcess.Id)); polling every five seconds."
