$taskRoot = Split-Path -Parent $PSScriptRoot
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
$taskApp = Join-Path $taskRoot 'dashboard\light_server.py'
& $taskPython $taskApp --port 8511
