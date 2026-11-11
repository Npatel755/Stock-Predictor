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

def eval_era(start_yr, end_yr, name):
    era_sessions = [d for d in all_sessions if start_yr <= int(d[:4]) <= end_yr]
    if len(era_sessions) < 60:
        return
    passed = 0
    ruined = 0
    pass_tr = []
    
    for i in range(len(era_sessions) - 60):
        cum = 0.0
        busted = False
        pass_run = False
        tr_days = 0
        
        for step in range(60):
            d = era_sessions[i + step]
            # Duo 1/day
            tr = c_clean.get(d, None)
            if not tr or not tr["traded"]:
                tr = on_clean.get(d, None)
            if not tr or not tr["traded"]:
                continue
                
            tr_days += 1
            # 6c -> 8c @ $1.5k -> 10c @ $2.6k, Def 3c
            if cum <= -250.0: sz = 3
            elif cum >= 2600.0: sz = 10
            elif cum >= 1500.0: sz = 8
            else: sz = 6
            
            pnl = tr["net_1c"] * sz
            mae = tr["mae_1c"] * sz
            
            if pnl <= -1000.0 or mae <= -1000.0 or (cum + mae) <= -2000.0:
                busted = True; break
                
            if pnl > 1500.0: pnl = 1500.0
            cum += pnl
            if cum <= -2000.0: busted = True; break
            if cum >= 4000.0:
                passed += 1; pass_run = True; pass_tr.append(tr_days); break
                
        if busted and not pass_run: ruined += 1
        
    tot = passed + ruined
    p_pct = passed / max(1, tot) * 100
    mean_tr = np.mean(pass_tr) if passed else 999
    med_tr = np.median(pass_tr) if passed else 999
    p25_tr = np.percentile(pass_tr, 25) if passed else 999
    print(f"Era {name:20s} ({start_yr}-{end_yr}) | Pass: {p_pct:5.1f}% | Mean TR: {mean_tr:4.1f}d | Med: {med_tr:4.1f}d | P25: {p25_tr:4.1f}d | Passed: {passed} | Ruined: {ruined}")

print("EVALUATION PASS TIME BY HISTORICAL ERA (TRAINING SPLIT ONLY):")
eval_era(2010, 2013, "Early Low-Vol")
eval_era(2014, 2017, "Mid Bull Run")
eval_era(2018, 2020, "High-Vol Expansion")
eval_era(2021, 2023, "Modern Era")
