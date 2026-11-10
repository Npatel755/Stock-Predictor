"""Audit: Empirical Time-to-Pass Distribution (Min, Max, Avg, Median).
Simulates full forward lifecycle of evaluation accounts across 16.9 years (2010-2026):
Rules:
- Profit Target: +$4,000
- Trailing Drawdown Floor: $2,000
- Daily Loss Limit: $1,000
- Consistency Rule: No single day > 50% of total profit (max day <= $2,000)

Calculates:
- Min days to pass
- Max days to pass
- Mean (average) days to pass
- Median days to pass
- 25th and 75th percentiles
- Total Pass Rate vs Total Ruin Rate
"""
import sys, json, gc
from pathlib import Path
import numpy as np, pandas as pd, duckdb

ROOT = Path(__file__).resolve().parents[1]

# Load VIX
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

def load_all_rth():
    """Loads all 16.9 years of RTH bars sequentially."""
    paths = [
        str(ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/train.parquet"),
        str(ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/validation.parquet"),
        str(ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/test.parquet")
    ]
    con = duckdb.connect()
    con.execute("PRAGMA memory_limit='1GB'")
    
    dfs = []
    for p in paths:
        q = f"""
        SELECT 
            (timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))::DATE AS date,
            (date_part('hour', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))*60 + 
             date_part('minute', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ)))::INT AS sod,
            open::DOUBLE AS open,
            high::DOUBLE AS high,
            low::DOUBLE AS low,
            close::DOUBLE AS close
        FROM read_parquet('{p}')
        WHERE (date_part('hour', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))*60 + 
               date_part('minute', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))) BETWEEN 570 AND 960
        ORDER BY date, sod
        """
        dfs.append(con.execute(q).fetch_df())
    con.close()
    
    rth = pd.concat(dfs, ignore_index=True)
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
    del rth, dfs
    gc.collect()
    return dates, gap_dict, grouped

print("Loading complete 16.9-year history (2010-2026)...", flush=True)
dates, gap_dict, grouped = load_all_rth()
print(f"Loaded {len(dates):,} total trading days.", flush=True)

def generate_daily_pnl(total_contracts=12, initial_stop=16.0, t1_pts=28.0, runner_tp_pts=120.0, vix_floor=15.0):
    half_contracts = total_contracts // 2
    daily_pnl = {}
    
    for d in dates:
        vix = get_vix_for_date(d)
        gap = gap_dict.get(d, 0.0)
        
        if vix < vix_floor or d not in grouped:
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
            
        idx_trade = np.where((sod >= 585) & (sod <= 955))[0]
        if len(idx_trade) == 0:
            daily_pnl[d] = {"net": 0.0, "mae": 0.0}
            continue
            
        day_pnl = 0.0
        day_mae = 0.0
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
            
            if not in_pos:
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
            else:
                if pos_dir == 1:
                    adverse = px_l - entry_px
                    if adverse < 0:
                        adv_dollars = adverse * PT_VAL * (half_contracts if leg1_closed else total_contracts)
                        if (day_pnl + adv_dollars) < day_mae:
                            day_mae = day_pnl + adv_dollars
                            
                    if not leg1_closed:
                        if px_h >= tp_leg1:
                            gain_pts = t1_pts - FRICTION_PTS
                            day_pnl += gain_pts * PT_VAL * half_contracts
                            leg1_closed = True
                            sl_leg2 = entry_px + 1.0
                        elif px_l <= sl_leg1:
                            loss_pts = -initial_stop - FRICTION_PTS
                            day_pnl += loss_pts * PT_VAL * total_contracts
                            in_pos = False
                            break
                    else:
                        if px_h >= tp_leg2:
                            gain_pts = runner_tp_pts - FRICTION_PTS
                            day_pnl += gain_pts * PT_VAL * half_contracts
                            in_pos = False
                            break
                        elif px_l <= sl_leg2:
                            gain_pts = (sl_leg2 - entry_px) - FRICTION_PTS
                            day_pnl += gain_pts * PT_VAL * half_contracts
                            in_pos = False
                            break
                elif pos_dir == -1:
                    adverse = entry_px - px_h
                    if adverse < 0:
                        adv_dollars = adverse * PT_VAL * (half_contracts if leg1_closed else total_contracts)
                        if (day_pnl + adv_dollars) < day_mae:
                            day_mae = day_pnl + adv_dollars
                            
                    if not leg1_closed:
                        if px_l <= tp_leg1:
                            gain_pts = t1_pts - FRICTION_PTS
                            day_pnl += gain_pts * PT_VAL * half_contracts
                            leg1_closed = True
                            sl_leg2 = entry_px - 1.0
                        elif px_h >= sl_leg1:
                            loss_pts = -initial_stop - FRICTION_PTS
                            day_pnl += loss_pts * PT_VAL * total_contracts
                            in_pos = False
                            break
                    else:
                        if px_l <= tp_leg2:
                            gain_pts = runner_tp_pts - FRICTION_PTS
                            day_pnl += gain_pts * PT_VAL * half_contracts
                            in_pos = False
                            break
                        elif px_h >= sl_leg2:
                            gain_pts = (entry_px - sl_leg2) - FRICTION_PTS
                            day_pnl += gain_pts * PT_VAL * half_contracts
                            in_pos = False
                            break
                            
                if day_pnl >= 1750.0:
                    break
                if day_pnl <= -400.0:
                    break
                    
        if in_pos:
            last_close = close[idx_trade[-1]]
            qty = half_contracts if leg1_closed else total_contracts
            pts = (last_close - entry_px if pos_dir == 1 else entry_px - last_close) - FRICTION_PTS
            day_pnl += pts * PT_VAL * qty
            
        daily_pnl[d] = {
            "net": day_pnl,
            "mae": min(day_mae, day_pnl)
        }
    return daily_pnl

def analyze_lifecycle(daily_pnl, label, target=4000.0, floor=2000.0, dll=1000.0, max_eval_days=90):
    """
    Simulates starting an evaluation on every single trading day in history.
    Tracks until account either passes ($4,000 + 50% consistency) or fails (drawdown or DLL).
    """
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
            
            # Check Daily Loss Limit breach
            if dp <= -dll or dm <= -dll:
                busted = True
                break
                
            # Check Trailing Drawdown breach
            if (hwm - (cum_pnl + dm)) >= floor or (cum_pnl + dm) <= -floor:
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
                
            # Check Target & Consistency Rule
            if cum_pnl >= target:
                # Topstep rule: No single day can exceed 50% of total profit
                if max_single_day <= (target * 0.50):
                    passed = True
                    days_to_pass.append(step + 1)
                    break
                # If target reached but single day > 50%, must keep trading until consistency met
                
        if busted:
            ruined_count += 1
        elif passed:
            passed_count += 1
        else:
            timeout_count += 1
            
    days_arr = np.array(days_to_pass) if len(days_to_pass) > 0 else np.array([0])
    
    print("=" * 80)
    print(f"LIFECYCLE EVALUATION ANALYSIS: {label}")
    print(f"Target: ${target:,.2f} | Floor: ${floor:,.2f} | DLL: ${dll:,.2f} | 50% Consistency Enforced")
    print("=" * 80)
    print(f"Total Evaluation Trials Simulated: {total_starts:,}")
    print(f"  Passed Accounts:                 {passed_count:,} ({passed_count/total_starts*100:.2f}%)")
    print(f"  Failed Accounts (Ruin):          {ruined_count:,} ({ruined_count/total_starts*100:.2f}%)")
    print(f"  Timed Out (> {max_eval_days} days):            {timeout_count:,} ({timeout_count/total_starts*100:.2f}%)")
    print("-" * 80)
    print(f"TIME TO PASS (TRADING DAYS):")
    print(f"  MINIMUM (Fastest Pass):          {days_arr.min()} trading days (~{days_arr.min()/5:.1f} weeks)")
    print(f"  AVERAGE (Mean):                  {days_arr.mean():.1f} trading days (~{days_arr.mean()/5:.1f} weeks)")
    print(f"  MEDIAN (50th Percentile):        {np.median(days_arr):.1f} trading days (~{np.median(days_arr)/5:.1f} weeks)")
    print(f"  25th PERCENTILE (Fast Market):   {np.percentile(days_arr, 25):.1f} trading days (~{np.percentile(days_arr, 25)/5:.1f} weeks)")
    print(f"  75th PERCENTILE (Normal Market): {np.percentile(days_arr, 75):.1f} trading days (~{np.percentile(days_arr, 75)/5:.1f} weeks)")
    print(f"  MAXIMUM (Slowest Pass):          {days_arr.max()} trading days (~{days_arr.max()/5:.1f} weeks)")
    print("=" * 80 + "\n")
    
    return {
        "label": label,
        "total_trials": total_starts,
        "passed": passed_count,
        "ruined": ruined_count,
        "pass_rate_pct": round(passed_count / total_starts * 100, 2),
        "ruin_rate_pct": round(ruined_count / total_starts * 100, 2),
        "min_days": int(days_arr.min()),
        "avg_days": round(float(days_arr.mean()), 1),
        "median_days": round(float(np.median(days_arr)), 1),
        "p25_days": round(float(np.percentile(days_arr, 25)), 1),
        "p75_days": round(float(np.percentile(days_arr, 75)), 1),
        "max_days": int(days_arr.max()),
    }

print("Running lifecycle simulation for 12 MNQ...", flush=True)
pnl_12c = generate_daily_pnl(total_contracts=12)
r_12c = analyze_lifecycle(pnl_12c, "Scale-Out Runner: 12 MNQ (Aggressive Sprint Tier)")

print("Running lifecycle simulation for 8 MNQ...", flush=True)
pnl_8c = generate_daily_pnl(total_contracts=8)
r_8c = analyze_lifecycle(pnl_8c, "Scale-Out Runner: 8 MNQ (Balanced Tier)")

print("Running lifecycle simulation for 6 MNQ...", flush=True)
pnl_6c = generate_daily_pnl(total_contracts=6)
r_6c = analyze_lifecycle(pnl_6c, "Scale-Out Runner: 6 MNQ (High-Survival Conservative Tier)")

# Save to JSON
with open(ROOT / "reports/TIME_TO_PASS_EVALUATION_REPORT.json", "w") as f:
    json.dump({"12c": r_12c, "8c": r_8c, "6c": r_6c}, f, indent=2)

print("Saved report to reports/TIME_TO_PASS_EVALUATION_REPORT.json")
print("DONE", flush=True)
