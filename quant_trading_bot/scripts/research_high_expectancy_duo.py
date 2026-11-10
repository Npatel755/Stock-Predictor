"""High-Expectancy Core Evaluation Optimizer.
Comparing:
1. Full 4-Sleeve noisy ensemble (Crabel + 30m trend + 60m trend + MES)
2. High-Expectancy Duo (Crabel Continuation + VIX-gated Overnight Dip)
3. Free-Roll Scale-Out on High-Expectancy Duo
4. Defensive Drawdown Ratchet + Asymmetric Cushion Staging
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
sys.path.insert(0, str(ROOT / "scripts"))

# 1. Load Intraday
src_dplus = (ROOT / "scripts/dplus_4_pilot.py").read_text().split("\nout = {}")[0]
ns_dplus = {"__file__": str(ROOT / "scripts/dplus_4_pilot.py")}
exec(src_dplus, ns_dplus)
base_intraday = ns_dplus["base"]

# 2. Load Calendar
vix_path = ROOT / "data/external/VIX_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df["date"] = pd.to_datetime(vix_df["DATE"]).dt.date
vix_train = vix_df[(vix_df["date"] >= pd.to_datetime("2010-06-01").date()) & (vix_df["date"] <= pd.to_datetime("2023-12-31").date())]
all_days = sorted(vix_train["date"].unique())
vix_dict = dict(zip(vix_df["date"], vix_df["CLOSE"]))

# 3. Load Overnight
with open(ROOT / "data/processed/overnight_trades_train.json") as f:
    on_trades = json.load(f)

# Group trades by day under different sleeve subsets:
# Subset A: All Sleeves
# Subset B: High-Expectancy Duo (Crabel Cont + Overnight Dip ONLY)
# Subset C: High-Expectancy Duo + Scale-Out Runner

trades_all_sleeves = {}
trades_duo = {}

# Overnight
for tr in on_trades:
    d = pd.to_datetime(tr["exit_day"]).date()
    item = {
        "type": "overnight",
        "net_1c": float(tr["pnl_1c"]),
        "mae_1c": float(tr["mae_1c"]),
        "pts": float(tr["pnl_1c"]) / 2.0,
    }
    trades_all_sleeves.setdefault(d, []).append(item)
    trades_duo.setdefault(d, []).append(item)

# Intraday
for t in base_intraday:
    d = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
    cont = t.get("cont", False)
    sleeve = t["sleeve"]
    is_crabel = sleeve.startswith("AG_CRABEL")
    
    net_1c = float(t["net"])
    pts_1c = net_1c / 2.0
    stop_r = float(t.get("stop_risk", 34.6 * 2.0))
    mae_1c = -min(stop_r, 70.0)
    
    item = {
        "type": "crabel" if is_crabel else "trend",
        "net_1c": net_1c,
        "mae_1c": mae_1c,
        "pts": pts_1c,
        "cont": cont,
        "is_crabel": is_crabel
    }
    
    trades_all_sleeves.setdefault(d, []).append(item)
    
    # Duo only takes Crabel continuation!
    if is_crabel and cont:
        trades_duo.setdefault(d, []).append(item)

def run_sim(trades_dict, label, base_sz=6, def_sz=2, def_thr=-350.0, stg2_sz=10, stg2_thr=1000.0, stg3_sz=12, stg3_thr=2200.0, use_scaleout=True, max_horizon=90):
    total = len(all_days) - max_horizon
    passed = 0
    ruined = 0
    timeout = 0
    pass_days = []
    max_dds = []
    
    for i in range(total):
        cum = 0.0
        hwm = 0.0
        floor = -2000.0
        busted = False
        pass_run = False
        peak_dd = 0.0
        max_d_pnl = -9999.0
        
        for step in range(max_horizon):
            d = all_days[i + step]
            tr_list = trades_dict.get(d, [])
            if not tr_list:
                continue
                
            # Dynamic Staging
            if cum <= def_thr:
                sz = def_sz
                o_sz = 1
            elif cum >= stg3_thr:
                sz = stg3_sz
                o_sz = 2
            elif cum >= stg2_thr:
                sz = stg2_sz
                o_sz = 2
            else:
                sz = base_sz
                o_sz = 1
                
            day_pnl = 0.0
            day_mae = 0.0
            
            for tr in tr_list:
                if tr["type"] == "overnight":
                    s = o_sz
                    mae = max(tr["mae_1c"], -25.0 * 2.0) * s
                    pnl = tr["net_1c"] * s
                    if tr["mae_1c"] < -25.0 * 2.0:
                        pnl = -25.0 * 2.0 * s
                else:
                    s = sz
                    mae = tr["mae_1c"] * s
                    pts = tr["pts"]
                    if use_scaleout and pts > 20.0:
                        run = min(pts, 85.0)
                        eff_pts = 0.5 * 20.0 + 0.5 * run
                        pnl = (eff_pts * 2.0 - 1.30 * 2.0) * s
                    else:
                        pnl = tr["net_1c"] * s
                        
                if (day_pnl + mae) < day_mae:
                    day_mae = day_pnl + mae
                day_pnl += pnl
                
                # Daily circuit breakers: lock at +$1,500, stop at -$350
                if day_pnl >= 1500.0 or day_pnl <= -350.0:
                    break
                    
            if day_pnl <= -1000.0 or day_mae <= -1000.0:
                busted = True; break
            if (cum + day_mae) <= floor:
                busted = True; break
                
            cum += day_pnl
            current_dd = hwm - cum
            if current_dd > peak_dd: peak_dd = current_dd
            if cum > hwm: hwm = cum
            if cum <= floor:
                busted = True; break
                
            if day_pnl > max_d_pnl: max_d_pnl = day_pnl
            
            # Pass Target + 50% consistency rule
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
    
    pass_pct = passed / total * 100
    ruin_pct = ruined / total * 100
    res_pct = passed / max(1, passed + ruined) * 100
    med_d = float(np.median(p_arr)) if passed > 0 else 999.0
    avg_dd = float(dd_arr.mean()) if passed > 0 else 999.0
    
    print(f"{label:65s} | Pass: {pass_pct:5.1f}% | Ruin: {ruin_pct:5.1f}% | Resolved Pass Rate: {res_pct:5.1f}% | Median: {med_d:4.1f}d | AvgDD: ${avg_dd:6.2f}")
    return {"label": label, "pass_pct": pass_pct, "ruin_pct": ruin_pct, "res_pct": res_pct, "med_d": med_d, "avg_dd": avg_dd}

print("="*95)
print("TESTING HIGH-EXPECTANCY DUO VS ALL-SLEEVE ENSEMBLE")
print("="*95)

# 1. All Sleeves (Horizon 90)
run_sim(trades_all_sleeves, "1. All-Sleeve Ensemble (Crabel+Trend+ON), 6c Base (90d)", base_sz=6, use_scaleout=True, max_horizon=90)

# 2. High-Expectancy Duo (Crabel Cont + ON Dip ONLY) (Horizon 90)
run_sim(trades_duo, "2. High-Expectancy Duo (Crabel Cont + ON Dip ONLY), 6c Base (90d)", base_sz=6, use_scaleout=True, max_horizon=90)

# 3. High-Expectancy Duo with Higher Base Size (8c Base -> 12c)
run_sim(trades_duo, "3. High-Expectancy Duo, 8c Base -> 12c Sprint (90d)", base_sz=8, def_sz=3, stg2_sz=12, stg2_thr=1000.0, stg3_sz=14, stg3_thr=2000.0, use_scaleout=True, max_horizon=90)

# 4. High-Expectancy Duo with Higher Base Size (10c Base -> 14c)
run_sim(trades_duo, "4. High-Expectancy Duo, 10c Base -> 14c Sprint (90d)", base_sz=10, def_sz=4, stg2_sz=14, stg2_thr=1000.0, stg3_sz=14, stg3_thr=2000.0, use_scaleout=True, max_horizon=90)

# 5. Horizon 180 (Full Evaluation Window)
run_sim(trades_duo, "5. High-Expectancy Duo, 8c Base -> 12c Sprint (180d Horizon)", base_sz=8, def_sz=3, stg2_sz=12, stg2_thr=1000.0, stg3_sz=14, stg3_thr=2000.0, use_scaleout=True, max_horizon=180)
run_sim(trades_duo, "6. High-Expectancy Duo, 10c Base -> 14c Sprint (180d Horizon)", base_sz=10, def_sz=4, stg2_sz=14, stg2_thr=1000.0, stg3_sz=14, stg3_thr=2000.0, use_scaleout=True, max_horizon=180)

# 6. Horizon 250 (Full 1-Year Horizon)
run_sim(trades_duo, "7. High-Expectancy Duo, 8c Base -> 12c Sprint (250d Horizon)", base_sz=8, def_sz=3, stg2_sz=12, stg2_thr=1000.0, stg3_sz=14, stg3_thr=2000.0, use_scaleout=True, max_horizon=250)
run_sim(trades_duo, "8. High-Expectancy Duo, 10c Base -> 14c Sprint (250d Horizon)", base_sz=10, def_sz=4, stg2_sz=14, stg2_thr=1000.0, stg3_sz=14, stg3_thr=2000.0, use_scaleout=True, max_horizon=250)
