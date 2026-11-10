"""Evaluate All Candidate Architectures Strictly on 14-Year Training Split (2010-2023).
METHODOLOGICAL INVARIANT:
- 100% RESTRICTED TO TRAINING DATA (2010-06-01 to 2023-12-31).
- ZERO TUNING, ZERO LOOKUPS ON VALIDATION (2024-2025) OR BLIND TEST (2026).
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")

# Load VIX
vix_path = ROOT / "data/external/VIX_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df["date"] = pd.to_datetime(vix_df["DATE"]).dt.date
vix_dict = dict(zip(vix_df["date"], vix_df["CLOSE"]))

# Load cached training trades
with open(ROOT / "data/processed/crabel_train_adaptive.json") as f:
    crabel_ad = json.load(f)
with open(ROOT / "data/processed/crabel_train_runner120.json") as f:
    crabel_120 = json.load(f)
with open(ROOT / "data/processed/overnight_trades_train.json") as f:
    on_raw = json.load(f)

# Normalize all keys to YYYY-MM-DD
crabel_ad_clean = {k[:10]: v for k, v in crabel_ad.items()}
crabel_120_clean = {k[:10]: v for k, v in crabel_120.items()}
on_trades_clean = {}
for tr in on_raw:
    d = tr["exit_day"][:10]
    mae_pts = float(tr["mae_pts"])
    pnl_1c = float(tr["pnl_1c"])
    if mae_pts <= -20.0:
        pnl_1c = -20.0 * 2.0 - 2.60 # stopped at -20 pts
        mae_1c = -20.0 * 2.0
    else:
        mae_1c = mae_pts * 2.0
    on_trades_clean[d] = {
        "net_1c": pnl_1c,
        "mae_1c": mae_1c,
        "traded": True
    }

# All training session dates normalized
all_sessions = sorted(list(crabel_ad_clean.keys()))
print(f"Total training sessions: {len(all_sessions)}")
print(f"Crabel active sessions: {sum(1 for v in crabel_120_clean.values() if v['traded'])}")
print(f"Overnight active sessions: {len(on_trades_clean)}")

STATIC_FLOOR = -2000.0
DLL_LIMIT = -1000.0
DAILY_LOCK = 1500.0

def run_simulation(
    name,
    trade_source,           # function returning list of trades for a date
    base_sz=6,
    cushion_sz=8,
    finisher_sz=10,
    cushion_thr=1500.0,
    finisher_thr=2600.0,
    def_thr=-250.0,
    def_sz=3,
    min_vix=0.0,
    max_sessions=150
):
    total = len(all_sessions) - max_sessions
    passed = 0
    ruined = 0
    timeouts = 0
    dll_breaches = 0
    pass_sess = []
    pass_tr_days = []
    max_dds = []
    
    for i in range(total):
        start_day = all_sessions[i]
        if vix_dict.get(pd.to_datetime(start_day).date(), 18.0) < min_vix:
            continue
            
        cum = 0.0
        hwm = 0.0
        busted = False
        pass_run = False
        peak_dd = 0.0
        tr_days = 0
        
        for step in range(max_sessions):
            d = all_sessions[i + step]
            tr_list = trade_source(d)
            if not tr_list:
                continue
                
            active_today = False
            day_pnl = 0.0
            day_mae = 0.0
            
            for tr in tr_list:
                active_today = True
                
                # Dynamic Cushion Sizing
                if cum <= def_thr:
                    sz = def_sz
                elif cum >= finisher_thr:
                    sz = finisher_sz
                elif cum >= cushion_thr:
                    sz = cushion_sz
                else:
                    sz = base_sz
                    
                pnl = tr["net_1c"] * sz
                mae = tr["mae_1c"] * sz
                
                if (day_pnl + mae) < day_mae:
                    day_mae = day_pnl + mae
                day_pnl += pnl
                
                # Daily consistency lock
                if day_pnl >= DAILY_LOCK:
                    day_pnl = DAILY_LOCK
                    break
                    
            if not active_today:
                continue
                
            tr_days += 1
            
            # Check Daily Loss Limit (-$1,000)
            if day_pnl <= DLL_LIMIT or day_mae <= DLL_LIMIT:
                busted = True
                dll_breaches += 1
                break
                
            # Check Static Floor during session
            if (cum + day_mae) <= STATIC_FLOOR:
                busted = True
                break
                
            cum += day_pnl
            current_dd = hwm - cum
            if current_dd > peak_dd: peak_dd = current_dd
            if cum > hwm: hwm = cum
            
            if cum <= STATIC_FLOOR:
                busted = True
                break
                
            if cum >= 4000.0 and day_pnl <= 2000.0:
                pass_run = True
                passed += 1
                pass_sess.append(step + 1)
                pass_tr_days.append(tr_days)
                max_dds.append(peak_dd)
                break
                
        if busted and not pass_run:
            ruined += 1
        elif not pass_run and not busted:
            timeouts += 1
            
    tot_evals = passed + ruined
    p_pct = (passed / max(1, tot_evals)) * 100
    r_pct = (ruined / max(1, tot_evals)) * 100
    
    mean_s = np.mean(pass_sess) if passed else 999.0
    med_s = np.median(pass_sess) if passed else 999.0
    p25_s = np.percentile(pass_sess, 25) if passed else 999.0
    
    mean_t = np.mean(pass_tr_days) if passed else 999.0
    med_t = np.median(pass_tr_days) if passed else 999.0
    p25_t = np.percentile(pass_tr_days, 25) if passed else 999.0
    min_t = np.min(pass_tr_days) if passed else 999
    
    avg_dd = np.mean(max_dds) if passed else 999.0
    
    print(f"{name:60s} | TR MEAN: {mean_t:4.1f}d | MED: {med_t:4.1f}d | P25: {p25_t:4.1f}d | MIN: {min_t:2d}d | Pass: {p_pct:5.1f}% | Ruin: {r_pct:4.1f}% | DLL: {dll_breaches:2d} | DD: ${avg_dd:.2f}")
    return {
        "name": name,
        "passed": passed, "ruined": ruined, "timeouts": timeouts, "dll_breaches": dll_breaches,
        "pass_pct": round(p_pct, 1), "ruin_pct": round(r_pct, 1),
        "mean_sessions": round(mean_s, 1), "med_sessions": round(med_s, 1), "p25_sessions": round(p25_s, 1),
        "mean_trade_days": round(mean_t, 1), "med_trade_days": round(med_t, 1), "p25_trade_days": round(p25_t, 1),
        "min_trade_days": int(min_t), "avg_dd": round(avg_dd, 2)
    }

# Define trade generator sources
# 1. Crabel Adaptive
def src_crabel_ad(d):
    tr = crabel_ad_clean.get(d, None)
    return [tr] if tr and tr["traded"] else []

# 2. Crabel Runner120
def src_crabel_120(d):
    tr = crabel_120_clean.get(d, None)
    return [tr] if tr and tr["traded"] else []

# 3. Duo 1/Day: Crabel 120 priority > Overnight Dip fallback
def src_duo_1day_120(d):
    tr_c = crabel_120_clean.get(d, None)
    if tr_c and tr_c["traded"]:
        return [tr_c]
    tr_o = on_trades_clean.get(d, None)
    if tr_o and tr_o["traded"]:
        return [tr_o]
    return []

# 4. Duo 1/Day: Crabel Adaptive priority > Overnight Dip fallback
def src_duo_1day_ad(d):
    tr_c = crabel_ad_clean.get(d, None)
    if tr_c and tr_c["traded"]:
        return [tr_c]
    tr_o = on_trades_clean.get(d, None)
    if tr_o and tr_o["traded"]:
        return [tr_o]
    return []

# 5. Duo Double-Dip: Overnight + Crabel (Max 2 trades, but if overnight loses, skip crabel!)
def src_duo_doubledip(d):
    res = []
    tr_o = on_trades_clean.get(d, None)
    tr_c = crabel_120_clean.get(d, None)
    
    if tr_o and tr_o["traded"]:
        res.append(tr_o)
        if tr_o["net_1c"] < 0:
            return res # stop for the day to protect DLL
            
    if tr_c and tr_c["traded"]:
        res.append(tr_c)
        
    return res

print("\n" + "="*125)
print("COMPREHENSIVE TRAINING EVALUATION GRID (STRICTLY TRAINING SPLIT 2010-2023)")
print("="*125)

grid_results = []

# Section 1: Single Sleeve Crabel
grid_results.append(run_simulation("1. Crabel Adaptive: Static 6 MNQ", src_crabel_ad, base_sz=6, cushion_sz=6, finisher_sz=6))
grid_results.append(run_simulation("2. Crabel Adaptive: Gentle Fortress (6c -> 8c @ $1.5k, Def 3c)", src_crabel_ad, base_sz=6, cushion_sz=8, finisher_sz=8, cushion_thr=1500.0, finisher_thr=1500.0, def_thr=-250.0, def_sz=3))
grid_results.append(run_simulation("3. Crabel Adaptive: Asym Finisher (6c -> 8c @ $1.5k -> 10c @ $2.6k, Def 3c)", src_crabel_ad, base_sz=6, cushion_sz=8, finisher_sz=10, cushion_thr=1500.0, finisher_thr=2600.0, def_thr=-250.0, def_sz=3))

grid_results.append(run_simulation("4. Crabel Runner120: Static 6 MNQ", src_crabel_120, base_sz=6, cushion_sz=6, finisher_sz=6))
grid_results.append(run_simulation("5. Crabel Runner120: Gentle Fortress (6c -> 8c @ $1.5k, Def 3c)", src_crabel_120, base_sz=6, cushion_sz=8, finisher_sz=8, cushion_thr=1500.0, finisher_thr=1500.0, def_thr=-250.0, def_sz=3))
grid_results.append(run_simulation("6. Crabel Runner120: Asym Finisher (6c -> 8c @ $1.5k -> 10c @ $2.6k, Def 3c)", src_crabel_120, base_sz=6, cushion_sz=8, finisher_sz=10, cushion_thr=1500.0, finisher_thr=2600.0, def_thr=-250.0, def_sz=3))
grid_results.append(run_simulation("7. Crabel Runner120: Sprint Finisher (6c -> 9c @ $1.2k -> 12c @ $2.5k, Def 3c)", src_crabel_120, base_sz=6, cushion_sz=9, finisher_sz=12, cushion_thr=1200.0, finisher_thr=2500.0, def_thr=-250.0, def_sz=3))

# Section 2: Duo-Sleeve 1/Day (Crabel > Overnight)
grid_results.append(run_simulation("8. Duo 1/Day (Crabel 120 > OVN): Static 6 MNQ", src_duo_1day_120, base_sz=6, cushion_sz=6, finisher_sz=6))
grid_results.append(run_simulation("9. Duo 1/Day (Crabel 120 > OVN): Gentle Fortress (6c -> 8c @ $1.5k, Def 3c)", src_duo_1day_120, base_sz=6, cushion_sz=8, finisher_sz=8, cushion_thr=1500.0, finisher_thr=1500.0, def_thr=-250.0, def_sz=3))
grid_results.append(run_simulation("10. Duo 1/Day (Crabel 120 > OVN): Asym Finisher (6c -> 8c @ $1.5k -> 10c @ $2.6k, Def 3c)", src_duo_1day_120, base_sz=6, cushion_sz=8, finisher_sz=10, cushion_thr=1500.0, finisher_thr=2600.0, def_thr=-250.0, def_sz=3))
grid_results.append(run_simulation("11. Duo 1/Day (Crabel 120 > OVN): Sprint Finisher (6c -> 9c @ $1.2k -> 12c @ $2.5k, Def 3c)", src_duo_1day_120, base_sz=6, cushion_sz=9, finisher_sz=12, cushion_thr=1200.0, finisher_thr=2500.0, def_thr=-250.0, def_sz=3))

# Section 3: Duo-Sleeve Double-Dip (Overnight + Crabel, skip Crabel if Overnight loses)
grid_results.append(run_simulation("12. Duo Double-Dip (Safe Filter): Static 6 MNQ", src_duo_doubledip, base_sz=6, cushion_sz=6, finisher_sz=6))
grid_results.append(run_simulation("13. Duo Double-Dip (Safe Filter): Gentle Fortress (6c -> 8c @ $1.5k, Def 3c)", src_duo_doubledip, base_sz=6, cushion_sz=8, finisher_sz=8, cushion_thr=1500.0, finisher_thr=1500.0, def_thr=-250.0, def_sz=3))
grid_results.append(run_simulation("14. Duo Double-Dip (Safe Filter): Asym Finisher (6c -> 8c @ $1.5k -> 10c @ $2.6k, Def 3c)", src_duo_doubledip, base_sz=6, cushion_sz=8, finisher_sz=10, cushion_thr=1500.0, finisher_thr=2600.0, def_thr=-250.0, def_sz=3))
grid_results.append(run_simulation("15. Duo Double-Dip (Safe Filter): Sprint Finisher (6c -> 9c @ $1.2k -> 12c @ $2.5k, Def 3c)", src_duo_doubledip, base_sz=6, cushion_sz=9, finisher_sz=12, cushion_thr=1200.0, finisher_thr=2500.0, def_thr=-250.0, def_sz=3))

# Section 4: High-Volatility Timing (VIX >= 18)
grid_results.append(run_simulation("16. Duo 1/Day High-Vol (VIX >= 18, 6c -> 8c -> 10c, Def 3c)", src_duo_1day_120, base_sz=6, cushion_sz=8, finisher_sz=10, cushion_thr=1500.0, finisher_thr=2600.0, def_thr=-250.0, def_sz=3, min_vix=18.0))
grid_results.append(run_simulation("17. Duo Double-Dip High-Vol (VIX >= 18, 6c -> 9c -> 12c, Def 3c)", src_duo_doubledip, base_sz=6, cushion_sz=9, finisher_sz=12, cushion_thr=1200.0, finisher_thr=2500.0, def_thr=-250.0, def_sz=3, min_vix=18.0))

out_path = ROOT / "reports/TRAINING_GRID_FINAL_ARCHITECTURES.json"
with open(out_path, "w") as f:
    json.dump(grid_results, f, indent=2)
print(f"\nAll 17 candidate architectures evaluated and saved to {out_path}")
