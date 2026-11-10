"""Research: 2-Week Median Passer Strategy Optimization (2010-2023 Training Split).
Goal: Find the institutional parameter set that achieves a MEDIAN time-to-pass of <= 10 trading days (2 weeks)
while strictly honoring:
- Profit Target: +$4,000
- Trailing Drawdown Floor: -$2,000 (locks at starting balance once HWM reaches +$2,000)
- Daily Loss Limit: -$1,000
- 50% Consistency Rule: No single day >= $2,000 (daily profit lock at +$1,750)
- Cost Model: $0.61 commission/side, 1.75 tick spread, 1.0 tick slippage (1.30 pts roundtrip)
"""
import sys, json, os
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

# Load trades from dplus_4_pilot
src_dplus = (ROOT / "scripts/dplus_4_pilot.py").read_text().split("\nout = {}")[0]
ns_dplus = {"__file__": str(ROOT / "scripts/dplus_4_pilot.py")}
exec(src_dplus, ns_dplus)
base_intraday = ns_dplus["base"]

# Load VIX
vix_path = ROOT / "data/external/VIX_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df["date"] = pd.to_datetime(vix_df["DATE"]).dt.date
vix_dict = dict(zip(vix_df["date"], vix_df["CLOSE"]))

# Map all intraday trades with detailed PnL and runner potential
trades_by_day = {}
for t in base_intraday:
    t_day = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
    vix = vix_dict.get(t_day, 18.0)
    cont = t.get("cont", False)
    sleeve = t["sleeve"]
    is_crabel = sleeve.startswith("AG_CRABEL")
    
    # In dplus_4, filter out Crabel non-continuation fades
    if is_crabel and not cont:
        continue
        
    net_1c = float(t["net"])
    # Standard stop loss risk is 34.6 pts = $69.20 at 1 contract
    stop_risk_1c = float(t.get("stop_risk", 34.6 * 2.0))
    mae_1c = -min(stop_risk_1c, 70.0)
    
    trades_by_day.setdefault(t_day, []).append({
        "net_1c": net_1c,
        "mae_1c": mae_1c,
        "sleeve": sleeve,
        "is_crabel": is_crabel,
        "entry_ts": t["entry_ts"]
    })

all_days = sorted(list(trades_by_day.keys()))
print(f"Total trade days in 14-year training split: {len(all_days)}")

def evaluate_fast_passer(
    stg1_size=6,
    stg2_size=10,
    stg2_threshold=1000.0,
    banker_pts=28.0,
    runner_pts=100.0,
    daily_lock=1750.0,
    daily_stop=400.0,
    max_eval_days=90
):
    total_starts = len(all_days) - max_eval_days
    passed = 0
    ruined = 0
    pass_days = []
    max_dds_on_pass = []
    
    for i in range(total_starts):
        cum = 0.0
        hwm = 0.0
        floor = -2000.0
        busted = False
        pass_run = False
        max_d_pnl = -9999.0
        peak_dd = 0.0
        
        for step in range(max_eval_days):
            d = all_days[i + step]
            vix = vix_dict.get(d, 18.0)
            if vix < 15.0 and d not in trades_by_day:
                continue
                
            trades = trades_by_day.get(d, [])
            if not trades:
                continue
                
            # Dynamic Staging
            current_size = stg2_size if cum >= stg2_threshold else stg1_size
            
            day_pnl = 0.0
            day_mae = 0.0
            
            for tr in trades:
                sz = current_size
                pnl = tr["net_1c"] * sz
                mae = tr["mae_1c"] * sz
                
                # Check runner expansion on trend days
                if tr["net_1c"] > 40.0:
                    # Model scale out: 50% at banker_pts, 50% at runner_pts
                    # Net 1c is already realistic with friction
                    pts_captured = tr["net_1c"] / 2.0
                    if pts_captured > 50.0:
                        # Big trend day
                        pnl = min(daily_lock, (banker_pts * 0.5 + runner_pts * 0.5) * 2.0 * sz - (1.30 * 2.0 * sz))
                        
                if (day_pnl + mae) < day_mae:
                    day_mae = day_pnl + mae
                    
                day_pnl += pnl
                
                # Circuit breakers
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
                
            # Pass Target + 50% Consistency Rule Compliance
            if cum >= 4000.0 and max_d_pnl <= 2000.0:
                pass_run = True
                passed += 1
                pass_days.append(step + 1)
                max_dds_on_pass.append(peak_dd)
                break
                
        if busted and not pass_run:
            ruined += 1
            
    p_arr = np.array(pass_days) if pass_days else np.array([0])
    dd_arr = np.array(max_dds_on_pass) if max_dds_on_pass else np.array([0])
    
    pass_pct = passed / total_starts * 100
    ruin_pct = ruined / total_starts * 100
    res_pass_pct = passed / max(1, passed + ruined) * 100
    med_days = float(np.median(p_arr)) if passed > 0 else 999.0
    p25_days = float(np.percentile(p_arr, 25)) if passed > 0 else 999.0
    p10_days = float(np.percentile(p_arr, 10)) if passed > 0 else 999.0
    min_days = int(p_arr.min()) if passed > 0 else 999
    avg_dd = float(dd_arr.mean()) if passed > 0 else 999.0
    
    return {
        "pass_pct": round(pass_pct, 1),
        "ruin_pct": round(ruin_pct, 1),
        "res_pass_pct": round(res_pass_pct, 1),
        "med_days": round(med_days, 1),
        "p25_days": round(p25_days, 1),
        "p10_days": round(p10_days, 1),
        "min_days": min_days,
        "avg_dd": round(avg_dd, 2)
    }

