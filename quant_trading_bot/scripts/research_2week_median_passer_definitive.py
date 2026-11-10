"""Definitive Research & Optimization: Achieving a 2-Week (10 Trading Days) Median Evaluation Pass.
Strictly on 14-Year Training Split (2010-2023). Zero exposure to Validation or Blind Test.

Prop Firm Evaluation Constraints:
- Profit Target: +$4,000
- Trailing Maximum Drawdown: -$2,000 (locks at starting balance once HWM reaches +$2,000)
- Daily Loss Limit: -$1,000
- 50% Consistency Rule: Single day profit must not exceed $2,000 (capped at +$1,750)
- CME Micro Friction: $0.61 commission/side, 1.75 tick spread, 1.0 tick slippage = 1.30 pts roundtrip

Evaluates:
1. All-Regimes Sprint: How to push median days to 10 across 14 years.
2. Velocity-Triggered Sprint: Launching evaluation when market velocity is active (VIX >= 18).
3. Sizing Architecture: Cushion-Staged (6 -> 10 MNQ, 8 -> 12 MNQ, 8 -> 14 MNQ).
4. Full Trade Set: Overnight Reopen Dip + Morning Crabel + Midday/Afternoon Trend.
"""
import sys, json, os
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

# 1. Load Intraday Trades (dplus_4_pilot)
src_dplus = (ROOT / "scripts/dplus_4_pilot.py").read_text().split("\nout = {}")[0]
ns_dplus = {"__file__": str(ROOT / "scripts/dplus_4_pilot.py")}
exec(src_dplus, ns_dplus)
base_intraday = ns_dplus["base"]

# 2. Load VIX
vix_path = ROOT / "data/external/VIX_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df["date"] = pd.to_datetime(vix_df["DATE"]).dt.date
vix_dict = dict(zip(vix_df["date"], vix_df["CLOSE"]))

# 3. Load Overnight Trades from replication
src_rep = (ROOT / "scripts/replicate_antigravity_d_plus.py").read_text()
ns_rep = {"__file__": str(ROOT / "scripts/replicate_antigravity_d_plus.py")}
exec(src_rep, ns_rep)
p_on = ns_rep["p_on"]
skip_night = ns_rep["skip_night"]
mn = ns_rep["mn"]
next_day_fn = ns_rep["ns"]["next_day"]
low_open_dict = ns_rep["ns"]["low_open"]

# 4. Consolidate all trades chronologically by day
trades_by_day = {}

# Overnight Trades
for (nk, p), sk in zip(p_on.items(), skip_night):
    if sk: continue
    ex_day = next_day_fn(nk)
    e = float(mn.at[nk, "e1805"])
    lo = min(float(mn.at[nk, "low_night"]), float(low_open_dict.get(ex_day, np.inf)))
    mae_pts = (lo - e)
    trades_by_day.setdefault(ex_day, []).append({
        "order": 0, # executed first at 09:45
        "type": "overnight",
        "net_1c": float(p),
        "mae_1c": mae_pts * 2.0,
        "sleeve": "OVERNIGHT"
    })

# Intraday Trades
for t in base_intraday:
    t_day = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
    cont = t.get("cont", False)
    sleeve = t["sleeve"]
    is_crabel = sleeve.startswith("AG_CRABEL")
    if is_crabel and not cont: 
        continue # filter non-continuation fades
        
    net_1c = float(t["net"])
    stop_r = float(t.get("stop_risk", 34.6 * 2.0))
    mae_1c = -min(stop_r, 70.0)
    
    order = 1 if is_crabel else 2
    trades_by_day.setdefault(t_day, []).append({
        "order": order,
        "type": "intraday",
        "net_1c": net_1c,
        "mae_1c": mae_1c,
        "sleeve": sleeve,
        "is_crabel": is_crabel
    })

# Sort trades within each day chronologically
for d in trades_by_day:
    trades_by_day[d].sort(key=lambda x: x["order"])

# Build continuous calendar of trading days (from 2010 to 2023)
trade_days_with_activity = sorted(list(trades_by_day.keys()))
print(f"Total days with trade signals: {len(trade_days_with_activity)}")

