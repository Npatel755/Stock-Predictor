"""Monte Carlo Risk of Ruin Audit for Book D+ on 2010-2023 Training Data.
STRICTLY TRAINING DATA ONLY: 2010-2023.
Zero access to Validation (2024-2025) or Blind Test (2026).

Applies:
Stationary Block Bootstrap (Politis & Romano, 1994) with mean block length L = 10 trades.
5,000 independent 1-year evaluation paths.
Funded Account: $50,000 starting capital, strict $2,000 trailing drawdown floor.
"""
import sys, os
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from research_book_d_plus_risk_reduction_train import evaluate_book_d

print("Extracting chronological trade P&Ls for Book D+ (VIX Backwardation Gate)...", flush=True)
b_back = evaluate_book_d("no_backwardation")

trades = np.array(b_back["closed_trades"], dtype=np.float64)
n_trades = len(trades)
print(f"Total Completed Trades/Nights: {n_trades}")
print(f"Net Profit: ${trades.sum():.2f}")
print(f"Expectancy: ${trades.mean():.2f} / trade")

# Simulation Parameters
N_PATHS = 5000
TRADES_PER_YEAR = int(round(n_trades / 14.0)) # ~147 trades per year
MEAN_BLOCK_LEN = 10
P_NEW_BLOCK = 1.0 / MEAN_BLOCK_LEN
FLOOR = 2000.0

print(f"\nRunning {N_PATHS:,} Stationary Block Bootstrap 1-Year Paths (Trades/Year = {TRADES_PER_YEAR})...", flush=True)

rng = np.random.default_rng(20261110)
path_nets = []
path_max_dds = []
breach_count = 0

for p in range(N_PATHS):
    # Generate stationary block bootstrap indices
    idx = []
    curr = rng.integers(0, n_trades)
    for _ in range(TRADES_PER_YEAR):
        if rng.random() < P_NEW_BLOCK:
            curr = rng.integers(0, n_trades)
        else:
            curr = (curr + 1) % n_trades
        idx.append(curr)
        
    p_trades = trades[idx]
    cum = np.cumsum(p_trades)
    peak = np.maximum.accumulate(cum)
    dd = peak - cum
    max_dd = float(np.max(dd))
    total_net = float(cum[-1])
    
    path_nets.append(total_net)
    path_max_dds.append(max_dd)
    
    if max_dd >= FLOOR:
        breach_count += 1

path_nets = np.array(path_nets)
path_max_dds = np.array(path_max_dds)
breach_prob = (breach_count / N_PATHS) * 100.0

print("\n" + "=" * 90)
print("MONTE CARLO RISK OF RUIN AUDIT: BOOK D+ (TRAINING 2010-2023)")
print("Starting Capital: $50,000 | Strict $2,000 Trailing Floor | 5,000 Paths")
print("=" * 90)
print(f"1-Year Breach Probability (P >= $2,000): {breach_prob:.2f}% ({breach_count} / {N_PATHS:,} paths)")
print(f"Median 1-Year Net Profit:                +${np.median(path_nets):.2f}")
print(f"Median Max Drawdown:                      ${np.median(path_max_dds):.2f}")
print(f"90th Percentile Max Drawdown:             ${np.percentile(path_max_dds, 90):.2f} (Buffer: +${2000.0 - np.percentile(path_max_dds, 90):.2f})")
print(f"95th Percentile Max Drawdown:             ${np.percentile(path_max_dds, 95):.2f} (Buffer: +${2000.0 - np.percentile(path_max_dds, 95):.2f})")
print(f"99th Percentile Max Drawdown:             ${np.percentile(path_max_dds, 99):.2f} (Buffer: +${2000.0 - np.percentile(path_max_dds, 99):.2f})")
print(f"Maximum Simulated Drawdown:               ${np.max(path_max_dds):.2f}")
print("=" * 90)
