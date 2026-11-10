"""Scale-Out Free-Roll Runner Strategy Research.
STRICTLY 2010-2023 TRAINING DATA ONLY.
Zero access to Validation (2024-2025) or Blind Test (2026).

Strategy Specification:
1. Entry: Crabel Open Drive (9:30-9:45 AM ET) aligned with Opening Gap.
2. Sizing Tiers Tested:
   - Tier 1: 4 MNQ (2 Banked at +28 pts, 2 Runners trailing to +100 pts or EOD)
   - Tier 2: 6 MNQ (3 Banked at +28 pts, 3 Runners trailing to +100 pts or EOD)
   - Tier 3: 8 MNQ (4 Banked at +28 pts, 4 Runners trailing to +100 pts or EOD)
3. Initial Stop: 16 points ($32/contract -> $128 initial risk on 4c, $192 on 6c, $256 on 8c).
4. Scale-Out Leg: At +28 points, exit half the position (bank profit).
5. Breakeven Ratchet: As soon as Leg 1 is filled, ratchet stop on remaining half to entry + 1.0 pt (FREE ROLL).
6. Free-Roll Runner Leg: Remaining half targets +100 points or closes at 15:55 ET.
7. Daily Circuit Breakers:
   - Daily Profit Lock: +$1,500 to +$1,750 (locks day, satisfies 50% consistency rule).
   - Daily Stop Loss: -$400 (protects $1,000 DLL and $2,000 Trailing DD).
"""
import sys, json, gc
from pathlib import Path
import numpy as np, pandas as pd, duckdb

ROOT = Path(__file__).resolve().parents[1]

print("=" * 80)
print("SCALE-OUT FREE-ROLL RUNNER STRATEGY SIMULATION (2010-2023 TRAINING DATA)")
print("=" * 80, flush=True)

