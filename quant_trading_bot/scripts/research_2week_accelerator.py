"""2-Week Median Evaluation Passer Accelerator (2010-2023 Training Split).
Goal: Engineer the Cushion-Staged Architecture so that MEDIAN time-to-pass is <= 10 trading days (2 weeks),
while preserving high pass rate and keeping ruin risk minimal.

Rules:
- Target: +$4,000
- Trailing Floor: -$2,000 (locks at starting balance once HWM reaches +$2,000)
- Daily Loss Limit: -$1,000
- 50% Consistency Rule: Single day profit must not exceed $2,000 (capped at +$1,750)
- Full CME Friction: $0.61 commission/side, 1.75 tick spread, 1.0 tick slippage = 1.30 pts roundtrip

Architecture Components:
1. Dual-Sleeve Frequency: Stopped Overnight Reopen Dip (18:05 -> 09:45) + Morning Crabel 15m + Trend Sleeves
2. Free-Roll Scale-Out: 50% banked at +25/28 pts, 50% free-roll runner for +80 to +120 pts
3. Precision Cushion Sizing:
   - Stage 1 (0 to Cushion Threshold): Size S1. Stop loss strictly capped to prevent DLL breach.
   - Stage 2 (Above Cushion): Size S2. Target acceleration into the $4,000 target.
4. Strict Daily Guardrails: Daily lock at +$1,750; Daily stop at -$380 to -$400.
"""
import sys, json, os
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

# 1. Load Intraday Trades
src_dplus = (ROOT / "scripts/dplus_4_pilot.py").read_text().split("\nout = {}")[0]
ns_dplus = {"__file__": str(ROOT / "scripts/dplus_4_pilot.py")}
exec(src_dplus, ns_dplus)
base_intraday = ns_dplus["base"]

# 2. Load VIX
vix_path = ROOT / "data/external/VIX_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df["date"] = pd.to_datetime(vix_df["DATE"]).dt.date
vix_dict = dict(zip(vix_df["date"], vix_df["CLOSE"]))

# 3. Load Cached Overnight Trades
on_path = ROOT / "data/processed/overnight_trades_train.json"
with open(on_path) as f:
    on_trades_data = json.load(f)

# 4. Map trades chronologically
trades_by_day = {}

# Overnight (Order 0: executed 18:05 to 09:45)
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

# Intraday
for t in base_intraday:
    t_day = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
    cont = t.get("cont", False)
    sleeve = t["sleeve"]
    is_crabel = sleeve.startswith("AG_CRABEL")
    if is_crabel and not cont: 
        continue # filter non-continuation
        
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

active_days = sorted(list(trades_by_day.keys()))
print(f"Total days with trades: {len(active_days)}")

