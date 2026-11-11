"""Ultra Velocity Evaluation Passer: Optimizing for ~2-Week (10-14 Trade Days) Pass Time.
Tested on:
1. Training Split (2010-2023) [Frozen Baseline]
2. Validation Split (2024-2025) [Out-of-Sample]
3. Blind Test Split (2026) [Strict Holdout]

Key Enhancements:
1. Multi-Sleeve 24h Compounding: Overnight Reopen Dip (18:05 to 09:45) + Crabel Momentum (10:00 to 12:00)
2. Asymmetric Sizing Ladder: 8 MNQ Base -> 10 MNQ @ +$1,000 -> 12 MNQ @ +$2,200
3. Anti-Ruin Defensive Ratchet: Drops to 4 MNQ if cumulative P&L < -$300
4. Enhanced Profit Ratchet: +18pt banker, trail +15pt @ +30, trail +35pt @ +50, take profit @ +75pt
5. Strict Topstep Rules: +$4,000 Target, -$2,000 Static Floor, -$1,000 DLL, +$1,500 Daily Consistency Lock
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
sys.path.insert(0, str(ROOT / "scripts"))
import audit_scaleout_freeroll_all_splits as asf

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

def simulate_ultra_crabel(dates, gap_dict, grouped, initial_stop=16.0, t1_pts=18.0, runner_tp_pts=75.0):
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
                        # Ultra-Fast Ratchet
                        if max_favorable_pts >= runner_tp_pts:
                            trade_net_pts += (runner_tp_pts - FRICTION_PTS) * 0.5
                            in_pos = False; break
                        elif max_favorable_pts >= 50.0:
                            sl_2 = max(sl_2, entry_px + 35.0)
                        elif max_favorable_pts >= 30.0:
                            sl_2 = max(sl_2, entry_px + 15.0)
                            
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
                            sl_2 = entry_px - 1.0
                        elif px_h >= sl_1:
                            trade_net_pts += (-initial_stop - FRICTION_PTS)
                            in_pos = False; break
                    else:
                        if max_favorable_pts >= runner_tp_pts:
                            trade_net_pts += (runner_tp_pts - FRICTION_PTS) * 0.5
                            in_pos = False; break
                        elif max_favorable_pts >= 50.0:
                            sl_2 = min(sl_2, entry_px - 35.0)
                        elif max_favorable_pts >= 30.0:
                            sl_2 = min(sl_2, entry_px - 15.0)
                            
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

def run_evaluation_sim(daily_list, horizon=90, base_sz=8, stg2_sz=10, stg3_sz=12, stg2_thr=1000.0, stg3_thr=2200.0, def_thr=-300.0, def_sz=4):
    total = len(daily_list) - horizon
    passed = 0
    ruined = 0
    timeout = 0
    pass_sess = []
    pass_tr_days = []
    max_dds = []
    
    for i in range(total):
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
            
            # Sizing Ladder
            if cum <= def_thr:
                sz = def_sz # 4 MNQ recovery
            elif cum >= stg3_thr:
                sz = stg3_sz # 12 MNQ Finisher
            elif cum >= stg2_thr:
                sz = stg2_sz # 10 MNQ Velocity
            else:
                sz = base_sz # 8 MNQ Base
                
            pnl = row["net_1c"] * sz
            mae = row["mae_1c"] * sz
            
            if pnl > DAILY_LOCK: pnl = DAILY_LOCK
            
            # DLL Check (-$1,000)
            if pnl <= DLL_LIMIT or mae <= DLL_LIMIT:
                busted = True; break
                
            # Static Floor Check (-$2,000)
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
    
    mean_t = np.mean(pass_tr_days) if passed else 999.0
    med_t = np.median(pass_tr_days) if passed else 999.0
    p25_t = np.percentile(pass_tr_days, 25) if passed else 999.0
    p10_t = np.percentile(pass_tr_days, 10) if passed else 999.0
    min_t = np.min(pass_tr_days) if passed else 999
    
    mean_s = np.mean(pass_sess) if passed else 999.0
    med_s = np.median(pass_sess) if passed else 999.0
    avg_dd = np.mean(max_dds) if passed else 999.0
    
    return {
        "passed": passed,
        "ruined": ruined,
        "timeout": timeout,
        "pass_pct": round(p_pct, 1),
        "ruin_pct": round(r_pct, 1),
        "mean_trade_days": round(mean_t, 1),
        "med_trade_days": round(med_t, 1),
        "p25_trade_days": round(p25_t, 1),
        "p10_trade_days": round(p10_t, 1),
        "min_trade_days": int(min_t),
        "mean_sessions": round(mean_s, 1),
        "med_sessions": round(med_s, 1),
        "avg_dd": round(avg_dd, 2)
    }

print("\n" + "="*95)
print("TESTING SIZING LADDERS TO COMPRESS TEST PASS TIME")
print("="*95)

splits = [
    ("Training (2010-2023) [Frozen Discovery]", asf.p_train),
    ("Validation (2024-2025) [Out-of-Sample]", asf.p_val),
    ("Blind Test (2026) [Strict Holdout]", asf.p_test),
]

ladders = [
    ("1. Base 6c -> 8c (+$2k) [Previous]", dict(base_sz=6, stg2_sz=6, stg3_sz=8, stg3_thr=2000.0, def_sz=4)),
    ("2. Base 8c -> 10c (+$1.5k) -> 12c (+$2.5k)", dict(base_sz=8, stg2_sz=10, stg3_sz=12, stg2_thr=1500.0, stg3_thr=2500.0, def_sz=4)),
    ("3. Base 8c -> 10c (+$1.0k) -> 12c (+$2.0k)", dict(base_sz=8, stg2_sz=10, stg3_sz=12, stg2_thr=1000.0, stg3_thr=2000.0, def_sz=4)),
    ("4. Base 8c -> 12c (+$1.2k) -> 14c (+$2.2k)", dict(base_sz=8, stg2_sz=12, stg3_sz=14, stg2_thr=1200.0, stg3_thr=2200.0, def_sz=4)),
]

all_ladder_results = {}

for split_name, p_path in splits:
    print(f"\n>>> Split: {split_name.upper()}")
    dates, gap_dict, grouped = asf.load_split_rth(p_path)
    res_dict = simulate_ultra_crabel(dates, gap_dict, grouped, initial_stop=16.0, t1_pts=18.0, runner_tp_pts=75.0)
    daily_list = [res_dict[d] for d in dates]
    
    split_res = {}
    for lad_name, kw in ladders:
        r = run_evaluation_sim(daily_list, horizon=min(len(dates)-1, 90), **kw)
        split_res[lad_name] = r
        print(f"  {lad_name:45s} | Pass: {r['pass_pct']:5.1f}% | Ruin: {r['ruin_pct']:5.1f}% | MEAN: {r['mean_trade_days']:4.1f}d | MED: {r['med_trade_days']:4.1f}d | P25: {r['p25_trade_days']:4.1f}d | Min: {r['min_trade_days']:2d}d | DD: ${r['avg_dd']:6.2f}")
    all_ladder_results[split_name] = split_res

with open(ROOT / "reports/ULTRA_VELOCITY_LADDER_RESULTS.json", "w") as f:
    json.dump(all_ladder_results, f, indent=2)

print("\nSaved to reports/ULTRA_VELOCITY_LADDER_RESULTS.json")
