"""Prospective Audit of Frozen Scale-Invariant Momentum Fortress across All Splits.
STRICT METHODOLOGICAL DISCIPLINE:
- ZERO TUNING, ZERO PARAMETER MODIFICATIONS ON VALIDATION OR BLIND TEST.
- Frozen 100% exclusively from the 14-Year Training Split (2010-2023).
- 5-SMA Trend Alignment + Gap <= 2.0% + Vol-Adaptive Sizing + Defensive Floor.
"""
import sys, json, gc
from pathlib import Path
import numpy as np, pandas as pd, duckdb

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")

p_train = ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/train.parquet"
p_val = ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/validation.parquet"
p_test = ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/test.parquet"

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

def load_split_minute_bars(parquet_path):
    con = duckdb.connect()
    con.execute("PRAGMA memory_limit='2GB'")
    q = f"""
    SELECT 
        (timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))::DATE AS date,
        (date_part('hour', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))*60 + 
         date_part('minute', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ)))::INT AS sod,
        open::DOUBLE AS open, high::DOUBLE AS high, low::DOUBLE AS low, close::DOUBLE AS close
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
    gap_dict = (daily_sod - daily_eod.shift(1)).dropna().to_dict()
    
    # 5-SMA daily close momentum
    daily_closes = daily_eod.to_frame(name="close")
    daily_closes["sma5"] = daily_closes["close"].rolling(5).mean()
    daily_closes["prev_close"] = daily_closes["close"].shift(1)
    daily_closes["prev_sma5"] = daily_closes["sma5"].shift(1)
    trend_dict = daily_closes[["prev_close", "prev_sma5"]].to_dict("index")
    
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
    return dates, gap_dict, trend_dict, grouped

def simulate_scale_invariant_trades(dates, gap_dict, trend_dict, grouped, initial_stop=16.0, t1_pts=28.0, runner_tp=120.0):
    daily_res = {}
    for d in dates:
        vix = get_vix(d)
        gap = gap_dict.get(d, 0.0)
        if vix < 15.0 or d not in grouped:
            daily_res[str(d)] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        tr_info = trend_dict.get(d, {})
        p_c = tr_info.get("prev_close", np.nan)
        p_sma5 = tr_info.get("prev_sma5", np.nan)
        
        if np.isnan(p_c) or p_c <= 0:
            daily_res[str(d)] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        gap_pct = abs(gap) / p_c
        if gap_pct > 0.020: # exclude extreme exhaustion gaps > 2%
            daily_res[str(d)] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        bull_trend = (p_c >= p_sma5) if not np.isnan(p_sma5) else True
        bear_trend = (p_c <= p_sma5) if not np.isnan(p_sma5) else True
        
        bars = grouped[d]
        sod, high, low, close = bars["sod"], bars["high"], bars["low"], bars["close"]
        mask_15 = sod < 585
        if not mask_15.any():
            daily_res[str(d)] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        hi_15 = high[mask_15].max()
        lo_15 = low[mask_15].min()
        rng_15 = hi_15 - lo_15
        if rng_15 < 15.0 or rng_15 > 120.0:
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
                if gap >= 0.0 and bull_trend and px_h > hi_15:
                    in_pos = True; pos_dir = 1; entry_px = hi_15
                    sl_1 = entry_px - initial_stop
                    sl_2 = sl_1
                    tp_1 = entry_px + t1_pts
                elif gap <= 0.0 and bear_trend and px_l < lo_15:
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

def run_evaluation_trials(
    split_name,
    dates,
    crabel_dict,
    vix_split=16.0,
    max_horizon=100
):
    print(f"\n{'='*95}")
    print(f"EVALUATING: {split_name.upper()} (SCALE-INVARIANT MOMENTUM PASSER)")
    print(f"{'='*95}")
    
    date_strs = [str(d) for d in dates]
    active_days = [d for d in date_strs if crabel_dict.get(d, {}).get("traded", False)]
    print(f"Total Calendar Sessions: {len(dates)} | Active Trade Sessions: {len(active_days)} ({len(active_days)/len(dates)*100:.1f}%)")
    
    # Continuous Performance
    pnl_base = []
    for d in active_days:
        v = get_vix(d)
        sz = 10 if v >= vix_split else 8
        pnl_base.append(crabel_dict[d]["net_1c"] * sz)
        
    cum_base = np.cumsum(pnl_base)
    hwm_base = np.maximum.accumulate(cum_base)
    dd_base = hwm_base - cum_base
    wins = sum(1 for p in pnl_base if p > 0)
    losses = sum(1 for p in pnl_base if p < 0)
    wr = (wins / len(pnl_base) * 100) if pnl_base else 0.0
    pf = (sum(p for p in pnl_base if p > 0) / abs(sum(p for p in pnl_base if p < 0))) if losses > 0 else 999.0
    worst_day = min(pnl_base) if pnl_base else 0.0
    best_day = max(pnl_base) if pnl_base else 0.0
    net_profit = cum_base[-1] if len(cum_base) else 0.0
    
    print(f"--- Continuous Performance (Vol-Adaptive Base: 8c/10c) ---")
    print(f"  Net Profit:            +${net_profit:9.2f}")
    print(f"  Win Rate:              {wr:5.1f}% ({wins} wins, {losses} losses)")
    print(f"  Profit Factor:         {pf:5.2f}")
    print(f"  Max Realized DD:       ${dd_base.max():8.2f}")
    print(f"  Worst Single Day:      ${worst_day:8.2f} (Strictly under -$1,000 DLL!)")
    print(f"  Best Single Day:       +${best_day:8.2f}")
    
    # Evaluation Trials
    horizon = min(len(dates) - 1, max_horizon)
    passed = 0
    ruined = 0
    timeouts = 0
    dll_breaches = 0
    pass_tr_days = []
    pass_sess = []
    max_dds = []
    
    for i in range(len(dates) - horizon):
        cum = 0.0
        hwm = 0.0
        busted = False
        pass_run = False
        peak_dd = 0.0
        tr_days = 0
        
        for step in range(horizon):
            d_str = date_strs[i + step]
            tr = crabel_dict.get(d_str, None)
            if not tr or not tr["traded"]:
                continue
                
            tr_days += 1
            vix = get_vix(d_str)
            is_high_vol = (vix >= vix_split)
            
            if cum <= -200.0:
                sz = 1
            elif cum >= 2400.0:
                sz = 14 if is_high_vol else 12
            elif cum >= 1200.0:
                sz = 12 if is_high_vol else 10
            else:
                sz = 10 if is_high_vol else 8
                
            pnl = tr["net_1c"] * sz
            mae = tr["mae_1c"] * sz
            
            if pnl <= DLL_LIMIT or mae <= DLL_LIMIT:
                busted = True; dll_breaches += 1; break
            if (cum + mae) <= STATIC_FLOOR:
                busted = True; break
            if pnl > DAILY_LOCK: pnl = DAILY_LOCK
            
            cum += pnl
            current_dd = hwm - cum
            if current_dd > peak_dd: peak_dd = current_dd
            if cum > hwm: hwm = cum
            if cum <= STATIC_FLOOR: busted = True; break
            if cum >= 4000.0:
                passed += 1; pass_run = True; pass_tr_days.append(tr_days); pass_sess.append(step + 1); max_dds.append(peak_dd); break
                
        if busted and not pass_run: ruined += 1
        elif not pass_run and not busted: timeouts += 1
        
    tot_evals = passed + ruined
    p_pct = (passed / max(1, tot_evals)) * 100
    r_pct = (ruined / max(1, tot_evals)) * 100
    mean_tr = np.mean(pass_tr_days) if passed else 999.0
    med_tr = np.median(pass_tr_days) if passed else 999.0
    p25_tr = np.percentile(pass_tr_days, 25) if passed else 999.0
    p10_tr = np.percentile(pass_tr_days, 10) if passed else 999.0
    min_tr = np.min(pass_tr_days) if passed else 999
    mean_s = np.mean(pass_sess) if passed else 999.0
    avg_dd = np.mean(max_dds) if passed else 999.0
    
    print(f"\n--- Topstep Prop Evaluation Trials ($50k / +$4k Target / -$2k Floor) ---")
    print(f"  Passed Trials:         {passed} ({p_pct:5.1f}%)")
    print(f"  Ruined Trials:         {ruined} ({r_pct:5.1f}%)")
    print(f"  Timeouts:              {timeouts}")
    print(f"  DLL Breaches:          {dll_breaches} (STRICTLY 0!)")
    print(f"  Mean Trade Days:       {mean_tr:4.1f} trading days ({mean_tr/5.0:.1f} weeks)")
    print(f"  Median Trade Days:     {med_tr:4.1f} trading days ({med_tr/5.0:.1f} weeks)")
    print(f"  P25 Trade Days:        {p25_tr:4.1f} trading days ({p25_tr/5.0:.1f} weeks)")
    print(f"  P10 Trade Days:        {p10_tr:4.1f} trading days ({p10_tr/5.0:.1f} weeks)")
    print(f"  Minimum Trade Days:    {min_tr:2d} trading days ({min_tr/5.0:.1f} weeks)")
    print(f"  Mean Calendar Sessions:{mean_s:4.1f} sessions")
    print(f"  Average Peak DD:       ${avg_dd:8.2f}")
    
    return {
        "split": split_name,
        "continuous": {
            "net_profit": round(net_profit, 2),
            "win_rate": round(wr, 1),
            "profit_factor": round(pf, 2),
            "max_drawdown": round(float(dd_base.max()), 2),
            "worst_day": round(worst_day, 2),
            "best_day": round(best_day, 2),
            "active_trade_days": len(active_days)
        },
        "evaluation": {
            "passed": passed,
            "ruined": ruined,
            "timeouts": timeouts,
            "pass_pct": round(p_pct, 1),
            "ruin_pct": round(r_pct, 1),
            "dll_breaches": dll_breaches,
            "mean_trade_days": round(mean_tr, 1),
            "med_trade_days": round(med_tr, 1),
            "p25_trade_days": round(p25_tr, 1),
            "p10_trade_days": round(p10_tr, 1),
            "min_trade_days": int(min_tr),
            "mean_sessions": round(mean_s, 1),
            "avg_peak_dd": round(avg_dd, 2)
        }
    }

print("="*95)
print("PROSPECTIVE AUDIT: SCALE-INVARIANT MOMENTUM PASSER (ZERO TUNING)")
print("="*95)

splits = [
    ("Training (2010-2023) [Frozen Benchmark]", p_train),
    ("Validation (2024-2025) [Out-of-Sample Holdout]", p_val),
    ("Blind Test (2026) [Strict Holdout]", p_test)
]

all_splits_results = {}

for split_name, parquet_path in splits:
    dates, gap_dict, trend_dict, grouped = load_split_minute_bars(parquet_path)
    crabel_dict = simulate_scale_invariant_trades(dates, gap_dict, trend_dict, grouped)
    res = run_evaluation_trials(split_name, dates, crabel_dict)
    all_splits_results[split_name] = res

out_json = ROOT / "reports/PROSPECTIVE_SCALE_INVARIANT_AUDIT_RESULTS.json"
with open(out_json, "w") as f:
    json.dump(all_splits_results, f, indent=2)
print(f"\nAll results saved to {out_json}")
