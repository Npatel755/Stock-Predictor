"""Research: Lowering Average Time to Pass Evaluation Limit.
STRICTLY 2010-2023 TRAINING DATA ONLY.
Zero access to Validation (2024-2025) or Blind Test (2026).

Explores 4 Architectural Enhancements to cut time-to-pass from 36.6 days down to < 20 days:
1. Dynamic Trailing Profit Ratchet on Leg 2 (locking gains at +50/+80/+110 pts instead of binary all-or-nothing).
2. Faster Scale-Out T1 Target (+20, +24, +28 pts) to increase Breakeven conversion rate.
3. Multi-Opportunity Session Architecture: Adding a 10:30 Trend Continuation entry.
4. Volatility-Adaptive Contract Sizing (sizing up to 14 MNQ exclusively on VIX >= 22 expansion days).
"""
import sys, json, gc
from pathlib import Path
import numpy as np, pandas as pd, duckdb

ROOT = Path(__file__).resolve().parents[1]

print("=" * 85)
print("RESEARCH: OPTIMIZING AVERAGE TIME-TO-PASS (2010-2023 TRAINING DATA ONLY)")
print("=" * 85, flush=True)

# 1. Load VIX
vix_path = ROOT / "data/external/VIX_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df["date"] = pd.to_datetime(vix_df["DATE"]).dt.date
vix_dict = dict(zip(vix_df["date"], vix_df["CLOSE"]))
cboe_dates = sorted(list(vix_dict.keys()))

def get_vix_for_date(d):
    dt = pd.to_datetime(d).date()
    if dt in vix_dict:
        return vix_dict[dt]
    return vix_dict[cboe_dates[-1]]

FRICTION_PTS = 1.30
PT_VAL = 2.00

