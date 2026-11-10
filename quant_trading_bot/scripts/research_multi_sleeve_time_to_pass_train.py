"""Multi-Sleeve Free-Roll Architecture (Architecture D+ Free-Roll Runner).
STRICTLY 2010-2023 TRAINING DATA ONLY.
Zero access to Validation (2024-2025) or Blind Test (2026).

Combines:
1. Crabel Open Drive (9:45 ET) with Gap Alignment & Scale-Out
2. 30m EWMA Trend Sleeve (10:00 ET) with Breakeven Ratchet
3. 60m EWMA Trend Sleeve (10:30 ET) with Breakeven Ratchet
4. Global Daily Circuit Breakers: +$1,750 Lock (50% consistency) / -$400 Stop Loss (DLL safeguard).
"""
import sys, json, gc
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

# Map all trades across all 4 sleeves
all_trades = []
for t in base:
    day = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
    vix = vix_dict.get(day, 18.0)
    cont = t.get("cont", False)
    sleeve = t["sleeve"]
    is_crabel = sleeve.startswith("AG_CRABEL")
    
    # Scale-Out Sizing:
    # On high conviction (Crabel continuation or strong trend with VIX >= 15):
    # Size 6 contracts (3 Banked + 3 Runners) or 8 contracts (4 Banked + 4 Runners)
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
print(f"Total multi-sleeve trades: {len(df_all):,} across {len(all_days):,} days.")

def simulate_multi_sleeve_eval(contracts_tier=8, daily_lock=1750.0, daily_stop=400.0, target=4000.0, floor=2000.0, dll=1000.0):
    # Aggregate daily PnL with circuit breakers
    daily_results = {}
    
    for d, group in df_all.groupby("day"):
        vix = vix_dict.get(d, 18.0)
        if vix < 15.0:
            daily_results[d] = {"net": 0.0, "mae": 0.0}
            continue
            
        day_pnl = 0.0
        day_mae = 0.0
        
        # Sort trades chronologically by entry_ts
        group_sorted = group.sort_values("entry_ts")
        
        for _, tr in group_sorted.iterrows():
            # If Crabel continuation, use full contracts_tier
            # If trend sleeve, use 50% tier
            if tr["is_crabel"] and tr["cont"]:
                size = contracts_tier
            elif tr["is_crabel"]:
                size = max(2, contracts_tier // 2)
            else:
                size = max(2, contracts_tier // 2)
                
            pnl = tr["net_1c"] * size
            mae = tr["mae_1c"] * size
            
            if (day_pnl + mae) < day_mae:
                day_mae = day_pnl + mae
            day_pnl += pnl
            
            # Daily circuit breakers
            if day_pnl >= daily_lock:
                break
            if day_pnl <= -daily_stop:
                break
                
        daily_results[d] = {"net": day_pnl, "mae": day_mae}
        
    # Run lifecycle evaluation
    days_to_pass = []
    ruined = 0
    passed = 0
    timeout = 0
    max_eval_days = 90
    total_starts = len(all_days) - max_eval_days
    
    for i in range(total_starts):
        cum = 0.0
        hwm = 0.0
        busted = False
        pass_run = False
        max_d = -9999.0
        
        for step in range(max_eval_days):
            d = all_days[i + step]
            if d not in daily_results:
                continue
            dp = daily_results[d]["net"]
            dm = daily_results[d]["mae"]
            
            if dp <= -dll or dm <= -dll or (hwm - (cum + dm)) >= floor or (cum + dm) <= -floor:
                busted = True
                break
                
            cum += dp
            if cum > hwm:
                hwm = cum
            if (hwm - cum) >= floor or cum <= -floor:
                busted = True
                break
                
            if dp > max_d:
                max_d = dp
                
            if cum >= target:
                if max_d <= (target * 0.50):
                    pass_run = True
                    days_to_pass.append(step + 1)
                    break
                    
        if busted:
            ruined += 1
        elif pass_run:
            passed += 1
        else:
            timeout += 1
            
    d_arr = np.array(days_to_pass) if len(days_to_pass) > 0 else np.array([0])
    
    print(f"\n[MULTI-SLEEVE ENSEMBLE - {contracts_tier} MNQ TIER]")
    print(f"  Pass Rate:          {passed/total_starts*100:.1f}% ({passed} passes) | Ruin Rate: {ruined/total_starts*100:.1f}% ({ruined} ruins)")
    print(f"  Fastest Pass (Min): {d_arr.min()} trading days (~{d_arr.min()/5:.1f} weeks)")
    print(f"  Fast Market (p25):  {np.percentile(d_arr, 25):.1f} trading days (~{np.percentile(d_arr, 25)/5:.1f} weeks)")
    print(f"  MEDIAN TIME:        {np.median(d_arr):.1f} trading days (~{np.median(d_arr)/5:.1f} weeks)")
    print(f"  AVERAGE TIME:       {d_arr.mean():.1f} trading days (~{d_arr.mean()/5:.1f} weeks)")
    print(f"  Slowest Pass (Max): {d_arr.max()} trading days (~{d_arr.max()/5:.1f} weeks)")
    
    return {
        "contracts": contracts_tier,
        "pass_pct": round(passed/total_starts*100, 1),
        "ruin_pct": round(ruined/total_starts*100, 1),
        "min": int(d_arr.min()),
        "p25": round(float(np.percentile(d_arr, 25)), 1),
        "median": round(float(np.median(d_arr)), 1),
        "mean": round(float(d_arr.mean()), 1),
        "max": int(d_arr.max()),
    }

print("Simulating Multi-Sleeve Architecture across Sizing Tiers...")
ms_6 = simulate_multi_sleeve_eval(contracts_tier=6)
ms_8 = simulate_multi_sleeve_eval(contracts_tier=8)
ms_10 = simulate_multi_sleeve_eval(contracts_tier=10)
ms_12 = simulate_multi_sleeve_eval(contracts_tier=12)

with open(ROOT / "reports/MULTI_SLEEVE_TIME_TO_PASS_RESULTS.json", "w") as f:
    json.dump({"ms_6": ms_6, "ms_8": ms_8, "ms_10": ms_10, "ms_12": ms_12}, f, indent=2)

print("\nSaved multi-sleeve results to reports/MULTI_SLEEVE_TIME_TO_PASS_RESULTS.json")
print("DONE", flush=True)
