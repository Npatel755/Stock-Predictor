"""Deep Research & Optimization Lab on the 14-Year Training Split (2010-2023) ONLY.
Objective:
- Compress average pass time to ~10-14 trade days (~2 weeks).
- Maintain 0.0% or near-0% ruin rate on Topstep $50,000 prop rules ($4k target, -$2k static floor, -$1k DLL).
- Strict Methodological Discipline: 100% Training split (train.parquet) ONLY. Zero touch of validation or test data.
- Strict Look-Ahead Free: Prior-session VIX close only.
- Defensive floor recovery: investigate recovery sizing (1, 2, 3, 4, 5 MNQ) so accounts don't get stuck in 1-micro penalty box.
- Scale-invariant filters that adapt to price levels across all eras.
"""
import sys, json, gc, bisect
from pathlib import Path
import numpy as np, pandas as pd, duckdb

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
p_train = ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/train.parquet"

# Load VIX History
vix_path = ROOT / "data/external/VIX_History.csv"
vix_df = pd.read_csv(vix_path)
vix_df["date"] = pd.to_datetime(vix_df["DATE"]).dt.date
vix_dict = dict(zip(vix_df["date"], vix_df["CLOSE"]))
cboe_dates = sorted(list(vix_dict.keys()))

def get_prior_vix(d):
    dt = pd.to_datetime(d).date()
    i = bisect.bisect_left(cboe_dates, dt) - 1
    return vix_dict[cboe_dates[max(i, 0)]]

FRICTION_PTS = 1.30
PT_VAL = 2.00
STATIC_FLOOR = -2000.0
DLL_LIMIT = -1000.0
DAILY_LOCK = 1500.0

