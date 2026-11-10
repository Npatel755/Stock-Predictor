"""Test Recovery Sizing (Def 2c vs Def 1c) on 14-Year Training Split (2010-2023).
METHODOLOGICAL INVARIANT:
- 100% EXCLUSIVELY ON TRAINING DATA.
- ZERO TUNING ON VALIDATION OR TEST.
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")

with open(ROOT / "data/processed/crabel_train_runner120.json") as f:
    c120 = json.load(f)

vix_path = ROOT / "data/external/VIX_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df["date"] = pd.to_datetime(vix_df["DATE"]).dt.date
vix_dict = dict(zip(vix_df["date"], vix_df["CLOSE"]))

c_clean = {k[:10]: v for k, v in c120.items()}
all_sessions = sorted(list(c_clean.keys()))

DLL_LIMIT = -1000.0
STATIC_FLOOR = -2000.0
DAILY_LOCK = 1500.0

def eval_def_variant(name, def_sz=1, def_thr=-200.0, base_sz_low=8, base_sz_high=10, max_horizon=100):
    passed = 0
    ruined = 0
    pass_tr = []
    max_dds = []
    dll_breaches = 0
    
    for i in range(len(all_sessions) - max_horizon):
        cum = 0.0
        hwm = 0.0
        busted, pass_run = False, False
        peak_dd = 0.0
        tr_days = 0
        
        for step in range(max_horizon):
            d = all_sessions[i + step]
            tr = c_clean.get(d, None)
            if not tr or not tr["traded"]:
                continue
                
            tr_days += 1
            vix = vix_dict.get(pd.to_datetime(d).date(), 18.0)
            is_high_vol = (vix >= 16.0)
            
            if cum <= def_thr:
                sz = def_sz
            elif cum >= 2400.0:
                sz = 14 if is_high_vol else 12
            elif cum >= 1200.0:
                sz = 12 if is_high_vol else 10
            else:
                sz = base_sz_high if is_high_vol else base_sz_low
                
            pnl = tr["net_1c"] * sz
            mae = tr["mae_1c"] * sz
            
            if pnl <= DLL_LIMIT or mae <= DLL_LIMIT:
                busted = True; dll_breaches += 1; break
            if (cum + mae) <= STATIC_FLOOR:
                busted = True; break
            if pnl > DAILY_LOCK: pnl = DAILY_LOCK
            
            cum += pnl
            current_dd = hwm - cum
            if current_dd > peak_dd: peak_dd = current_dd
            if cum > hwm: hwm = cum
            if cum <= STATIC_FLOOR: busted = True; break
            if cum >= 4000.0:
                passed += 1; pass_run = True; pass_tr.append(tr_days); max_dds.append(peak_dd); break
                
        if busted and not pass_run: ruined += 1
        
    tot = passed + ruined
    p_pct = passed / max(1, tot) * 100
    r_pct = ruined / max(1, tot) * 100
    mean_tr = np.mean(pass_tr) if passed else 999.0
    med_tr = np.median(pass_tr) if passed else 999.0
    p25_tr = np.percentile(pass_tr, 25) if passed else 999.0
    p10_tr = np.percentile(pass_tr, 10) if passed else 999.0
    min_tr = np.min(pass_tr) if passed else 999
    avg_dd = np.mean(max_dds) if passed else 999.0
    
    print(f"{name:58s} | Pass: {p_pct:5.1f}% | Ruin: {r_pct:4.1f}% | MeanTR: {mean_tr:4.1f}d | MedTR: {med_tr:4.1f}d | P25: {p25_tr:4.1f}d | P10: {p10_tr:4.1f}d | Min: {min_tr:2d}d | DLL: {dll_breaches:2d} | DD: ${avg_dd:.0f}")

print("="*125)
print("TESTING DEFENSIVE RECOVERY SIZE ON TRAINING SPLIT:")
print("="*125)
eval_def_variant("1. Def Size = 1 MNQ (def_thr = -$200)", def_sz=1, def_thr=-200.0)
eval_def_variant("2. Def Size = 2 MNQ (def_thr = -$200)", def_sz=2, def_thr=-200.0)
eval_def_variant("3. Def Size = 2 MNQ (def_thr = -$250)", def_sz=2, def_thr=-250.0)
eval_def_variant("4. Def Size = 3 MNQ (def_thr = -$250)", def_sz=3, def_thr=-250.0)
eval_def_variant("5. Def Size = 2 MNQ (def_thr = -$150)", def_sz=2, def_thr=-150.0)
