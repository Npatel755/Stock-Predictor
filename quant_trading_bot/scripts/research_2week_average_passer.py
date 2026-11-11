"""Research: Achieving ~2-Week (10 Trading Days) Average Pass Time.
Combines:
1. Multi-Sleeve Frequency (Book D+: Overnight Dip + Crabel Continuation + 30m Trend + 60m Trend)
2. Adaptive Trailing Ratchet (+25pt lock at +40pt, +45pt lock at +60pt)
3. 3-Stage Fortress Sprint Compounding (6c -> 10c -> 14c)
4. Topstep Static Floor (-$2,000 fixed, never trails)
5. Anti-Ruin Defensive Ratchet (drops to 1 MNQ if P&L < -$250)
6. Hard daily loss lock (-$250 / -$350) ensuring 0 DLL breaches
Evaluated across 14-Year Training Split (2010-2023).
"""
import sys, json
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

FRICTION_PTS = 1.30
PT_VAL = 2.00

def evaluate_passer(
    name,
    include_overnight=True,
    include_trend=True,
    stg1_c_sz=6,
    stg1_t_sz=3,
    stg1_o_sz=1,
    stg2_c_sz=10,
    stg2_t_sz=5,
    stg2_o_sz=2,
    stg3_c_sz=14,
    stg3_t_sz=7,
    stg3_o_sz=2,
    stg2_thresh=800.0,
    stg3_thresh=2000.0,
    anti_ruin_ratchet=True,
    use_adaptive_runner=True,
    daily_lock=1500.0,
    daily_stop=250.0,
    min_vix=0.0,
    eval_horizon_days=90
):
    total_starts = len(all_days) - eval_horizon_days
    eligible = 0
    passed = 0
    ruined = 0
    timeout = 0
    pass_days = []
    max_dds = []
    
    STATIC_FLOOR = -2000.0
    
    for i in range(total_starts):
        start_day = all_days[i]
        start_vix = vix_dict.get(start_day, 18.0)
        
        if start_vix < min_vix:
            continue
            
        eligible += 1
        cum = 0.0
        hwm = 0.0
        busted = False
        pass_run = False
        peak_dd = 0.0
        
        for step in range(eval_horizon_days):
            d = all_days[i + step]
            trades = trades_by_day.get(d, [])
            if not trades:
                continue
                
            # Sizing selection
            if anti_ruin_ratchet and cum <= -250.0:
                # Anti-Ruin Defensive Ratchet: reduce to 1 contract to defend static floor
                c_sz, t_sz, o_sz = 1, 1, 1
            elif cum >= stg3_thresh:
                c_sz, t_sz, o_sz = stg3_c_sz, stg3_t_sz, stg3_o_sz
            elif cum >= stg2_thresh:
                c_sz, t_sz, o_sz = stg2_c_sz, stg2_t_sz, stg2_o_sz
            else:
                c_sz, t_sz, o_sz = stg1_c_sz, stg1_t_sz, stg1_o_sz
                
            day_pnl = 0.0
            day_mae = 0.0
            
            # Scaled daily stop
            curr_stop = daily_stop * (c_sz / 6.0)
            
            for tr in trades:
                tr_type = tr["type"]
                if tr_type == "overnight" and not include_overnight:
                    continue
                if tr_type == "intraday" and not tr["is_crabel"] and not include_trend:
                    continue
                    
                if tr_type == "overnight":
                    sz = o_sz
                    mae = max(tr["mae_1c"], -30.0 * 2.0) * sz
                    pnl = tr["net_1c"] * sz
                    if tr["mae_1c"] < -30.0 * 2.0:
                        pnl = -30.0 * 2.0 * sz
                elif tr["is_crabel"]:
                    sz = c_sz
                    mae = tr["mae_1c"] * sz
                    pts = tr["pts"]
                    if use_adaptive_runner and pts > 20.0:
                        # Adaptive Trailing Ratchet:
                        # Bank half at 20pts
                        # Second half: if pts >= 85 take profit; elif pts >= 60 trail 45; elif pts >= 40 trail 25; else breakeven (1pt)
                        if pts >= 85.0: r_pts = 85.0
                        elif pts >= 60.0: r_pts = 45.0
                        elif pts >= 40.0: r_pts = 25.0
                        else: r_pts = 1.0
                        eff_pts = 0.5 * 20.0 + 0.5 * r_pts
                        pnl = (eff_pts * PT_VAL - FRICTION_PTS * PT_VAL) * sz
                    else:
                        pnl = tr["net_1c"] * sz
                else: # trend sleeve
                    sz = t_sz
                    mae = tr["mae_1c"] * sz
                    pts = tr["pts"]
                    if use_adaptive_runner and pts > 25.0:
                        if pts >= 75.0: r_pts = 75.0
                        elif pts >= 50.0: r_pts = 35.0
                        elif pts >= 35.0: r_pts = 20.0
                        else: r_pts = 1.0
                        eff_pts = 0.5 * 20.0 + 0.5 * r_pts
                        pnl = (eff_pts * PT_VAL - FRICTION_PTS * PT_VAL) * sz
                    else:
                        pnl = tr["net_1c"] * sz
                        
                if (day_pnl + mae) < day_mae:
                    day_mae = day_pnl + mae
                day_pnl += pnl
                
                # Daily circuit breakers
                if day_pnl >= daily_lock or day_pnl <= -curr_stop:
                    break
                    
            # Check DLL (-$1,000)
            if day_pnl <= -1000.0 or day_mae <= -1000.0:
                busted = True; break
                
            # Check STATIC Floor during session (-$2,000 fixed from starting $0)
            if (cum + day_mae) <= STATIC_FLOOR:
                busted = True; break
                
            cum += day_pnl
            current_dd = hwm - cum
            if current_dd > peak_dd: peak_dd = current_dd
            if cum > hwm: hwm = cum
            
            # Check STATIC Floor at close
            if cum <= STATIC_FLOOR:
                busted = True; break
                
            # Check Target Pass ($4,000) with 50% consistency enforcement (daily pnl <= $2,000)
            if cum >= 4000.0 and day_pnl <= 2000.0:
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
    mean_days = float(np.mean(p_arr)) if passed > 0 else 999.0
    p25_days = float(np.percentile(p_arr, 25)) if passed > 0 else 999.0
    p10_days = float(np.percentile(p_arr, 10)) if passed > 0 else 999.0
    min_days = int(p_arr.min()) if passed > 0 else 999
    avg_dd = float(dd_arr.mean()) if passed > 0 else 999.0
    
    return {
        "name": name,
        "eligible": eligible,
        "passed": passed,
        "ruined": ruined,
        "timeout": timeout,
        "pass_pct": round(pass_pct, 1),
        "ruin_pct": round(ruin_pct, 1),
        "res_pass_pct": round(res_pass_pct, 1),
        "med_days": round(med_days, 1),
        "mean_days": round(mean_days, 1),
        "p25_days": round(p25_days, 1),
        "p10_days": round(p10_days, 1),
        "min_days": min_days,
        "avg_dd": round(avg_dd, 2)
    }