# 2. Load 14-Year Training Bars
path_train = str(ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/train.parquet")
con = duckdb.connect()
con.execute("PRAGMA memory_limit='1GB'")

q = f"""
SELECT 
    (timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))::DATE AS date,
    (date_part('hour', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))*60 + 
     date_part('minute', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ)))::INT AS sod,
    open::DOUBLE AS open,
    high::DOUBLE AS high,
    low::DOUBLE AS low,
    close::DOUBLE AS close
FROM read_parquet('{path_train}')
WHERE (date_part('hour', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))*60 + 
       date_part('minute', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))) BETWEEN 570 AND 960
ORDER BY date, sod
"""
rth = con.execute(q).fetch_df()
con.close()

dates = sorted(rth["date"].unique())
daily_eod = rth[rth.sod == 960].groupby("date")["close"].last()
daily_sod = rth[rth.sod == 570].groupby("date")["open"].first()
gap_series = (daily_sod - daily_eod.shift(1)).dropna()
gap_dict = gap_series.to_dict()

grouped = {}
for d, g in rth.groupby("date"):
    grouped[d] = {
        "sod": g["sod"].to_numpy(),
        "high": g["high"].to_numpy(),
        "low": g["low"].to_numpy(),
        "close": g["close"].to_numpy(),
    }
del rth
gc.collect()

print(f"Loaded {len(dates):,} training days (2010-2023).", flush=True)

def simulate_enhanced_engine(
    total_contracts=12,
    initial_stop=16.0,
    t1_pts=24.0,           # faster scale out
    runner_tp_pts=110.0,
    use_trailing_ratchet=True, # ratchet profit on runner
    allow_second_entry=False,  # second trade if morning won
    vix_adaptive_size=False    # 14c if VIX >= 22, 10c if VIX < 22
):
    daily_pnl = {}
    
    for d in dates:
        vix = get_vix_for_date(d)
        gap = gap_dict.get(d, 0.0)
        
        # Volatility filter
        if vix < 15.0 or d not in grouped:
            daily_pnl[d] = {"net": 0.0, "mae": 0.0}
            continue
            
        bars = grouped[d]
        sod = bars["sod"]
        high = bars["high"]
        low = bars["low"]
        close = bars["close"]
        
        mask_15 = sod < 585
        if not mask_15.any():
            daily_pnl[d] = {"net": 0.0, "mae": 0.0}
            continue
            
        hi_15 = high[mask_15].max()
        lo_15 = low[mask_15].min()
        rng_15 = hi_15 - lo_15
        
        if rng_15 < 15.0:
            daily_pnl[d] = {"net": 0.0, "mae": 0.0}
            continue
            
        # Determine contracts for today
        if vix_adaptive_size:
            n_c = 14 if vix >= 22.0 else (12 if vix >= 18.0 else 8)
        else:
            n_c = total_contracts
            
        half_c = n_c // 2
        
        idx_trade = np.where((sod >= 585) & (sod <= 955))[0]
        if len(idx_trade) == 0:
            daily_pnl[d] = {"net": 0.0, "mae": 0.0}
            continue
            
        day_pnl = 0.0
        day_mae = 0.0
        trades_today = 0
        
        in_pos = False
        pos_dir = 0
        entry_px = 0.0
        leg1_closed = False
        sl_leg1 = 0.0
        sl_leg2 = 0.0
        tp_leg1 = 0.0
        tp_leg2 = 0.0
        
        for idx in idx_trade:
            px_h, px_l = high[idx], low[idx]
            curr_sod = sod[idx]
            
            if not in_pos:
                # First entry (9:45 - 10:15)
                can_first = (curr_sod <= 615 and trades_today == 0)
                # Second entry (10:30 - 11:30) if allowed and first trade was profitable
                can_second = (allow_second_entry and trades_today == 1 and day_pnl > 0 and curr_sod >= 630 and curr_sod <= 690)
                
                if can_first:
                    if gap >= 0.0 and px_h > hi_15:
                        in_pos = True
                        pos_dir = 1
                        entry_px = hi_15
                        sl_leg1 = entry_px - initial_stop
                        sl_leg2 = sl_leg1
                        tp_leg1 = entry_px + t1_pts
                        tp_leg2 = entry_px + runner_tp_pts
                        leg1_closed = False
                    elif gap <= 0.0 and px_l < lo_15:
                        in_pos = True
                        pos_dir = -1
                        entry_px = lo_15
                        sl_leg1 = entry_px + initial_stop
                        sl_leg2 = sl_leg1
                        tp_leg1 = entry_px - t1_pts
                        tp_leg2 = entry_px - runner_tp_pts
                        leg1_closed = False
                elif can_second:
                    # Second entry: Trend extension breakout
                    if pos_dir == 1 and px_h > hi_15 + 20.0:
                        in_pos = True
                        pos_dir = 1
                        entry_px = px_h
                        sl_leg1 = entry_px - 14.0
                        sl_leg2 = sl_leg1
                        tp_leg1 = entry_px + 20.0
                        tp_leg2 = entry_px + 60.0
                        leg1_closed = False
                    elif pos_dir == -1 and px_l < lo_15 - 20.0:
                        in_pos = True
                        pos_dir = -1
                        entry_px = px_l
                        sl_leg1 = entry_px + 14.0
                        sl_leg2 = sl_leg1
                        tp_leg1 = entry_px - 20.0
                        tp_leg2 = entry_px - 60.0
                        leg1_closed = False
            else:
                if pos_dir == 1:
                    adverse = px_l - entry_px
                    if adverse < 0:
                        adv_dollars = adverse * PT_VAL * (half_c if leg1_closed else n_c)
                        if (day_pnl + adv_dollars) < day_mae:
                            day_mae = day_pnl + adv_dollars
                            
                    if not leg1_closed:
                        if px_h >= tp_leg1:
                            gain_pts = t1_pts - FRICTION_PTS
                            day_pnl += gain_pts * PT_VAL * half_c
                            leg1_closed = True
                            sl_leg2 = entry_px + 1.0 # Breakeven
                        elif px_l <= sl_leg1:
                            loss_pts = -initial_stop - FRICTION_PTS
                            day_pnl += loss_pts * PT_VAL * n_c
                            in_pos = False
                            trades_today += 1
                            break
                    else:
                        # Leg 2 Trailing Ratchet Logic
                        if use_trailing_ratchet:
                            run_up = px_h - entry_px
                            if run_up >= 90.0:
                                sl_leg2 = max(sl_leg2, entry_px + 65.0)
                            elif run_up >= 65.0:
                                sl_leg2 = max(sl_leg2, entry_px + 45.0)
                            elif run_up >= 45.0:
                                sl_leg2 = max(sl_leg2, entry_px + 25.0)
                                
                        if px_h >= tp_leg2:
                            gain_pts = runner_tp_pts - FRICTION_PTS
                            day_pnl += gain_pts * PT_VAL * half_c
                            in_pos = False
                            trades_today += 1
                            break
                        elif px_l <= sl_leg2:
                            gain_pts = (sl_leg2 - entry_px) - FRICTION_PTS
                            day_pnl += gain_pts * PT_VAL * half_c
                            in_pos = False
                            trades_today += 1
                            break
                elif pos_dir == -1:
                    adverse = entry_px - px_h
                    if adverse < 0:
                        adv_dollars = adverse * PT_VAL * (half_c if leg1_closed else n_c)
                        if (day_pnl + adv_dollars) < day_mae:
                            day_mae = day_pnl + adv_dollars
                            
                    if not leg1_closed:
                        if px_l <= tp_leg1:
                            gain_pts = t1_pts - FRICTION_PTS
                            day_pnl += gain_pts * PT_VAL * half_c
                            leg1_closed = True
                            sl_leg2 = entry_px - 1.0 # Breakeven
                        elif px_h >= sl_leg1:
                            loss_pts = -initial_stop - FRICTION_PTS
                            day_pnl += loss_pts * PT_VAL * n_c
                            in_pos = False
                            trades_today += 1
                            break
                    else:
                        if use_trailing_ratchet:
                            run_down = entry_px - px_l
                            if run_down >= 90.0:
                                sl_leg2 = min(sl_leg2, entry_px - 65.0)
                            elif run_down >= 65.0:
                                sl_leg2 = min(sl_leg2, entry_px - 45.0)
                            elif run_down >= 45.0:
                                sl_leg2 = min(sl_leg2, entry_px - 25.0)
                                
                        if px_l <= tp_leg2:
                            gain_pts = runner_tp_pts - FRICTION_PTS
                            day_pnl += gain_pts * PT_VAL * half_c
                            in_pos = False
                            trades_today += 1
                            break
                        elif px_h >= sl_leg2:
                            gain_pts = (entry_px - sl_leg2) - FRICTION_PTS
                            day_pnl += gain_pts * PT_VAL * half_c
                            in_pos = False
                            trades_today += 1
                            break
                            
                # Circuit breakers
                if day_pnl >= 1750.0:
                    break
                if day_pnl <= -400.0:
                    break
                    
        if in_pos:
            last_close = close[idx_trade[-1]]
            qty = half_c if leg1_closed else n_c
            pts = (last_close - entry_px if pos_dir == 1 else entry_px - last_close) - FRICTION_PTS
            day_pnl += pts * PT_VAL * qty
            
        daily_pnl[d] = {
            "net": day_pnl,
            "mae": min(day_mae, day_pnl)
        }
    return daily_pnl

def evaluate_lifecycle(daily_pnl, label, target=4000.0, floor=2000.0, dll=1000.0, max_eval_days=90):
    days_to_pass = []
    ruined_count = 0
    passed_count = 0
    timeout_count = 0
    
    total_starts = len(dates) - max_eval_days
    
    for start_idx in range(total_starts):
        cum_pnl = 0.0
        hwm = 0.0
        busted = False
        passed = False
        max_single_day = -9999.0
        
        for step in range(max_eval_days):
            d = dates[start_idx + step]
            dp = daily_pnl[d]["net"]
            dm = daily_pnl[d]["mae"]
            
            if dp <= -dll or dm <= -dll or (hwm - (cum_pnl + dm)) >= floor or (cum_pnl + dm) <= -floor:
                busted = True
                break
                
            cum_pnl += dp
            if cum_pnl > hwm:
                hwm = cum_pnl
                
            if (hwm - cum_pnl) >= floor or cum_pnl <= -floor:
                busted = True
                break
                
            if dp > max_single_day:
                max_single_day = dp
                
            if cum_pnl >= target:
                if max_single_day <= (target * 0.50):
                    passed = True
                    days_to_pass.append(step + 1)
                    break
                    
        if busted:
            ruined_count += 1
        elif passed:
            passed_count += 1
        else:
            timeout_count += 1
            
    days_arr = np.array(days_to_pass) if len(days_to_pass) > 0 else np.array([0])
    pass_pct = (passed_count / total_starts) * 100
    ruin_pct = (ruined_count / total_starts) * 100
    
    print(f"\n{label}:")
    print(f"  Pass Rate:          {pass_pct:.1f}% ({passed_count} passes) | Ruin Rate: {ruin_pct:.1f}% ({ruined_count} ruins)")
    print(f"  Fastest Pass (Min): {days_arr.min()} trading days (~{days_arr.min()/5:.1f} weeks)")
    print(f"  Fast Market (p25):  {np.percentile(days_arr, 25):.1f} trading days (~{np.percentile(days_arr, 25)/5:.1f} weeks)")
    print(f"  Median Time:        {np.median(days_arr):.1f} trading days (~{np.median(days_arr)/5:.1f} weeks)")
    print(f"  Average Time:       {days_arr.mean():.1f} trading days (~{days_arr.mean()/5:.1f} weeks)")
    print(f"  Slowest Pass (Max): {days_arr.max()} trading days (~{days_arr.max()/5:.1f} weeks)")
    
    return {
        "label": label,
        "pass_pct": round(pass_pct, 1),
        "ruin_pct": round(ruin_pct, 1),
        "min": int(days_arr.min()),
        "p25": round(float(np.percentile(days_arr, 25)), 1),
        "median": round(float(np.median(days_arr)), 1),
        "mean": round(float(days_arr.mean()), 1),
        "max": int(days_arr.max()),
    }

# Run Comparison Experiments on Training Partition
print("\n--- BASELINE: ag_freeroll_sprint_v1 (12 MNQ, Fixed T1=28, No Ratchet) ---")
pnl_base = simulate_enhanced_engine(total_contracts=12, initial_stop=16.0, t1_pts=28.0, runner_tp_pts=120.0, use_trailing_ratchet=False)
r0 = evaluate_lifecycle(pnl_base, "Baseline v1 (No Ratchet)")

print("\n--- ENHANCEMENT 1: Dynamic Trailing Ratchet on Runner (+45->+25, +65->+45, +90->+65) ---")
pnl_e1 = simulate_enhanced_engine(total_contracts=12, initial_stop=16.0, t1_pts=28.0, runner_tp_pts=110.0, use_trailing_ratchet=True)
r1 = evaluate_lifecycle(pnl_e1, "Enhancement 1 (Dynamic Trailing Ratchet)")

print("\n--- ENHANCEMENT 2: Faster Scale-Out T1 (+22 pts) + Dynamic Ratchet ---")
pnl_e2 = simulate_enhanced_engine(total_contracts=12, initial_stop=16.0, t1_pts=22.0, runner_tp_pts=110.0, use_trailing_ratchet=True)
r2 = evaluate_lifecycle(pnl_e2, "Enhancement 2 (Faster Scale-Out T1=22 + Ratchet)")

print("\n--- ENHANCEMENT 3: Faster Scale-Out T1=22 + Dynamic Ratchet + Volatility-Adaptive Sizing (14c on VIX>=22) ---")
pnl_e3 = simulate_enhanced_engine(total_contracts=12, initial_stop=16.0, t1_pts=22.0, runner_tp_pts=110.0, use_trailing_ratchet=True, vix_adaptive_size=True)
r3 = evaluate_lifecycle(pnl_e3, "Enhancement 3 (Adaptive Size 14c on High VIX + T1=22 + Ratchet)")

# Save research output
with open(ROOT / "reports/RESEARCH_LOWER_TIME_TO_PASS_RESULTS.json", "w") as f:
    json.dump({"r0": r0, "r1": r1, "r2": r2, "r3": r3}, f, indent=2)

print("\nSaved research results to reports/RESEARCH_LOWER_TIME_TO_PASS_RESULTS.json")
print("DONE", flush=True)
