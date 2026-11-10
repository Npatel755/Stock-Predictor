"""Champion Enhancement Lab: Systematically Improving Evaluation Pass Velocity on Training Split.
METHODOLOGICAL INVARIANT:
- 100% STRICTLY ON TRAINING DATA (2010-06-01 to 2023-12-31).
- ZERO ACCESS, ZERO LOOKUPS, ZERO TUNING ON VALIDATION (2024-2025) OR BLIND TEST (2026).
"""
import sys, json, gc
from pathlib import Path
import numpy as np, pandas as pd, duckdb

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
p_train = ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/train.parquet"

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

print("Loading Training RTH minute bars via DuckDB...")
con = duckdb.connect()
con.execute("PRAGMA memory_limit='2GB'")
q = f"""
SELECT 
    (timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))::DATE AS date,
    (date_part('hour', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))*60 + 
     date_part('minute', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ)))::INT AS sod,
    open::DOUBLE AS open,
    high::DOUBLE AS high,
    low::DOUBLE AS low,
    close::DOUBLE AS close,
    volume::DOUBLE AS volume
FROM read_parquet('{p_train}')
WHERE (date_part('hour', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))*60 + 
       date_part('minute', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))) BETWEEN 570 AND 960
ORDER BY date, sod
"""
rth = con.execute(q).fetch_df()
con.close()

dates = sorted(rth["date"].unique())
daily_eod = rth[rth.sod == 960].groupby("date")["close"].last()
daily_sod = rth[rth.sod == 570].groupby("date")["open"].first()
gap_dict = (daily_sod - daily_eod.shift(1)).dropna().to_dict()

grouped = {}
for d, g in rth.groupby("date"):
    grouped[d] = {
        "sod": g["sod"].to_numpy(),
        "open": g["open"].to_numpy(),
        "high": g["high"].to_numpy(),
        "low": g["low"].to_numpy(),
        "close": g["close"].to_numpy(),
        "volume": g["volume"].to_numpy(),
    }
del rth
gc.collect()

print(f"Loaded {len(dates)} sessions across 14-year Training Split.")