print("\n--- GRID SEARCH: OPTIMIZING FOR MEDIAN <= 10 TRADING DAYS (2 WEEKS) ---")
grid = [
    # Baseline
    ("Baseline Cushion-Staged (6 -> 10 MNQ, thr=1200)", dict(stg1_size=6, stg2_size=10, stg2_threshold=1200.0, runner_pts=100.0)),
    # Earlier Stage 2 threshold
    ("Fast Cushion (6 -> 10 MNQ, thr=800)", dict(stg1_size=6, stg2_size=10, stg2_threshold=800.0, runner_pts=100.0)),
    # Earlier Stage 2 + 12 MNQ finisher
    ("Sprint Finisher (6 -> 12 MNQ, thr=1000, run=110pt)", dict(stg1_size=6, stg2_size=12, stg2_threshold=1000.0, runner_pts=110.0)),
    # Aggressive Stage 1 (8 MNQ) -> Stage 2 (12 MNQ)
    ("High-Velocity Sprint (8 -> 12 MNQ, thr=1000, run=100pt)", dict(stg1_size=8, stg2_size=12, stg2_threshold=1000.0, runner_pts=100.0)),
    # High-Velocity Sprint (8 -> 14 MNQ, thr=1200, run=110pt)
    ("Maximum Velocity (8 -> 14 MNQ, thr=1200, run=110pt)", dict(stg1_size=8, stg2_size=14, stg2_threshold=1200.0, runner_pts=110.0)),
    # Aggressive 8 MNQ with strict 300 stop
    ("Fast Conservative (8 -> 10 MNQ, thr=800, stop=350)", dict(stg1_size=8, stg2_size=10, stg2_threshold=800.0, runner_pts=100.0, daily_stop=350.0)),
    # Free-roll sprint with 120 pt runner
    ("Free-Roll 2-Week Sprint (8 -> 12 MNQ, thr=800, run=120pt)", dict(stg1_size=8, stg2_size=12, stg2_threshold=800.0, runner_pts=120.0)),
    # 10 MNQ Stage 1 with 14 MNQ Stage 2
    ("Extreme 2-Week Sprint (10 -> 14 MNQ, thr=1000, run=100pt)", dict(stg1_size=10, stg2_size=14, stg2_threshold=1000.0, runner_pts=100.0)),
]

results = []
for label, kwargs in grid:
    res = evaluate_fast_passer(**kwargs)
    res["config"] = label
    results.append(res)
    print(f"{label:58s} | Med: {res['med_days']:4.1f}d ({res['med_days']/5:.1f}wk) | p25: {res['p25_days']:4.1f}d | Min: {res['min_days']}d | Pass: {res['pass_pct']:5.1f}% | Ruin: {res['ruin_pct']:4.1f}% | Resolved: {res['res_pass_pct']:5.1f}% | AvgDD: ${res['avg_dd']:6.2f}")

with open(ROOT / "reports/TWO_WEEK_MEDIAN_OPTIMIZATION_RESULTS.json", "w") as f:
    json.dump(results, f, indent=2)

print("\n[SUCCESS] 2-Week optimization completed and saved.")
