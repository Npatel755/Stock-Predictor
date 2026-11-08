import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from pathlib import Path
import audit_master_7y_continuous as a

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = Path(r"C:\Users\Nick\.gemini\antigravity\brain\892d6d20-4274-43dc-a605-1f060d93027d")

# Prepare equity curves
df_brk2, _, _ = a.run_strat_full(a.mnq_morning_breakout_2c, a.bars_mnq_7y)
df_brk1, _, _ = a.run_strat_full(dict(a.mnq_morning_breakout_2c, max_contracts=1), a.bars_mnq_7y)
df_trd, _, _ = a.run_strat_full(a.mnq_afternoon_trend_1c, a.bars_mnq_7y)

m3 = pd.merge(df_brk2[['ts', 'cash', 'worst']].rename(columns={'cash': 'c_brk', 'worst': 'w_brk'}),
              df_trd[['ts', 'cash', 'worst']].rename(columns={'cash': 'c_trd', 'worst': 'w_trd'}),
              on='ts', how='outer').sort_values('ts').ffill().fillna(50000.0)

m1 = pd.merge(df_brk1[['ts', 'cash', 'worst']].rename(columns={'cash': 'c_brk', 'worst': 'w_brk'}),
              df_trd[['ts', 'cash', 'worst']].rename(columns={'cash': 'c_trd', 'worst': 'w_trd'}),
              on='ts', how='outer').sort_values('ts').ffill().fillna(50000.0)

m3['net_pnl'] = (m3['c_brk'] - 50000.0) + (m3['c_trd'] - 50000.0)
m1['net_pnl'] = (m1['c_brk'] - 50000.0) + (m1['c_trd'] - 50000.0)

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={'height_ratios': [2.5, 1]})

# Top plot: Net P&L
ax1.plot(m3['ts'], m3['net_pnl'], label='Portfolio 3 (MNQ Morning 2c + Afternoon 1c) - Net +$18.7k / +$20.1k', color='#10b981', linewidth=2)
ax1.plot(m1['ts'], m1['net_pnl'], label='Portfolio 1 (MNQ Morning 1c + Afternoon 1c) - Net +$10.4k / +$11.6k', color='#3b82f6', linewidth=1.8, linestyle='--')
ax1.set_title('Master 7-Year Continuous Equity Curve (2020-2026)\n10M Search Discoveries with Holiday Early-Close Flattening Active', fontsize=14, fontweight='bold', pad=12)
ax1.set_ylabel('Cumulative Net P&L ($)', fontsize=11, fontweight='bold')
ax1.grid(True, linestyle=':', alpha=0.6)
ax1.legend(loc='upper left', fontsize=10, framealpha=0.9)

# Drawdown plot
m3['peak'] = m3['net_pnl'].cummax()
m3['dd'] = m3['peak'] - ((m3['w_brk'] - 50000.0) + (m3['w_trd'] - 50000.0))

m1['peak'] = m1['net_pnl'].cummax()
m1['dd'] = m1['peak'] - ((m1['w_brk'] - 50000.0) + (m1['w_trd'] - 50000.0))

ax2.plot(m3['ts'], -m3['dd'], label='Portfolio 3 Drawdown (Worst: $1,625.75)', color='#f59e0b', linewidth=1.5)
ax2.plot(m1['ts'], -m1['dd'], label='Portfolio 1 Drawdown (Worst: $1,385.75)', color='#6366f1', linewidth=1.5, linestyle='--')
ax2.axhline(-2000.0, color='#ef4444', linestyle='-', linewidth=2, label='Strict Funded Account Limit (-$2,000.00)')
ax2.fill_between(m3['ts'], -m3['dd'], 0, color='#f59e0b', alpha=0.15)
ax2.set_ylabel('Trailing Drawdown ($)', fontsize=11, fontweight='bold')
ax2.set_xlabel('Date', fontsize=11, fontweight='bold')
ax2.grid(True, linestyle=':', alpha=0.6)
ax2.legend(loc='lower left', fontsize=9, framealpha=0.9)

plt.tight_layout()
png_path = ARTIFACT_DIR / "master_7year_portfolio3_vs_portfolio1.png"
svg_path = ARTIFACT_DIR / "master_7year_portfolio3_vs_portfolio1.svg"
plt.savefig(png_path, dpi=200)
plt.savefig(svg_path)
plt.close()
print(f"Saved charts to {png_path} and {svg_path}")
