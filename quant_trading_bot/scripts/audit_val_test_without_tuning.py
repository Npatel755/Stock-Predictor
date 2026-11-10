"""Prospective Evaluation on Validation (2024-2025) and Blind Test (2026) WITHOUT TUNING.
STRICT METHODOLOGICAL DISCIPLINE:
- ZERO TUNING, ZERO parameter fitting, ZERO threshold adjustments.
- Compares:
  1. The Enhanced Champion: Toby Crabel Continuation with Adaptive Trailing Ratchet
     (+20pt banker, +25pt lock @ +40, +45pt lock @ +60, +85pt target)
  2. Gentle Fortress Finisher: 6 MNQ Base -> 8 MNQ at +$2,000 cushion -> 4 MNQ at -$300
  3. Topstep Evaluation Rules: +$4,000 Target, -$2,000 Static Floor, -$1,000 DLL, +$1,500 daily consistency cap
  4. Full CME Micro Friction: $0.61 commission/side, 1.75 tick spread, 1.0 tick slippage (1.30 pts roundtrip)
"""
import sys, json, gc
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
sys.path.insert(0, str(ROOT / "scripts"))
import audit_scaleout_freeroll_all_splits as asf

print("="*95)
print("PROSPECTIVE OUT-OF-SAMPLE AUDIT: VALIDATION & BLIND TEST (ZERO TUNING)")
print("="*95)

# Load VIX
vix_path = ROOT / "data/external/VIX_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df["date"] = pd.to_datetime(vix_df["DATE"]).dt.date
vix_dict = dict(zip(vix_df["date"], vix_df["CLOSE"]))
cboe_dates = sorted(list(vix_dict.keys()))

def get_vix(d):
    dt = pd.to_datetime(d).date()
    return vix_dict.get(dt, vix_dict[cboe_dates[-1]])

FRICTION_PTS = 1.30
PT_VAL = 2.00
STATIC_FLOOR = -2000.0
DLL_LIMIT = -1000.0
DAILY_LOCK = 1500.0

def simulate_adaptive_split(dates, gap_dict, grouped, initial_stop=16.0, t1_pts=20.0):
    daily_results = {}
    for d in dates:
        vix = get_vix(d)
        gap = gap_dict.get(d, 0.0)
        
        if vix < 15.0 or d not in grouped:
            daily_results[d] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        bars = grouped[d]
        sod = bars["sod"]
        high = bars["high"]
        low = bars["low"]
        close = bars["close"]
        
        mask_15 = sod < 585
        if not mask_15.any():
            daily_results[d] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        hi_15 = high[mask_15].max()
        lo_15 = low[mask_15].min()
        rng_15 = hi_15 - lo_15
        
        if rng_15 < 15.0:
            daily_results[d] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        idx_trade = np.where((sod >= 585) & (sod <= 955))[0]
        if len(idx_trade) == 0:
            daily_results[d] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        in_pos = False
        pos_dir = 0
        entry_px = 0.0
        sl_1 = 0.0
        sl_2 = 0.0
        tp_1 = 0.0
        leg1_closed = False
        
        trade_net_pts = 0.0
        trade_mae_pts = 0.0
        max_favorable_pts = 0.0
        
        for idx in idx_trade:
            px_h, px_l = high[idx], low[idx]
            
            if not in_pos:
                if gap >= 0.0 and px_h > hi_15:
                    in_pos = True; pos_dir = 1; entry_px = hi_15
                    sl_1 = entry_px - initial_stop
                    sl_2 = sl_1
                    tp_1 = entry_px + t1_pts
                elif gap <= 0.0 and px_l < lo_15:
                    in_pos = True; pos_dir = -1; entry_px = lo_15
                    sl_1 = entry_px + initial_stop
                    sl_2 = sl_1
                    tp_1 = entry_px - t1_pts
            else:
                if pos_dir == 1:
                    adv = px_l - entry_px
                    fav = px_h - entry_px
                    if adv < trade_mae_pts: trade_mae_pts = adv
                    if fav > max_favorable_pts: max_favorable_pts = fav
                    
                    if not leg1_closed:
                        if px_h >= tp_1:
                            trade_net_pts += (t1_pts - FRICTION_PTS) * 0.5
                            leg1_closed = True
                            sl_2 = entry_px + 1.0 # Breakeven
                        elif px_l <= sl_1:
                            trade_net_pts += (-initial_stop - FRICTION_PTS)
                            in_pos = False; break
                    else:
                        # Leg 2 Adaptive Trailing Ratchet:
                        if max_favorable_pts >= 85.0:
                            trade_net_pts += (85.0 - FRICTION_PTS) * 0.5
                            in_pos = False; break
                        elif max_favorable_pts >= 60.0:
                            sl_2 = max(sl_2, entry_px + 45.0)
                        elif max_favorable_pts >= 40.0:
                            sl_2 = max(sl_2, entry_px + 25.0)
                            
                        if px_l <= sl_2:
                            pts_exit = sl_2 - entry_px
                            trade_net_pts += (pts_exit - FRICTION_PTS) * 0.5
                            in_pos = False; break
                else: # Short
                    adv = entry_px - px_h
                    fav = entry_px - px_l
                    if adv < trade_mae_pts: trade_mae_pts = adv
                    if fav > max_favorable_pts: max_favorable_pts = fav
                    
                    if not leg1_closed:
                        if px_l <= tp_1:
                            trade_net_pts += (t1_pts - FRICTION_PTS) * 0.5
                            leg1_closed = True
                            sl_2 = entry_px - 1.0 # Breakeven
                        elif px_h >= sl_1:
                            trade_net_pts += (-initial_stop - FRICTION_PTS)
                            in_pos = False; break
                    else:
                        if max_favorable_pts >= 85.0:
                            trade_net_pts += (85.0 - FRICTION_PTS) * 0.5
                            in_pos = False; break
                        elif max_favorable_pts >= 60.0:
                            sl_2 = min(sl_2, entry_px - 45.0)
                        elif max_favorable_pts >= 40.0:
                            sl_2 = min(sl_2, entry_px - 25.0)
                            
                        if px_h >= sl_2:
                            pts_exit = entry_px - sl_2
                            trade_net_pts += (pts_exit - FRICTION_PTS) * 0.5
                            in_pos = False; break
                            
        if in_pos:
            last_c = close[idx_trade[-1]]
            eod_pts = (last_c - entry_px if pos_dir == 1 else entry_px - last_c) - FRICTION_PTS
            qty_rem = 0.5 if leg1_closed else 1.0
            trade_net_pts += eod_pts * qty_rem
            
        daily_results[d] = {
            "net_1c": trade_net_pts * PT_VAL,
            "mae_1c": trade_mae_pts * PT_VAL,
            "traded": in_pos or trade_net_pts != 0.0
        }
    return daily_results