def load_training_data():
    con = duckdb.connect()
    con.execute("PRAGMA memory_limit='4GB'")
    q = f"""
    SELECT 
        (timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))::DATE AS date,
        (date_part('hour', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))*60 + 
         date_part('minute', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ)))::INT AS sod,
        open::DOUBLE AS open, high::DOUBLE AS high, low::DOUBLE AS low, close::DOUBLE AS close
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
    
    # Trend signals on prior closes
    daily_closes = daily_eod.to_frame(name="close")
    daily_closes["sma3"] = daily_closes["close"].rolling(3).mean()
    daily_closes["sma5"] = daily_closes["close"].rolling(5).mean()
    daily_closes["sma10"] = daily_closes["close"].rolling(10).mean()
    daily_closes["prev_close"] = daily_closes["close"].shift(1)
    daily_closes["prev_sma3"] = daily_closes["sma3"].shift(1)
    daily_closes["prev_sma5"] = daily_closes["sma5"].shift(1)
    daily_closes["prev_sma10"] = daily_closes["sma10"].shift(1)
    trend_dict = daily_closes.to_dict("index")
    
    grouped = {}
    for d, g in rth.groupby("date"):
        grouped[d] = {
            "sod": g["sod"].to_numpy(),
            "open": g["open"].to_numpy(),
            "high": g["high"].to_numpy(),
            "low": g["low"].to_numpy(),
            "close": g["close"].to_numpy(),
        }
    del rth
    gc.collect()
    return dates, gap_dict, trend_dict, grouped

dates, gap_dict, trend_dict, grouped = load_training_data()
print(f"Loaded {len(dates)} training dates (2010-2023).")

def simulate_trades(
    dates, gap_dict, trend_dict, grouped,
    initial_stop=16.0, t1_pts=28.0, runner_tp=120.0,
    use_trend_filter="sma5", # "none", "sma3", "sma5", "sma10"
    max_gap_pct=0.020, # 2.0% gap filter
    pessimistic_fills=True
):
    daily_res = {}
    for d in dates:
        vix = get_prior_vix(d) # 100% causal prior-session VIX
        gap = gap_dict.get(d, 0.0)
        if vix < 15.0 or d not in grouped:
            daily_res[str(d)] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        tr_info = trend_dict.get(d, {})
        p_c = tr_info.get("prev_close", np.nan)
        if np.isnan(p_c) or p_c <= 0:
            daily_res[str(d)] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        gap_pct = abs(gap) / p_c
        if max_gap_pct is not None and gap_pct > max_gap_pct:
            daily_res[str(d)] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        bull_trend = True
        bear_trend = True
        if use_trend_filter == "sma3":
            p_sma = tr_info.get("prev_sma3", np.nan)
            if not np.isnan(p_sma): bull_trend = (p_c >= p_sma); bear_trend = (p_c <= p_sma)
        elif use_trend_filter == "sma5":
            p_sma = tr_info.get("prev_sma5", np.nan)
            if not np.isnan(p_sma): bull_trend = (p_c >= p_sma); bear_trend = (p_c <= p_sma)
        elif use_trend_filter == "sma10":
            p_sma = tr_info.get("prev_sma10", np.nan)
            if not np.isnan(p_sma): bull_trend = (p_c >= p_sma); bear_trend = (p_c <= p_sma)
            
        bars = grouped[d]
        sod, O, high, low, close = bars["sod"], bars["open"], bars["high"], bars["low"], bars["close"]
        mask_15 = sod < 585
        if not mask_15.any():
            daily_res[str(d)] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        hi_15 = high[mask_15].max()
        lo_15 = low[mask_15].min()
        rng_15 = hi_15 - lo_15
        
        # Scale-invariant minimum range: at least 0.10% of price (replaces fixed 15 pts on 20k NQ)
        min_rng = max(15.0, p_c * 0.0010)
        if rng_15 < min_rng:
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
        done = False
        
        for idx in idx_trade:
            px_h, px_l, px_o = high[idx], low[idx], O[idx]
            if not in_pos:
                if gap >= 0.0 and bull_trend and px_h > hi_15:
                    in_pos = True; pos_dir = 1
                    entry_px = max(px_o, hi_15) if pessimistic_fills else hi_15
                    sl_1 = entry_px - initial_stop
                    sl_2 = sl_1
                    tp_1 = entry_px + t1_pts
                    if pessimistic_fills and px_l <= sl_1:
                        trade_net_pts += (-initial_stop - FRICTION_PTS)
                        trade_mae_pts = -initial_stop
                        in_pos = False; done = True; break
                elif gap <= 0.0 and bear_trend and px_l < lo_15:
                    in_pos = True; pos_dir = -1
                    entry_px = min(px_o, lo_15) if pessimistic_fills else lo_15
                    sl_1 = entry_px + initial_stop
                    sl_2 = sl_1
                    tp_1 = entry_px - t1_pts
                    if pessimistic_fills and px_h >= sl_1:
                        trade_net_pts += (-initial_stop - FRICTION_PTS)
                        trade_mae_pts = -initial_stop
                        in_pos = False; done = True; break
            else:
                if pos_dir == 1:
                    adv = max(px_l - entry_px, -initial_stop)
                    fav = px_h - entry_px
                    if not leg1_closed and adv < trade_mae_pts: trade_mae_pts = adv
                    if fav > max_fav: max_fav = fav
                    
                    hit_sl1 = (px_l <= sl_1)
                    hit_tp1 = (px_h >= tp_1)
                    hit_sl2 = (px_l <= sl_2)
                    
                    if not leg1_closed:
                        # If pessimistic and both hit in same bar, stop hits first
                        if pessimistic_fills and hit_sl1:
                            trade_net_pts += (-initial_stop - FRICTION_PTS)
                            in_pos = False; break
                        elif hit_tp1:
                            trade_net_pts += (t1_pts - FRICTION_PTS) * 0.5
                            leg1_closed = True
                            sl_2 = entry_px + 1.0 # Breakeven ratchet
                            if pessimistic_fills and hit_sl2:
                                trade_net_pts += (1.0 - FRICTION_PTS) * 0.5
                                in_pos = False; break
                        elif hit_sl1:
                            trade_net_pts += (-initial_stop - FRICTION_PTS)
                            in_pos = False; break
                    else:
                        hit_rtp = (fav >= runner_tp) if pessimistic_fills else (max_fav >= runner_tp)
                        if pessimistic_fills and hit_sl2:
                            pts_exit = sl_2 - entry_px
                            trade_net_pts += (pts_exit - FRICTION_PTS) * 0.5
                            in_pos = False; break
                        elif hit_rtp:
                            trade_net_pts += (runner_tp - FRICTION_PTS) * 0.5
                            in_pos = False; break
                        elif hit_sl2:
                            pts_exit = sl_2 - entry_px
                            trade_net_pts += (pts_exit - FRICTION_PTS) * 0.5
                            in_pos = False; break
                else: # Short
                    adv = max(entry_px - px_h, -initial_stop)
                    fav = entry_px - px_l
                    if not leg1_closed and adv < trade_mae_pts: trade_mae_pts = adv
                    if fav > max_fav: max_fav = fav
                    
                    hit_sl1 = (px_h >= sl_1)
                    hit_tp1 = (px_l <= tp_1)
                    hit_sl2 = (px_h >= sl_2)
                    
                    if not leg1_closed:
                        if pessimistic_fills and hit_sl1:
                            trade_net_pts += (-initial_stop - FRICTION_PTS)
                            in_pos = False; break
                        elif hit_tp1:
                            trade_net_pts += (t1_pts - FRICTION_PTS) * 0.5
                            leg1_closed = True
                            sl_2 = entry_px - 1.0
                            if pessimistic_fills and hit_sl2:
                                trade_net_pts += (1.0 - FRICTION_PTS) * 0.5
                                in_pos = False; break
                        elif hit_sl1:
                            trade_net_pts += (-initial_stop - FRICTION_PTS)
                            in_pos = False; break
                    else:
                        hit_rtp = (fav >= runner_tp) if pessimistic_fills else (max_fav >= runner_tp)
                        if pessimistic_fills and hit_sl2:
                            pts_exit = entry_px - sl_2
                            trade_net_pts += (pts_exit - FRICTION_PTS) * 0.5
                            in_pos = False; break
                        elif hit_rtp:
                            trade_net_pts += (runner_tp - FRICTION_PTS) * 0.5
                            in_pos = False; break
                        elif hit_sl2:
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
            "traded": bool(in_pos or trade_net_pts != 0.0 or done)
        }
    return daily_res

def eval_ladder(
    dates, daily_res,
    floor_trigger=-300.0,
    floor_size=3, # MNQ size when below floor_trigger
    base_size=8,
    accel_size=10,
    sprint_size=12,
    vol_bonus=2, # +2 MNQ if prior VIX >= 16
    vix_split=16.0,
    horizon=100
):
    ds = [str(d) for d in dates]
    passed = 0
    ruined = 0
    timeouts = 0
    dll_breaches = 0
    pass_tr_days = []
    max_dds = []
    
    for i in range(len(ds) - horizon):
        cum = 0.0
        hwm = 0.0
        busted = False
        pass_run = False
        peak_dd = 0.0
        tr_days = 0
        
        for step in range(horizon):
            d_str = ds[i + step]
            tr = daily_res.get(d_str, None)
            if not tr or not tr["traded"]:
                continue
                
            tr_days += 1
            vix = get_prior_vix(d_str)
            bonus = vol_bonus if vix >= vix_split else 0
            
            # Sizing logic
            if cum <= floor_trigger:
                sz = floor_size
            elif cum >= 2400.0:
                sz = sprint_size + bonus
            elif cum >= 1200.0:
                sz = accel_size + bonus
            else:
                sz = base_size + bonus
                
            pnl = tr["net_1c"] * sz
            mae = tr["mae_1c"] * sz
            
            # Risk checks
            if pnl <= DLL_LIMIT or mae <= DLL_LIMIT:
                busted = True; dll_breaches += 1; break
            if (cum + mae) <= STATIC_FLOOR:
                busted = True; break
            if pnl > DAILY_LOCK: pnl = DAILY_LOCK
            
            cum += pnl
            c_dd = hwm - cum
            if c_dd > peak_dd: peak_dd = c_dd
            if cum > hwm: hwm = cum
            if cum <= STATIC_FLOOR: busted = True; break
            if cum >= 4000.0:
                passed += 1; pass_run = True; pass_tr_days.append(tr_days); max_dds.append(peak_dd); break
                
        if busted and not pass_run: ruined += 1
        elif not pass_run and not busted: timeouts += 1
        
    tot = passed + ruined
    p_pct = (passed / max(1, tot)) * 100
    r_pct = (ruined / max(1, tot)) * 100
    mean_tr = np.mean(pass_tr_days) if passed else 999.0
    med_tr = np.median(pass_tr_days) if passed else 999.0
    p10_tr = np.percentile(pass_tr_days, 10) if passed else 999.0
    avg_dd = np.mean(max_dds) if passed else 999.0
    
    return {
        "passed": passed, "ruined": ruined, "timeouts": timeouts,
        "pass_pct": round(p_pct, 1), "ruin_pct": round(r_pct, 1),
        "dll_breaches": dll_breaches,
        "mean_trade_days": round(mean_tr, 1), "med_trade_days": round(med_tr, 1),
        "p10_trade_days": round(p10_tr, 1), "avg_dd": round(avg_dd, 1)
    }

print("Running baseline simulation with pessimistic fills...")
daily_base = simulate_trades(dates, gap_dict, trend_dict, grouped, pessimistic_fills=True, use_trend_filter="none")
print(f"Total active trade days in base: {sum(1 for v in daily_base.values() if v['traded'])}")

print("\n--- GRID 1: Trend Filter vs Pessimistic Fills on Training (2010-2023) ---")
for tf in ["none", "sma3", "sma5", "sma10"]:
    daily_tf = simulate_trades(dates, gap_dict, trend_dict, grouped, pessimistic_fills=True, use_trend_filter=tf)
    act = sum(1 for v in daily_tf.values() if v['traded'])
    wins = sum(1 for v in daily_tf.values() if v['traded'] and v['net_1c'] > 0)
    net_1c = sum(v['net_1c'] for v in daily_tf.values())
    wr = wins / max(1, act) * 100
    res = eval_ladder(dates, daily_tf, floor_trigger=-200.0, floor_size=1)
    print(f"Filter: {tf:6s} | Trades: {act:4d} | WinRate: {wr:4.1f}% | Net 1c: ${net_1c:7.1f} | Pass%: {res['pass_pct']:5.1f}% | Ruin%: {res['ruin_pct']:4.1f}% | MeanDays: {res['mean_trade_days']:4.1f} | MedDays: {res['med_trade_days']:4.1f} | DD: ${res['avg_dd']:6.1f}")

print("\n--- GRID 2: Defensive Floor Sizing (1 vs 2 vs 3 vs 4 vs 5 MNQ) & Trigger (-$200 vs -$350 vs -$500) ---")
# Using SMA5 filter
daily_sma5 = simulate_trades(dates, gap_dict, trend_dict, grouped, pessimistic_fills=True, use_trend_filter="sma5")
for trig in [-200.0, -350.0, -500.0]:
    for fsz in [1, 2, 3, 4, 5]:
        res = eval_ladder(dates, daily_sma5, floor_trigger=trig, floor_size=fsz)
        print(f"Trigger: ${trig:5.0f} | FloorSz: {fsz}c | Pass%: {res['pass_pct']:5.1f}% | Ruin%: {res['ruin_pct']:4.1f}% | Timeouts: {res['timeouts']:4d} | MeanDays: {res['mean_trade_days']:4.1f} | MedDays: {res['med_trade_days']:4.1f} | DLL: {res['dll_breaches']} | DD: ${res['avg_dd']:6.1f}")

print("\n--- GRID 3: Acceleration Sizing Ladder on Training ---")
for base, acc, spr in [(8, 10, 12), (10, 12, 14), (6, 8, 10)]:
    for trig in [-350.0]:
        for fsz in [2, 3, 4]:
            res = eval_ladder(dates, daily_sma5, floor_trigger=trig, floor_size=fsz, base_size=base, accel_size=acc, sprint_size=spr)
            print(f"Ladder: {base}/{acc}/{spr}c | Floor: {fsz}c @ ${trig:.0f} | Pass%: {res['pass_pct']:5.1f}% | Ruin%: {res['ruin_pct']:4.1f}% | Timeouts: {res['timeouts']:4d} | MeanDays: {res['mean_trade_days']:4.1f} | MedDays: {res['med_trade_days']:4.1f} | DLL: {res['dll_breaches']} | DD: ${res['avg_dd']:6.1f}")
