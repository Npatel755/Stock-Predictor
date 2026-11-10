"""Test Gap-Continuation Bonus Sizing on 14-Year Training Split (2010-2023) ONLY.
"""
import sys, json, gc
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
sys.path.insert(0, str(ROOT / "scripts"))

from audit_vol_adaptive_fortress_train import sim, load_train, prior_day_vix

dates, gap_dict, G = load_train()
daily, amb, n_tr = sim(dates, gap_dict, G, prior_day_vix, pess=False)

ds = [str(d) for d in dates]

def test_gap_boost(
    base_sz=10,
    accel_sz=12,
    sprint_sz=14,
    gap_bonus=2, # +2 MNQ on gap continuation
    def_thr=-400.0,
    horizon=100
):
    passed, ruined, timeouts, dll_b = 0, 0, 0, 0
    pass_days, pass_sess, dds = [], [], []
    
    for i in range(len(ds) - horizon):
        cum, hwm, busted, pass_run, peak_dd, tr_days = 0.0, 0.0, False, False, 0.0, 0
        for step in range(horizon):
            d_str = ds[i + step]
            tr = daily.get(d_str, None)
            if not tr or not tr["traded"]: continue
            tr_days += 1
            
            vix = prior_day_vix(d_str)
            is_hv = (vix >= 16.0)
            gap = gap_dict.get(d_str, 0.0)
            
            # Base sizing
            if cum <= def_thr:
                sz = 1
            elif cum >= 2400.0:
                sz = sprint_sz + (2 if is_hv else 0)
            elif cum >= 1200.0:
                sz = accel_sz + (2 if is_hv else 0)
            else:
                sz = base_sz + (2 if is_hv else 0)
                
            # If gap continuation, add gap_bonus
            # Note: in Crabel, long entries only take positive gap or flat gap, short entries only take negative gap
            # So virtually all active trades are continuation!
            if gap_bonus > 0 and cum > def_thr:
                sz += gap_bonus
                
            pnl = tr["net_1c"] * sz
            mae = tr["mae_1c"] * sz
            
            if pnl <= -1000.0 or mae <= -1000.0:
                busted = True; dll_b += 1; break
            if (cum + mae) <= -2000.0:
                busted = True; break
            if pnl > 1500.0: pnl = 1500.0
            
            cum += pnl
            c_dd = hwm - cum
            if c_dd > peak_dd: peak_dd = c_dd
            if cum > hwm: hwm = cum
            if cum <= -2000.0: busted = True; break
            if cum >= 4000.0:
                passed += 1; pass_run = True; pass_days.append(tr_days); pass_sess.append(step+1); dds.append(peak_dd); break
                
        if busted and not pass_run: ruined += 1
        elif not pass_run and not busted: timeouts += 1
        
    p_pct = (passed / max(1, passed + ruined)) * 100
    r_pct = (ruined / max(1, passed + ruined)) * 100
    mean_tr = np.mean(pass_days) if passed else 999.0
    med_tr = np.median(pass_days) if passed else 999.0
    p25_tr = np.percentile(pass_days, 25) if passed else 999.0
    p10_tr = np.percentile(pass_days, 10) if passed else 999.0
    min_tr = np.min(pass_days) if passed else 999
    avg_dd = np.mean(dds) if passed else 999.0
    
    return {
        "passed": passed, "ruined": ruined, "timeouts": timeouts,
        "pass_pct": round(p_pct, 1), "ruin_pct": round(r_pct, 1),
        "mean_days": round(mean_tr, 1), "med_days": round(med_tr, 1),
        "p25_days": round(p25_tr, 1), "p10_days": round(p10_tr, 1),
        "min_days": int(min_tr), "avg_dd": round(avg_dd, 1), "dll": dll_b
    }

print("="*95)
print("TESTING GAP ACCELERATOR SIZING ON TRAINING (2010-2023)")
print("="*95)

for gb in [0, 2, 4]:
    for base in [8, 10, 12]:
        r = test_gap_boost(base_sz=base, accel_sz=base+2, sprint_sz=base+4, gap_bonus=gb, def_thr=-400.0)
        print(f"Base: {base:2d}c | GapBonus: +{gb}c || Pass: {r['passed']:3d} ({r['pass_pct']:5.1f}%) | Ruin: {r['ruined']:2d} ({r['ruin_pct']:4.1f}%) | Mean: {r['mean_days']:4.1f}d | Med: {r['med_days']:4.1f}d | P25: {r['p25_days']:4.1f}d | P10: {r['p10_days']:4.1f}d | Min: {r['min_days']:2d}d | Peak DD: ${r['avg_dd']:6.1f} | DLL: {r['dll']}")
