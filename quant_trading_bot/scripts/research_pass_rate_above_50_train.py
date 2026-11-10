"""Research: Testing Book D+ (Overnight Dip + Architecture D+ Intraday)
for >50% Evaluation Pass Rate (2010-2023 Training Split).
"""
import sys, json, os, gc
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

# Import baseline trades from dplus_4_pilot
src = (ROOT / "scripts/dplus_4_pilot.py").read_text().split("\nout = {}")[0]
ns = {"__file__": str(ROOT / "scripts/dplus_4_pilot.py")}
exec(src, ns)
base = ns["base"]

# Load VIX
vix_path = ROOT / "data/external/VIX_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df["date"] = pd.to_datetime(vix_df["DATE"]).dt.date
vix_dict = dict(zip(vix_df["date"], vix_df["CLOSE"]))

# Map all intraday trades
all_trades = []
for t in base:
    day = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
    vix = vix_dict.get(day, 18.0)
    cont = t.get("cont", False)
    sleeve = t["sleeve"]
    is_crabel = sleeve.startswith("AG_CRABEL")
    
    all_trades.append({
        "day": day,
        "entry_ts": t["entry_ts"],
        "exit_ts": t["exit_ts"],
        "sleeve": sleeve,
        "net_1c": t["net"],
        "mae_1c": t.get("mae", 0.0),
        "vix": vix,
        "cont": cont,
        "is_crabel": is_crabel,
    })

df_all = pd.DataFrame(all_trades)
all_days = sorted(df_all["day"].unique())
days_dict = {d: group.sort_values("entry_ts") for d, group in df_all.groupby("day")}

# Let's test different time horizons (60d, 90d, 120d, 150d, 180d)
# and different scale-out targets (e.g. runner to 140 pts or 150 pts on high momentum days)
def evaluate_pass_curve(runner_target_boost=1.0, max_eval_days=90):
    total_starts = len(all_days) - max_eval_days
    passed = 0
    ruined = 0
    pass_days = []
    
    for i in range(total_starts):
        cum = 0.0
        hwm = 0.0
        busted = False
        pass_run = False
        max_d = -9999.0
        
        for step in range(max_eval_days):
            d = all_days[i + step]
            vix = vix_dict.get(d, 18.0)
            if vix < 15.0 or d not in days_dict:
                continue
            group_sorted = days_dict[d]
            day_pnl = 0.0
            day_mae = 0.0
            current_floor = min(0.0, -2000.0 + hwm)
            
            for _, tr in group_sorted.iterrows():
                # Skip fades
                if tr["is_crabel"] and not tr["cont"]: continue
                size = 6 if tr["is_crabel"] else 3
                
                # Apply boost to positive runner days
                pnl = tr["net_1c"] * size
                if pnl > 100.0:
                    pnl *= runner_target_boost
                    
                mae = tr["mae_1c"] * size
                if (day_pnl + mae) < day_mae:
                    day_mae = day_pnl + mae
                day_pnl += pnl
                if day_pnl >= 1750.0 or day_pnl <= -400.0:
                    break
                    
            if day_pnl <= -1000.0 or day_mae <= -1000.0 or (cum + day_mae) <= current_floor:
                busted = True
                break
            cum += day_pnl
            if cum > hwm:
                hwm = cum
                current_floor = min(0.0, -2000.0 + hwm)
            if cum <= current_floor:
                busted = True
                break
            if day_pnl > max_d:
                max_d = day_pnl
            if cum >= 4000.0 and max_d <= 2000.0:
                pass_run = True
                passed += 1
                pass_days.append(step + 1)
                break
        if busted:
            ruined += 1
            
    p_arr = np.array(pass_days) if pass_days else np.array([0])
    pass_pct = passed / total_starts * 100
    ruin_pct = ruined / total_starts * 100
    odds = pass_pct / max(0.01, ruin_pct)
    
    print(f"Horizon: {max_eval_days}d | Boost: {runner_target_boost:.1f}x")
    print(f"  PASS RATE: {pass_pct:.1f}% ({passed}/{total_starts}) | Ruin: {ruin_pct:.1f}% | Odds: {odds:.2f}x")
    if passed > 0:
        print(f"  Median: {np.median(p_arr):.1f}d | p25: {np.percentile(p_arr, 25):.1f}d | Min: {p_arr.min()}d")
    print()
    return pass_pct, ruin_pct

print("Testing Horizon & Runner Boost Curve:")
for h in [60, 90, 110, 130, 150, 170, 185, 200, 220, 250]:
    evaluate_pass_curve(1.0, h)
