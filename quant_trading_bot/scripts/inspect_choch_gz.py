import subprocess, gzip, io, pandas as pd

try:
    data = subprocess.check_output(['git', 'show', 'remotes/research/claude-research:claude_research/strategies/tjr_liquidity_sweep/lab/results/choch/results_configs.csv.gz'])
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as f:
        df = pd.read_csv(f, low_memory=False)
    sub = df[df.config_hash.str.startswith('6fe8') == True]
    if len(sub) > 0:
        print("Found 6fe8:")
        print(sub[['config_hash', 'tf', 'n', 'stop', 'target_r', 'trades', 'win_rate', 'avg_r', 'profit_factor', 'sharpe']])
    print("\nTop 10 choch by win_rate (trades >= 200):")
    print(df[df.trades >= 200].sort_values('win_rate', ascending=False)[['config_hash', 'tf', 'n', 'stop', 'target_r', 'trades', 'win_rate', 'avg_r', 'sharpe']].head(10))
except Exception as e:
    print(e)