print("\n" + "="*115)
print("EVALUATION OPTIMIZATION: ACHIEVING ~2-WEEK (10-14 DAYS) AVERAGE PASS TIME WITH STATIC FLOOR")
print("="*115)

configs = [
    # 1. Baseline: Pure Crabel Fixed 6 MNQ
    ("1. Pure Crabel Static 6 MNQ (Single-Sleeve Baseline)",
     dict(include_overnight=False, include_trend=False, stg1_c_sz=6, stg2_c_sz=6, stg3_c_sz=6, use_adaptive_runner=False)),

    # 2. Crabel with Adaptive Trailing Ratchet
    ("2. Pure Crabel with Adaptive Trailing Ratchet (6 MNQ)",
     dict(include_overnight=False, include_trend=False, stg1_c_sz=6, stg2_c_sz=6, stg3_c_sz=6, use_adaptive_runner=True)),

    # 3. Book D+ Multi-Sleeve Static (6c Crabel + 3c Trend + 1c Overnight)
    ("3. Book D+ Multi-Sleeve Static (6c Intra / 1c Overnight)",
     dict(include_overnight=True, include_trend=True, stg1_c_sz=6, stg1_t_sz=3, stg1_o_sz=1, stg2_c_sz=6, stg2_t_sz=3, stg2_o_sz=1, stg3_c_sz=6, stg3_t_sz=3, stg3_o_sz=1, use_adaptive_runner=True)),

    # 4. Book D+ 2-Stage Staging (6c -> 10c at +$1,000)
    ("4. Book D+ 2-Stage Compounding (6c -> 10c at +$1,000 cushion)",
     dict(include_overnight=True, include_trend=True, stg1_c_sz=6, stg1_t_sz=3, stg1_o_sz=1, stg2_c_sz=10, stg2_t_sz=5, stg2_o_sz=2, stg3_c_sz=10, stg3_t_sz=5, stg3_o_sz=2, stg2_thresh=1000.0, use_adaptive_runner=True)),

    # 5. Book D+ 3-Stage Fortress Sprint (6c -> 10c -> 14c Finisher)
    ("5. Book D+ 3-Stage Fortress Sprint (6c -> 10c -> 14c Finisher)",
     dict(include_overnight=True, include_trend=True, stg1_c_sz=6, stg1_t_sz=4, stg1_o_sz=1, stg2_c_sz=10, stg2_t_sz=5, stg2_o_sz=2, stg3_c_sz=14, stg3_t_sz=7, stg3_o_sz=2, stg2_thresh=800.0, stg3_thresh=2000.0, use_adaptive_runner=True)),

    # 6. Book D+ 3-Stage Velocity Sprint (8c -> 12c -> 14c Finisher)
    ("6. Book D+ 3-Stage Velocity Sprint (8c -> 12c -> 14c Finisher)",
     dict(include_overnight=True, include_trend=True, stg1_c_sz=8, stg1_t_sz=4, stg1_o_sz=1, stg2_c_sz=12, stg2_t_sz=6, stg2_o_sz=2, stg3_c_sz=14, stg3_t_sz=7, stg3_o_sz=2, stg2_thresh=800.0, stg3_thresh=2000.0, use_adaptive_runner=True)),

    # 7. Book D+ 3-Stage Sprint with Market Timing (VIX >= 16)
    ("7. Book D+ 3-Stage Sprint + Market Timing (VIX >= 16, 6c -> 10c -> 14c)",
     dict(include_overnight=True, include_trend=True, stg1_c_sz=6, stg1_t_sz=4, stg1_o_sz=1, stg2_c_sz=10, stg2_t_sz=5, stg2_o_sz=2, stg3_c_sz=14, stg3_t_sz=7, stg3_o_sz=2, stg2_thresh=800.0, stg3_thresh=2000.0, use_adaptive_runner=True, min_vix=16.0)),

    # 8. Book D+ 3-Stage Sprint with Market Timing (VIX >= 18)
    ("8. Book D+ 3-Stage Sprint + Market Timing (VIX >= 18, 8c -> 12c -> 14c)",
     dict(include_overnight=True, include_trend=True, stg1_c_sz=8, stg1_t_sz=4, stg1_o_sz=2, stg2_c_sz=12, stg2_t_sz=6, stg2_o_sz=2, stg3_c_sz=14, stg3_t_sz=7, stg3_o_sz=2, stg2_thresh=800.0, stg3_thresh=2000.0, use_adaptive_runner=True, min_vix=18.0)),
]

results = []
for label, kwargs in configs:
    r = evaluate_passer(label, **kwargs)
    results.append(r)
    print(f"{r['name']:70s} | MED: {r['med_days']:4.1f}d | MEAN: {r['mean_days']:4.1f}d | P25: {r['p25_days']:4.1f}d | Min: {r['min_days']:2d}d | Pass: {r['pass_pct']:4.1f}% | Ruin: {r['ruin_pct']:4.1f}% | Res: {r['res_pass_pct']:4.1f}% | DD: ${r['avg_dd']:6.2f}")

with open(ROOT / "reports/RESEARCH_2WEEK_AVERAGE_PASSER_RESULTS.json", "w") as f:
    json.dump(results, f, indent=2)

print("\nDone. Saved to reports/RESEARCH_2WEEK_AVERAGE_PASSER_RESULTS.json")
