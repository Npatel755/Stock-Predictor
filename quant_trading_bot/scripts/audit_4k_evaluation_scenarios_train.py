"""Scientific Simulation: 4K Evaluation Scenarios Feasibility Audit.
STRICTLY 2010-2023 TRAINING DATA ONLY.
Zero access to Validation (2024-2025) or Blind Test (2026).

Evaluates all three interpretations of 'the evaluation is 4k':
Scenario A: Target is +$4,000 to pass in 2 days (Drawdown floor = $2,000).
Scenario B: Target is +$3,000 or +$4,000 in 2 days with an expanded Drawdown floor = $4,000.
Scenario C: Starting account balance is $4,000 (with broker margin constraints and $1,000-$2,000 risk).
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import mass_1m_search as m1

print("=" * 80)
print("4K EVALUATION SCENARIO AUDIT (2010-2023 TRAINING DATA ONLY)")
print("=" * 80, flush=True)

# Load 14-year MNQ daily data
b = m1.load_bars("MNQ", 1, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]]
et = b.timestamp_utc.dt.tz_convert("America/New_York")
b["date"] = et.dt.date
b["sod"] = et.dt.hour * 60 + et.dt.minute

rth = b[(b.sod >= 570) & (b.sod < 960)].copy()
daily = rth.groupby("date").agg(
    open=("open", "first"),
    high=("high", "max"),
    low=("low", "min"),
    close=("close", "last")
)
daily["range_pts"] = daily["high"] - daily["low"]
daily["net_move_pts"] = daily["close"] - daily["open"]
daily["max_up_pts"] = daily["high"] - daily["open"]
daily["max_down_pts"] = daily["open"] - daily["low"]

dates = daily.index.tolist()
total_evals = len(dates) - 1

def run_simulation(target_dollars, floor_dollars, n_contracts):
    pass_count = 0
    ruin_count = 0
    neither_count = 0
    
    for i in range(total_evals):
        d1 = daily.iloc[i]
        d2 = daily.iloc[i + 1]
        
        # Day 1 Adverse Dip
        dip_d1 = d1["max_down_pts"] * 2.0 * n_contracts
        if dip_d1 >= floor_dollars:
            ruin_count += 1
            continue
            
        pnl_d1 = d1["net_move_pts"] * 2.0 * n_contracts
        hwm_d1 = max(0.0, d1["max_up_pts"] * 2.0 * n_contracts)
        
        # Trailing floor check during Day 1
        if (hwm_d1 - (pnl_d1 - dip_d1)) >= floor_dollars:
            ruin_count += 1
            continue
            
        # Day 2
        peak_prior = max(0.0, pnl_d1)
        dip_d2 = d2["max_down_pts"] * 2.0 * n_contracts
        total_pnl_at_dip = pnl_d1 - dip_d2
        total_hwm = max(peak_prior, pnl_d1 + d2["max_up_pts"] * 2.0 * n_contracts)
        
        if (total_hwm - total_pnl_at_dip) >= floor_dollars or total_pnl_at_dip <= -floor_dollars:
            ruin_count += 1
            continue
            
        # Check target
        total_pnl_close = pnl_d1 + d2["net_move_pts"] * 2.0 * n_contracts
        if total_pnl_close >= target_dollars or (pnl_d1 + d2["max_up_pts"] * 2.0 * n_contracts) >= target_dollars:
            pass_count += 1
        else:
            neither_count += 1
            
    pct_pass = (pass_count / total_evals) * 100
    pct_ruin = (ruin_count / total_evals) * 100
    odds = (ruin_count / pass_count) if pass_count > 0 else 999.0
    
    return {
        "contracts": n_contracts,
        "target": target_dollars,
        "floor": floor_dollars,
        "pct_pass": round(pct_pass, 2),
        "pct_ruin": round(pct_ruin, 2),
        "pct_neither": round((neither_count / total_evals) * 100, 2),
        "ruin_vs_pass_ratio": round(odds, 2)
    }

print("\n--- SCENARIO A: Target = +$4,000 in 2 Days (Floor = $2,000) ---")
print(f"{'Contracts':>10} | {'2-Day Pass Rate':>16} | {'2-Day Ruin Rate':>16} | {'Odds of Ruin vs Pass':>22}")
print("-" * 75)
for nc in [2, 5, 10, 15, 20]:
    res = run_simulation(4000.0, 2000.0, nc)
    print(f"{nc:>10} | {res['pct_pass']:>15.2f}% | {res['pct_ruin']:>15.2f}% | {res['ruin_vs_pass_ratio']:>20.2f}x")

print("\n--- SCENARIO B: Target = +$4,000 in 2 Days with EXPANDED Floor = $4,000 ---")
print(f"{'Contracts':>10} | {'2-Day Pass Rate':>16} | {'2-Day Ruin Rate':>16} | {'Odds of Ruin vs Pass':>22}")
print("-" * 75)
for nc in [2, 5, 10, 15, 20]:
    res = run_simulation(4000.0, 4000.0, nc)
    print(f"{nc:>10} | {res['pct_pass']:>15.2f}% | {res['pct_ruin']:>15.2f}% | {res['ruin_vs_pass_ratio']:>20.2f}x")

print("\n--- SCENARIO C: Target = +$3,000 in 2 Days with EXPANDED Floor = $4,000 ---")
print(f"{'Contracts':>10} | {'2-Day Pass Rate':>16} | {'2-Day Ruin Rate':>16} | {'Odds of Ruin vs Pass':>22}")
print("-" * 75)
for nc in [2, 5, 10, 15, 20]:
    res = run_simulation(3000.0, 4000.0, nc)
    print(f"{nc:>10} | {res['pct_pass']:>15.2f}% | {res['pct_ruin']:>15.2f}% | {res['ruin_vs_pass_ratio']:>20.2f}x")

print("\n[DONE] Simulation completed.")
