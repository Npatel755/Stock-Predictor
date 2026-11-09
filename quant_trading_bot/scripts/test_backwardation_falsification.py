"""Negative control test for the 69 backwardation trades removed from Architecture D.
Skill: negative-control-testing.
"""
import sys, numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'src'))

from research_vix_gate_architecture_d_train import (
    b_mnq_15, b_mnq_30, b_mnq_60, b_mes_15, b_mes_30,
    cal_dates, vix_ratio, prior_backw_map, run_simulation, base, gated
)

df_base_tr = base['df_trades']
print(f"Total baseline trades: {len(df_base_tr)}")

# Identify removed trades
removed_net = base['total_net'] - gated['total_net']
print(f"Removed Net P&L (Total Base - Gated): ${removed_net:.2f}")

# Run 100 random removals of 69 trades
np.random.seed(42)
random_removed_nets = []
trade_nets = df_base_tr['net'].to_numpy()

for i in range(200):
    idx = np.random.choice(len(trade_nets), size=69, replace=False)
    random_removed_nets.append(float(np.sum(trade_nets[idx])))

p5 = np.percentile(random_removed_nets, 5)
p1 = np.percentile(random_removed_nets, 1)
mean_rand = np.mean(random_removed_nets)

print("\n" + "=" * 80)
print("FALSIFICATION SCORECARD FOR REMOVED TRADES (Skill: negative-control-testing):")
print(f"Actual Net of Removed Trades:          ${removed_net:,.2f}")
print(f"Random 69-Trade Removal Mean:         +${mean_rand:,.2f}")
print(f"Random 69-Trade Removal 5th Pct:      +${p5:,.2f}")
print(f"Random 69-Trade Removal 1st Pct:      +${p1:,.2f}")
print(f"Is Actual Removed Net < 1st Percentile? {removed_net < p1}")
print("=" * 80)
