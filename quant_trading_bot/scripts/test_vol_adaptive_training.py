"""Test Adaptive Volatility Scaling strictly on 14-Year Training Split (2010-2023).
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

# VIX
vix_path = ROOT / "data/external/VIX_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df["date"] = pd.to_datetime(vix_df["DATE"]).dt.date
vix_dict = dict(zip(vix_df["date"], vix_df["CLOSE"]))

c_clean = {k[:10]: v for k, v in c120.items()}
all_sessions = sorted(list(c_clean.keys()))

DLL_LIMIT = -1000.0
STATIC_FLOOR = -2000.0
DAILY_LOCK = 1500.0

def eval_vol_adaptive(
    name,
    base_sz_low=8,
    base_sz_high=10,
    stg2_sz_low=10,
    stg2_sz_high=12,
    stg3_sz_low=12,
    stg3_sz_high=14,
    stg2_thr=1200.0,
    stg3_thr=2400.0,
    def_thr=-200.0,
    def_sz=1,
    vix_split=18.0,
    max_horizon=100
):
    passed = 0
    ruined = 0
    timeouts = 0
    dll_breaches = 0
    pass_tr = []
    pass_sess = []
    max_dds = []
    
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
            is_high_vol = (vix >= vix_split)
            
            # Sizing Ladder with Vol-Adaptive capability
            if cum <= def_thr:
                sz = def_sz
            elif cum >= stg3_thr:
                sz = stg3_sz_high if is_high_vol else stg3_sz_low
            elif cum >= stg2_thr:
                sz = stg2_sz_high if is_high_vol else stg2_sz_low
            else:
                sz = base_sz_high if is_high_vol else base_sz_low
                
            pnl = tr["net_1c"] * sz
            mae = tr["mae_1c"] * sz
            
            if pnl <= DLL_LIMIT or mae <= DLL_LIMIT:
                busted = True
                dll_breaches += 1
                break
                
            if (cum + mae) <= STATIC_FLOOR:
                busted = True
                break
                
            if pnl > DAILY_LOCK:
                pnl = DAILY_LOCK
                
            cum += pnl
            current_dd = hwm - cum
            if current_dd > peak_dd: peak_dd = current_dd
            if cum > hwm: hwm = cum
            
            if cum <= STATIC_FLOOR:
                busted = True
                break
                
            if cum >= 4000.0:
                passed += 1
                pass_run = True
                pass_tr.append(tr_days)
                pass_sess.append(step + 1)
                max_dds.append(peak_dd)
                break
                
        if busted and not pass_run:
            ruined += 1
        elif not pass_run and not busted:
            timeouts += 1
            
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
print("TESTING VOLATILITY-ADAPTIVE SIZING ON 14-YEAR TRAINING SPLIT (2010-2023)")
print("="*125)

# Benchmark: Static ladder
eval_vol_adaptive("1. Static Ladder (8c -> 10c -> 12c, Def 1c @ -$200)",
                  base_sz_low=8, base_sz_high=8, stg2_sz_low=10, stg2_sz_high=10, stg3_sz_low=12, stg3_sz_high=12)

# Variant 2: High Vol Boost (8c/10c -> 10c/12c -> 12c/14c)
eval_vol_adaptive("2. Vol-Adaptive Sprint (Low 8/10/12c | High 10/12/14c @ VIX>=18)",
                  base_sz_low=8, base_sz_high=10, stg2_sz_low=10, stg2_sz_high=12, stg3_sz_low=12, stg3_sz_high=14, vix_split=18.0)

# Variant 3: High Vol Boost (Low 8/10/12c | High 10/12/14c @ VIX>=20)
eval_vol_adaptive("3. Vol-Adaptive Sprint (Low 8/10/12c | High 10/12/14c @ VIX>=20)",
                  base_sz_low=8, base_sz_high=10, stg2_sz_low=10, stg2_sz_high=12, stg3_sz_low=12, stg3_sz_high=14, vix_split=20.0)

# Variant 4: Ultra Vol-Adaptive (Low 8/10/12c | High 10/12/14c @ VIX>=16)
eval_vol_adaptive("4. Vol-Adaptive Sprint (Low 8/10/12c | High 10/12/14c @ VIX>=16)",
                  base_sz_low=8, base_sz_high=10, stg2_sz_low=10, stg2_sz_high=12, stg3_sz_low=12, stg3_sz_high=14, vix_split=16.0)

# Variant 5: Hyper-Sprint (Low 8/11/13c | High 10/12/14c @ VIX>=18)
eval_vol_adaptive("5. Hyper-Sprint (Low 8/11/13c | High 10/12/14c @ VIX>=18)",
                  base_sz_low=8, base_sz_high=10, stg2_sz_low=11, stg2_sz_high=12, stg3_sz_low=13, stg3_sz_high=14, vix_split=18.0)
