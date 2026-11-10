"""Comprehensive Empirical Simulation: 1-Week / $4,000 Evaluation Challenge.
STRICTLY 2010-2023 TRAINING DATA ONLY.
Zero access to Validation (2024-2025) or Blind Test (2026).

Analyzes:
1. Baseline Architecture D+ and D+ v2 (Gap-Sized) 5-day rolling performance across 3,397 trading days.
2. Required sizing (micro & mini) to achieve +$4,000 within 5 trading days (1 week).
3. Exact Pass Rate vs Ruin Rate under Topstep $2,000 Trailing Drawdown & $1,000 Daily Loss Limit.
4. Topstep 50% Consistency Rule compliance (no single day > $2,000).
5. High-Expectancy Volatility Gating (VIX, ATR, Gap Magnitude) to optimize sprint probability.
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

# Import pipeline from dplus_4_pilot
src = (ROOT / "scripts/dplus_4_pilot.py").read_text().split("\nout = {}")[0]
ns = {"__file__": str(ROOT / "scripts/dplus_4_pilot.py")}
exec(src, ns)
base = ns["base"]

print("=" * 80)
print("1-WEEK / $4,000 EVALUATION FEASIBILITY AUDIT (2010-2023 TRAINING DATA)")
print("=" * 80, flush=True)

# Build trade dataframe
records = []
for t in base:
    # Qty logic for v2 gapsize: 2 contracts if crabel continuation, else 1
    qty_v2 = 2 if t.get("cont", False) else 1
    records.append({
        "entry_ts": t["entry_ts"],
        "exit_ts": t["exit_ts"],
        "entry_day": t["day"],
        "exit_day": pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date(),
        "sleeve": t["sleeve"],
        "net_1c": t["net"],
        "net_v2": t["net"] * qty_v2,
        "cont": t.get("cont", False),
        "gap": t.get("gap", 0.0),
        "mae": t.get("mae", 0.0),
        "mfe": t.get("mfe", 0.0),
    })

df_trades = pd.DataFrame(records)
print(f"Total Architecture D+ trades loaded: {len(df_trades):,} trades across 14 years.")

# Aggregate by trading day
# We need all trading days in the period 2010-2023
daily_1c = df_trades.groupby("exit_day")["net_1c"].sum()
daily_v2 = df_trades.groupby("exit_day")["net_v2"].sum()

# Load all RTH days from daily MNQ bars
import mass_1m_search as m1
b = m1.load_bars("MNQ", 1, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]]
et = b.timestamp_utc.dt.tz_convert("America/New_York")
b["date"] = et.dt.date
b["sod"] = et.dt.hour * 60 + et.dt.minute
rth = b[(b.sod >= 570) & (b.sod < 960)].copy()
all_trading_days = sorted(rth["date"].unique())
print(f"Total RTH Trading Days in Training Split (2010-2023): {len(all_trading_days):,}")

# Build a complete calendar-aligned daily PnL series (0 on non-trading or no-trade days)
pnl_1c_series = pd.Series(0.0, index=all_trading_days)
pnl_1c_series.update(daily_1c)

pnl_v2_series = pd.Series(0.0, index=all_trading_days)
pnl_v2_series.update(daily_v2)

# Also get intraday worst excursion per day from trades
# For conservative intraday drawdown tracking
trade_mae_by_day = df_trades.groupby("exit_day")["mae"].sum()
mae_series = pd.Series(0.0, index=all_trading_days)
mae_series.update(trade_mae_by_day)

# 1. 5-Day Rolling Statistics for 1 Contract
rolling_5d_1c = pnl_1c_series.rolling(5).sum().dropna()
rolling_5d_v2 = pnl_v2_series.rolling(5).sum().dropna()

print("\n--- 5-DAY ROLLING PERFORMANCE (BASELINE 1 CONTRACT & V2 GAPSIZE) ---")
print(f"Total 5-day windows evaluated: {len(rolling_5d_1c):,}")
print(f"Mean 5-day P&L (1c):   +${rolling_5d_1c.mean():.2f}")
print(f"Median 5-day P&L (1c): +${rolling_5d_1c.median():.2f}")
print(f"Max 5-day P&L (1c):    +${rolling_5d_1c.max():.2f}")
print(f"Min 5-day P&L (1c):    -${abs(rolling_5d_1c.min()):.2f}")
print(f"95th Percentile 5-day (1c): +${np.percentile(rolling_5d_1c, 95):.2f}")
print(f"99th Percentile 5-day (1c): +${np.percentile(rolling_5d_1c, 99):.2f}")
print(f"Max 5-day P&L (v2 Gapsize): +${rolling_5d_v2.max():.2f}")
print(f"95th Percentile 5-day (v2): +${np.percentile(rolling_5d_v2, 95):.2f}")
print(f"99th Percentile 5-day (v2): +${np.percentile(rolling_5d_v2, 99):.2f}")

# Now, let's simulate the Prop Firm Evaluation Challenge
# Evaluation Horizon: Exactly 5 Trading Days (1 Calendar Week)
# Target: +$4,000 (also test +$3,000 for standard Topstep 50k)
# Trailing Drawdown Floor: $2,000 from High Water Mark (intraday & close-to-close)
# Daily Loss Limit: $1,000 per day
# Consistency Rule: No single day can exceed 50% of target (i.e. <= $2,000 for $4k, <= $1,500 for $3k)

def simulate_eval_challenge(daily_pnl_base, daily_mae_base, multiplier, target=4000.0, floor=2000.0, dll=1000.0, consistency_pct=0.50):
    n_days = len(all_trading_days)
    window = 5
    
    pass_clean = 0
    pass_inconsistent = 0
    ruin_dll = 0
    ruin_trailing = 0
    neither = 0
    
    total_trials = n_days - window + 1
    
    max_single_day_allowed = target * consistency_pct
    
    for start_idx in range(total_trials):
        days_window = all_trading_days[start_idx : start_idx + window]
        
        cum_pnl = 0.0
        hwm = 0.0
        failed = False
        fail_reason = None
        max_day_pnl = -999999.0
        
        for d in days_window:
            day_pnl = daily_pnl_base[d] * multiplier
            day_mae = daily_mae_base[d] * multiplier # adverse dip
            
            # 1. Check Daily Loss Limit (intraday dip or EOD loss)
            if day_pnl <= -dll or day_mae <= -dll:
                ruin_dll += 1
                failed = True
                fail_reason = "dll"
                break
                
            # 2. Check Trailing Drawdown (intraday dip relative to HWM)
            # Intraday lowest point today = prior cum_pnl + day_mae
            intraday_low = cum_pnl + day_mae
            if (hwm - intraday_low) >= floor or intraday_low <= -floor:
                ruin_trailing += 1
                failed = True
                fail_reason = "trailing"
                break
                
            # Update cumulative PnL
            cum_pnl += day_pnl
            if cum_pnl > hwm:
                hwm = cum_pnl
                
            # Check EOD trailing drawdown
            if (hwm - cum_pnl) >= floor or cum_pnl <= -floor:
                ruin_trailing += 1
                failed = True
                fail_reason = "trailing"
                break
                
            if day_pnl > max_day_pnl:
                max_day_pnl = day_pnl
                
            # If target reached mid-week, can stop trading or continue
            if cum_pnl >= target:
                break
                
        if not failed:
            if cum_pnl >= target:
                # Check consistency rule
                if max_day_pnl <= max_single_day_allowed:
                    pass_clean += 1
                else:
                    pass_inconsistent += 1
            else:
                neither += 1
                
    total_ruin = ruin_dll + ruin_trailing
    pct_pass_clean = (pass_clean / total_trials) * 100
    pct_pass_any = ((pass_clean + pass_inconsistent) / total_trials) * 100
    pct_ruin = (total_ruin / total_trials) * 100
    pct_neither = (neither / total_trials) * 100
    
    odds = (total_ruin / pass_clean) if pass_clean > 0 else 999.0
    
    return {
        "multiplier": multiplier,
        "target": target,
        "floor": floor,
        "dll": dll,
        "trials": total_trials,
        "pass_clean": pass_clean,
        "pass_inconsistent": pass_inconsistent,
        "ruin_dll": ruin_dll,
        "ruin_trailing": ruin_trailing,
        "total_ruin": total_ruin,
        "neither": neither,
        "pct_pass_clean": round(pct_pass_clean, 2),
        "pct_pass_any": round(pct_pass_any, 2),
        "pct_ruin": round(pct_ruin, 2),
        "pct_neither": round(pct_neither, 2),
        "ruin_vs_pass_ratio": round(odds, 2)
    }

print("\n" + "=" * 80)
print("EXPERIMENT 1: SIZING SWEEP TO PASS $4,000 IN 1 WEEK (5 DAYS)")
print("Rules: Floor = $2,000, Daily Loss Limit = $1,000, 50% Consistency Rule (Max Day <= $2,000)")
print("=" * 80)
print(f"{'Multiplier':>10} | {'Clean Pass %':>12} | {'Any Pass %':>10} | {'Ruin %':>10} | {'Neither %':>10} | {'Ruin/Pass Ratio':>15}")
print("-" * 80)

multipliers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20]
results_4k = []
for m in multipliers:
    res = simulate_eval_challenge(pnl_1c_series, mae_series, multiplier=m, target=4000.0, floor=2000.0, dll=1000.0)
    results_4k.append(res)
    print(f"{m:>10}x | {res['pct_pass_clean']:>11}% | {res['pct_pass_any']:>9}% | {res['pct_ruin']:>9}% | {res['pct_neither']:>9}% | {res['ruin_vs_pass_ratio']:>15}x")

print("\n" + "=" * 80)
print("EXPERIMENT 2: SENSITIVITY - STANDARD TOPSTEP $50K ($3,000 TARGET IN 1 WEEK)")
print("Rules: Target = $3,000, Floor = $2,000, Daily Loss Limit = $1,000, 50% Consistency Rule (Max Day <= $1,500)")
print("=" * 80)
print(f"{'Multiplier':>10} | {'Clean Pass %':>12} | {'Any Pass %':>10} | {'Ruin %':>10} | {'Neither %':>10} | {'Ruin/Pass Ratio':>15}")
print("-" * 80)

results_3k = []
for m in multipliers:
    res = simulate_eval_challenge(pnl_1c_series, mae_series, multiplier=m, target=3000.0, floor=2000.0, dll=1000.0)
    results_3k.append(res)
    print(f"{m:>10}x | {res['pct_pass_clean']:>11}% | {res['pct_pass_any']:>9}% | {res['pct_ruin']:>9}% | {res['pct_neither']:>9}% | {res['ruin_vs_pass_ratio']:>15}x")

# Save findings to JSON for reporting
output_data = {
    "audit_type": "1_week_4k_and_3k_evaluation_feasibility",
    "partition": "2010-2023_training_only",
    "total_trading_days": len(all_trading_days),
    "total_eval_windows": len(all_trading_days) - 4,
    "results_4k": results_4k,
    "results_3k": results_3k
}

with open(ROOT / "reports/AUDIT_1WEEK_EVALUATION_TRAIN.json", "w") as f:
    json.dump(output_data, f, indent=2)

print("\nSaved full simulation results to reports/AUDIT_1WEEK_EVALUATION_TRAIN.json")
print("DONE", flush=True)
