"""2-Week Breakthrough Optimization: Reaching <= 10 Trading Days Median Pass.
Strictly on 14-Year Training Split (2010-2023).

Testing:
1. High-Frequency Multi-Session Ensemble (Overnight + Crabel + 30m Trend + 60m Trend)
2. Cushion-Staged Velocity Scaling (Stage 1: 6c -> Stage 2: 8c/10c -> Stage 3: 12c)
3. Free-roll Runner Capture (+25pt banker, +80-100pt runner)
4. Evaluation Timing: All-Regimes vs Active-Regimes (VIX >= 18, 20)
5. Strict Topstep/Apex Evaluation rules ($4,000 target, $2,000 trailing floor, $1,000 DLL, 50% consistency rule, $1.30 CME micro friction).
"""
import sys, json, os
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

# Load Intraday
src_dplus = (ROOT / "scripts/dplus_4_pilot.py").read_text().split("\nout = {}")[0]
ns_dplus = {"__file__": str(ROOT / "scripts/dplus_4_pilot.py")}
exec(src_dplus, ns_dplus)
base_intraday = ns_dplus["base"]

# Load VIX
vix_path = ROOT / "data/external/VIX_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df["date"] = pd.to_datetime(vix_df["DATE"]).dt.date
vix_dict = dict(zip(vix_df["date"], vix_df["CLOSE"]))

# Load Cached Overnight Trades
with open(ROOT / "data/processed/overnight_trades_train.json") as f:
    on_trades_data = json.load(f)

# Build day-by-day event sequence
trades_by_day = {}

# Overnight Trades
for tr in on_trades_data:
    ex_day = pd.to_datetime(tr["exit_day"]).date()
    trades_by_day.setdefault(ex_day, []).append({
        "order": 0,
        "type": "overnight",
        "net_1c": float(tr["pnl_1c"]),
        "mae_1c": float(tr["mae_1c"]),
        "pts": float(tr["pnl_1c"]) / 2.0,
        "sleeve": "OVERNIGHT"
    })

# Intraday Trades
for t in base_intraday:
    t_day = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
    cont = t.get("cont", False)
    sleeve = t["sleeve"]
    is_crabel = sleeve.startswith("AG_CRABEL")
    if is_crabel and not cont: 
        continue
        
    net_1c = float(t["net"])
    pts_1c = net_1c / 2.0
    stop_r = float(t.get("stop_risk", 34.6 * 2.0))
    mae_1c = -min(stop_r, 70.0)
    
    order = 1 if is_crabel else 2
    trades_by_day.setdefault(t_day, []).append({
        "order": order,
        "type": "intraday",
        "net_1c": net_1c,
        "mae_1c": mae_1c,
        "pts": pts_1c,
        "sleeve": sleeve,
        "is_crabel": is_crabel
    })

for d in trades_by_day:
    trades_by_day[d].sort(key=lambda x: x["order"])

all_days = sorted(list(trades_by_day.keys()))
print(f"Total days with trades loaded: {len(all_days)}")

