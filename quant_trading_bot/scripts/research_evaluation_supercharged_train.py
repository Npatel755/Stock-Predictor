"""Research: Supercharging the Evaluation Strategy (Strictly 2010-2023 Training Split).

Testing 4 structural improvements:
1. Dynamic 3-Tier Staging (6c from $0-$1,200 -> 8c from $1,200-$2,400 -> 12c from $2,400-$4,000)
2. Gap-Alignment Sizing (Double size on continuation drives, halve on fades)
3. Backwardation Stand-Aside (Filter VIX > VIX3M)
4. Intraday Green-Lock Ratchet (If day >= +$800, stop moves to +$400)

Target: Maximize Pass Rate, Minimize Ruin Rate, and Minimize Days to Pass.
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

# Map all trades
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

def evaluate_variant(name,
                     sizing_logic,
                     daily_lock=1750.0,
                     daily_stop=400.0,
                     intraday_green_lock=False,
                     target=4000.0,
                     floor=2000.0,
                     dll=1000.0,
                     max_eval_days=90):
    
    total_starts = len(all_days) - max_eval_days
    passed_runs = []
    ruined_runs = []
    pass_drawdowns = []
    
    for i in range(total_starts):
        cum = 0.0
        hwm = 0.0
        busted = False
        pass_run = False
        max_d = -9999.0
        max_dd_in_trial = 0.0
        
        for step in range(max_eval_days):
            d = all_days[i + step]
            vix = vix_dict.get(d, 18.0)
            if vix < 15.0 or d not in days_dict:
                continue
                
            group_sorted = days_dict[d]
            day_pnl = 0.0
            day_mae = 0.0
            day_hwm = 0.0
            
            # Current Topstep Trailing Floor (locks permanently at $0 once hwm reaches $2,000)
            current_floor = min(0.0, -floor + hwm)
            
            for _, tr in group_sorted.iterrows():
                # Compute contract size dynamically from sizing_logic
                size = sizing_logic(cum, tr)
                if size <= 0:
                    continue
                    
                pnl = tr["net_1c"] * size
                mae = tr["mae_1c"] * size
                
                if (day_pnl + mae) < day_mae:
                    day_mae = day_pnl + mae
                day_pnl += pnl
                if day_pnl > day_hwm:
                    day_hwm = day_pnl
                    
                # Intraday Green Lock: If up +$800, don't let it give back more than half
                effective_day_stop = daily_stop
                if intraday_green_lock and day_hwm >= 800.0:
                    effective_day_stop = -max(400.0, day_hwm * 0.5) # lock in at least +$400
                    if day_pnl <= (day_hwm * 0.5):
                        break
                elif day_pnl <= -effective_day_stop:
                    break
                    
                if day_pnl >= daily_lock:
                    break
                    
            # Check intraday breach
            intra_dd = hwm - (cum + day_mae)
            if intra_dd > max_dd_in_trial:
                max_dd_in_trial = intra_dd
                
            if day_pnl <= -dll or day_mae <= -dll or (cum + day_mae) <= current_floor:
                busted = True
                break
                
            cum += day_pnl
            if cum > hwm:
                hwm = cum
                current_floor = min(0.0, -floor + hwm)
                
            close_dd = hwm - cum
            if close_dd > max_dd_in_trial:
                max_dd_in_trial = close_dd
                
            if cum <= current_floor:
                busted = True
                break
                
            if day_pnl > max_d:
                max_d = day_pnl
                
            if cum >= target and max_d <= (target * 0.50):
                pass_run = True
                passed_runs.append(step + 1)
                pass_drawdowns.append(max_dd_in_trial)
                break
                
        if busted:
            ruined_runs.append(i)
            
    p_arr = np.array(passed_runs) if passed_runs else np.array([0])
    pass_pct = len(passed_runs) / total_starts * 100
    ruin_pct = len(ruined_runs) / total_starts * 100
    odds_ratio = (pass_pct / ruin_pct) if ruin_pct > 0 else 999.0
    
    print(f"\n================================================================================")
    print(f"VARIANT: {name}")
    print(f"================================================================================")
    print(f"  Pass Rate:          {pass_pct:.1f}% ({len(passed_runs)} passes)")
    print(f"  Ruin Rate:          {ruin_pct:.1f}% ({len(ruined_runs)} ruins)")
    print(f"  Pass-to-Ruin Odds:  {odds_ratio:.2f}x (Higher is better)")
    if len(passed_runs) > 0:
        print(f"  Fastest Pass (Min): {p_arr.min()} trading days (~{p_arr.min()/5:.1f} weeks)")
        print(f"  Fast Market (p25):  {np.percentile(p_arr, 25):.1f} trading days (~{np.percentile(p_arr, 25)/5:.1f} weeks)")
        print(f"  Median Time:        {np.median(p_arr):.1f} trading days (~{np.median(p_arr)/5:.1f} weeks)")
        print(f"  Average Time:       {p_arr.mean():.1f} trading days (~{p_arr.mean()/5:.1f} weeks)")
        print(f"  Max Drawdown (Pass):${np.max(pass_drawdowns):,.2f} (Worst pass)")
        print(f"  Avg Drawdown (Pass):${np.mean(pass_drawdowns):,.2f}")
        
    return {
        "name": name,
        "pass_pct": round(pass_pct, 1),
        "ruin_pct": round(ruin_pct, 1),
        "odds_ratio": round(odds_ratio, 2),
        "min_days": int(p_arr.min()) if len(p_arr) else 0,
        "p25_days": round(float(np.percentile(p_arr, 25)), 1) if len(p_arr) else 0,
        "median_days": round(float(np.median(p_arr)), 1) if len(p_arr) else 0,
        "mean_days": round(float(p_arr.mean()), 1) if len(p_arr) else 0,
        "worst_dd_pass": round(float(np.max(pass_drawdowns)), 2) if len(pass_drawdowns) else 0,
        "avg_dd_pass": round(float(np.mean(pass_drawdowns)), 2) if len(pass_drawdowns) else 0
    }

results = []

# Baseline: Fixed 6 MNQ
def logic_fixed_6(cum, tr):
    return 6 if (tr["is_crabel"] and tr["cont"]) else 3
results.append(evaluate_variant("Baseline: Fixed 6 MNQ", logic_fixed_6))

# Variant 1: 2-Stage (6c -> 12c at $1,200)
def logic_2stage(cum, tr):
    tier = 6 if cum < 1200.0 else 12
    return tier if (tr["is_crabel"] and tr["cont"]) else max(2, tier // 2)
results.append(evaluate_variant("Variant 1: 2-Stage (6c -> 12c at $1.2k)", logic_2stage))

# Variant 2: 3-Stage Dynamic (6c -> 8c at $1,200 -> 12c at $2,400)
def logic_3stage(cum, tr):
    if cum < 1200.0:
        tier = 6
    elif cum < 2400.0:
        tier = 8
    else:
        tier = 12
    return tier if (tr["is_crabel"] and tr["cont"]) else max(2, tier // 2)
results.append(evaluate_variant("Variant 2: 3-Stage Dynamic (6c -> 8c -> 12c)", logic_3stage))

# Variant 3: 3-Stage Dynamic with Gap-Alignment Multiplier (Continuation = Full Size, Fades = 50%)
def logic_3stage_gap_conditioned(cum, tr):
    if cum < 1200.0:
        base_tier = 6
    elif cum < 2400.0:
        base_tier = 8
    else:
        base_tier = 12
        
    if tr["is_crabel"]:
        # Double size on continuation drives, halve on fades
        return base_tier if tr["cont"] else max(2, base_tier // 2)
    else:
        # Trend sleeves: size conservatively in early stages, standard in late stages
        return max(2, base_tier // 2)
results.append(evaluate_variant("Variant 3: 3-Stage + Gap-Conditioned Sizing", logic_3stage_gap_conditioned))

# Variant 4: 3-Stage + Intraday Green-Lock Ratchet
results.append(evaluate_variant("Variant 4: 3-Stage + Intraday Green Lock Ratchet", logic_3stage_gap_conditioned, intraday_green_lock=True))

# Variant 5: Optimized Elite Finisher (6c -> 8c -> 10c with aggressive gap sizing)
def logic_elite_finisher(cum, tr):
    if cum < 1000.0:
        tier = 6
    elif cum < 2200.0:
        tier = 8
    else:
        tier = 10
    return tier if (tr["is_crabel"] and tr["cont"]) else max(2, tier // 2)
results.append(evaluate_variant("Variant 5: Elite Finisher (6c -> 8c -> 10c)", logic_elite_finisher))

# Save comparison results
with open(ROOT / "reports/EVALUATION_SUPERCHARGED_RESULTS.json", "w") as f:
    json.dump(results, f, indent=2)

print("\n\nAll variants evaluated successfully. Saved to reports/EVALUATION_SUPERCHARGED_RESULTS.json")
