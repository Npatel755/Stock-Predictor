"""Run Monte Carlo on Ensemble Portfolio."""
import json
import numpy as np
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from monte_carlo_risk_of_ruin import run_monte_carlo

ROOT = Path(__file__).resolve().parents[1]

df = pd.read_csv(ROOT / 'runs/saved_portfolio_F_multi_strategy_ensemble/equity_test.csv')
deltas = df['pnl'].diff().dropna()
deltas = deltas[deltas != 0.0].to_numpy()

res = run_monte_carlo(deltas, n_simulations=10000, n_trades_per_year=120)

print("=" * 80)
print("10,000-PATH MONTE CARLO FOR MULTI-STRATEGY ENSEMBLE (PORTFOLIO F)")
print("=" * 80)
print(f"Probability of Breaching $2k DD: {res['probability_breaching_2k_pct']:.2f}%")
print(f"Median Expected Annual Drawdown:   ${res['median_drawdown']:,.2f}")
print(f"90th Percentile Max Drawdown:      ${res['p90_drawdown']:,.2f}")
print(f"95th Percentile Max Drawdown:      ${res['p95_drawdown']:,.2f}")
print(f"Median Expected Annual P&L:        +${res['median_annual_pnl']:,.2f}")
print(f"10th - 90th Percentile P&L:        +${res['p10_annual_pnl']:,.2f} to +${res['p90_annual_pnl']:,.2f}")

out_path = ROOT / 'runs/overnight_institutional_research/monte_carlo_ensemble_f.json'
json.dump(res, open(out_path, 'w'), indent=2)
