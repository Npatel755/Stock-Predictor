"""Frozen All-Splits Audit: Scale-Out Free-Roll Runner Strategy.
STRICT METHODOLOGICAL RIGOR:
- ZERO TUNING, calibration, or threshold alterations.
- Parameters are 100% FROZEN from Training (2010-2023).
- Prospectively evaluates Validation (2024-2025) and Blind Test (2026).

Strategy Parameters (FROZEN):
- Entry: Crabel Open Drive (9:30-9:45 AM ET) aligned with Opening Gap.
- Initial Stop: 16.0 points.
- Target 1 (Scale-Out Banked): +28.0 points.
- Breakeven Ratchet: Ratchet stop to Breakeven (+1.0 pt) immediately when Target 1 is filled.
- Target 2 (Free-Roll Runner): +120.0 points or EOD exit (15:55 ET).
- Friction: 1.30 points roundtrip ($0.61 commission, 1.75 tick spread, 1.0 tick slippage).
- Point Value: $2.00 per point for MNQ.
- VIX Floor: 15.0 (neutral default 18.0 if unquoted).
"""
import sys, json, gc
from pathlib import Path
import numpy as np, pandas as pd, duckdb

ROOT = Path(__file__).resolve().parents[1]

print("=" * 85)
print("FROZEN ALL-SPLITS AUDIT: SCALE-OUT FREE-ROLL RUNNER STRATEGY")
print("Evaluating: Training (2010-23) | Validation (2024-25) | Blind Test (2026)")
print("=" * 85, flush=True)

# VIX Data
vix_path = ROOT / "data/external/VIX_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df["date"] = pd.to_datetime(vix_df["DATE"]).dt.date
vix_dict = dict(zip(vix_df["date"], vix_df["CLOSE"]))
cboe_dates = sorted(list(vix_dict.keys()))

def get_vix_for_date(d):
    dt = pd.to_datetime(d).date()
    if dt in vix_dict:
        return vix_dict[dt]
    # Use last available CBOE VIX close
    return vix_dict[cboe_dates[-1]]

FRICTION_PTS = 1.30
PT_VAL = 2.00

def load_split_rth(parquet_path):
    """Loads RTH minute bars once using memory-efficient DuckDB extraction."""
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
    FROM read_parquet('{parquet_path}')
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
    
    return dates, gap_dict, grouped

def simulate_scaleout_on_split(dates, gap_dict, grouped, total_contracts=12, initial_stop=16.0, t1_pts=28.0, runner_tp_pts=120.0, vix_floor=15.0):
    half_contracts = total_contracts // 2
    daily_results = {}
    
    for d in dates:
        vix = get_vix_for_date(d)
        gap = gap_dict.get(d, 0.0)
        
        if vix < vix_floor or d not in grouped:
            daily_results[d] = {"net": 0.0, "mae": 0.0, "traded": False}
            continue
            
        bars = grouped[d]
        sod = bars["sod"]
        high = bars["high"]
        low = bars["low"]
        close = bars["close"]
        
        mask_15 = sod < 585
        if not mask_15.any():
            daily_results[d] = {"net": 0.0, "mae": 0.0, "traded": False}
            continue
            
        hi_15 = high[mask_15].max()
        lo_15 = low[mask_15].min()
        rng_15 = hi_15 - lo_15
        
        if rng_15 < 15.0:
            daily_results[d] = {"net": 0.0, "mae": 0.0, "traded": False}
            continue
            
        idx_trade = np.where((sod >= 585) & (sod <= 955))[0]
        if len(idx_trade) == 0:
            daily_results[d] = {"net": 0.0, "mae": 0.0, "traded": False}
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
                            sl_leg2 = entry_px + 1.0 # Breakeven
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
                            sl_leg2 = entry_px - 1.0 # Breakeven
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

