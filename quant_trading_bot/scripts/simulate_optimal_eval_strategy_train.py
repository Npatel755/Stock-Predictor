"""Optimal Evaluation Strategy: Volatility-Conditioned Dual-Speed Architecture.
STRICTLY 2010-2023 TRAINING DATA ONLY.
Zero access to Validation (2024-2025) or Blind Test (2026).
"""
import sys, json, gc
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

# Import baseline trades
src = (ROOT / "scripts/dplus_4_pilot.py").read_text().split("\nout = {}")[0]
ns = {"__file__": str(ROOT / "scripts/dplus_4_pilot.py")}
exec(src, ns)
base = ns["base"]

# Free up unneeded namespace items
del ns, src
gc.collect()

# Load VIX data
vix_path = ROOT / "data/external/VIX_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df["date"] = pd.to_datetime(vix_df["DATE"]).dt.date
vix_dict = dict(zip(vix_df["date"], vix_df["CLOSE"]))

# Map trades with VIX and gap
trades_processed = []
for t in base:
    day = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
    vix = vix_dict.get(day, 18.0)
    cont = t.get("cont", False)
    crabel = t.get("sleeve", "").startswith("AG_CRABEL")
    trades_processed.append({
        "day": day,
        "sleeve": t["sleeve"],
        "net_1c": t["net"],
        "mae_1c": t.get("mae", 0.0),
        "vix": vix,
        "cont": cont,
        "crabel": crabel,
    })

df_tp = pd.DataFrame(trades_processed)
all_days = sorted(df_tp["day"].unique())
print(f"Total trading days with trades: {len(all_days):,}")

def simulate_strategy(mode="blind_sprint", n_contracts=6, daily_cap=900.0, daily_stop=400.0):
    daily_stats = {}
    for d in all_days:
        day_trades = df_tp[df_tp["day"] == d]
        if len(day_trades) == 0:
            daily_stats[d] = {"net": 0.0, "mae": 0.0}
            continue
            
        day_pnl = 0.0
        day_mae = 0.0
        
        for _, tr in day_trades.iterrows():
            if mode == "blind_sprint":
                size = n_contracts
            elif mode == "dual_speed":
                # High-edge sprint conditions:
                # 1. Crabel gap continuation with VIX >= 18 -> Size n_contracts
                # 2. VIX >= 16 -> Size half
                # 3. Else 1 contract
                if tr["crabel"] and tr["cont"] and tr["vix"] >= 18.0:
                    size = n_contracts
                elif tr["vix"] >= 16.0:
                    size = max(2, n_contracts // 2)
                else:
                    size = 1
            else:
                size = 1
                
            trade_pnl = tr["net_1c"] * size
            trade_mae = tr["mae_1c"] * size
            
            if (day_pnl + trade_mae) < day_mae:
                day_mae = day_pnl + trade_mae
            day_pnl += trade_pnl
            
            # Circuit breakers
            if day_pnl >= daily_cap:
                break
            if day_pnl <= -daily_stop:
                break
                
        daily_stats[d] = {"net": day_pnl, "mae": day_mae}
        
    return daily_stats

print("=" * 80)
print("EVALUATION ARCHITECTURE COMPARISON (14-YEAR TRAINING DATA 2010-2023)")
print("Target = $4,000 in 5 Days (1 Week) | Floor = $2,000 | DLL = $1,000")
print("=" * 80)

def audit_eval_performance(daily_stats, label, target=4000.0, floor=2000.0, dll=1000.0):
    total_windows = len(all_days) - 4
    clean_pass = 0
    inconsistent_pass = 0
    ruined = 0
    ruined_trailing = 0
    ruined_dll = 0
    neither = 0
    max_day_limit = target * 0.50
    
    for i in range(total_windows):
        w_days = all_days[i : i + 5]
        cum_pnl = 0.0
        hwm = 0.0
        busted = False
        max_day = -9999.0
        
        for d in w_days:
            dp = daily_stats[d]["net"]
            dm = daily_stats[d]["mae"]
            
            if dp <= -dll or dm <= -dll:
                ruined_dll += 1
                busted = True
                break
                
            if (hwm - (cum_pnl + dm)) >= floor or (cum_pnl + dm) <= -floor:
                ruined_trailing += 1
                busted = True
                break
                
            cum_pnl += dp
            if cum_pnl > hwm:
                hwm = cum_pnl
                
            if (hwm - cum_pnl) >= floor or cum_pnl <= -floor:
                ruined_trailing += 1
                busted = True
                break
                
            if dp > max_day:
                max_day = dp
                
            if cum_pnl >= target:
                break
                
        if busted:
            ruined += 1
        elif cum_pnl >= target:
            if max_day <= max_day_limit:
                clean_pass += 1
            else:
                inconsistent_pass += 1
        else:
            neither += 1
            
    total_ruin = ruined_dll + ruined_trailing
    pct_clean = (clean_pass / total_windows) * 100
    pct_any = ((clean_pass + inconsistent_pass) / total_windows) * 100
    pct_ruin = (total_ruin / total_windows) * 100
    pct_neither = (neither / total_windows) * 100
    
    print(f"\n{label}:")
    print(f"  Clean Pass Rate (50% rule): {pct_clean:.2f}% ({clean_pass} weeks)")
    print(f"  Any Pass Rate:              {pct_any:.2f}% ({clean_pass + inconsistent_pass} weeks)")
    print(f"  Account Ruin Rate:          {pct_ruin:.2f}% ({total_ruin} weeks: DLL={ruined_dll}, Trailing DD={ruined_trailing})")
    print(f"  Account Safe (End < $4k):   {pct_neither:.2f}% ({neither} weeks)")
    if clean_pass > 0:
        print(f"  Ruin-to-Clean-Pass Ratio:   {total_ruin / clean_pass:.1f}x")
    return {
        "label": label,
        "clean_pass": clean_pass,
        "pct_clean": round(pct_clean, 2),
        "total_ruin": total_ruin,
        "pct_ruin": round(pct_ruin, 2),
        "neither": neither,
        "pct_neither": round(pct_neither, 2),
    }

r1 = audit_eval_performance(simulate_strategy("blind_sprint", n_contracts=6, daily_cap=900, daily_stop=400), "Blind Sprint (Fixed 6 Contracts, No Gating)")
r2 = audit_eval_performance(simulate_strategy("blind_sprint", n_contracts=8, daily_cap=900, daily_stop=400), "Blind Sprint (Fixed 8 Contracts, No Gating)")
r3 = audit_eval_performance(simulate_strategy("blind_sprint", n_contracts=10, daily_cap=900, daily_stop=400), "Blind Sprint (Fixed 10 Contracts [1 Mini], No Gating)")
r4 = audit_eval_performance(simulate_strategy("dual_speed", n_contracts=6, daily_cap=900, daily_stop=400), "Dual-Speed Architecture (Sprint 6c on High VIX + Gap, 2c Base, $900 Lock, $400 Stop)")
r5 = audit_eval_performance(simulate_strategy("dual_speed", n_contracts=8, daily_cap=900, daily_stop=400), "Dual-Speed Architecture (Sprint 8c on High VIX + Gap, 2c Base, $900 Lock, $400 Stop)")
r6 = audit_eval_performance(simulate_strategy("dual_speed", n_contracts=10, daily_cap=900, daily_stop=400), "Dual-Speed Architecture (Sprint 10c on High VIX + Gap, 2c Base, $900 Lock, $400 Stop)")

print("\nSimulation complete.")
