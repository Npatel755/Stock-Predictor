import json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")

with open(ROOT / "data/processed/crabel_train_runner120.json") as f:
    c120 = json.load(f)
with open(ROOT / "data/processed/overnight_trades_train.json") as f:
    on_raw = json.load(f)

c_clean = {k[:10]: v for k, v in c120.items()}
on_clean = {}
for tr in on_raw:
    d = tr["exit_day"][:10]
    mae = float(tr["mae_pts"])
    pnl = float(tr["pnl_1c"])
    if mae <= -20.0:
        pnl = -20.0 * 2.0 - 2.60
        mae_1c = -40.0
    else:
        mae_1c = mae * 2.0
    on_clean[d] = {"net_1c": pnl, "mae_1c": mae_1c, "traded": True}

all_sessions = sorted(list(c_clean.keys()))

def test_config(name, base_sz, stg2_sz, stg3_sz, stg2_thr, stg3_thr, def_thr, def_sz, max_sess=120):
    passed = 0
    ruined = 0
    timeouts = 0
    dll_breaches = 0
    pass_tr = []
    pass_sess = []
    max_dds = []
    
    for i in range(len(all_sessions) - max_sess):
        cum = 0.0
        hwm = 0.0
        busted = False
        pass_run = False
        peak_dd = 0.0
        tr_days = 0
        
        for step in range(max_sess):
            d = all_sessions[i + step]
            # Duo 1/day
            tr = c_clean.get(d, None)
            if not tr or not tr["traded"]:
                tr = on_clean.get(d, None)
            if not tr or not tr["traded"]:
                continue
                
            tr_days += 1
            
            # Sizing Ladder
            if cum <= def_thr:
                sz = def_sz
            elif cum >= stg3_thr:
                sz = stg3_sz
            elif cum >= stg2_thr:
                sz = stg2_sz
            else:
                sz = base_sz
                
            pnl = tr["net_1c"] * sz
            mae = tr["mae_1c"] * sz
            
            if pnl <= -1000.0 or mae <= -1000.0:
                busted = True
                dll_breaches += 1
                break
                
            if (cum + mae) <= -2000.0:
                busted = True
                break
                
            if pnl > 1500.0:
                pnl = 1500.0
                
            cum += pnl
            current_dd = hwm - cum
            if current_dd > peak_dd: peak_dd = current_dd
            if cum > hwm: hwm = cum
            
            if cum <= -2000.0:
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
    min_tr = np.min(pass_tr) if passed else 999
    mean_s = np.mean(pass_sess) if passed else 999.0
    avg_dd = np.mean(max_dds) if passed else 999.0
    
    print(f"{name:55s} | TR MEAN: {mean_tr:4.1f}d | MED: {med_tr:4.1f}d | P25: {p25_tr:4.1f}d | MIN: {min_tr:2d}d | SESS: {mean_s:4.1f} | Pass: {p_pct:5.1f}% | Ruin: {r_pct:4.1f}% | DLL: {dll_breaches:2d} | DD: ${avg_dd:.2f}")

print("="*125)
print("TESTING 2-WEEK VELOCITY SIZING ON 14-YEAR TRAINING SPLIT (2010-2023)")
print("="*125)

test_config("1. Base 6c -> 8c @ $1.5k -> 10c @ $2.6k (Def 3c @ -$250)", 6, 8, 10, 1500.0, 2600.0, -250.0, 3)
test_config("2. Base 7c -> 9c @ $1.5k -> 11c @ $2.6k (Def 3c @ -$250)", 7, 9, 11, 1500.0, 2600.0, -250.0, 3)
test_config("3. Base 8c -> 10c @ $1.5k -> 12c @ $2.7k (Def 3c @ -$250)", 8, 10, 12, 1500.0, 2700.0, -250.0, 3)
test_config("4. Base 8c -> 10c @ $1.2k -> 12c @ $2.4k (Def 3c @ -$250)", 8, 10, 12, 1200.0, 2400.0, -250.0, 3)
test_config("5. Base 8c -> 11c @ $1.2k -> 14c @ $2.5k (Def 3c @ -$250)", 8, 11, 14, 1200.0, 2500.0, -250.0, 3)
test_config("6. Base 8c -> 10c @ $1.5k -> 12c @ $2.7k (Def 2c @ -$200)", 8, 10, 12, 1500.0, 2700.0, -200.0, 2)
test_config("7. Base 8c -> 10c @ $1.5k -> 12c @ $2.7k (Def 1c @ -$200)", 8, 10, 12, 1500.0, 2700.0, -200.0, 1)
test_config("8. Base 8c -> 10c @ $1.2k -> 12c @ $2.4k (Def 1c @ -$200)", 8, 10, 12, 1200.0, 2400.0, -200.0, 1)
