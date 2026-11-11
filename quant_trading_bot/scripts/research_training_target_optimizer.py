"""Training-Only Parameter & Mechanism Optimization Lab.
Exclusively on 14-Year Training Split (2010-2023).
Testing:
1. Stop loss: 14, 16, 18, 20 pts
2. Target 1 (Banker leg): 20, 24, 28, 32 pts
3. Target 2 (Runner leg): 80, 100, 120, 150 pts
4. Breakeven offset: +1.0 pt vs +2.0 pts
5. Floor trigger: -$300 vs -$350 vs -$400
All with 100% causal prior-session VIX, pessimistic fills (checking entry bar, stop-first ordering).
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

# 5-SMA daily close momentum
daily_closes = daily_eod.to_frame(name="close")
daily_closes["sma5"] = daily_closes["close"].rolling(5).mean()
daily_closes["prev_close"] = daily_closes["close"].shift(1)
daily_closes["prev_sma5"] = daily_closes["sma5"].shift(1)
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

def run_sim(initial_stop, t1_pts, runner_tp, be_offset=1.0):
    daily_res = {}
    for d in dates:
        vix = get_prior_vix(d)
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
            
        if abs(gap) / p_c > 0.020:
            daily_res[str(d)] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        bull_trend = (p_c >= p_sma5) if not np.isnan(p_sma5) else True
        bear_trend = (p_c <= p_sma5) if not np.isnan(p_sma5) else True
            
        bars = grouped[d]
        sod, O, high, low, close = bars["sod"], bars["open"], bars["high"], bars["low"], bars["close"]
        mask_15 = sod < 585
        if not mask_15.any():
            daily_res[str(d)] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        hi_15 = high[mask_15].max()
        lo_15 = low[mask_15].min()
        rng_15 = hi_15 - lo_15
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
        done = False
        
        for idx in idx_trade:
            px_h, px_l, px_o = high[idx], low[idx], O[idx]
            if not in_pos:
                if gap >= 0.0 and bull_trend and px_h > hi_15:
                    in_pos = True; pos_dir = 1
                    entry_px = max(px_o, hi_15)
                    sl_1 = entry_px - initial_stop
                    sl_2 = sl_1
                    tp_1 = entry_px + t1_pts
                    if px_l <= sl_1:
                        trade_net_pts += (-initial_stop - FRICTION_PTS)
                        trade_mae_pts = -initial_stop
                        in_pos = False; done = True; break
                elif gap <= 0.0 and bear_trend and px_l < lo_15:
                    in_pos = True; pos_dir = -1
                    entry_px = min(px_o, lo_15)
                    sl_1 = entry_px + initial_stop
                    sl_2 = sl_1
                    tp_1 = entry_px - t1_pts
                    if px_h >= sl_1:
                        trade_net_pts += (-initial_stop - FRICTION_PTS)
                        trade_mae_pts = -initial_stop
                        in_pos = False; done = True; break
            else:
                if pos_dir == 1:
                    adv = max(px_l - entry_px, -initial_stop)
                    fav = px_h - entry_px
                    if not leg1_closed and adv < trade_mae_pts: trade_mae_pts = adv
                    
                    hit_sl1 = (px_l <= sl_1)
                    hit_tp1 = (px_h >= tp_1)
                    hit_sl2 = (px_l <= sl_2)
                    
                    if not leg1_closed:
                        if hit_sl1:
                            trade_net_pts += (-initial_stop - FRICTION_PTS)
                            in_pos = False; break
                        elif hit_tp1:
                            trade_net_pts += (t1_pts - FRICTION_PTS) * 0.5
                            leg1_closed = True
                            sl_2 = entry_px + be_offset
                            if hit_sl2:
                                trade_net_pts += (be_offset - FRICTION_PTS) * 0.5
                                in_pos = False; break
                    else:
                        if hit_sl2:
                            trade_net_pts += (be_offset - FRICTION_PTS) * 0.5
                            in_pos = False; break
                        elif fav >= runner_tp:
                            trade_net_pts += (runner_tp - FRICTION_PTS) * 0.5
                            in_pos = False; break
                else: # Short
                    adv = max(entry_px - px_h, -initial_stop)
                    fav = entry_px - px_l
                    if not leg1_closed and adv < trade_mae_pts: trade_mae_pts = adv
                    
                    hit_sl1 = (px_h >= sl_1)
                    hit_tp1 = (px_l <= tp_1)
                    hit_sl2 = (px_h >= sl_2)
                    
                    if not leg1_closed:
                        if hit_sl1:
                            trade_net_pts += (-initial_stop - FRICTION_PTS)
                            in_pos = False; break
                        elif hit_tp1:
                            trade_net_pts += (t1_pts - FRICTION_PTS) * 0.5
                            leg1_closed = True
                            sl_2 = entry_px - be_offset
                            if hit_sl2:
                                trade_net_pts += (be_offset - FRICTION_PTS) * 0.5
                                in_pos = False; break
                    else:
                        if hit_sl2:
                            trade_net_pts += (be_offset - FRICTION_PTS) * 0.5
                            in_pos = False; break
                        elif fav >= runner_tp:
                            trade_net_pts += (runner_tp - FRICTION_PTS) * 0.5
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

def eval_ladder(daily_res, floor_trigger=-350.0):
    ds = [str(d) for d in dates]
    passed, ruined, timeouts, dll_b = 0, 0, 0, 0
    pass_days = []
    dds = []
    
    for i in range(len(ds) - 100):
        cum, hwm, busted, pass_run, peak_dd, tr_days = 0.0, 0.0, False, False, 0.0, 0
        for step in range(100):
            d_str = ds[i + step]
            tr = daily_res.get(d_str, None)
            if not tr or not tr["traded"]: continue
            tr_days += 1
            vix = get_prior_vix(d_str)
            bonus = 2 if vix >= 16.0 else 0
            
            if cum <= floor_trigger: sz = 1
            elif cum >= 2400.0: sz = 12 + bonus
            elif cum >= 1200.0: sz = 10 + bonus
            else: sz = 8 + bonus
            
            pnl = tr["net_1c"] * sz
            mae = tr["mae_1c"] * sz
            
            if pnl <= DLL_LIMIT or mae <= DLL_LIMIT:
                busted = True; dll_b += 1; break
            if (cum + mae) <= STATIC_FLOOR:
                busted = True; break
            if pnl > DAILY_LOCK: pnl = DAILY_LOCK
            
            cum += pnl
            c_dd = hwm - cum
            if c_dd > peak_dd: peak_dd = c_dd
            if cum > hwm: hwm = cum
            if cum <= STATIC_FLOOR: busted = True; break
            if cum >= 4000.0:
                passed += 1; pass_run = True; pass_days.append(tr_days); dds.append(peak_dd); break
                
        if busted and not pass_run: ruined += 1
        elif not pass_run and not busted: timeouts += 1
        
    p_pct = (passed / max(1, passed + ruined)) * 100
    r_pct = (ruined / max(1, passed + ruined)) * 100
    mean_tr = np.mean(pass_days) if passed else 999.0
    med_tr = np.median(pass_days) if passed else 999.0
    p10_tr = np.percentile(pass_days, 10) if passed else 999.0
    avg_dd = np.mean(dds) if passed else 999.0
    
    return {
        "pass_pct": round(p_pct, 1), "ruin_pct": round(r_pct, 1),
        "mean_days": round(mean_tr, 1), "med_days": round(med_tr, 1),
        "p10_days": round(p10_tr, 1), "avg_dd": round(avg_dd, 1), "dll": dll_b
    }

print("="*95)
print("TRAINING-ONLY BRACKET PARAMETER GRID (STOP, T1, RUNNER)")
print("="*95)

results = []
for stop in [14.0, 16.0, 18.0, 20.0]:
    for t1 in [22.0, 28.0, 32.0]:
        for rtp in [100.0, 120.0, 150.0]:
            dres = run_sim(initial_stop=stop, t1_pts=t1, runner_tp=rtp)
            act = sum(1 for v in dres.values() if v['traded'])
            wins = sum(1 for v in dres.values() if v['traded'] and v['net_1c'] > 0)
            wr = wins / max(1, act) * 100
            net_1c = sum(v['net_1c'] for v in dres.values())
            pf_win = sum(v['net_1c'] for v in dres.values() if v['net_1c'] > 0)
            pf_loss = abs(sum(v['net_1c'] for v in dres.values() if v['net_1c'] < 0))
            pf = pf_win / max(1.0, pf_loss)
            ev = eval_ladder(dres, floor_trigger=-350.0)
            print(f"SL: {stop:4.1f} | T1: {t1:4.1f} | T2: {rtp:5.1f} || WR: {wr:4.1f}% | PF: {pf:4.2f} | Net1c: ${net_1c:7.1f} || Pass%: {ev['pass_pct']:5.1f}% | Ruin%: {ev['ruin_pct']:4.1f}% | Mean: {ev['mean_days']:4.1f}d | Med: {ev['med_days']:4.1f}d | DD: ${ev['avg_dd']:5.0f}")
            results.append({
                "stop": stop, "t1": t1, "t2": rtp, "wr": wr, "pf": pf, "net_1c": net_1c, "eval": ev
            })

with open(ROOT / "reports/TRAINING_BRACKET_GRID_RESULTS.json", "w") as f:
    json.dump(results, f, indent=2)
print("Complete.")