def simulate_strategy_variant(
    initial_stop=16.0,
    t1_pts=28.0,
    runner_tp=120.0,
    min_or_rng=15.0,
    max_or_rng=120.0,
    min_gap_pts=0.0, # require minimum gap size
    gap_direction_only=True,
    ratchet_profile="fixed_120", # "fixed_120", "ratchet_ladder", "tight_ratchet"
    vix_floor=15.0
):
    daily_res = {}
    for d in dates:
        vix = get_vix(d)
        gap = gap_dict.get(d, 0.0)
        if vix < vix_floor or d not in grouped:
            daily_res[str(d)] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        bars = grouped[d]
        sod, high, low, close = bars["sod"], bars["high"], bars["low"], bars["close"]
        mask_15 = sod < 585
        if not mask_15.any():
            daily_res[str(d)] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        hi_15 = high[mask_15].max()
        lo_15 = low[mask_15].min()
        rng_15 = hi_15 - lo_15
        
        # Opening Range filter
        if rng_15 < min_or_rng or rng_15 > max_or_rng:
            daily_res[str(d)] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        # Gap size filter
        if abs(gap) < min_gap_pts:
            daily_res[str(d)] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        idx_trade = np.where((sod >= 585) & (sod <= 955))[0]
        if len(idx_trade) == 0:
            daily_res[str(d)] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
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
        max_fav = 0.0
        
        for idx in idx_trade:
            px_h, px_l = high[idx], low[idx]
            if not in_pos:
                if (not gap_direction_only or gap >= 0.0) and px_h > hi_15:
                    in_pos = True; pos_dir = 1; entry_px = hi_15
                    sl_1 = entry_px - initial_stop
                    sl_2 = sl_1
                    tp_1 = entry_px + t1_pts
                elif (not gap_direction_only or gap <= 0.0) and px_l < lo_15:
                    in_pos = True; pos_dir = -1; entry_px = lo_15
                    sl_1 = entry_px + initial_stop
                    sl_2 = sl_1
                    tp_1 = entry_px - t1_pts
            else:
                if pos_dir == 1:
                    adv = max(px_l - entry_px, -initial_stop)
                    fav = px_h - entry_px
                    if not leg1_closed and adv < trade_mae_pts: trade_mae_pts = adv
                    if fav > max_fav: max_fav = fav
                    
                    if not leg1_closed:
                        if px_h >= tp_1:
                            trade_net_pts += (t1_pts - FRICTION_PTS) * 0.5
                            leg1_closed = True
                            sl_2 = entry_px + 1.0 # Breakeven
                        elif px_l <= sl_1:
                            trade_net_pts += (-initial_stop - FRICTION_PTS)
                            in_pos = False; break
                    else:
                        # Runner trailing ratchet profiles
                        if ratchet_profile == "ratchet_ladder":
                            if max_fav >= runner_tp:
                                trade_net_pts += (runner_tp - FRICTION_PTS) * 0.5
                                in_pos = False; break
                            elif max_fav >= 90.0:
                                sl_2 = max(sl_2, entry_px + 70.0)
                            elif max_fav >= 60.0:
                                sl_2 = max(sl_2, entry_px + 40.0)
                            elif max_fav >= 40.0:
                                sl_2 = max(sl_2, entry_px + 20.0)
                        elif ratchet_profile == "tight_ratchet":
                            if max_fav >= runner_tp:
                                trade_net_pts += (runner_tp - FRICTION_PTS) * 0.5
                                in_pos = False; break
                            elif max_fav >= 70.0:
                                sl_2 = max(sl_2, entry_px + 50.0)
                            elif max_fav >= 45.0:
                                sl_2 = max(sl_2, entry_px + 25.0)
                        elif ratchet_profile == "fixed_120":
                            if max_fav >= runner_tp:
                                trade_net_pts += (runner_tp - FRICTION_PTS) * 0.5
                                in_pos = False; break
                                
                        if px_l <= sl_2:
                            pts_exit = sl_2 - entry_px
                            trade_net_pts += (pts_exit - FRICTION_PTS) * 0.5
                            in_pos = False; break
                else: # Short
                    adv = max(entry_px - px_h, -initial_stop)
                    fav = entry_px - px_l
                    if not leg1_closed and adv < trade_mae_pts: trade_mae_pts = adv
                    if fav > max_fav: max_fav = fav
                    
                    if not leg1_closed:
                        if px_l <= tp_1:
                            trade_net_pts += (t1_pts - FRICTION_PTS) * 0.5
                            leg1_closed = True
                            sl_2 = entry_px - 1.0 # Breakeven
                        elif px_h >= sl_1:
                            trade_net_pts += (-initial_stop - FRICTION_PTS)
                            in_pos = False; break
                    else:
                        if ratchet_profile == "ratchet_ladder":
                            if max_fav >= runner_tp:
                                trade_net_pts += (runner_tp - FRICTION_PTS) * 0.5
                                in_pos = False; break
                            elif max_fav >= 90.0:
                                sl_2 = min(sl_2, entry_px - 70.0)
                            elif max_fav >= 60.0:
                                sl_2 = min(sl_2, entry_px - 40.0)
                            elif max_fav >= 40.0:
                                sl_2 = min(sl_2, entry_px - 20.0)
                        elif ratchet_profile == "tight_ratchet":
                            if max_fav >= runner_tp:
                                trade_net_pts += (runner_tp - FRICTION_PTS) * 0.5
                                in_pos = False; break
                            elif max_fav >= 70.0:
                                sl_2 = min(sl_2, entry_px - 50.0)
                            elif max_fav >= 45.0:
                                sl_2 = min(sl_2, entry_px - 25.0)
                        elif ratchet_profile == "fixed_120":
                            if max_fav >= runner_tp:
                                trade_net_pts += (runner_tp - FRICTION_PTS) * 0.5
                                in_pos = False; break
                                
                        if px_h >= sl_2:
                            pts_exit = entry_px - sl_2
                            trade_net_pts += (pts_exit - FRICTION_PTS) * 0.5
                            in_pos = False; break
                            
        if in_pos:
            last_c = close[idx_trade[-1]]
            eod_pts = (last_c - entry_px if pos_dir == 1 else entry_px - last_c) - FRICTION_PTS
            qty_rem = 0.5 if leg1_closed else 1.0
            trade_net_pts += eod_pts * qty_rem
            
        daily_res[str(d)] = {
            "net_1c": float(trade_net_pts * PT_VAL),
            "mae_1c": float(trade_mae_pts * PT_VAL),
            "traded": bool(in_pos or trade_net_pts != 0.0)
        }
    return daily_res

def eval_passer_fast(daily_res, label, base_sz=8, stg2_sz=10, stg3_sz=12, stg2_thr=1200.0, stg3_thr=2400.0, def_thr=-200.0, def_sz=1, max_horizon=100):
    date_strs = [str(d) for d in dates]
    active_days = [d for d in date_strs if daily_res.get(d, {}).get("traded", False)]
    
    # Continuous
    pnls = [daily_res[d]["net_1c"] * base_sz for d in active_days]
    net_c = sum(pnls)
    wr = sum(1 for p in pnls if p > 0) / len(pnls) * 100 if pnls else 0.0
    pf = sum(p for p in pnls if p > 0) / abs(sum(p for p in pnls if p < 0)) if sum(1 for p in pnls if p < 0) else 999.0
    
    # Trials
    passed, ruined = 0, 0
    pass_tr = []
    max_dds = []
    
    for i in range(len(dates) - max_horizon):
        cum = 0.0
        hwm = 0.0
        busted, pass_run = False, False
        peak_dd = 0.0
        tr_days = 0
        
        for step in range(max_horizon):
            d_str = date_strs[i + step]
            tr = daily_res.get(d_str, None)
            if not tr or not tr["traded"]:
                continue
                
            tr_days += 1
            if cum <= def_thr: sz = def_sz
            elif cum >= stg3_thr: sz = stg3_sz
            elif cum >= stg2_thr: sz = stg2_sz
            else: sz = base_sz
            
            pnl = tr["net_1c"] * sz
            mae = tr["mae_1c"] * sz
            
            if pnl <= DLL_LIMIT or mae <= DLL_LIMIT or (cum + mae) <= STATIC_FLOOR:
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
    min_tr = np.min(pass_tr) if passed else 999
    avg_dd = np.mean(max_dds) if passed else 999.0
    
    print(f"{label:58s} | Pass: {p_pct:5.1f}% | Ruin: {r_pct:4.1f}% | MeanTR: {mean_tr:4.1f}d | MedTR: {med_tr:4.1f}d | P25: {p25_tr:4.1f}d | Min: {min_tr:2d}d | WR: {wr:4.1f}% | PF: {pf:4.2f} | Net: ${net_c:7.0f} | DD: ${avg_dd:.0f}")
    return {
        "label": label, "pass_pct": round(p_pct, 1), "ruin_pct": round(r_pct, 1),
        "mean_tr": round(mean_tr, 1), "med_tr": round(med_tr, 1), "p25_tr": round(p25_tr, 1),
        "min_tr": int(min_tr), "wr": round(wr, 1), "pf": round(pf, 2), "net": round(net_c, 2), "dd": round(avg_dd, 2)
    }

