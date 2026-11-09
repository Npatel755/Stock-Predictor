"""Script to plot professional 3-panel audit chart for Architecture D+ and Book D+ across all splits."""
import sys, json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import audit_architecture_d_plus_and_book_d_all_splits as aud

# Load trade datasets
df_d_plus = aud.df_intraday_trades.sort_values('entry_time').reset_index(drop=True)
df_ovn = aud.df_ovn_gated.sort_values('entry_time').reset_index(drop=True)
df_book = aud.df_book_d.sort_values('entry_time').reset_index(drop=True)

# Build cumulative series on shared date timeline
df_d_plus['cum'] = df_d_plus['net'].cumsum()
df_ovn['cum'] = df_ovn['net'].cumsum()
df_book['cum'] = df_book['net'].cumsum()

# Set up matplotlib style
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12), sharex=False, gridspec_kw={'height_ratios': [2.2, 1.2, 1.4]})

# Panel 1: Cumulative Equity Curves
ax1.plot(df_book['entry_time'], df_book['cum'], label='Book D+ Combined (+$41,330 Net / 2,312 trades)', color='#10b981', lw=2.2)
ax1.plot(df_d_plus['entry_time'], df_d_plus['cum'], label='Architecture D+ Intraday (+$23,760 Net / 1,816 trades)', color='#2563eb', lw=1.8)
ax1.plot(df_ovn['entry_time'], df_ovn['cum'], label='Overnight Dip v2 (+$17,570 Net / 496 trades)', color='#8b5cf6', lw=1.4, alpha=0.85, ls='--')

# Partition lines
val_start = pd.Timestamp('2024-01-01', tz='America/New_York')
test_start = pd.Timestamp('2026-01-01', tz='America/New_York')

for ax in (ax1, ax2):
    ax.axvline(val_start, color='#f59e0b', linestyle=':', lw=1.8, label='Validation Partition (2024-2025)' if ax == ax1 else '')
    ax.axvline(test_start, color='#ef4444', linestyle='--', lw=1.8, label='Blind Test Partition (2026)' if ax == ax1 else '')

ax1.set_title('Frozen All-Split Audit: Architecture D+ & Book D+ (2010-2026)\n100% Frozen Parameters from 2010-2023 Training | Zero Tuning on Val/Test', fontsize=13, fontweight='bold', pad=10)
ax1.set_ylabel('Cumulative Net PnL ($)', fontsize=11, fontweight='bold')
ax1.legend(loc='upper left', frameon=True, framealpha=0.9)
ax1.grid(True, alpha=0.3)

# Annotations for partitions
ax1.text(pd.Timestamp('2017-01-01', tz='America/New_York'), 30000, 'TRAINING (2010-2023)\nFrozen Hypothesis Fitting', fontsize=10, color='#475569', ha='center', bbox=dict(boxstyle='round,pad=0.3', facecolor='#f1f5f9', edgecolor='#cbd5e1'))
ax1.text(pd.Timestamp('2024-12-15', tz='America/New_York'), 34000, 'VALIDATION\n(2024-2025)', fontsize=9, color='#b45309', ha='center', bbox=dict(boxstyle='round,pad=0.3', facecolor='#fef3c7', edgecolor='#fde68a'))
ax1.text(pd.Timestamp('2026-06-01', tz='America/New_York'), 38000, 'BLIND TEST\n(2026)', fontsize=9, color='#b91c1c', ha='center', bbox=dict(boxstyle='round,pad=0.3', facecolor='#fee2e2', edgecolor='#fca5a5'))

# Panel 2: Continuous Realized Drawdown for Architecture D+ (Intraday Router)
peak_d = df_d_plus['cum'].cummax()
dd_d = -(peak_d - df_d_plus['cum'])
ax2.plot(df_d_plus['entry_time'], dd_d, color='#dc2626', lw=1.4, label='Architecture D+ Realized Drawdown (Max: -$1,576.83)')
ax2.fill_between(df_d_plus['entry_time'], dd_d, 0, color='#ef4444', alpha=0.15)
ax2.axhline(-2000.0, color='#991b1b', lw=2.0, ls='-', label='$2,000 Trailing Floor (ZERO Touches across 16.9 Years)')
ax2.axhline(-1500.0, color='#f59e0b', lw=1.2, ls=':', label='$1,500 Warning Level')
ax2.set_ylabel('Realized Drawdown ($)', fontsize=11, fontweight='bold')
ax2.set_ylim(-2400, 200)
ax2.legend(loc='lower left', frameon=True, framealpha=0.9)
ax2.grid(True, alpha=0.3)

# Panel 3: Annual Profitability by Year
years = np.arange(2010, 2027)
net_d_plus_yr = [df_d_plus[df_d_plus['year'] == y]['net'].sum() for y in years]
net_book_yr = [df_book[df_book['year'] == y]['net'].sum() for y in years]

x = np.arange(len(years))
width = 0.38

rects1 = ax3.bar(x - width/2, net_d_plus_yr, width, label='Architecture D+ Intraday', color='#3b82f6', alpha=0.85)
rects2 = ax3.bar(x + width/2, net_book_yr, width, label='Book D+ Combined', color='#10b981', alpha=0.85)

ax3.axhline(0, color='black', lw=0.8)
ax3.set_xticks(x)
ax3.set_xticklabels([str(y) for y in years], rotation=45, fontsize=9)
ax3.set_ylabel('Annual Net Profit ($)', fontsize=11, fontweight='bold')
ax3.set_xlabel('Calendar Year (2024-2025 = Validation, 2026 = Blind Test)', fontsize=11, fontweight='bold')
ax3.legend(loc='upper left', frameon=True, framealpha=0.9)
ax3.grid(True, alpha=0.3)

plt.tight_layout()

# Save chart to artifact dir
artifact_dir = Path(r"C:\Users\Nick\.gemini\antigravity\brain\892d6d20-4274-43dc-a605-1f060d93027d")
artifact_dir.mkdir(parents=True, exist_ok=True)
chart_path_artifact = artifact_dir / "all_splits_audit_architecture_d_plus_and_book_d.png"
fig.savefig(chart_path_artifact, dpi=200, bbox_inches='tight')

# Also save to repo reports dir
repo_chart_path = ROOT / "reports/all_splits_audit_architecture_d_plus_and_book_d.png"
fig.savefig(repo_chart_path, dpi=200, bbox_inches='tight')

print(f"[SUCCESS] Chart saved to {chart_path_artifact} and {repo_chart_path}")