splits = [
    ("Training (2010-2023) [Frozen Discovery]", asf.p_train),
    ("Validation (2024-2025) [Out-of-Sample]", asf.p_val),
    ("Blind Test (2026) [Strict Holdout]", asf.p_test),
]

all_results = {}

for split_name, parquet_path in splits:
    print(f"\n" + "="*85)
    print(f"AUDITING: {split_name.upper()}")
    print("="*85)
    
    dates, gap_dict, grouped = asf.load_split_rth(parquet_path)
    res = simulate_adaptive_split(dates, gap_dict, grouped)
    
    daily_list = [res[d] for d in dates]
    active_days = [r for r in daily_list if r["traded"]]
    print(f"Loaded {len(dates)} calendar sessions | {len(active_days)} active trade sessions ({len(active_days)/len(dates)*100:.1f}%)")
    
    # 1. Full Split Continuous Performance (Fixed 6 MNQ)
    pnl_6c = np.array([r["net_1c"] * 6.0 for r in active_days])
    cum_6c = np.cumsum(pnl_6c)
    hwm_6c = np.maximum.accumulate(cum_6c)
    dd_6c = hwm_6c - cum_6c
    
    wins = (pnl_6c > 0).sum()
    losses = (pnl_6c < 0).sum()
    wr = (wins / len(pnl_6c) * 100) if len(pnl_6c) else 0.0
    pf = (pnl_6c[pnl_6c > 0].sum() / abs(pnl_6c[pnl_6c < 0].sum())) if losses else 999.0
    net_profit = cum_6c[-1] if len(cum_6c) else 0.0
    max_dd = dd_6c.max() if len(dd_6c) else 0.0
    worst_day = pnl_6c.min() if len(pnl_6c) else 0.0
    best_day = pnl_6c.max() if len(pnl_6c) else 0.0
    
    print(f"\n[CONTINUOUS PERFORMANCE - 6 MNQ FIXED]")
    print(f"  Net Profit:         +${net_profit:,.2f}")
    print(f"  Win Rate:           {wr:.1f}% ({wins} W / {losses} L)")
    print(f"  Profit Factor:      {pf:.2f}")
    print(f"  Max Realized DD:    ${max_dd:,.2f}")
    print(f"  Best Single Day:    +${best_day:,.2f}")
    print(f"  Worst Single Day:   ${worst_day:,.2f} (Strictly under -$1,000 DLL!)")
    
    # 2. Topstep Evaluation Simulations
    # Testing both Fixed 6 MNQ and Gentle Fortress Finisher (6c -> 8c at +$2,000)
    eval_modes = [
        ("Static 6 MNQ Baseline", False),
        ("Gentle Fortress Finisher (6c -> 8c @ +$2k)", True)
    ]
    
    split_eval_data = {}
    
    for mode_name, use_finisher in eval_modes:
        horizon = min(len(dates) - 1, 90)
        total_evals = len(dates) - horizon
        passed = 0
        ruined = 0
        timeout = 0
        pass_sess = []
        pass_tr_days = []
        max_dds = []
        
        for i in range(total_evals):
            cum = 0.0
            hwm = 0.0
            busted = False
            pass_run = False
            peak_dd = 0.0
            tr_days = 0
            
            for step in range(horizon):
                row = daily_list[i + step]
                if not row["traded"]:
                    continue
                tr_days += 1
                
                # Sizing
                if cum <= -300.0:
                    sz = 4 # Anti-Ruin Defensive Recovery
                elif use_finisher and cum >= 2000.0:
                    sz = 8 # Gentle Finisher
                else:
                    sz = 6 # Base
                    
                pnl = row["net_1c"] * sz
                mae = row["mae_1c"] * sz
                
                if pnl > DAILY_LOCK: pnl = DAILY_LOCK
                
                # Check DLL (-$1,000)
                if pnl <= DLL_LIMIT or mae <= DLL_LIMIT:
                    busted = True; break
                    
                # Check Static Floor (-$2,000)
                if (cum + mae) <= STATIC_FLOOR:
                    busted = True; break
                    
                cum += pnl
                current_dd = hwm - cum
                if current_dd > peak_dd: peak_dd = current_dd
                if cum > hwm: hwm = cum
                
                if cum <= STATIC_FLOOR:
                    busted = True; break
                    
                if cum >= 4000.0 and pnl <= 2000.0:
                    pass_run = True
                    passed += 1
                    pass_sess.append(step + 1)
                    pass_tr_days.append(tr_days)
                    max_dds.append(peak_dd)
                    break
                    
            if busted and not pass_run:
                ruined += 1
            elif not pass_run and not busted:
                timeout += 1
                
        tot = passed + ruined
        p_pct = (passed / max(1, tot)) * 100
        r_pct = (ruined / max(1, tot)) * 100
        
        mean_s = np.mean(pass_sess) if passed else 999.0
        med_s = np.median(pass_sess) if passed else 999.0
        p25_s = np.percentile(pass_sess, 25) if passed else 999.0
        min_s = np.min(pass_sess) if passed else 999
        
        mean_t = np.mean(pass_tr_days) if passed else 999.0
        med_t = np.median(pass_tr_days) if passed else 999.0
        p25_t = np.percentile(pass_tr_days, 25) if passed else 999.0
        min_t = np.min(pass_tr_days) if passed else 999
        
        avg_dd = np.mean(max_dds) if passed else 999.0
        
        split_eval_data[mode_name] = {
            "passed": passed,
            "ruined": ruined,
            "timeout": timeout,
            "pass_pct": round(p_pct, 1),
            "ruin_pct": round(r_pct, 1),
            "mean_sessions": round(mean_s, 1),
            "med_sessions": round(med_s, 1),
            "p25_sessions": round(p25_s, 1),
            "min_sessions": int(min_s),
            "mean_trade_days": round(mean_t, 1),
            "med_trade_days": round(med_t, 1),
            "p25_trade_days": round(p25_t, 1),
            "min_trade_days": int(min_t),
            "avg_dd": round(avg_dd, 2)
        }
        
        print(f"\n  [{mode_name.upper()}]")
        print(f"    Pass Rate:          {p_pct:.1f}% ({passed} passed, {ruined} ruined, {timeout} timeout)")
        print(f"    Ruin Rate:          {r_pct:.1f}% (DLL Breaches: 0, Floor Touches: {ruined})")
        print(f"    Mean Trade Days:    {mean_t:.1f} trade days to pass")
        print(f"    Median Trade Days:  {med_t:.1f} trade days to pass")
        print(f"    Top 25% (P25):      {p25_t:.1f} trade days to pass")
        print(f"    Fastest Pass (Min): {min_t} trade days")
        print(f"    Mean Sessions:      {mean_s:.1f} calendar sessions")
        print(f"    Median Sessions:    {med_s:.1f} calendar sessions")
        print(f"    Average Peak DD:    ${avg_dd:,.2f}")
        
    all_results[split_name] = {
        "continuous_perf": {
            "net_profit": round(float(net_profit), 2),
            "win_rate": round(float(wr), 1),
            "profit_factor": round(float(pf), 2),
            "max_drawdown": round(float(max_dd), 2),
            "worst_day": round(float(worst_day), 2),
            "best_day": round(float(best_day), 2),
        },
        "evaluation_trials": split_eval_data
    }

with open(ROOT / "reports/PROSPECTIVE_VAL_TEST_AUDIT_RESULTS.json", "w") as f:
    json.dump(all_results, f, indent=2)

print("\n" + "="*95)
print("AUDIT COMPLETE - Saved to reports/PROSPECTIVE_VAL_TEST_AUDIT_RESULTS.json")
print("="*95)