print("\n" + "="*125)
print("TRAINING-ONLY ENHANCEMENT LAB: SYSTEMATIC EXPLORATION")
print("="*125)

results = []

# 1. Baseline Frozen Champion (Fixed 120 Runner)
r_base = simulate_strategy_variant(t1_pts=28.0, runner_tp=120.0, ratchet_profile="fixed_120")
results.append(eval_passer_fast(r_base, "1. Baseline Frozen (T1 +28, Runner +120 fixed)"))

# 2. Ratchet Ladder (Locks +20 @ +40, +40 @ +60, +70 @ +90, +120 TP)
r_ratchet = simulate_strategy_variant(t1_pts=28.0, runner_tp=120.0, ratchet_profile="ratchet_ladder")
results.append(eval_passer_fast(r_ratchet, "2. Ratchet Ladder (+20@40, +40@60, +70@90, +120TP)"))

# 3. Tight Ratchet (+25 @ +45, +50 @ +70, +120 TP)
r_tight = simulate_strategy_variant(t1_pts=28.0, runner_tp=120.0, ratchet_profile="tight_ratchet")
results.append(eval_passer_fast(r_tight, "3. Tight Ratchet (+25@45, +50@70, +120TP)"))

# 4. Faster Banker T1 (+24 pts banker instead of +28 pts)
r_fast_bank = simulate_strategy_variant(t1_pts=24.0, runner_tp=120.0, ratchet_profile="ratchet_ladder")
results.append(eval_passer_fast(r_fast_bank, "4. Fast Banker (+24pt T1 + Ratchet Ladder)"))

# 5. Ultra Banker T1 (+20 pts banker)
r_ultra_bank = simulate_strategy_variant(t1_pts=20.0, runner_tp=120.0, ratchet_profile="ratchet_ladder")
results.append(eval_passer_fast(r_ultra_bank, "5. Ultra Banker (+20pt T1 + Ratchet Ladder)"))

# 6. High-Expectancy Opening Range Filter (OR >= 20.0 pts)
r_or20 = simulate_strategy_variant(t1_pts=28.0, runner_tp=120.0, min_or_rng=20.0, ratchet_profile="ratchet_ladder")
results.append(eval_passer_fast(r_or20, "6. Quality Filter: OR Range >= 20 pts + Ratchet"))

# 7. Quality Filter: Minimum Gap >= 5.0 pts
r_gap5 = simulate_strategy_variant(t1_pts=28.0, runner_tp=120.0, min_gap_pts=5.0, ratchet_profile="ratchet_ladder")
results.append(eval_passer_fast(r_gap5, "7. Quality Filter: Gap >= 5 pts + Ratchet"))

# 8. Sizing Ladder Tuning on Best Variant (Test different stage thresholds)
print("\n--- Sizing Ladder Exploration on Ratchet Ladder ---")
results.append(eval_passer_fast(r_ratchet, "8. Ratchet Ladder (8c -> 10c @ $1.0k -> 12c @ $2.2k)", stg2_thr=1000.0, stg3_thr=2200.0))
results.append(eval_passer_fast(r_ratchet, "9. Ratchet Ladder (8c -> 11c @ $1.2k -> 13c @ $2.4k)", stg2_sz=11, stg3_sz=13, stg2_thr=1200.0, stg3_thr=2400.0))
results.append(eval_passer_fast(r_ratchet, "10. Ratchet Ladder Sprint (9c -> 11c @ $1.2k -> 13c @ $2.4k)", base_sz=9, stg2_sz=11, stg3_sz=13, stg2_thr=1200.0, stg3_thr=2400.0))
results.append(eval_passer_fast(r_ratchet, "11. Ratchet Ladder (8c -> 10c @ $1.2k -> 12c @ $2.4k, Def -$150)", def_thr=-150.0))

out_path = ROOT / "reports/TRAINING_CHAMPION_LAB_RESULTS.json"
with open(out_path, "w") as f:
    json.dump(results, f, indent=2)
print(f"\nAll enhancement lab results saved to {out_path}")
