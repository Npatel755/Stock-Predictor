"""Multi-Sleeve Fast Evaluation Passer Simulation: Target 2-3 Weeks (Max 1 Month / 10-21 Sessions).
TRAINING SPLIT (2010-2023) ONLY.
Strict Methodological Protocol:
- Zero touch of Validation (2024-2025) or Blind Test (2026).
- Sourced from 2,356 multi-sleeve trades cached in data/processed/multi_sleeve_trades_train.parquet.
- 4 High-Expectancy Sleeves: Crabel 15m Morning, Overnight Dip v2 (0.55% stop), TRD60 Intraday Trend, MES30 Trend.
- Realized day stop ($400 max day loss to protect -$1,000 DLL).
- Honest accounting across ALL sliding starting sessions in the 14-year training split.
- Reporting P(Funded <= 10 sessions), P(Funded <= 15 sessions), P(Funded <= 21 sessions).
- Resets counted, reset fees estimated ($49 Topstep reset).
- Side-by-side comparison with Matched Zero-Edge Negative Control.
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")

# Load cached trades
trades_df = pd.read_parquet(ROOT / "data/processed/multi_sleeve_trades_train.parquet")

# Filter out weak PM trend, focus on the 4 proven sleeves
CORE_SLEEVES = ["AG_CRABEL15_D_1c", "OVERNIGHT_DIP", "AG_TRD60_D_1c", "AG_MES_TRD30_D_1c"]
trades_df = trades_df[trades_df.sleeve.isin(CORE_SLEEVES)].copy()
trades_df["tout"] = pd.to_datetime(trades_df.tout_str, utc=True)
trades_df["tin"] = pd.to_datetime(trades_df.tin_str, utc=True)
trades_df["date"] = trades_df.tout.dt.tz_convert("America/New_York").dt.date

# Sort chronologically
trades_df = trades_df.sort_values("tin").reset_index(drop=True)

# Build zero-edge control by subtracting sleeve mean net
sleeve_means = trades_df.groupby("sleeve")["net_today"].mean().to_dict()
trades_df["net_zero"] = trades_df.apply(lambda r: r["net_today"] - sleeve_means[r["sleeve"]], axis=1)

print(f"Loaded {len(trades_df)} core multi-sleeve trades across {trades_df.date.nunique()} unique sessions.")
print("Sleeve mean expectancies per 1-micro trade:")
for sl, m in sleeve_means.items():
    print(f"  {sl:20s}: +${m:.2f}")

# Group trades by date
days_list = sorted(trades_df.date.unique())
trades_by_date = {d: trades_df[trades_df.date == d] for d in days_list}

STATIC_FLOOR = -2000.0
DLL_LIMIT = -1000.0
DAILY_LOCK = 1500.0

def simulate_eval(
    sizing_map,      # dict of sleeve -> contracts, or int/float multiplier
    reset_thr,       # reset threshold in cumulative equity (e.g. -$400)
    day_stop=400.0,  # stop taking intraday trades if realized day loss exceeds this
    is_zero_edge=False,
    dynamic=False,   # dynamic laddering based on balance
    max_sessions=21
):
    n_starts = len(days_list) - max_sessions
    passed_10 = 0
    passed_15 = 0
    passed_21 = 0
    resets_paid_list = []
    days_to_pass_list = []
    worst_day_loss = 0.0
    max_attempt_dd = 0.0

    net_col = "net_zero" if is_zero_edge else "net_today"

    for s in range(n_starts):
        used = 0
        resets = 0
        funded = False

        while used < max_sessions:
            cum = 0.0
            hwm = 0.0
            attempt_outcome = "open"
            step = 0
            attempt_len = max_sessions - used

            for step in range(attempt_len):
                d = days_list[s + used + step]
                day_trades = trades_by_date[d]

                day_pnl = 0.0
                day_mae = 0.0

                for t in day_trades.itertuples():
                    sl = t.sleeve
                    
                    # Determine sizing
                    if dynamic:
                        if cum >= 2500.0:
                            sz = 4.0
                        elif cum >= 1000.0:
                            sz = 3.0
                        else:
                            sz = 2.0
                    elif isinstance(sizing_map, dict):
                        sz = sizing_map.get(sl, 2.0)
                    else:
                        sz = float(sizing_map)

                    # Intra-day stop protection
                    if t.sleeve != "OVERNIGHT_DIP" and day_pnl <= -day_stop:
                        continue # Skip trade if day stop reached

                    t_pnl = getattr(t, net_col) * sz
                    day_pnl += t_pnl

                if day_pnl < worst_day_loss:
                    worst_day_loss = day_pnl

                # Topstep Daily Loss Limit Check
                if day_pnl <= DLL_LIMIT:
                    attempt_outcome = "busted"; break

                # Consistency Rule / Daily Lock
                capped_pnl = min(day_pnl, DAILY_LOCK)
                cum += capped_pnl

                # Track drawdown
                hwm = max(hwm, cum)
                dd = hwm - cum
                if dd > max_attempt_dd:
                    max_attempt_dd = dd

                # Floor check
                if cum <= STATIC_FLOOR:
                    attempt_outcome = "busted"; break

                # Target check
                if cum >= 4000.0:
                    attempt_outcome = "passed"; break

                # Strategic Reset threshold check
                if cum <= reset_thr:
                    attempt_outcome = "reset"; break

            sess_used = step + 1
            used += sess_used

            if attempt_outcome == "passed":
                funded = True
                days_to_pass_list.append(used)
                if used <= 10: passed_10 += 1
                if used <= 15: passed_15 += 1
                if used <= 21: passed_21 += 1
                resets_paid_list.append(resets)
                break
            elif attempt_outcome in ("reset", "busted"):
                resets += 1
            else: # Ran out of sessions
                break

    p10_pct = passed_10 / n_starts * 100
    p15_pct = passed_15 / n_starts * 100
    p21_pct = passed_21 / n_starts * 100
    avg_resets = np.mean(resets_paid_list) if resets_paid_list else 0.0
    med_days = np.median(days_to_pass_list) if days_to_pass_list else 999.0

    return {
        "p10_pct": round(p10_pct, 1),
        "p15_pct": round(p15_pct, 1),
        "p21_pct": round(p21_pct, 1),
        "avg_resets_paid": round(avg_resets, 1),
        "median_sessions": round(med_days, 1),
        "worst_day_loss": round(worst_day_loss, 1),
        "max_attempt_dd": round(max_attempt_dd, 1),
        "n_passed": passed_21
    }

print("\n" + "="*105)
print(f"{'CONFIGURATION':40s} || {'REAL 2wk':8s} {'REAL 3wk':8s} {'REAL 1mo':8s} || {'ZERO 1mo':8s} {'EDGE BOOST':10s} || {'RESETS':6s} {'COST':8s}")
print("="*105)

configs = [
    # Name, sizing, reset_thr, day_stop, dynamic
    ("Conservative 2c Base (Reset @ -$400)", 2.0, -400.0, 400.0, False),
    ("Balanced 3c Base (Reset @ -$500)", 3.0, -500.0, 450.0, False),
    ("Sprint 4c Base (Reset @ -$600)", 4.0, -600.0, 500.0, False),
    ("Conviction Sizing (Crabel 4c, Night 3c, MES 3c, TRD 2c | Reset -$500)",
     {"AG_CRABEL15_D_1c": 4.0, "OVERNIGHT_DIP": 3.0, "AG_MES_TRD30_D_1c": 3.0, "AG_TRD60_D_1c": 2.0},
     -500.0, 500.0, False),
    ("Dynamic Ladder 2c->3c->4c (Reset @ -$450)", 2.0, -450.0, 450.0, True),
    ("Aggressive Dynamic 3c->4c->5c (Reset @ -$600)", 3.0, -600.0, 500.0, True),
]

summary_results = []
for name, sz, rthr, dstop, dyn in configs:
    real = simulate_eval(sz, rthr, day_stop=dstop, is_zero_edge=False, dynamic=dyn)
    zero = simulate_eval(sz, rthr, day_stop=dstop, is_zero_edge=True, dynamic=dyn)

    edge_boost = real["p21_pct"] - zero["p21_pct"]
    est_cost = (real["avg_resets_paid"] * 49.0) + 49.0

    print(f"{name:40s} || {real['p10_pct']:5.1f}%   {real['p15_pct']:5.1f}%   {real['p21_pct']:5.1f}%   || {zero['p21_pct']:5.1f}%   +{edge_boost:5.1f}%     || {real['avg_resets_paid']:4.1f}   ${est_cost:5.0f}")
    summary_results.append({
        "name": name,
        "real": real,
        "zero_edge": zero,
        "edge_boost": round(edge_boost, 1),
        "est_cost": round(est_cost, 0)
    })

out_json = ROOT / "reports/RESEARCH_MULTI_SLEEVE_FAST_PASSER_TRAINING.json"
with open(out_json, "w") as f:
    json.dump(summary_results, f, indent=2)
print(f"\nSaved detailed simulation results to {out_json}")
