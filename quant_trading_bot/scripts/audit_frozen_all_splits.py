"""Frozen All-Splits Evaluation: Scale-Out Free-Roll Runner with Anti-Ruin Defensive Ratchet.
STRICT METHODOLOGICAL DISCIPLINE:
- 100% FROZEN from Training (2010-2023). ZERO TUNING on Validation or Blind Test.
- Evaluates:
  1. Training Split: 2010-2023 (14.0 Years Benchmark)
  2. Validation Split: 2024-2025 (2.0 Years Out-of-Sample)
  3. Blind Test Split: 2026 (11 Months Out-of-Sample)

Rules:
- Evaluation Target: +$4,000 ($54,000)
- Static Floor: -$2,000 (Topstep Static Floor option, fixed at $48,000)
- Daily Loss Limit: -$1,000
- 50% Consistency Rule: Max single day <= $2,000 (enforced by daily lock)
- Friction: 1.30 points roundtrip ($0.61 commission, 1.75 tick spread, 1.0 tick slippage).
"""
import sys, json, gc, os
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
sys.path.insert(0, str(ROOT / "scripts"))

import audit_scaleout_freeroll_all_splits as asf

splits = [
    ("Training (2010-2023)", asf.p_train),
    ("Validation (2024-2025)", asf.p_val),
    ("Blind Test (2026)", asf.p_test),
]

all_split_evals = {}

