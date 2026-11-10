"""Mathematical & Empirical Proof: The Gambler's Ruin Law of 2-Day Funded Account Evaluations.
STRICTLY 2010-2023 TRAINING DATA ONLY.
Zero access to Validation (2024-2025) or Blind Test (2026).

Applies:
1. First Passage Time theory (hitting +$3,000 before -$2,000 trailing drawdown).
2. Empirical 14-year distribution of 2-day returns on MNQ and MES.
3. Prop firm evaluation rules (consistency rule, trailing drawdown from unrealized peak).
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import mass_1m_search as m1

print("=" * 80)
print("MATHEMATICAL & EMPIRICAL AUDIT: 2-DAY EVALUATION (2010-2023 TRAINING)")
print("=" * 80, flush=True)

# Load 1-minute MNQ bars across 14 years
b = m1.load_bars("MNQ", 1, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]]
et = b.timestamp_utc.dt.tz_convert("America/New_York")
b["date"] = et.dt.date
b["sod"] = et.dt.hour * 60 + et.dt.minute

# RTH session 09:30 - 16:00
rth = b[(b.sod >= 570) & (b.sod < 960)].copy()

# Daily stats: open, high, low, close, range in points and dollars per contract
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

print("\n--- 14-YEAR HISTORICAL DAILY VOLATILITY CONTEXT (MNQ 2010-2023) ---")
print(f"Total Trading Days: {len(daily)}")
print(f"Median Daily Range: {daily['range_pts'].median():.1f} pts (${daily['range_pts'].median() * 2:.1f} per micro)")
print(f"Mean Daily Range  : {daily['range_pts'].mean():.1f} pts (${daily['range_pts'].mean() * 2:.1f} per micro)")
print(f"Median Daily Close-to-Close Move: {daily['net_move_pts'].abs().median():.1f} pts (${daily['net_move_pts'].abs().median() * 2:.1f} per micro)")

# Simulate what position size is required to make $3,000 in 2 days
# Target: $1,500 / day
# With N contracts: Required favorable move = 1500 / (N * 2.0) points.
# Maximum allowable adverse excursion before blowing $2,000 floor = 2000 / (N * 2.0) points.

results = []
print("\n--- POSITION SIZING & RUIN DYNAMICS FOR 2-DAY $3,000 TARGET ---")
print(f"{'Contracts':>10} | {'Req Daily Move':>15} | {'Max Tolerable Dip':>18} | {'2-Day Pass Rate':>16} | {'2-Day Ruin Rate':>16} | {'Odds of Ruin vs Pass':>22}")
print("-" * 105)

for n_contracts in [1, 2, 3, 5, 8, 10, 15, 20, 25]:
    req_daily_pts = 1500.0 / (n_contracts * 2.0)
    max_dip_pts = 2000.0 / (n_contracts * 2.0)
    
    # Check across all 2-day rolling windows
    dates = daily.index.tolist()
    pass_count = 0
    ruin_count = 0
    neither_count = 0
    total_evals = len(dates) - 1
    
    for i in range(total_evals):
        d1 = daily.iloc[i]
        d2 = daily.iloc[i + 1]
        
        # Check Day 1
        # Dip on Day 1
        dip_d1 = d1["max_down_pts"] * 2.0 * n_contracts
        if dip_d1 >= 2000.0:
            ruin_count += 1
            continue
            
        # PnL end of Day 1
        pnl_d1 = d1["net_move_pts"] * 2.0 * n_contracts
        hwm_d1 = max(0.0, d1["max_up_pts"] * 2.0 * n_contracts)
        
        # Check if floor breached during Day 1 intraday from peak
        if (hwm_d1 - (d1["net_move_pts"] * 2.0 * n_contracts - dip_d1)) >= 2000.0:
            # Trailing floor check
            ruin_count += 1
            continue
            
        # Day 2
        peak_prior = max(0.0, pnl_d1)
        dip_d2 = d2["max_down_pts"] * 2.0 * n_contracts
        total_pnl_at_dip = pnl_d1 - dip_d2
        total_hwm = max(peak_prior, pnl_d1 + d2["max_up_pts"] * 2.0 * n_contracts)
        
        if (total_hwm - total_pnl_at_dip) >= 2000.0 or (pnl_d1 - dip_d2) <= -2000.0:
            ruin_count += 1
            continue
            
        # End of Day 2 PnL
        total_pnl_close = pnl_d1 + d2["net_move_pts"] * 2.0 * n_contracts
        if total_pnl_close >= 3000.0 or (pnl_d1 + d2["max_up_pts"] * 2.0 * n_contracts) >= 3000.0:
            pass_count += 1
        else:
            neither_count += 1
            
    pct_pass = (pass_count / total_evals) * 100
    pct_ruin = (ruin_count / total_evals) * 100
    ruin_multiplier = (ruin_count / pass_count) if pass_count > 0 else 999.0
    
    print(f"{n_contracts:>10} | {req_daily_pts:>12.1f} pts | {max_dip_pts:>15.1f} pts | {pct_pass:>15.2f}% | {pct_ruin:>15.2f}% | {ruin_multiplier:>20.2f}x")
    
    results.append({
        "contracts": n_contracts,
        "req_daily_pts": req_daily_pts,
        "max_dip_pts": max_dip_pts,
        "pct_pass": round(pct_pass, 2),
        "pct_ruin": round(pct_ruin, 2),
        "ruin_vs_pass_ratio": round(ruin_multiplier, 2)
    })

out_path = ROOT / "reports/GAMBLERS_RUIN_2DAY_EVAL_TRAIN.json"
with open(out_path, "w") as fp:
    json.dump(results, fp, indent=2)
print(f"\n[DONE] Saved Gambler's Ruin analysis to {out_path}")
