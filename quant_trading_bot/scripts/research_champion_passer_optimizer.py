"""Champion Evaluation Passer Optimizer: Minimizing Drawdown & Maximizing Pass Probability.
Strictly on 14-Year Training Split (2010-2023).

Systematic Tests:
1. Base Sizing Search (3, 4, 5, 6 MNQ)
2. Defensive Ratchet Thresholds (-$200, -$300, -$400, -$500)
3. Defensive Size (1 vs 2 MNQ)
4. Cushion Acceleration Tiers (+$800, +$1,000, +$1,200)
5. Sprint Sizing Tiers (8, 10, 12, 14 MNQ)
6. Daily Loss Stop (-$250, -$300, -$350, -$400)
7. Scale-Out Parameters (Banker +20 vs +25 pts; Runner +75 vs +85 vs +100 pts)
"""
import sys, json, os
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
sys.path.insert(0, str(ROOT / "scripts"))

# 1. Load Intraday
src_dplus = (ROOT / "scripts/dplus_4_pilot.py").read_text().split("\nout = {}")[0]
ns_dplus = {"__file__": str(ROOT / "scripts/dplus_4_pilot.py")}
exec(src_dplus, ns_dplus)
base_intraday = ns_dplus["base"]

# 2. Load Calendar & VIX
vix_path = ROOT / "data/external/VIX_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df["date"] = pd.to_datetime(vix_df["DATE"]).dt.date
vix_train = vix_df[(vix_df["date"] >= pd.to_datetime("2010-06-01").date()) & (vix_df["date"] <= pd.to_datetime("2023-12-31").date())]
all_days = sorted(vix_train["date"].unique())
vix_dict = dict(zip(vix_df["date"], vix_df["CLOSE"]))

# 3. Load Overnight
with open(ROOT / "data/processed/overnight_trades_train.json") as f:
    on_trades = json.load(f)

# Filtered Trade Book (Crabel Continuation with VIX >= 15 + Stopped Overnight Dip)
trades_book = {}

for tr in on_trades:
    d = pd.to_datetime(tr["exit_day"]).date()
    trades_book.setdefault(d, []).append({
        "order": 0,
        "type": "overnight",
        "net_1c": float(tr["pnl_1c"]),
        "mae_1c": float(tr["mae_1c"]),
        "pts": float(tr["pnl_1c"]) / 2.0
    })

for t in base_intraday:
    d = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
    vix = vix_dict.get(d, 18.0)
    # High-expectancy Crabel continuation
    if vix >= 15.0 and t["sleeve"].startswith("AG_CRABEL") and t.get("cont", False):
        net_1c = float(t["net"])
        stop_r = float(t.get("stop_risk", 34.6 * 2.0))
        trades_book.setdefault(d, []).append({
            "order": 1,
            "type": "crabel",
            "net_1c": net_1c,
            "mae_1c": -min(stop_r, 70.0),
            "pts": net_1c / 2.0
        })

for d in trades_book:
    trades_book[d].sort(key=lambda x: x["order"])

print(f"Loaded {len(all_days)} trading days, {len(trades_book)} active trade days.")

def test_config(
    label,
    base_sz=4,
    def_sz=1,
    def_thr=-300.0,
    stg2_sz=8,
    stg2_thr=1000.0,
    stg3_sz=12,
    stg3_thr=2200.0,
    daily_stop=280.0,
    daily_lock=1500.0,
    banker_pts=20.0,
    runner_pts=85.0,
    horizon_days=500
):
    total = len(all_days) - horizon_days
    passed = 0
    ruined = 0
    pass_days = []
    max_dds = []
    
    for i in range(total):
        cum = 0.0
        hwm = 0.0
        floor = -2000.0
        peak_dd = 0.0
        busted = False
        pass_run = False
        max_d_pnl = -9999.0
        
        for step in range(horizon_days):
            d = all_days[i + step]
            tr_list = trades_book.get(d, [])
            if not tr_list:
                continue
                
            # Asymmetric Staging
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
                s = o_sz if tr["type"] == "overnight" else sz
                mae = max(tr["mae_1c"], -25.0 * 2.0) * s if tr["type"] == "overnight" else tr["mae_1c"] * s
                pts = tr["pts"]
                
                if tr["type"] != "overnight" and pts > 20.0:
                    run = min(pts, runner_pts)
                    eff_pts = 0.5 * banker_pts + 0.5 * run
                    pnl = (eff_pts * 2.0 - 1.30 * 2.0) * s
                else:
                    pnl = tr["net_1c"] * s
                    
                if (day_pnl + mae) < day_mae:
                    day_mae = day_pnl + mae
                day_pnl += pnl
                
                # Daily circuit breakers
                if day_pnl >= daily_lock or day_pnl <= -daily_stop:
                    break
                    
            if day_pnl <= -1000.0 or day_mae <= -1000.0 or (cum + day_mae) <= floor:
                busted = True; break
                
            cum += day_pnl
            current_dd = hwm - cum
            if current_dd > peak_dd: peak_dd = current_dd
            if cum > hwm: hwm = cum
            if cum <= floor: busted = True; break
            
            if day_pnl > max_d_pnl: max_d_pnl = day_pnl
            
            if cum >= 4000.0 and max_d_pnl <= 2000.0:
                pass_run = True
                passed += 1
                pass_days.append(step + 1)
                max_dds.append(peak_dd)
                break
                
        if busted and not pass_run:
            ruined += 1
            
    p_arr = np.array(pass_days) if pass_days else np.array([0])
    dd_arr = np.array(max_dds) if max_dds else np.array([0])
    
    pass_pct = passed / max(1, passed + ruined) * 100
    ruin_pct = ruined / max(1, passed + ruined) * 100
    med_days = float(np.median(p_arr)) if passed > 0 else 999.0
    p25_days = float(np.percentile(p_arr, 25)) if passed > 0 else 999.0
    avg_dd = float(dd_arr.mean()) if passed > 0 else 999.0
    
    return {
        "label": label,
        "passed": passed,
        "ruined": ruined,
        "total_resolved": passed + ruined,
        "pass_pct": round(pass_pct, 1),
        "ruin_pct": round(ruin_pct, 1),
        "med_days": round(med_days, 1),
        "p25_days": round(p25_days, 1),
        "avg_dd": round(avg_dd, 2)
    }

