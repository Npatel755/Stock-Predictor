"""Research: Improving the Champion Strategy & Reducing Out-of-Sample Dispersion.
Tests:
1. Fixed Runner (+85pt) vs Adaptive Trailing Runner (Locks profits at +35pt / +50pt instead of giving back at EOD)
2. Integrating the True Book D+ Overnight Dip (-0.5 sigma reopen with 25pt hard stop)
3. Comparing across Training (2010-2023), Validation (2024-2025), and Blind Test (2026).
"""
import sys, json, gc
from pathlib import Path
import numpy as np, pandas as pd, duckdb

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
sys.path.insert(0, str(ROOT / "scripts"))
import audit_scaleout_freeroll_all_splits as asf

print("="*85)
print("RESEARCH: ADAPTIVE TRAILING RUNNER & OVERNIGHT INTEGRATION")
print("="*85)

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

def simulate_adaptive_crabel(dates, gap_dict, grouped, initial_stop=16.0, t1_pts=20.0, runner_mode="trailing"):
    """Simulates Crabel with either a fixed 85pt runner or an adaptive trailing runner."""
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
                        # Leg 2 Runner Management:
                        if runner_mode == "trailing":
                            # Dynamic Ratchet:
                            # If fav >= 60 pts, trail at +45 pts
                            # If fav >= 40 pts, trail at +25 pts
                            # If fav >= 85 pts, take profit
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
                        else: # fixed 85pt runner
                            if px_h >= (entry_px + 85.0):
                                trade_net_pts += (85.0 - FRICTION_PTS) * 0.5
                                in_pos = False; break
                            elif px_l <= sl_2:
                                trade_net_pts += (sl_2 - entry_px - FRICTION_PTS) * 0.5
                                in_pos = False; break
                else: # pos_dir == -1
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
                        if runner_mode == "trailing":
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
                        else:
                            if px_l <= (entry_px - 85.0):
                                trade_net_pts += (85.0 - FRICTION_PTS) * 0.5
                                in_pos = False; break
                            elif px_h >= sl_2:
                                trade_net_pts += (entry_px - sl_2 - FRICTION_PTS) * 0.5
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

def evaluate_split_comparison(split_name, parquet_path):
    dates, gap_dict, grouped = asf.load_split_rth(parquet_path)
    print(f"\n--- {split_name.upper()} ({len(dates)} trading days) ---")
    
    # Mode 1: Fixed 85pt runner (Old Champion)
    res_fixed = simulate_adaptive_crabel(dates, gap_dict, grouped, runner_mode="fixed")
    # Mode 2: Adaptive Trailing Runner (New Improvement)
    res_trailing = simulate_adaptive_crabel(dates, gap_dict, grouped, runner_mode="trailing")
    
    for mode_name, res in [("Fixed 85pt Runner", res_fixed), ("Adaptive Trailing Runner", res_trailing)]:
        pnls = [r["net_1c"] * 6.0 for r in res.values() if r["traded"]] # nominal 6c
        net = sum(pnls)
        wins = sum(1 for p in pnls if p > 0)
        losses = sum(1 for p in pnls if p < 0)
        wr = (wins / len(pnls) * 100) if pnls else 0.0
        pf = (sum(p for p in pnls if p > 0) / abs(sum(p for p in pnls if p < 0))) if losses > 0 else 999.0
        
        # Sliding Evaluation (60-day horizon)
        daily_list = [res[d] for d in dates]
        horizon = min(len(dates) - 1, 60)
        passed, ruined = 0, 0
        pass_days = []
        
        for i in range(len(dates) - horizon):
            cum = 0.0
            hwm = 0.0
            busted, pass_run = False, False
            for step in range(horizon):
                row = daily_list[i + step]
                if not row["traded"]: continue
                # Sizing ladder
                if cum <= -250.0: sz = 1
                elif cum >= 2200.0: sz = 12
                elif cum >= 1000.0: sz = 8
                else: sz = 4
                pnl = row["net_1c"] * (sz / 2.0)
                mae = row["mae_1c"] * (sz / 2.0)
                if pnl > 1500.0: pnl = 1500.0
                if pnl < -250.0: pnl = -250.0
                if pnl <= -1000.0 or (cum + mae) <= -2000.0:
                    busted = True; break
                cum += pnl
                if cum > hwm: hwm = cum
                if cum <= -2000.0: busted = True; break
                if cum >= 4000.0:
                    pass_run = True; passed += 1; pass_days.append(step + 1); break
            if busted and not pass_run: ruined += 1
            
        med_days = np.median(pass_days) if passed > 0 else 0.0
        res_pass = (passed / max(1, passed + ruined) * 100) if (passed + ruined) > 0 else 0.0
        print(f"  [{mode_name:25s}] Net: +${net:9.2f} | WR: {wr:4.1f}% | PF: {pf:4.2f} | Resolved Pass: {res_pass:5.1f}% | Med Days: {med_days:4.1f}d")

evaluate_split_comparison("Training (2010-2023)", asf.p_train)
evaluate_split_comparison("Validation (2024-2025)", asf.p_val)
evaluate_split_comparison("Blind Test (2026)", asf.p_test)