def evaluate_sprint_engine(
    stg1_c_sz=6,
    stg1_t_sz=3,
    stg1_o_sz=1,
    stg2_c_sz=10,
    stg2_t_sz=5,
    stg2_o_sz=2,
    stg3_c_sz=12,
    stg3_t_sz=6,
    stg3_o_sz=2,
    stg2_thresh=800.0,
    stg3_thresh=2000.0,
    daily_lock=1750.0,
    daily_stop=380.0,
    banker_pts=25.0,
    runner_pts=90.0,
    min_vix=0.0,
    eval_horizon_days=60
):
    total_starts = len(all_days) - eval_horizon_days
    eligible = 0
    passed = 0
    ruined = 0
    timeout = 0
    pass_days = []
    max_dds = []
    
    for i in range(total_starts):
        start_day = all_days[i]
        start_vix = vix_dict.get(start_day, 18.0)
        
        if start_vix < min_vix:
            continue
            
        eligible += 1
        cum = 0.0
        hwm = 0.0
        floor = -2000.0
        busted = False
        pass_run = False
        max_d_pnl = -9999.0
        peak_dd = 0.0
        
        for step in range(eval_horizon_days):
            d = all_days[i + step]
            trades = trades_by_day.get(d, [])
            if not trades:
                continue
                
            # 3-Stage Dynamic Cushion
            if cum >= stg3_thresh:
                c_sz, t_sz, o_sz = stg3_c_sz, stg3_t_sz, stg3_o_sz
            elif cum >= stg2_thresh:
                c_sz, t_sz, o_sz = stg2_c_sz, stg2_t_sz, stg2_o_sz
            else:
                c_sz, t_sz, o_sz = stg1_c_sz, stg1_t_sz, stg1_o_sz
                
            day_pnl = 0.0
            day_mae = 0.0
            
            for tr in trades:
                if tr["type"] == "overnight":
                    sz = o_sz
                    mae = max(tr["mae_1c"], -30.0 * 2.0) * sz
                    pnl = tr["net_1c"] * sz
                    if tr["mae_1c"] < -30.0 * 2.0:
                        pnl = -30.0 * 2.0 * sz
                elif tr["is_crabel"]:
                    sz = c_sz
                    mae = tr["mae_1c"] * sz
                    pts = tr["pts"]
                    if pts > 25.0:
                        run = min(pts, runner_pts)
                        eff_pts = 0.5 * banker_pts + 0.5 * run
                        pnl = (eff_pts * 2.0 - 1.30 * 2.0) * sz
                    else:
                        pnl = tr["net_1c"] * sz
                else: # trend sleeve
                    sz = t_sz
                    mae = tr["mae_1c"] * sz
                    pts = tr["pts"]
                    if pts > 28.0:
                        run = min(pts, runner_pts)
                        eff_pts = 0.5 * banker_pts + 0.5 * run
                        pnl = (eff_pts * 2.0 - 1.30 * 2.0) * sz
                    else:
                        pnl = tr["net_1c"] * sz
                        
                if (day_pnl + mae) < day_mae:
                    day_mae = day_pnl + mae
                day_pnl += pnl
                
                # Daily circuit breakers
                if day_pnl >= daily_lock or day_pnl <= -daily_stop:
                    break
                    
            if day_pnl <= -1000.0 or day_mae <= -1000.0:
                busted = True; break
            if (cum + day_mae) <= floor:
                busted = True; break
                
            cum += day_pnl
            current_dd = hwm - cum
            if current_dd > peak_dd: peak_dd = current_dd
            if cum > hwm:
                hwm = cum
                floor = 0.0 if hwm >= 2000.0 else -2000.0 + hwm
            if cum <= floor:
                busted = True; break
                
            if day_pnl > max_d_pnl: max_d_pnl = day_pnl
            
            # Target pass check + 50% consistency enforcement
            if cum >= 4000.0 and max_d_pnl <= 2000.0:
                pass_run = True
                passed += 1
                pass_days.append(step + 1)
                max_dds.append(peak_dd)
                break
                
        if busted and not pass_run:
            ruined += 1
        elif not pass_run and not busted:
            timeout += 1
            
    p_arr = np.array(pass_days) if pass_days else np.array([0])
    dd_arr = np.array(max_dds) if max_dds else np.array([0])
    
    pass_pct = passed / max(1, eligible) * 100
    ruin_pct = ruined / max(1, eligible) * 100
    res_pass_pct = passed / max(1, passed + ruined) * 100
    med_days = float(np.median(p_arr)) if passed > 0 else 999.0
    p25_days = float(np.percentile(p_arr, 25)) if passed > 0 else 999.0
    p10_days = float(np.percentile(p_arr, 10)) if passed > 0 else 999.0
    min_days = int(p_arr.min()) if passed > 0 else 999
    avg_dd = float(dd_arr.mean()) if passed > 0 else 999.0
    
    return {
        "eligible": eligible,
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

print("\n" + "="*95)
print("GRID SEARCH: 2-WEEK (10 TRADING DAYS) MEDIAN PASSER WITH 3-STAGE CUSHION COMPOUNDING")
print("="*95)

grid = [
    # 1. 2-Stage Baseline (6/3 -> 10/5)
    ("1. Baseline 2-Stage (6/3 -> 10/5 MNQ, thr=1000)", 
     dict(stg1_c_sz=6, stg1_t_sz=3, stg1_o_sz=1, stg2_c_sz=10, stg2_t_sz=5, stg2_o_sz=2, stg3_c_sz=10, stg3_t_sz=5, stg3_o_sz=2, stg2_thresh=1000.0)),
     
    # 2. 3-Stage Finisher (6/3 -> 10/5 -> 12/6 at +$2,000 locked floor)
    ("2. 3-Stage Finisher (6/3 -> 10/5 -> 12/6 MNQ, thr=800/2000)", 
     dict(stg1_c_sz=6, stg1_t_sz=3, stg1_o_sz=1, stg2_c_sz=10, stg2_t_sz=5, stg2_o_sz=2, stg3_c_sz=12, stg3_t_sz=6, stg3_o_sz=2, stg2_thresh=800.0, stg3_thresh=2000.0)),

    # 3. 3-Stage Sprint Finisher (6/4 -> 10/6 -> 14/7 MNQ, thr=800/2000)
    ("3. Sprint 3-Stage (6/4 -> 10/6 -> 14/7 MNQ, thr=800/2000)", 
     dict(stg1_c_sz=6, stg1_t_sz=4, stg1_o_sz=1, stg2_c_sz=10, stg2_t_sz=6, stg2_o_sz=2, stg3_c_sz=14, stg3_t_sz=7, stg3_o_sz=2, stg2_thresh=800.0, stg3_thresh=2000.0)),

    # 4. Aggressive 8 MNQ Start (8/4 -> 12/6 -> 14/7 MNQ, thr=800/2000)
    ("4. Aggressive Velocity (8/4 -> 12/6 -> 14/7 MNQ, thr=800/2000)", 
     dict(stg1_c_sz=8, stg1_t_sz=4, stg1_o_sz=1, stg2_c_sz=12, stg2_t_sz=6, stg2_o_sz=2, stg3_c_sz=14, stg3_t_sz=7, stg3_o_sz=2, stg2_thresh=800.0, stg3_thresh=2000.0)),

    # 5. Timing Gate: VIX >= 18 (Active Market Sprint) with 3-Stage Finisher
    ("5. Active Market Timing (VIX >= 18, 6/4 -> 10/6 -> 14/7 MNQ)", 
     dict(stg1_c_sz=6, stg1_t_sz=4, stg1_o_sz=1, stg2_c_sz=10, stg2_t_sz=6, stg2_o_sz=2, stg3_c_sz=14, stg3_t_sz=7, stg3_o_sz=2, stg2_thresh=800.0, stg3_thresh=2000.0, min_vix=18.0)),

    # 6. Timing Gate: VIX >= 20 (High Vol Sprint) with 3-Stage Finisher
    ("6. High Vol Sprint Timing (VIX >= 20, 8/4 -> 12/6 -> 14/7 MNQ)", 
     dict(stg1_c_sz=8, stg1_t_sz=4, stg1_o_sz=2, stg2_c_sz=12, stg2_t_sz=6, stg2_o_sz=2, stg3_c_sz=14, stg3_t_sz=7, stg3_o_sz=2, stg2_thresh=800.0, stg3_thresh=2000.0, min_vix=20.0)),

    # 7. Timing Gate: VIX >= 22 (Extreme Vol Sprint) with 3-Stage Finisher
    ("7. Extreme Vol Sprint Timing (VIX >= 22, 8/4 -> 12/6 -> 14/7 MNQ)", 
     dict(stg1_c_sz=8, stg1_t_sz=4, stg1_o_sz=2, stg2_c_sz=12, stg2_t_sz=6, stg2_o_sz=2, stg3_c_sz=14, stg3_t_sz=7, stg3_o_sz=2, stg2_thresh=800.0, stg3_thresh=2000.0, min_vix=22.0)),
]

output_results = []
for label, kwargs in grid:
    res = evaluate_sprint_engine(**kwargs)
    res["label"] = label
    output_results.append(res)
    print(f"{label:65s} | MED: {res['med_days']:4.1f}d ({res['med_weeks']:3.1f}w) | p25: {res['p25_days']:4.1f}d | Min: {res['min_days']:2d}d | Pass: {res['pass_pct']:4.1f}% | Ruin: {res['ruin_pct']:4.1f}% | Res: {res['res_pass_pct']:4.1f}% | DD: ${res['avg_dd']:6.2f}")

with open(ROOT / "reports/BREAKTHROUGH_3STAGE_SPRINT_RESULTS.json", "w") as f:
    json.dump(output_results, f, indent=2)

print("\nDone. Saved to reports/BREAKTHROUGH_3STAGE_SPRINT_RESULTS.json")
