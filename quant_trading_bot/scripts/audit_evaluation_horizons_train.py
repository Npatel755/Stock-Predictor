"""Multi-Horizon Prop Firm Evaluation Feasibility Audit.
STRICTLY 2010-2023 TRAINING DATA ONLY.
Zero access to Validation (2024-2025) or Blind Test (2026).

Analyzes the exact Pass Rate vs Ruin Rate across horizons:
- 5 Trading Days (1 Week)
- 10 Trading Days (2 Weeks)
- 15 Trading Days (3 Weeks)
- 20 Trading Days (1 Month)

Target: $4,000 (and $3,000 sensitivity)
Floor: $2,000 Trailing Drawdown
Daily Loss Limit: $1,000
50% Consistency Rule enforced (no single day > 50% of target).
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

# Import baseline trades from dplus_4_pilot
src = (ROOT / "scripts/dplus_4_pilot.py").read_text().split("\nout = {}")[0]
ns = {"__file__": str(ROOT / "scripts/dplus_4_pilot.py")}
exec(src, ns)
base = ns["base"]

# Build trades and calendar series
import mass_1m_search as m1
b = m1.load_bars("MNQ", 1, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]]
et = b.timestamp_utc.dt.tz_convert("America/New_York")
b["date"] = et.dt.date
b["sod"] = et.dt.hour * 60 + et.dt.minute
rth = b[(b.sod >= 570) & (b.sod < 960)].copy()
all_days = sorted(rth["date"].unique())

# Prepare PnL series for Architecture D+ v2 (Gap-Sized)
records = []
for t in base:
    qty = 2 if t.get("cont", False) else 1
    records.append({
        "day": pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date(),
        "net": t["net"] * qty,
        "mae": t.get("mae", 0.0) * qty,
    })
df_t = pd.DataFrame(records)
daily_pnl = df_t.groupby("day")["net"].sum()
daily_mae = df_t.groupby("day")["mae"].sum()

pnl_series = pd.Series(0.0, index=all_days)
pnl_series.update(daily_pnl)

mae_series = pd.Series(0.0, index=all_days)
mae_series.update(daily_mae)

def evaluate_horizon(horizon_days, target=4000.0, floor=2000.0, dll=1000.0, multiplier=1.0):
    total_evals = len(all_days) - horizon_days + 1
    clean_pass = 0
    inconsistent_pass = 0
    ruined = 0
    neither = 0
    max_day_limit = target * 0.50
    
    for i in range(total_evals):
        w_days = all_days[i : i + horizon_days]
        cum_pnl = 0.0
        hwm = 0.0
        busted = False
        max_day = -9999.0
        
        for d in w_days:
            dp = pnl_series[d] * multiplier
            dm = mae_series[d] * multiplier
            
            # Daily loss limit check
            if dp <= -dll or dm <= -dll:
                busted = True
                break
                
            # Trailing drawdown check
            if (hwm - (cum_pnl + dm)) >= floor or (cum_pnl + dm) <= -floor:
                busted = True
                break
                
            cum_pnl += dp
            if cum_pnl > hwm:
                hwm = cum_pnl
                
            if (hwm - cum_pnl) >= floor or cum_pnl <= -floor:
                busted = True
                break
                
            if dp > max_day:
                max_day = dp
                
            if cum_pnl >= target:
                break
                
        if busted:
            ruined += 1
        elif cum_pnl >= target:
            if max_day <= max_day_limit:
                clean_pass += 1
            else:
                inconsistent_pass += 1
        else:
            neither += 1
            
    return {
        "horizon": horizon_days,
        "multiplier": multiplier,
        "pct_clean_pass": round((clean_pass / total_evals) * 100, 2),
        "pct_any_pass": round(((clean_pass + inconsistent_pass) / total_evals) * 100, 2),
        "pct_ruin": round((ruined / total_evals) * 100, 2),
        "pct_neither": round((neither / total_evals) * 100, 2),
        "ruin_vs_pass_ratio": round((ruined / clean_pass), 2) if clean_pass > 0 else 999.0
    }

print("=" * 85)
print("MULTI-HORIZON EVALUATION FEASIBILITY (TARGET = $4,000, FLOOR = $2,000)")
print("=" * 85)
print(f"{'Horizon':>10} | {'Multiplier':>10} | {'Clean Pass %':>12} | {'Any Pass %':>10} | {'Ruin %':>10} | {'Neither %':>10}")
print("-" * 85)

for h in [5, 10, 15, 20]:
    for m in [2, 3, 4, 5, 6, 8, 10]:
        res = evaluate_horizon(h, target=4000.0, floor=2000.0, dll=1000.0, multiplier=m)
        print(f"{h:>8} d | {m:>8}x | {res['pct_clean_pass']:>11}% | {res['pct_any_pass']:>9}% | {res['pct_ruin']:>9}% | {res['pct_neither']:>9}%")
    print("-" * 85)

print("\nDONE", flush=True)