def run_evaluation_sprint(
    stg1_intra_sz=6,
    stg1_on_sz=1,
    stg2_intra_sz=10,
    stg2_on_sz=2,
    stg2_threshold=1000.0,
    min_vix_start=0.0,
    daily_lock=1750.0,
    daily_stop=380.0,
    on_stop_pts=30.0,
    runner_bonus_pts=0.0,
    max_days=60
):
    total_eligible = 0
    passed = 0
    ruined = 0
    timeout = 0
    pass_days = []
    max_dds_on_pass = []
    
    n_days = len(trade_days_with_activity)
    
    for i in range(n_days - max_days):
        start_day = trade_days_with_activity[i]
        start_vix = vix_dict.get(start_day, 18.0)
        
        # Velocity Sprint Trigger: Start evaluation only when market has sufficient volatility
        if start_vix < min_vix_start:
            continue
            
        total_eligible += 1
        cum = 0.0
        hwm = 0.0
        floor = -2000.0
        busted = False
        pass_run = False
        max_d_pnl = -9999.0
        peak_dd = 0.0
        
        for step in range(max_days):
            d = trade_days_with_activity[i + step]
            trades = trades_by_day.get(d, [])
            if not trades:
                continue
                
            in_stg2 = (cum >= stg2_threshold)
            i_sz = stg2_intra_sz if in_stg2 else stg1_intra_sz
            o_sz = stg2_on_sz if in_stg2 else stg1_on_sz
            
            day_pnl = 0.0
            day_mae = 0.0
            
            for tr in trades:
                if tr["type"] == "overnight":
                    sz = o_sz
                    mae = max(tr["mae_1c"], -on_stop_pts * 2.0) * sz
                    pnl = tr["net_1c"] * sz
                    if tr["mae_1c"] < -on_stop_pts * 2.0:
                        pnl = -on_stop_pts * 2.0 * sz
                else:
                    sz = i_sz
                    mae = tr["mae_1c"] * sz
                    pnl = tr["net_1c"] * sz
                    # If strong trend day and runner bonus configured
                    if runner_bonus_pts > 0 and tr["net_1c"] > 40.0:
                        # Capture extra runner points
                        pnl += (runner_bonus_pts * 0.5 * 2.0 * sz)
                    
                if (day_pnl + mae) < day_mae:
                    day_mae = day_pnl + mae
                day_pnl += pnl
                
                # Daily circuit breakers
                if day_pnl >= daily_lock or day_pnl <= -daily_stop:
                    break
                    
            # Check Daily Loss Limit (-$1,000)
            if day_pnl <= -1000.0 or day_mae <= -1000.0:
                busted = True
                break
                
            # Check Trailing Drawdown Floor
            if (cum + day_mae) <= floor:
                busted = True
                break
                
            cum += day_pnl
            current_dd = hwm - cum
            if current_dd > peak_dd:
                peak_dd = current_dd
                
            if cum > hwm:
                hwm = cum
                floor = 0.0 if hwm >= 2000.0 else -2000.0 + hwm
                
            if cum <= floor:
                busted = True
                break
                
            if day_pnl > max_d_pnl:
                max_d_pnl = day_pnl
                
            # Pass Condition: Target +$4,000 + 50% consistency rule
            if cum >= 4000.0 and max_d_pnl <= 2000.0:
                pass_run = True
                passed += 1
                pass_days.append(step + 1)
                max_dds_on_pass.append(peak_dd)
                break
                
        if busted and not pass_run:
            ruined += 1
        elif not pass_run and not busted:
            timeout += 1
            
    p_arr = np.array(pass_days) if pass_days else np.array([0])
    dd_arr = np.array(max_dds_on_pass) if max_dds_on_pass else np.array([0])
    
    pass_pct = passed / max(1, total_eligible) * 100
    ruin_pct = ruined / max(1, total_eligible) * 100
    res_pass_pct = passed / max(1, passed + ruined) * 100
    med_days = float(np.median(p_arr)) if passed > 0 else 999.0
    p25_days = float(np.percentile(p_arr, 25)) if passed > 0 else 999.0
    p10_days = float(np.percentile(p_arr, 10)) if passed > 0 else 999.0
    min_days = int(p_arr.min()) if passed > 0 else 999
    avg_dd = float(dd_arr.mean()) if passed > 0 else 999.0
    
    return {
        "eligible_trials": total_eligible,
        "passed": passed,
        "ruined": ruined,
        "timeout": timeout,
        "pass_pct": round(pass_pct, 1),
        "ruin_pct": round(ruin_pct, 1),
        "res_pass_pct": round(res_pass_pct, 1),
        "med_days": round(med_days, 1),
        "med_weeks": round(med_days / 5.0, 1),
        "p25_days": round(p25_days, 1),
        "p10_days": round(p10_days, 1),
        "min_days": min_days,
        "avg_dd": round(avg_dd, 2)
    }

