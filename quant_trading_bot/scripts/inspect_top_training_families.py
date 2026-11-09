import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
qualifiers = json.load(open(ROOT / 'runs/htf_swing_training_qualifiers.json'))
df = pd.DataFrame(qualifiers)

print("=" * 110)
print("TOP TRAINING CANDIDATES BY FAMILY (TRAIN: 2020-2023)")
print("=" * 110)

cols = ['sym', 'tf', 'family', 'session', 'lookback', 'threshold', 'stop_atr', 'target_ratio', 'hold_bars', 'trailing_atr', 'net_pnl', 'trades', 'expectancy', 'intrabar_dd', 'calmar']

for grp, g_df in df.groupby(['sym', 'tf', 'family']):
    print(f"\n--- {grp[0]} {grp[1]} {grp[2]} ({len(g_df)} candidates) ---")
    top = g_df.sort_values('net_pnl', ascending=False)
    print(top[cols].head(3).to_string(index=False))