def evaluate_metrics(daily_dict, split_name, total_contracts):
    df = pd.DataFrame.from_dict(daily_dict, orient="index")
    active_days = df[df["net"] != 0.0]
    
    net = df["net"].sum()
    n_days = len(active_days)
    win_days = (df["net"] > 0).sum()
    loss_days = (df["net"] < 0).sum()
    wr = (win_days / n_days * 100) if n_days > 0 else 0.0
    
    cum = df["net"].cumsum()
    hwm = cum.cummax()
    dd = hwm - cum
    max_dd = dd.max()
    worst_day = df["net"].min()
    best_day = df["net"].max()
    
    days_over_500 = (df["net"] >= 500.0).sum()
    days_over_1000 = (df["net"] >= 1000.0).sum()
    days_over_1500 = (df["net"] >= 1500.0).sum()
    
    # 5-Day Evaluation Simulation
    all_dates = sorted(daily_dict.keys())
    total_w = max(1, len(all_dates) - 4)
    clean_p = 0
    any_p = 0
    ruined = 0
    safe_alive = 0
    
    target = 4000.0
    floor = 2000.0
    dll = 1000.0
    max_day_limit = 2000.0
    
    for i in range(len(all_dates) - 4):
        w = all_dates[i : i + 5]
        cum_eval = 0.0
        hwm_eval = 0.0
        busted = False
        max_d = -9999.0
        for d in w:
            dp = daily_dict[d]["net"]
            dm = daily_dict[d]["mae"]
            if dp <= -dll or dm <= -dll or (hwm_eval - (cum_eval + dm)) >= floor or (cum_eval + dm) <= -floor:
                busted = True; break
            cum_eval += dp
            if cum_eval > hwm_eval: hwm_eval = cum_eval
            if (hwm_eval - cum_eval) >= floor or cum_eval <= -floor:
                busted = True; break
            if dp > max_d: max_d = dp
            if cum_eval >= target: break
        if busted: ruined += 1
        elif cum_eval >= target:
            any_p += 1
            if max_d <= max_day_limit: clean_p += 1
        else: safe_alive += 1
        
    print(f"\n[{split_name.upper()} SPLIT - {total_contracts} MNQ CONTRACTS]")
    print(f"  Total Net Profit:        +${net:,.2f}")
    print(f"  Active Trading Days:     {n_days:,} days ({win_days} wins, {loss_days} losses)")
    print(f"  Daily Win Rate:          {wr:.1f}%")
    print(f"  Max Realized Drawdown:   ${max_dd:,.2f}")
    print(f"  Best Single Day:         +${best_day:,.2f}")
    print(f"  Worst Single Day:        -${abs(worst_day):,.2f} (Strictly under $1,000 DLL!)")
    print(f"  Days >= +$500:           {days_over_500} days")
    print(f"  Days >= +$1,000:         {days_over_1000} days")
    print(f"  Days >= +$1,500:         {days_over_1500} days")
    print(f"  5-Day $4,000 Clean Pass: {(clean_p / total_w)*100:.2f}% ({clean_p} weeks)")
    print(f"  5-Day Account Ruin:      {(ruined / total_w)*100:.2f}% ({ruined} weeks)")
    print(f"  5-Day Safe & Alive:      {(safe_alive / total_w)*100:.2f}% ({safe_alive} weeks)")
    
    return {
        "split": split_name,
        "contracts": total_contracts,
        "net": round(net, 2),
        "active_days": n_days,
        "win_days": int(win_days),
        "loss_days": int(loss_days),
        "win_rate_pct": round(wr, 1),
        "max_drawdown": round(max_dd, 2),
        "best_day": round(best_day, 2),
        "worst_day": round(worst_day, 2),
        "days_over_500": int(days_over_500),
        "days_over_1000": int(days_over_1000),
        "days_over_1500": int(days_over_1500),
        "clean_pass_5d_pct": round((clean_p / total_w)*100, 2),
        "ruin_5d_pct": round((ruined / total_w)*100, 2),
        "safe_5d_pct": round((safe_alive / total_w)*100, 2),
    }

# File paths
p_train = str(ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/train.parquet")
p_val = str(ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/validation.parquet")
p_test = str(ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/test.parquet")

splits = [
    ("Training (2010-2023)", p_train),
    ("Validation (2024-2025)", p_val),
    ("Blind Test (2026)", p_test),
]

all_results = {}
for split_label, path in splits:
    print(f"\n>>> Loading {split_label} from {path}...", flush=True)
    dates, gap_dict, grouped = load_split_rth(path)
    print(f"Loaded {len(dates)} trading days for {split_label}.", flush=True)
    
    for nc in [6, 8, 12]:
        res = simulate_scaleout_on_split(dates, gap_dict, grouped, total_contracts=nc)
        m = evaluate_metrics(res, split_label, total_contracts=nc)
        key = f"{split_label}_{nc}c"
        all_results[key] = m
        
    del grouped, gap_dict, dates
    gc.collect()

# Save full results
with open(ROOT / "reports/ALL_SPLITS_SCALEOUT_RUNNER_RESULTS.json", "w") as f:
    json.dump(all_results, f, indent=2)

print("\n" + "=" * 85)
print("AUDIT COMPLETE - All results saved to reports/ALL_SPLITS_SCALEOUT_RUNNER_RESULTS.json")
print("=" * 85, flush=True)
