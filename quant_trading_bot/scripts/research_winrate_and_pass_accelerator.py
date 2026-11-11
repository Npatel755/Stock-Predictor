"""Advanced Alpha Discovery & Pass Accelerator Lab: 14-Year Training Split (2010-2023) ONLY.
METHODOLOGICAL INVARIANT:
- 100% EXCLUSIVELY ON TRAINING DATA (2010-06-01 to 2023-12-31).
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
    open::DOUBLE AS open, high::DOUBLE AS high, low::DOUBLE AS low, close::DOUBLE AS close,
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
gap_series = (daily_sod - daily_eod.shift(1)).dropna()
gap_dict = gap_series.to_dict()

# Compute Daily Trend (e.g. 5-day and 20-day close SMA)
daily_closes = daily_eod.to_frame(name="close")
daily_closes["sma20"] = daily_closes["close"].rolling(20).mean()
daily_closes["sma5"] = daily_closes["close"].rolling(5).mean()
daily_closes["prev_close"] = daily_closes["close"].shift(1)
daily_closes["prev_sma20"] = daily_closes["sma20"].shift(1)
daily_closes["prev_sma5"] = daily_closes["sma5"].shift(1)
trend_dict = daily_closes[["prev_close", "prev_sma20", "prev_sma5"]].to_dict("index")

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

print(f"Loaded {len(dates)} calendar sessions across 14-year Training Split.")

def simulate_strategy_advanced(
    initial_stop=16.0,
    t1_pts=28.0,
    runner_tp=120.0,
    min_or_rng=15.0,
    max_or_rng=120.0,
    min_gap=0.0,
    max_gap=150.0, # filter exhaustion gaps
    trend_filter="none", # "none", "sma20", "sma5", "prev_day_dir"
    breakout_buffer=0.0, # points above OR high required
    vix_floor=15.0
):
    daily_res = {}
    for d in dates:
        vix = get_vix(d)
        gap = gap_dict.get(d, 0.0)
        if vix < vix_floor or d not in grouped:
            daily_res[str(d)] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        # Gap size filter
        if abs(gap) < min_gap or abs(gap) > max_gap:
            daily_res[str(d)] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        # Trend filter
        tr_info = trend_dict.get(d, {})
        p_c = tr_info.get("prev_close", np.nan)
        p_sma20 = tr_info.get("prev_sma20", np.nan)
        p_sma5 = tr_info.get("prev_sma5", np.nan)
        
        bull_trend = True
        bear_trend = True
        if trend_filter == "sma20" and not np.isnan(p_sma20):
            bull_trend = (p_c >= p_sma20)
            bear_trend = (p_c <= p_sma20)
        elif trend_filter == "sma5" and not np.isnan(p_sma5):
            bull_trend = (p_c >= p_sma5)
            bear_trend = (p_c <= p_sma5)
            
        bars = grouped[d]
        sod, high, low, close = bars["sod"], bars["high"], bars["low"], bars["close"]
        mask_15 = sod < 585
        if not mask_15.any():
            daily_res[str(d)] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        hi_15 = high[mask_15].max()
        lo_15 = low[mask_15].min()
        rng_15 = hi_15 - lo_15
        if rng_15 < min_or_rng or rng_15 > max_or_rng:
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
        
        trigger_hi = hi_15 + breakout_buffer
        trigger_lo = lo_15 - breakout_buffer
        
        for idx in idx_trade:
            px_h, px_l = high[idx], low[idx]
            if not in_pos:
                if gap >= 0.0 and bull_trend and px_h > trigger_hi:
                    in_pos = True; pos_dir = 1; entry_px = trigger_hi
                    sl_1 = entry_px - initial_stop
                    sl_2 = sl_1
                    tp_1 = entry_px + t1_pts
                elif gap <= 0.0 and bear_trend and px_l < trigger_lo:
                    in_pos = True; pos_dir = -1; entry_px = trigger_lo
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

def eval_passer(daily_res, label, max_horizon=100):
    date_strs = [str(d) for d in dates]
    active_days = [d for d in date_strs if daily_res.get(d, {}).get("traded", False)]
    
    # Continuous
    pnls = []
    for d in active_days:
        v = get_vix(d)
        sz = 10 if v >= 16.0 else 8
        pnls.append(daily_res[d]["net_1c"] * sz)
        
    net_c = sum(pnls)
    wr = sum(1 for p in pnls if p > 0) / len(pnls) * 100 if pnls else 0.0
    pf = sum(p for p in pnls if p > 0) / abs(sum(p for p in pnls if p < 0)) if sum(1 for p in pnls if p < 0) else 999.0
    
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
            vix = get_vix(d_str)
            is_high_vol = (vix >= 16.0)
            
            if cum <= -200.0: sz = 1
            elif cum >= 2400.0: sz = 14 if is_high_vol else 12
            elif cum >= 1200.0: sz = 12 if is_high_vol else 10
            else: sz = 10 if is_high_vol else 8
            
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
    p10_tr = np.percentile(pass_tr, 10) if passed else 999.0
    min_tr = np.min(pass_tr) if passed else 999
    avg_dd = np.mean(max_dds) if passed else 999.0
    
    print(f"{label:58s} | Pass: {p_pct:5.1f}% | Ruin: {r_pct:4.1f}% | MeanTR: {mean_tr:4.1f}d | MedTR: {med_tr:4.1f}d | P25: {p25_tr:4.1f}d | P10: {p10_tr:4.1f}d | Min: {min_tr:2d}d | WR: {wr:4.1f}% | PF: {pf:4.2f} | Net: ${net_c:7.0f} | DD: ${avg_dd:.0f}")
    return {
        "label": label, "pass_pct": round(p_pct, 1), "ruin_pct": round(r_pct, 1),
        "mean_tr": round(mean_tr, 1), "med_tr": round(med_tr, 1), "p25_tr": round(p25_tr, 1),
        "p10_tr": round(p10_tr, 1), "min_tr": int(min_tr), "wr": round(wr, 1), "pf": round(pf, 2),
        "net": round(net_c, 2), "dd": round(avg_dd, 2)
    }

print("\n" + "="*125)
print("TESTING ADVANCED ALPHA HYPOTHESES ON TRAINING SPLIT ONLY (2010-2023):")
print("="*125)

grid = []

# 1. Baseline Frozen Vol-Adaptive
r_base = simulate_strategy_advanced()
grid.append(eval_passer(r_base, "1. Current Frozen Baseline (Vol-Adaptive)"))

# 2. Exhaustion Gap Filter: Exclude extreme gaps > 100 pts
r_no_exh = simulate_strategy_advanced(max_gap=100.0)
grid.append(eval_passer(r_no_exh, "2. Exclude Exhaustion Gaps (> 100 pts)"))

# 3. Minimum Gap Imbalance: Require Gap >= 5 pts
r_gap5 = simulate_strategy_advanced(min_gap=5.0)
grid.append(eval_passer(r_gap5, "3. Require Directional Gap >= 5 pts"))

# 4. Trend Filter: 20-Day SMA Alignment
r_sma20 = simulate_strategy_advanced(trend_filter="sma20")
grid.append(eval_passer(r_sma20, "4. Multi-Day Trend Filter: 20-SMA Alignment"))

# 5. Trend Filter: 5-Day SMA Momentum
r_sma5 = simulate_strategy_advanced(trend_filter="sma5")
grid.append(eval_passer(r_sma5, "5. Fast Trend Filter: 5-SMA Momentum"))

# 6. Breakout Confirmation Buffer: +1.5 pt buffer
r_buf = simulate_strategy_advanced(breakout_buffer=1.5)
grid.append(eval_passer(r_buf, "6. Breakout Confirmation Buffer (+1.5 pts)"))

# 7. Tighter Initial Stop (14.0 pts vs 16.0 pts)
r_stop14 = simulate_strategy_advanced(initial_stop=14.0)
grid.append(eval_passer(r_stop14, "7. Tighter Initial Stop (14.0 pts vs 16.0 pts)"))

# 8. Adaptive Banker T1: +26 pts
r_bank26 = simulate_strategy_advanced(t1_pts=26.0)
grid.append(eval_passer(r_bank26, "8. Accelerated Banker T1 (+26.0 pts)"))

# 9. Synergistic Combination of Top Improvements
r_synergy = simulate_strategy_advanced(
    t1_pts=26.0,
    min_gap=3.0,
    max_gap=120.0,
    initial_stop=15.0
)
grid.append(eval_passer(r_synergy, "9. Synergistic Multi-Edge Champion"))

out_f = ROOT / "reports/TRAINING_ALPHA_ACCELERATOR_GRID.json"
with open(out_f, "w") as f:
    json.dump(grid, f, indent=2)
print(f"\nAll results saved to {out_f}")
