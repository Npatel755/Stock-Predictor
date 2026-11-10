"""Freeroll Profit Accelerator Research for Multi-Sleeve Fast-Passer.
TRAINING SPLIT (2010-2023) ONLY.
Objective: Accelerate 2-3 week passing rate by scaling size only when in comfortable profit cushion.
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
trades_df = pd.read_parquet(ROOT / "data/processed/multi_sleeve_trades_train.parquet")
CORE_SLEEVES = ["AG_CRABEL15_D_1c", "OVERNIGHT_DIP", "AG_TRD60_D_1c", "AG_MES_TRD30_D_1c"]
trades_df = trades_df[trades_df.sleeve.isin(CORE_SLEEVES)].copy()
trades_df["tout"] = pd.to_datetime(trades_df.tout_str, utc=True)
trades_df["tin"] = pd.to_datetime(trades_df.tin_str, utc=True)
trades_df["date"] = trades_df.tout.dt.tz_convert("America/New_York").dt.date
trades_df = trades_df.sort_values("tin").reset_index(drop=True)

# Build matched zero-edge control
sleeve_means = trades_df.groupby("sleeve")["net_today"].mean().to_dict()
trades_df["net_zero"] = trades_df.apply(lambda r: r["net_today"] - sleeve_means[r["sleeve"]], axis=1)

days_list = sorted(trades_df.date.unique())
trades_by_date = {d: trades_df[trades_df.date == d] for d in days_list}

def run_accelerator(
    base_map,       # base sizing at 0 balance
    tier1_mult,     # multiplier when balance >= tier1_thr
    tier2_mult,     # multiplier when balance >= tier2_thr
    tier1_thr=1500.0,
    tier2_thr=2800.0,
    reset_thr=-500.0,
    day_stop=350.0, # circuit breaker on realized day loss
    max_day_risk=750.0
):
    results = {}
    for is_zero in (False, True):
        col = "net_zero" if is_zero else "net_today"
        passed_10 = 0; passed_15 = 0; passed_21 = 0
        resets_paid = []
        days_to_pass = []
        worst_day = 0.0
        dll_breaches = 0
        
        n_starts = len(days_list) - 21
        for s in range(n_starts):
            used = 0; resets = 0
            while used < 21:
                cum = 0.0; outcome = "open"
                for step in range(21 - used):
                    d = days_list[s + used + step]
                    d_trades = trades_by_date[d]
                    
                    # Determine current tier multiplier based on starting day balance
                    if cum >= tier2_thr:
                        mult = tier2_mult
                    elif cum >= tier1_thr:
                        mult = tier1_mult
                    else:
                        mult = 1.0
                        
                    day_pnl = 0.0
                    for t in d_trades.itertuples():
                        # Base sizing scaled by tier multiplier
                        sz = base_map.get(t.sleeve, 2.0) * mult
                        # Overnight dip is capped at max 2 contracts for risk control
                        if t.sleeve == "OVERNIGHT_DIP":
                            sz = min(sz, 2.0)
                            
                        trade_risk = t.risk_today * sz
                        
                        # Realized day stop circuit breaker: if already lost day_stop, halt!
                        if day_pnl <= -day_stop:
                            continue
                        # Hard pre-trade DLL guard
                        if (day_pnl - trade_risk) <= -max_day_risk:
                            continue
                            
                        day_pnl += getattr(t, col) * sz
                        
                    if day_pnl < worst_day: worst_day = day_pnl
                    if day_pnl <= -1000.0: dll_breaches += 1; outcome = "busted"; break
                    
                    cum += min(day_pnl, 1500.0) # 50% consistency rule daily lock
                    
                    if cum <= -2000.0: outcome = "busted"; break
                    if cum >= 4000.0: outcome = "passed"; break
                    if cum <= reset_thr: outcome = "reset"; break
                    
                used += (step + 1)
                if outcome == "passed":
                    days_to_pass.append(used)
                    if used <= 10: passed_10 += 1
                    if used <= 15: passed_15 += 1
                    if used <= 21: passed_21 += 1
                    resets_paid.append(resets)
                    break
                elif outcome in ("reset", "busted"):
                    resets += 1
                else:
                    break
                    
        key = "zero" if is_zero else "real"
        results[key] = {
            "p10": round(passed_10 / n_starts * 100, 1),
            "p15": round(passed_15 / n_starts * 100, 1),
            "p21": round(passed_21 / n_starts * 100, 1),
            "resets": round(float(np.mean(resets_paid)), 1) if resets_paid else 0.0,
            "median_days": round(float(np.median(days_to_pass)), 1) if days_to_pass else 0.0,
            "worst_day": round(worst_day, 1),
            "dll_breaches": dll_breaches,
            "n_passed": passed_21
        }
    return results

base_config = {"AG_CRABEL15_D_1c": 3.0, "OVERNIGHT_DIP": 1.5, "AG_MES_TRD30_D_1c": 3.0, "AG_TRD60_D_1c": 2.0}

print("="*105)
print(f"{'ACCELERATOR CONFIG':42s} || {'REAL 2wk':8s} {'REAL 3wk':8s} {'REAL 1mo':8s} || {'ZERO 1mo':8s} {'ALPHA BOOST':11s} || {'RESETS':6s} {'DLL':5s}")
print("="*105)

test_configs = [
    ("No Accelerator (Flat 1.0x Base)", 1.0, 1.0, 1500.0, 2800.0),
    ("Gentle Sprint (1.33x @ $1500, 1.67x @ $2800)", 1.33, 1.67, 1500.0, 2800.0),
    ("Moderate Sprint (1.50x @ $1500, 2.00x @ $2800)", 1.50, 2.00, 1500.0, 2800.0),
    ("Early Sprint (1.50x @ $1200, 2.00x @ $2500)", 1.50, 2.00, 1200.0, 2500.0),
    ("Aggressive Sprint (1.67x @ $1200, 2.33x @ $2500)", 1.67, 2.33, 1200.0, 2500.0),
    ("Ultra Sprint (2.00x @ $1200, 2.50x @ $2500)", 2.00, 2.50, 1200.0, 2500.0),
]

summary = []
for name, t1_m, t2_m, t1_t, t2_t in test_configs:
    r = run_accelerator(base_config, t1_m, t2_m, tier1_thr=t1_t, tier2_thr=t2_t)
    real, zero = r["real"], r["zero"]
    boost = round(real["p21"] - zero["p21"], 1)
    print(f"{name:42s} || {real['p10']:5.1f}%   {real['p15']:5.1f}%   {real['p21']:5.1f}%   || {zero['p21']:5.1f}%   +{boost:5.1f}%      || {real['resets']:4.1f}   {real['dll_breaches']:3d}")
    summary.append({"name": name, "real": real, "zero": zero, "boost": boost})

out_json = ROOT / "reports/RESEARCH_FREEROLL_ACCELERATOR_TRAINING.json"
with open(out_json, "w") as f:
    json.dump(summary, f, indent=2)
print(f"\nSaved results to {out_json}")
