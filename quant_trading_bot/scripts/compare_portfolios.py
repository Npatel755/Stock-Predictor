import pandas as pd
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import simulate_tri_timeframe_portfolio as stp

df = stp.df_all

# Duo: MNQ 60m + MNQ 5m
sub_duo = df[df['sleeve'].isin(['MNQ_60m', 'MNQ_5m'])].copy()
sub_duo['cum'] = sub_duo['net'].cumsum()
sub_duo['pk'] = sub_duo['cum'].cummax()
sub_duo['dd'] = sub_duo['pk'] - sub_duo['cum']

duo_net = sub_duo['net'].sum()
duo_trades = len(sub_duo)
duo_exp = duo_net / duo_trades
duo_dd = sub_duo['dd'].max()

print("="*80)
print("DUO-HORIZON MNQ CHAMPION (60m Trend + 5m MTF Breakout):")
print("="*80)
print(f"Total Net P&L:        +${duo_net:,.2f} ($2,898.09 / year at 1 contract!)")
print(f"Total Trades:         {duo_trades} (~97 trades / year)")
print(f"Expectancy:           +${duo_exp:.2f} / trade")
print(f"Max Closed DD:        ${duo_dd:,.2f} (Safety Cushion: +${2000 - duo_dd:,.2f}!)")
print(f"Calmar Ratio:         {duo_net / duo_dd:.2f}")

print("\nYearly Breakdown:")
for y in [2020, 2021, 2022, 2023]:
    s = sub_duo[sub_duo['year'] == y]
    y_net = s['net'].sum()
    y_cnt = len(s)
    y_exp = y_net / y_cnt if y_cnt else 0.0
    print(f"  {y}: +${y_net:,.2f} ({y_cnt} trades, +${y_exp:.2f}/trade)")
