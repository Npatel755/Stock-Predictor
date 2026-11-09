"""Block Bootstrap Monte Carlo Risk-of-Ruin Simulator (Training 2010-2023).
Skill: risk-of-ruin-monte-carlo.
Evaluates 1-year evaluation survival under the strict $2,000 trailing drawdown floor.
"""
import sys, numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runs/training_search_500k_v1/code'))
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'src'))

from research_vix_gate_architecture_d_train import base, gated

# Trade records from 2010-2023 Training Data
df_base = base['df_trades']
df_gated = gated['df_trades']

def simulate_funded_mc(df_tr, label="Strategy", num_paths=5000, block_geom_p=0.10):
    # Group by calendar day to preserve intraday streak autocorrelation
    daily_pnl = df_tr.groupby('year')['net'].sum() # verify year
    
    # We need day-level PnL
    # Since df_tr has trade nets, let's use the sequence of trades
    trade_nets = df_tr['net'].to_numpy()
    n_trades = len(trade_nets)
    trades_per_year = int(n_trades / 14) # ~120 trades/year
    
    rng = np.random.default_rng(101)
    breaches_floor = 0
    max_drawdowns = []
    annual_nets = []
    
    for _ in range(num_paths):
        # Stationary block bootstrap
        sim_trades = []
        while len(sim_trades) < trades_per_year:
            start_idx = rng.integers(n_trades)
            block_len = rng.geometric(block_geom_p)
            for step in range(block_len):
                sim_trades.append(trade_nets[(start_idx + step) % n_trades])
        sim_trades = np.array(sim_trades[:trades_per_year])
        
        # Cumulative PnL path
        cum_pnl = np.cumsum(sim_trades)
        peak = np.maximum.accumulate(np.concatenate([[0.0], cum_pnl]))[:-1]
        underwater = peak - cum_pnl
        path_max_dd = float(np.max(underwater))
        
        # Check $2,000 trailing floor breach
        if path_max_dd >= 2000.0:
            breaches_floor += 1
            
        max_drawdowns.append(path_max_dd)
        annual_nets.append(float(cum_pnl[-1]))
        
    prob_breach = breaches_floor / num_paths * 100.0
    median_dd = float(np.median(max_drawdowns))
    p95_dd = float(np.percentile(max_drawdowns, 95))
    p99_dd = float(np.percentile(max_drawdowns, 99))
    median_net = float(np.median(annual_nets))
    
    return {
        "label": label,
        "prob_breach": prob_breach,
        "median_dd": median_dd,
        "p95_dd": p95_dd,
        "p99_dd": p99_dd,
        "median_net": median_net,
        "trades_per_year": trades_per_year
    }

print("\nRunning Stationary Block Bootstrap Monte Carlo Simulation (5,000 1-Year Paths)...", flush=True)
res_base = simulate_funded_mc(df_base, label="Architecture D Baseline")
res_gated = simulate_funded_mc(df_gated, label="Architecture D + VIX Backwardation Gate (D+)")

print("=" * 95)
print(f"MONTE CARLO RISK-OF-RUIN SCORECARD ($50K Account, Strict $2,000 Trailing Floor, 5,000 Paths):")
print("=" * 95)
for res in [res_base, res_gated]:
    print(f"\nStrategy: {res['label']}")
    print(f"  Trades / Year:                      {res['trades_per_year']} trades/year")
    print(f"  Median 1-Year Net Profit:          +${res['median_net']:,.2f}")
    print(f"  Median Max Drawdown:                ${res['median_dd']:,.2f}")
    print(f"  95th Percentile Max Drawdown:       ${res['p95_dd']:,.2f}")
    print(f"  99th Percentile Max Drawdown:       ${res['p99_dd']:,.2f}")
    print(f"  Prob of Breaching $2,000 Floor:     {res['prob_breach']:.2f}%")

print("=" * 95)