print("\n" + "="*85)
print("COMPREHENSIVE OPTIMIZATION: 2-WEEK (10 TRADING DAYS) MEDIAN PASSER")
print("="*85)

test_matrix = [
    # Baseline
    ("1. Baseline Cushion-Staged (6c -> 10c, all regimes)", 
     dict(stg1_intra_sz=6, stg1_on_sz=1, stg2_intra_sz=10, stg2_on_sz=2, stg2_threshold=1000.0, min_vix_start=0.0)),
     
    # Faster Stage 2 Trigger
    ("2. Fast Cushion (6c -> 10c, cushion=$800, all regimes)", 
     dict(stg1_intra_sz=6, stg1_on_sz=1, stg2_intra_sz=10, stg2_on_sz=2, stg2_threshold=800.0, min_vix_start=0.0)),

    # Increased Velocity: 8c -> 12c (All regimes)
    ("3. High-Velocity Sizing (8c -> 12c, cushion=$1000, all regimes)", 
     dict(stg1_intra_sz=8, stg1_on_sz=2, stg2_intra_sz=12, stg2_on_sz=2, stg2_threshold=1000.0, min_vix_start=0.0)),

    # Free-roll Runner Scaling (8c -> 12c + Runner Bonus)
    ("4. Free-Roll Runner Expansion (8c -> 12c, +30pt runner, all regimes)", 
     dict(stg1_intra_sz=8, stg1_on_sz=2, stg2_intra_sz=12, stg2_on_sz=2, stg2_threshold=1000.0, runner_bonus_pts=30.0, min_vix_start=0.0)),

    # Active Volatility Trigger (VIX >= 18)
    ("5. Active Market Sprint (VIX >= 18, 6c -> 10c)", 
     dict(stg1_intra_sz=6, stg1_on_sz=1, stg2_intra_sz=10, stg2_on_sz=2, stg2_threshold=1000.0, min_vix_start=18.0)),

    # Active Volatility Trigger (VIX >= 18, 8c -> 12c)
    ("6. Active Market Sprint (VIX >= 18, 8c -> 12c)", 
     dict(stg1_intra_sz=8, stg1_on_sz=2, stg2_intra_sz=12, stg2_on_sz=2, stg2_threshold=1000.0, min_vix_start=18.0)),

    # High Volatility Velocity Sprint (VIX >= 20, 8c -> 12c)
    ("7. High Volatility Sprint (VIX >= 20, 8c -> 12c)", 
     dict(stg1_intra_sz=8, stg1_on_sz=2, stg2_intra_sz=12, stg2_on_sz=2, stg2_threshold=1000.0, min_vix_start=20.0)),

    # High Volatility Sprint with Runner (VIX >= 20, 8c -> 14c)
    ("8. High Vol Sprint + Runner (VIX >= 20, 8c -> 14c, run bonus=30pt)", 
     dict(stg1_intra_sz=8, stg1_on_sz=2, stg2_intra_sz=14, stg2_on_sz=2, stg2_threshold=1000.0, runner_bonus_pts=30.0, min_vix_start=20.0)),

    # Extreme Volatility Sprint (VIX >= 22, 8c -> 12c)
    ("9. Extreme Vol Sprint (VIX >= 22, 8c -> 12c)", 
     dict(stg1_intra_sz=8, stg1_on_sz=2, stg2_intra_sz=12, stg2_on_sz=2, stg2_threshold=1000.0, min_vix_start=22.0)),
]

results = []
for label, kwargs in test_matrix:
    res = run_evaluation_sprint(**kwargs)
    res["config"] = label
    results.append(res)
    print(f"{label:65s} | MEDIAN: {res['med_days']:4.1f}d ({res['med_weeks']:3.1f}w) | p25: {res['p25_days']:4.1f}d | Min: {res['min_days']}d | Pass: {res['pass_pct']:5.1f}% | Ruin: {res['ruin_pct']:4.1f}% | Resolved: {res['res_pass_pct']:5.1f}% | AvgDD: ${res['avg_dd']:6.2f} (N={res['eligible_trials']})")

out_path = ROOT / "reports/DEFINITIVE_2WEEK_MEDIAN_PASSER_RESULTS.json"
with open(out_path, "w") as f:
    json.dump(results, f, indent=2)

print("\n" + "="*85)
print(f"[SUCCESS] Definitive optimization complete. Results saved to: {out_path.name}")
print("="*85)
