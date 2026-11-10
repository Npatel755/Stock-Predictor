import subprocess, gzip, io, pandas as pd

try:
    out = subprocess.check_output(['git', 'show', 'remotes/research/claude-research:claude_research/strategies/tjr_liquidity_sweep/lab/results/choch/es_check.csv'], encoding='utf-8', errors='ignore')
    print("=== es_check.csv ===")
    print(out[:1000])
except Exception as e:
    print(e)