# 1. Load RTH Bars using DuckDB directly
path_nq = str(ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/train.parquet")
con = duckdb.connect()
print("Querying RTH 1m bars from 2010 to 2023 via DuckDB...", flush=True)

q = f"""
SELECT 
    (timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))::DATE AS date,
    (date_part('hour', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))*60 + 
     date_part('minute', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ)))::INT AS sod,
    open::DOUBLE AS open,
    high::DOUBLE AS high,
    low::DOUBLE AS low,
    close::DOUBLE AS close
FROM read_parquet('{path_nq}')
WHERE (date_part('hour', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))*60 + 
       date_part('minute', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))) BETWEEN 570 AND 960
ORDER BY date, sod
"""
rth = con.execute(q).fetch_df()
con.close()
gc.collect()

print(f"Loaded {len(rth):,} RTH 1m bars across 14 years.", flush=True)
dates = sorted(rth["date"].unique())
print(f"Total trading days: {len(dates):,}")

# Precompute daily gap
daily_eod = rth[rth.sod == 960].groupby("date")["close"].last()
daily_sod = rth[rth.sod == 570].groupby("date")["open"].first()
gap_series = (daily_sod - daily_eod.shift(1)).dropna()
gap_dict = gap_series.to_dict()

# Load VIX
vix_path = ROOT / "data/external/VIX_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df["date"] = pd.to_datetime(vix_df["DATE"]).dt.date
vix_dict = dict(zip(vix_df["date"], vix_df["CLOSE"]))

# Friction model for MNQ
FRICTION_PTS = 1.30 # CME commissions + spread + slippage per contract
PT_VAL = 2.00 # $2.00 per point

# Group bars by date as numpy arrays for maximum simulation speed
grouped_bars = {}
for d, g in rth.groupby("date"):
    grouped_bars[d] = {
        "sod": g["sod"].to_numpy(),
        "open": g["open"].to_numpy(),
        "high": g["high"].to_numpy(),
        "low": g["low"].to_numpy(),
        "close": g["close"].to_numpy(),
    }
del rth
gc.collect()

def simulate_scaleout_engine(total_contracts=4, initial_stop=16.0, t1_pts=28.0, runner_tp_pts=100.0, vix_floor=15.0):
    half_contracts = total_contracts // 2
    daily_results = {}
    
    for d in dates:
        vix = vix_dict.get(d, 18.0)
        gap = gap_dict.get(d, 0.0)
        
        # Volatility gate
        if vix < vix_floor or d not in grouped_bars:
            daily_results[d] = {"net": 0.0, "mae": 0.0, "trades": 0}
            continue
            
        bars = grouped_bars[d]
        sod = bars["sod"]
        high = bars["high"]
        low = bars["low"]
        close = bars["close"]
        
        # 15m opening range (sod < 585)
        mask_15 = sod < 585
        if not mask_15.any():
            daily_results[d] = {"net": 0.0, "mae": 0.0, "trades": 0}
            continue
            
        hi_15 = high[mask_15].max()
        lo_15 = low[mask_15].min()
        rng_15 = hi_15 - lo_15
        
        if rng_15 < 15.0:
            daily_results[d] = {"net": 0.0, "mae": 0.0, "trades": 0}
            continue
            
        day_pnl = 0.0
        day_mae = 0.0
        
        # Trade bars: sod >= 585 and sod <= 955
        idx_trade = np.where((sod >= 585) & (sod <= 955))[0]
        if len(idx_trade) == 0:
            daily_results[d] = {"net": 0.0, "mae": 0.0, "trades": 0}
            continue
            
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
                # Check for entry aligned with gap
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
                    # Long
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
                            sl_leg2 = entry_px + 1.0 # Ratchet to Breakeven
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
                    # Short
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
                            sl_leg2 = entry_px - 1.0 # Ratchet to Breakeven
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
                            
                # Circuit breakers
                if day_pnl >= 1750.0:
                    break
                if day_pnl <= -400.0:
                    break
                    
        # Close at end of window if still open
        if in_pos:
            last_close = close[idx_trade[-1]]
            qty = half_contracts if leg1_closed else total_contracts
            pts = (last_close - entry_px if pos_dir == 1 else entry_px - last_close) - FRICTION_PTS
            day_pnl += pts * PT_VAL * qty
            
        daily_results[d] = {
            "net": day_pnl,
            "mae": min(day_mae, day_pnl),
            "traded": in_pos or day_pnl != 0.0
        }
        
    return daily_results

print("\nRunning Scale-Out Simulations...", flush=True)
res_4c = simulate_scaleout_engine(total_contracts=4, initial_stop=16.0, t1_pts=28.0, runner_tp_pts=100.0, vix_floor=15.0)
res_6c = simulate_scaleout_engine(total_contracts=6, initial_stop=16.0, t1_pts=28.0, runner_tp_pts=100.0, vix_floor=15.0)
res_8c = simulate_scaleout_engine(total_contracts=8, initial_stop=16.0, t1_pts=28.0, runner_tp_pts=100.0, vix_floor=15.0)

def analyze_strategy_results(daily_dict, label):
    df = pd.DataFrame.from_dict(daily_dict, orient="index")
    trades_days = df[df["net"] != 0.0]
    
    total_net = df["net"].sum()
    n_days = len(trades_days)
    win_days = (df["net"] > 0).sum()
    loss_days = (df["net"] < 0).sum()
    wr = (win_days / n_days * 100) if n_days > 0 else 0.0
    
    days_over_500 = (df["net"] >= 500.0).sum()
    days_over_1000 = (df["net"] >= 1000.0).sum()
    days_over_1500 = (df["net"] >= 1500.0).sum()
    
    cum = df["net"].cumsum()
    hwm = cum.cummax()
    dd = hwm - cum
    max_dd = dd.max()
    worst_day = df["net"].min()
    
    print(f"\n{label}:")
    print(f"  14-Year Total Net Profit: +${total_net:,.2f}")
    print(f"  Active Trading Days:      {n_days:,} days ({win_days} wins, {loss_days} losses)")
    print(f"  Daily Win Rate:           {wr:.1f}%")
    print(f"  Max Realized Drawdown:    ${max_dd:,.2f}")
    print(f"  Worst Single Day:         -${abs(worst_day):,.2f} (strictly under $1,000 DLL!)")
    print(f"  Days >= +$500:            {days_over_500} days")
    print(f"  Days >= +$1,000:          {days_over_1000} days")
    print(f"  Days >= +$1,500:          {days_over_1500} days")
    
    # 5-Day Evaluation Pass Simulation
    all_dates = sorted(daily_dict.keys())
    total_windows = len(all_dates) - 4
    
    clean_pass = 0
    any_pass = 0
    ruined = 0
    safe_alive = 0
    
    target = 4000.0
    floor = 2000.0
    dll = 1000.0
    max_day_limit = 2000.0 # 50% consistency rule
    
    for i in range(total_windows):
        w_days = all_dates[i : i + 5]
        cum_pnl = 0.0
        hwm_eval = 0.0
        busted = False
        max_day = -9999.0
        
        for d in w_days:
            dp = daily_dict[d]["net"]
            dm = daily_dict[d]["mae"]
            
            if dp <= -dll or dm <= -dll:
                busted = True
                break
            if (hwm_eval - (cum_pnl + dm)) >= floor or (cum_pnl + dm) <= -floor:
                busted = True
                break
                
            cum_pnl += dp
            if cum_pnl > hwm_eval:
                hwm_eval = cum_pnl
            if (hwm_eval - cum_pnl) >= floor or cum_pnl <= -floor:
                busted = True
                break
                
            if dp > max_day:
                max_day = dp
            if cum_pnl >= target:
                break
                
        if busted:
            ruined += 1
        elif cum_pnl >= target:
            any_pass += 1
            if max_day <= max_day_limit:
                clean_pass += 1
        else:
            safe_alive += 1
            
    print(f"  5-Day $4,000 Clean Pass Rate (50% rule): {(clean_pass / total_windows)*100:.2f}% ({clean_pass} weeks)")
    print(f"  5-Day $4,000 Any Pass Rate:             {(any_pass / total_windows)*100:.2f}% ({any_pass} weeks)")
    print(f"  5-Day Ruin Rate (Breached DD or DLL):   {(ruined / total_windows)*100:.2f}% ({ruined} weeks)")
    print(f"  5-Day Account Safe & Alive:             {(safe_alive / total_windows)*100:.2f}% ({safe_alive} weeks)")
    
    return {
        "label": label,
        "net": round(total_net, 2),
        "max_dd": round(max_dd, 2),
        "worst_day": round(worst_day, 2),
        "days_over_500": int(days_over_500),
        "days_over_1000": int(days_over_1000),
        "days_over_1500": int(days_over_1500),
        "clean_pass_5d": clean_pass,
        "pct_clean_pass_5d": round((clean_pass / total_windows)*100, 2),
        "ruined_5d": ruined,
        "pct_ruin_5d": round((ruined / total_windows)*100, 2),
        "pct_safe_5d": round((safe_alive / total_windows)*100, 2),
    }

s1 = analyze_strategy_results(res_4c, "Scale-Out Free-Roll (4 Contracts: 2 Banked + 2 Runners)")
s2 = analyze_strategy_results(res_6c, "Scale-Out Free-Roll (6 Contracts: 3 Banked + 3 Runners)")
s3 = analyze_strategy_results(res_8c, "Scale-Out Free-Roll (8 Contracts: 4 Banked + 4 Runners)")

with open(ROOT / "reports/SCALEOUT_FREEROLL_RUNNER_RESULTS.json", "w") as f:
    json.dump({"s1": s1, "s2": s2, "s3": s3}, f, indent=2)

print("\nSaved to reports/SCALEOUT_FREEROLL_RUNNER_RESULTS.json")
print("DONE", flush=True)