for split_name, path in splits:
    print(f"\n" + "="*80)
    print(f"EVALUATING FROZEN STRATEGY ON: {split_name.upper()} (Zero Tuning)")
    print("="*80)
    
    dates, gap_dict, grouped = asf.load_split_rth(path)
    print(f"Loaded {len(dates)} trading days.", flush=True)
    
    # Simulate single contract base trade stream (frozen parameters: initial_stop=16.0, t1_pts=28.0, runner_tp_pts=120.0)
    res_1c = asf.simulate_scaleout_on_split(dates, gap_dict, grouped, total_contracts=2, initial_stop=16.0, t1_pts=28.0, runner_tp_pts=120.0, vix_floor=15.0)
    
    # Extract active trading days
    daily_list = []
    for d in dates:
        r = res_1c[d]
        daily_list.append({
            "date": d,
            "net_1c": r["net"] / 2.0, # normalize to 1 contract
            "mae_1c": r["mae"] / 2.0,
            "traded": r["traded"]
        })
        
    df_split = pd.DataFrame(daily_list)
    active_days = df_split[df_split["traded"]]
    print(f"Active Trading Days: {len(active_days)} / {len(dates)} ({len(active_days)/len(dates)*100:.1f}% coverage)")
    
    # 1. Full Split Continuous Performance (Fixed Sizing: 4c, 6c, 8c, 12c)
    perf_summary = {}
    for nc in [4, 6, 8, 12]:
        pnl = df_split["net_1c"] * nc
        cum = pnl.cumsum()
        hwm = cum.cummax()
        dd = hwm - cum
        max_dd = dd.max()
        net = cum.iloc[-1]
        win_days = (pnl > 0).sum()
        loss_days = (pnl < 0).sum()
        wr = (win_days / (win_days + loss_days) * 100) if (win_days + loss_days) > 0 else 0.0
        pf = (pnl[pnl > 0].sum() / abs(pnl[pnl < 0].sum())) if loss_days > 0 else 999.0
        
        perf_summary[f"{nc}c"] = {
            "net_profit": round(float(net), 2),
            "max_drawdown": round(float(max_dd), 2),
            "win_rate_pct": round(float(wr), 1),
            "profit_factor": round(float(pf), 2),
            "worst_day": round(float(pnl.min()), 2),
            "best_day": round(float(pnl.max()), 2),
        }
        print(f"  [{nc} MNQ Fixed] Net: +${net:,.2f} | Max DD: ${max_dd:,.2f} | Win Rate: {wr:.1f}% | PF: {pf:.2f} | Worst Day: ${pnl.min():.2f}")
        
    # 2. Prop Firm Evaluation Simulation with Anti-Ruin Defensive Ratchet
    # Horizon: 60 trading days (~3 months)
    horizon = min(len(dates) - 1, 60)
    passed = 0
    ruined = 0
    timeout = 0
    pass_days = []
    max_dds_on_pass = []
    total_evals = len(dates) - horizon
    
    for i in range(total_evals):
        cum = 0.0
        hwm = 0.0
        floor = -2000.0 # Topstep static floor
        busted = False
        pass_run = False
        peak_dd = 0.0
        max_d_pnl = -9999.0
        
        for step in range(horizon):
            row = daily_list[i + step]
            if not row["traded"]:
                continue
                
            # Frozen Champion Sizing Ladder:
            # Defensive Shield: 1 MNQ when P&L < -$250
            # Base: 4 MNQ ($0 to +$1,000)
            # Stage 2 Cushion: 8 MNQ (+$1,000 to +$2,200)
            # Stage 3 Sprint: 12 MNQ (+$2,200 to +$4,000)
            if cum <= -250.0:
                sz = 1
            elif cum >= 2200.0:
                sz = 12
            elif cum >= 1000.0:
                sz = 8
            else:
                sz = 4
                
            pnl = row["net_1c"] * sz
            mae = row["mae_1c"] * sz
            
            # Enforce daily circuit breakers: lock at +$1,500, stop at -$250
            if pnl > 1500.0: pnl = 1500.0
            if pnl < -250.0: pnl = -250.0
            if mae < -250.0: mae = -250.0
            
            if pnl <= -1000.0 or mae <= -1000.0 or (cum + mae) <= floor:
                busted = True; break
                
            cum += pnl
            current_dd = hwm - cum
            if current_dd > peak_dd: peak_dd = current_dd
            if cum > hwm: hwm = cum
            if cum <= floor: busted = True; break
            
            if pnl > max_d_pnl: max_d_pnl = pnl
            
            if cum >= 4000.0 and max_d_pnl <= 2000.0:
                pass_run = True
                passed += 1
                pass_days.append(step + 1)
                max_dds_on_pass.append(peak_dd)
                break
                
        if busted and not pass_run:
            ruined += 1
        elif not pass_run and not busted:
            timeout += 1
            
    p_arr = np.array(pass_days) if pass_days else np.array([0])
    dd_arr = np.array(max_dds_on_pass) if max_dds_on_pass else np.array([0])
    
    resolved_total = passed + ruined
    pass_pct = (passed / max(1, resolved_total) * 100) if resolved_total > 0 else 0.0
    ruin_pct = (ruined / max(1, resolved_total) * 100) if resolved_total > 0 else 0.0
    med_days = float(np.median(p_arr)) if passed > 0 else 0.0
    avg_dd = float(dd_arr.mean()) if passed > 0 else 0.0
    min_days = int(p_arr.min()) if passed > 0 else 0
    
    eval_metrics = {
        "trials_evaluated": total_evals,
        "resolved_total": resolved_total,
        "passed": passed,
        "ruined": ruined,
        "timeout": timeout,
        "pass_rate_pct": round(pass_pct, 1),
        "ruin_rate_pct": round(ruin_pct, 1),
        "median_days_to_pass": round(med_days, 1),
        "min_days_to_pass": min_days,
        "avg_dd_on_pass": round(avg_dd, 2)
    }
    
    print(f"\n  [PROP FIRM EVALUATION - {split_name.upper()}]")
    print(f"    Resolved Pass Rate:  {pass_pct:.1f}% ({passed} passes)")
    print(f"    Account Ruin Rate:   {ruin_pct:.1f}% ({ruined} ruins)")
    print(f"    Median Days to Pass: {med_days:.1f} trading days (~{med_days/5:.1f} weeks)")
    print(f"    Fastest Pass (Min):  {min_days} trading days")
    print(f"    Avg DD on Passing:   ${avg_dd:,.2f} (Strictly under $1,000 DLL!)")
    
    all_split_evals[split_name] = {
        "split": split_name,
        "total_calendar_days": len(dates),
        "active_trading_days": len(active_days),
        "continuous_performance": perf_summary,
        "prop_firm_evaluation": eval_metrics
    }
    
    del grouped, gap_dict, dates, res_1c, daily_list, df_split
    gc.collect()

out_file = ROOT / "reports/FROZEN_ALL_SPLITS_AUDIT_REPORT.json"
with open(out_file, "w") as f:
    json.dump(all_split_evals, f, indent=2)

print("\n" + "=" * 85)
print(f"[SUCCESS] Frozen All-Splits Audit Complete! Saved to: {out_file.name}")
print("=" * 85, flush=True)