def simulate_2week_passer(
    stg1_crabel_sz=6,
    stg1_trend_sz=3,
    stg1_on_sz=1,
    stg2_crabel_sz=10,
    stg2_trend_sz=5,
    stg2_on_sz=2,
    cushion_threshold=800.0,
    daily_lock=1750.0,
    daily_stop=380.0,
    on_hard_stop_pts=30.0,
    scaleout_banker_pts=25.0,
    scaleout_runner_pts=90.0,
    use_scaleout=True,
    min_vix_gate=0.0,
    max_days=60
):
    total_eligible = 0
    passed = 0
    ruined = 0
    timeout = 0
    pass_days = []
    max_dds = []
    
    for i in range(len(active_days) - max_days):
        start_day = active_days[i]
        vix_start = vix_dict.get(start_day, 18.0)
        
        if vix_start < min_vix_gate:
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
            d = active_days[i + step]
            trades = trades_by_day.get(d, [])
            if not trades:
                continue
                
            in_stg2 = (cum >= cushion_threshold)
            c_sz = stg2_crabel_sz if in_stg2 else stg1_crabel_sz
            t_sz = stg2_trend_sz if in_stg2 else stg1_trend_sz
            o_sz = stg2_on_sz if in_stg2 else stg1_on_sz
            
            day_pnl = 0.0
            day_mae = 0.0
            
            for tr in trades:
                if tr["type"] == "overnight":
                    sz = o_sz
                    mae = max(tr["mae_1c"], -on_hard_stop_pts * 2.0) * sz
                    pnl = tr["net_1c"] * sz
                    if tr["mae_1c"] < -on_hard_stop_pts * 2.0:
                        pnl = -on_hard_stop_pts * 2.0 * sz
                elif tr["is_crabel"]:
                    sz = c_sz
                    mae = tr["mae_1c"] * sz
                    pts = tr["pts"]
                    if use_scaleout and pts > 25.0:
                        # 50% banked at scaleout_banker_pts, 50% runner
                        run_captured = min(pts, scaleout_runner_pts)
                        effective_pts = 0.5 * scaleout_banker_pts + 0.5 * run_captured
                        pnl = (effective_pts * 2.0 - 1.30 * 2.0) * sz
                    else:
                        pnl = tr["net_1c"] * sz
                else:
                    sz = t_sz
                    mae = tr["mae_1c"] * sz
                    pts = tr["pts"]
                    if use_scaleout and pts > 30.0:
                        run_captured = min(pts, scaleout_runner_pts)
                        effective_pts = 0.5 * scaleout_banker_pts + 0.5 * run_captured
                        pnl = (effective_pts * 2.0 - 1.30 * 2.0) * sz
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
            
            # Target pass check with 50% consistency enforcement
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
    
    pass_pct = passed / max(1, total_eligible) * 100
    ruin_pct = ruined / max(1, total_eligible) * 100
    res_pass_pct = passed / max(1, passed + ruined) * 100
    med_days = float(np.median(p_arr)) if passed > 0 else 999.0
    p25_days = float(np.percentile(p_arr, 25)) if passed > 0 else 999.0
    p10_days = float(np.percentile(p_arr, 10)) if passed > 0 else 999.0
    min_days = int(p_arr.min()) if passed > 0 else 999
    avg_dd = float(dd_arr.mean()) if passed > 0 else 999.0
    
    return {
        "eligible": total_eligible,
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

print("\n" + "="*90)
print("TESTING 2-WEEK (10 TRADING DAYS) MEDIAN PASSER ARCHITECTURES")
print("="*90)

configs = [
    # 1. Standard Cushion-Staged baseline (6c Crabel / 3c Trend -> 10c / 5c)
    ("1. Baseline Cushion-Staged (6/3 -> 10/5 MNQ, thr=1000)", 
     dict(stg1_crabel_sz=6, stg1_trend_sz=3, stg1_on_sz=1, stg2_crabel_sz=10, stg2_trend_sz=5, stg2_on_sz=2, cushion_threshold=1000.0)),

    # 2. Earlier Stage 2 threshold (+ $800)
    ("2. Fast Stage 2 Trigger (6/3 -> 10/5 MNQ, thr=800)", 
     dict(stg1_crabel_sz=6, stg1_trend_sz=3, stg1_on_sz=1, stg2_crabel_sz=10, stg2_trend_sz=5, stg2_on_sz=2, cushion_threshold=800.0)),

    # 3. Enhanced Trend Sizing: 6c Crabel / 4c Trend -> 10c / 6c Trend
    ("3. Accelerated Multi-Sleeve (6/4 -> 10/6 MNQ, thr=800)", 
     dict(stg1_crabel_sz=6, stg1_trend_sz=4, stg1_on_sz=1, stg2_crabel_sz=10, stg2_trend_sz=6, stg2_on_sz=2, cushion_threshold=800.0)),

    # 4. Free-Roll 100 pt Runner (6/4 -> 10/6 MNQ, runner=100pt)
    ("4. Free-Roll 100pt Runner (6/4 -> 10/6 MNQ, thr=800, run=100pt)", 
     dict(stg1_crabel_sz=6, stg1_trend_sz=4, stg1_on_sz=1, stg2_crabel_sz=10, stg2_trend_sz=6, stg2_on_sz=2, cushion_threshold=800.0, scaleout_runner_pts=100.0)),

    # 5. Finisher Scale to 12 MNQ in Stage 2 (6/4 -> 12/6 MNQ, thr=800)
    ("5. Finisher Scale (6/4 -> 12/6 MNQ, thr=800, run=110pt)", 
     dict(stg1_crabel_sz=6, stg1_trend_sz=4, stg1_on_sz=1, stg2_crabel_sz=12, stg2_trend_sz=6, stg2_on_sz=2, cushion_threshold=800.0, scaleout_runner_pts=110.0)),

    # 6. Sprint Sizing: 8/4 -> 12/6 MNQ (thr=800)
    ("6. Velocity Sprint (8/4 -> 12/6 MNQ, thr=800, run=100pt)", 
     dict(stg1_crabel_sz=8, stg1_trend_sz=4, stg1_on_sz=1, stg2_crabel_sz=12, stg2_trend_sz=6, stg2_on_sz=2, cushion_threshold=800.0, scaleout_runner_pts=100.0)),

    # 7. Velocity Sprint + Active Market Gate (VIX >= 18)
    ("7. Active Market Sprint (VIX >= 18, 6/4 -> 12/6 MNQ, thr=800)", 
     dict(stg1_crabel_sz=6, stg1_trend_sz=4, stg1_on_sz=1, stg2_crabel_sz=12, stg2_trend_sz=6, stg2_on_sz=2, cushion_threshold=800.0, min_vix_gate=18.0)),

    # 8. Velocity Sprint + High Vol Market Gate (VIX >= 20)
    ("8. High Vol Sprint (VIX >= 20, 8/4 -> 12/6 MNQ, thr=800)", 
     dict(stg1_crabel_sz=8, stg1_trend_sz=4, stg1_on_sz=2, stg2_crabel_sz=12, stg2_trend_sz=6, stg2_on_sz=2, cushion_threshold=800.0, min_vix_gate=20.0)),
]

res_list = []
for label, kwargs in configs:
    res = simulate_2week_passer(**kwargs)
    res["config"] = label
    res_list.append(res)
    print(f"{label:65s} | MEDIAN: {res['med_days']:4.1f}d ({res['med_weeks']:3.1f}w) | p25: {res['p25_days']:4.1f}d | Min: {res['min_days']}d | Pass: {res['pass_pct']:5.1f}% | Ruin: {res['ruin_pct']:4.1f}% | Resolved: {res['res_pass_pct']:5.1f}% | AvgDD: ${res['avg_dd']:6.2f}")

out_f = ROOT / "reports/TWO_WEEK_ACCELERATOR_MATRIX.json"
with open(out_f, "w") as f:
    json.dump(res_list, f, indent=2)

print("\nSaved matrix to:", out_f)
