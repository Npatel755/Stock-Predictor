$taskRoot = Split-Path -Parent $PSScriptRoot
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
$taskApp = Join-Path $taskRoot 'dashboard\app.py'
& $taskPython -m streamlit run $taskApp --server.address 127.0.0.1 --server.port 8511
