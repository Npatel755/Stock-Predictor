"""Grid Search for 2-Week (10-14 Days) Average Evaluation Passer.
Finds the exact configuration that achieves:
- Mean pass time around 10 to 14 days (~2 weeks)
- Ultra-low ruin rate (protected by Anti-Ruin Defensive Ratchet)
- Topstep static floor and -$1,000 DLL invariants
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
vix_train = vix_df[(vix_df["date"] >= pd.to_datetime("2010-06-01").date()) & (vix_df["date"] <= pd.to_datetime("2023-12-31").date())]
all_sessions = sorted(vix_train["date"].unique())
vix_dict = dict(zip(vix_df["date"], vix_df["CLOSE"]))

# Load Cached Overnight Trades
with open(ROOT / "data/processed/overnight_trades_train.json") as f:
    on_trades = json.load(f)

# Build day-by-day events
events_by_day = {}

for tr in on_trades:
    d = pd.to_datetime(tr["exit_day"]).date()
    events_by_day.setdefault(d, []).append({
        "order": 0,
        "type": "overnight",
        "net_1c": float(tr["pnl_1c"]),
        "mae_1c": float(tr["mae_1c"]),
        "pts": float(tr["pnl_1c"]) / 2.0
    })

for t in base_intraday:
    d = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
    vix = vix_dict.get(d, 18.0)
    sleeve = t["sleeve"]
    cont = t.get("cont", False)
    if sleeve.startswith("AG_CRABEL") and not cont:
        continue
    net_1c = float(t["net"])
    stop_r = float(t.get("stop_risk", 34.6 * 2.0))
    events_by_day.setdefault(d, []).append({
        "order": 1 if sleeve.startswith("AG_CRABEL") else 2,
        "type": "intraday",
        "sleeve": sleeve,
        "net_1c": net_1c,
        "mae_1c": -min(stop_r, 70.0),
        "pts": net_1c / 2.0
    })

for d in events_by_day:
    events_by_day[d].sort(key=lambda x: x["order"])

FRICTION_PTS = 1.30
PT_VAL = 2.00

def test_config(
    label,
    base_c=6, base_t=3, base_o=1,
    stg2_c=10, stg2_t=5, stg2_o=2,
    stg3_c=14, stg3_t=7, stg3_o=2,
    stg2_thr=800.0,
    stg3_thr=2000.0,
    def_thr=-250.0,
    daily_stop=280.0,
    daily_lock=1500.0,
    min_vix=0.0,
    horizon_sessions=150
):
    total = len(all_sessions) - horizon_sessions
    passed = 0
    ruined = 0
    pass_sess = []
    pass_tr_days = []
    max_dds = []
    STATIC_FLOOR = -2000.0
    
    for i in range(total):
        start_day = all_sessions[i]
        if vix_dict.get(start_day, 18.0) < min_vix:
            continue
            
        cum = 0.0
        hwm = 0.0
        busted = False
        pass_run = False
        peak_dd = 0.0
        tr_days = 0
        
        for step in range(horizon_sessions):
            d = all_sessions[i + step]
            tr_list = events_by_day.get(d, [])
            if not tr_list:
                continue
            tr_days += 1
            
            # Staging
            if cum <= def_thr:
                c_sz, t_sz, o_sz = 1, 1, 1
            elif cum >= stg3_thr:
                c_sz, t_sz, o_sz = stg3_c, stg3_t, stg3_o
            elif cum >= stg2_thr:
                c_sz, t_sz, o_sz = stg2_c, stg2_t, stg2_o
            else:
                c_sz, t_sz, o_sz = base_c, base_t, base_o
                
            day_pnl = 0.0
            day_mae = 0.0
            curr_stop = daily_stop * (c_sz / float(base_c))
            
            for tr in tr_list:
                if tr["type"] == "overnight":
                    sz = o_sz
                    mae = max(tr["mae_1c"], -25.0 * 2.0) * sz
                    pnl = tr["net_1c"] * sz
                    if tr["mae_1c"] < -25.0 * 2.0:
                        pnl = -25.0 * 2.0 * sz
                elif tr["sleeve"].startswith("AG_CRABEL"):
                    sz = c_sz
                    mae = tr["mae_1c"] * sz
                    pts = tr["pts"]
                    if pts > 20.0:
                        if pts >= 85.0: r = 85.0
                        elif pts >= 60.0: r = 45.0
                        elif pts >= 40.0: r = 25.0
                        else: r = 1.0
                        eff = 0.5 * 20.0 + 0.5 * r
                        pnl = (eff * PT_VAL - FRICTION_PTS * PT_VAL) * sz
                    else:
                        pnl = tr["net_1c"] * sz
                else: # Trend
                    sz = t_sz
                    mae = tr["mae_1c"] * sz
                    pts = tr["pts"]
                    if pts > 25.0:
                        if pts >= 75.0: r = 75.0
                        elif pts >= 50.0: r = 35.0
                        elif pts >= 35.0: r = 20.0
                        else: r = 1.0
                        eff = 0.5 * 20.0 + 0.5 * r
                        pnl = (eff * PT_VAL - FRICTION_PTS * PT_VAL) * sz
                    else:
                        pnl = tr["net_1c"] * sz
                        
                if (day_pnl + mae) < day_mae: day_mae = day_pnl + mae
                day_pnl += pnl
                if day_pnl >= daily_lock or day_pnl <= -curr_stop:
                    break
                    
            if day_pnl <= -1000.0 or day_mae <= -1000.0 or (cum + day_mae) <= STATIC_FLOOR:
                busted = True; break
                
            cum += day_pnl
            current_dd = hwm - cum
            if current_dd > peak_dd: peak_dd = current_dd
            if cum > hwm: hwm = cum
            if cum <= STATIC_FLOOR:
                busted = True; break
                
            if cum >= 4000.0 and day_pnl <= 2000.0:
                pass_run = True
                passed += 1
                pass_sess.append(step + 1)
                pass_tr_days.append(tr_days)
                max_dds.append(peak_dd)
                break
                
        if busted and not pass_run:
            ruined += 1
            
    tot_eval = passed + ruined
    p_pct = (passed / max(1, tot_eval)) * 100
    r_pct = (ruined / max(1, tot_eval)) * 100
    
    mean_s = np.mean(pass_sess) if passed else 999.0
    med_s = np.median(pass_sess) if passed else 999.0
    p25_s = np.percentile(pass_sess, 25) if passed else 999.0
    min_s = np.min(pass_sess) if passed else 999
    
    mean_t = np.mean(pass_tr_days) if passed else 999.0
    med_t = np.median(pass_tr_days) if passed else 999.0
    
    avg_dd = np.mean(max_dds) if passed else 999.0
    
    return {
        "label": label,
        "passed": passed,
        "ruined": ruined,
        "pass_pct": round(p_pct, 1),
        "ruin_pct": round(r_pct, 1),
        "mean_sessions": round(mean_s, 1),
        "med_sessions": round(med_s, 1),
        "p25_sessions": round(p25_s, 1),
        "min_sessions": int(min_s),
        "mean_tr_days": round(mean_t, 1),
        "med_tr_days": round(med_t, 1),
        "avg_dd": round(avg_dd, 2)
    }

print("="*125)
print("SEARCHING FOR ~2-WEEK (10-14 DAYS) AVERAGE PASS TIME CONFIGURATION")
print("="*125)

configs = [
    # Baseline
    ("1. Standard Fortress (6c -> 10c -> 12c)", dict(base_c=6, base_t=3, base_o=1, stg2_c=10, stg2_t=5, stg2_o=2, stg3_c=12, stg3_t=6, stg3_o=2, stg2_thr=1000.0, stg3_thr=2200.0)),
    
    # 2. Faster Compounding
    ("2. Fast Compounding (6c -> 10c -> 14c, Thr: 750/1800)", dict(base_c=6, base_t=3, base_o=1, stg2_c=10, stg2_t=5, stg2_o=2, stg3_c=14, stg3_t=7, stg3_o=2, stg2_thr=750.0, stg3_thr=1800.0)),

    # 3. Aggressive Base 8 MNQ
    ("3. Power Base (8c -> 12c -> 14c, Thr: 800/2000)", dict(base_c=8, base_t=4, base_o=1, stg2_c=12, stg2_t=6, stg2_o=2, stg3_c=14, stg3_t=7, stg3_o=2, stg2_thr=800.0, stg3_thr=2000.0)),

    # 4. Turbo Velocity (8c -> 14c -> 14c, Thr: 700/1500)
    ("4. Turbo Velocity (8c -> 14c -> 14c, Thr: 700/1500)", dict(base_c=8, base_t=4, base_o=2, stg2_c=14, stg2_t=7, stg2_o=2, stg3_c=14, stg3_t=7, stg3_o=2, stg2_thr=700.0, stg3_thr=1500.0)),

    # 5. Vol Timing VIX >= 16 (Power Base)
    ("5. Vol Timing VIX >= 16 (8c -> 12c -> 14c)", dict(base_c=8, base_t=4, base_o=1, stg2_c=12, stg2_t=6, stg2_o=2, stg3_c=14, stg3_t=7, stg3_o=2, stg2_thr=800.0, stg3_thr=2000.0, min_vix=16.0)),

    # 6. Vol Timing VIX >= 18 (Turbo Velocity)
    ("6. Vol Timing VIX >= 18 (8c -> 14c -> 14c)", dict(base_c=8, base_t=4, base_o=2, stg2_c=14, stg2_t=7, stg2_o=2, stg3_c=14, stg3_t=7, stg3_o=2, stg2_thr=700.0, stg3_thr=1500.0, min_vix=18.0)),

    # 7. Vol Timing VIX >= 20 (Target 2-Week Sprint)
    ("7. High Vol Sprint VIX >= 20 (10c -> 14c -> 14c)", dict(base_c=10, base_t=5, base_o=2, stg2_c=14, stg2_t=7, stg2_o=2, stg3_c=14, stg3_t=7, stg3_o=2, stg2_thr=600.0, stg3_thr=1400.0, min_vix=20.0)),
]

res = []
for lbl, kw in configs:
    r = test_config(lbl, **kw)
    res.append(r)
    print(f"{r['label']:55s} | MEAN: {r['mean_sessions']:4.1f}s ({r['mean_tr_days']:4.1f} tr) | MED: {r['med_sessions']:4.1f}s ({r['med_tr_days']:4.1f} tr) | p25: {r['p25_sessions']:4.1f}s | Min: {r['min_sessions']:2d}s | Pass: {r['pass_pct']:4.1f}% | Ruin: {r['ruin_pct']:4.1f}% | DD: ${r['avg_dd']:6.2f}")

with open(ROOT / "reports/RESEARCH_2WEEK_AVERAGE_RESULTS.json", "w") as f:
    json.dump(res, f, indent=2)
print("\nDone. Saved to reports/RESEARCH_2WEEK_AVERAGE_RESULTS.json")