print("\n" + "="*95)
print("OPTIMIZING FOR MAXIMUM PASS PROBABILITY & MINIMAL DRAWDOWN")
print("="*95)

grid = [
    # Baseline
    ("1. Baseline: 4 MNQ Base -> 8c -> 12c (Def: 1c at -$300)", 
     dict(base_sz=4, def_sz=1, def_thr=-300.0, stg2_sz=8, stg3_sz=12, daily_stop=280.0)),

    # Def size = 2 MNQ (recovers faster from minor pullbacks)
    ("2. Fast Recovery: 4 MNQ Base -> 8c -> 12c (Def: 2c at -$300)", 
     dict(base_sz=4, def_sz=2, def_thr=-300.0, stg2_sz=8, stg3_sz=12, daily_stop=280.0)),

    # 5 MNQ Base with 1c Defensive
    ("3. Power Base: 5 MNQ Base -> 8c -> 12c (Def: 1c at -$300)", 
     dict(base_sz=5, def_sz=1, def_thr=-300.0, stg2_sz=8, stg3_sz=12, daily_stop=300.0)),

    # 5 MNQ Base with 2c Defensive
    ("4. Power Base: 5 MNQ Base -> 8c -> 12c (Def: 2c at -$300)", 
     dict(base_sz=5, def_sz=2, def_thr=-300.0, stg2_sz=8, stg3_sz=12, daily_stop=300.0)),

    # Earlier Stage 2 threshold (+$800 instead of +$1,000)
    ("5. Early Cushion: 4 MNQ Base -> 8c (+$800) -> 12c (+$2k)", 
     dict(base_sz=4, def_sz=1, def_thr=-300.0, stg2_sz=8, stg2_thr=800.0, stg3_sz=12, stg3_thr=2000.0, daily_stop=280.0)),

    # Ultra-Safe 3 MNQ Start with 1c Defensive
    ("6. Fortress Ultra: 3 MNQ Base -> 6c (+$600) -> 10c (+$1.5k) -> 12c (+$2.5k)", 
     dict(base_sz=3, def_sz=1, def_thr=-250.0, stg2_sz=6, stg2_thr=600.0, stg3_sz=10, stg3_thr=1500.0, daily_stop=250.0)),

    # Finisher Sprint: 5 MNQ Base -> 10c (+$1k) -> 14c (+$2.2k)
    ("7. Finisher Sprint: 5 MNQ Base -> 10c (+$1k) -> 14c (+$2.2k)", 
     dict(base_sz=5, def_sz=2, def_thr=-300.0, stg2_sz=10, stg2_thr=1000.0, stg3_sz=14, stg3_thr=2200.0, daily_stop=320.0)),

    # Strict Daily Stop -$250 with 4 MNQ
    ("8. Strict Daily Stop -$250: 4 MNQ Base -> 8c -> 12c (Def: 1c)", 
     dict(base_sz=4, def_sz=1, def_thr=-250.0, stg2_sz=8, stg3_sz=12, daily_stop=250.0)),
]

results = []
for label, kwargs in grid:
    res = test_config(label, **kwargs)
    results.append(res)
    print(f"{label:65s} | Pass: {res['pass_pct']:5.1f}% | Ruin: {res['ruin_pct']:5.1f}% | Med: {res['med_days']:4.1f}d | p25: {res['p25_days']:4.1f}d | DD: ${res['avg_dd']:6.2f} (N={res['total_resolved']})")

out_file = ROOT / "reports/CHAMPION_PASSER_OPTIMIZATION_RESULTS.json"
with open(out_file, "w") as f:
    json.dump(results, f, indent=2)

print("\n" + "="*95)
print(f"Optimization complete. Saved to: {out_file.name}")
print("="*95)
