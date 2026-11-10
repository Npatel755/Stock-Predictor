"""Test Fast Banker + Vol-Adaptive Sizing on 14-Year Training Split (2010-2023).
METHODOLOGICAL INVARIANT:
- 100% EXCLUSIVELY ON TRAINING DATA.
- ZERO TUNING ON VALIDATION OR TEST.
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")

# Load minute bars for training
import duckdb
p_train = ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/train.parquet"
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

con = duckdb.connect()
con.execute("PRAGMA memory_limit='2GB'")
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

grouped = {}
for d, g in rth.groupby("date"):
    grouped[d] = {
        "sod": g["sod"].to_numpy(),
        "high": g["high"].to_numpy(),
        "low": g["low"].to_numpy(),
        "close": g["close"].to_numpy(),
    }
del rth

def simulate_fast_banker_trades(t1_pts=24.0, runner_tp=120.0, use_ratchet=True):
    daily_res = {}
    for d in dates:
        vix = get_vix(d)
        gap = gap_dict.get(d, 0.0)
        if vix < 15.0 or d not in grouped:
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
        if rng_15 < 15.0:
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
                if gap >= 0.0 and px_h > hi_15:
                    in_pos = True; pos_dir = 1; entry_px = hi_15
                    sl_1 = entry_px - 16.0
                    sl_2 = sl_1
                    tp_1 = entry_px + t1_pts
                elif gap <= 0.0 and px_l < lo_15:
                    in_pos = True; pos_dir = -1; entry_px = lo_15
                    sl_1 = entry_px + 16.0
                    sl_2 = sl_1
                    tp_1 = entry_px - t1_pts
            else:
                if pos_dir == 1:
                    adv = max(px_l - entry_px, -16.0)
                    fav = px_h - entry_px
                    if not leg1_closed and adv < trade_mae_pts: trade_mae_pts = adv
                    if fav > max_fav: max_fav = fav
                    
                    if not leg1_closed:
                        if px_h >= tp_1:
                            trade_net_pts += (t1_pts - FRICTION_PTS) * 0.5
                            leg1_closed = True
                            sl_2 = entry_px + 1.0
                        elif px_l <= sl_1:
                            trade_net_pts += (-16.0 - FRICTION_PTS)
                            in_pos = False; break
                    else:
                        if use_ratchet:
                            if max_fav >= runner_tp:
                                trade_net_pts += (runner_tp - FRICTION_PTS) * 0.5
                                in_pos = False; break
                            elif max_fav >= 90.0: sl_2 = max(sl_2, entry_px + 70.0)
                            elif max_fav >= 60.0: sl_2 = max(sl_2, entry_px + 40.0)
                            elif max_fav >= 40.0: sl_2 = max(sl_2, entry_px + 20.0)
                        else:
                            if max_fav >= runner_tp:
                                trade_net_pts += (runner_tp - FRICTION_PTS) * 0.5
                                in_pos = False; break
                                
                        if px_l <= sl_2:
                            pts_exit = sl_2 - entry_px
                            trade_net_pts += (pts_exit - FRICTION_PTS) * 0.5
                            in_pos = False; break
                else: # Short
                    adv = max(entry_px - px_h, -16.0)
                    fav = entry_px - px_l
                    if not leg1_closed and adv < trade_mae_pts: trade_mae_pts = adv
                    if fav > max_fav: max_fav = fav
                    
                    if not leg1_closed:
                        if px_l <= tp_1:
                            trade_net_pts += (t1_pts - FRICTION_PTS) * 0.5
                            leg1_closed = True
                            sl_2 = entry_px - 1.0
                        elif px_h >= sl_1:
                            trade_net_pts += (-16.0 - FRICTION_PTS)
                            in_pos = False; break
                    else:
                        if use_ratchet:
                            if max_fav >= runner_tp:
                                trade_net_pts += (runner_tp - FRICTION_PTS) * 0.5
                                in_pos = False; break
                            elif max_fav >= 90.0: sl_2 = min(sl_2, entry_px - 70.0)
                            elif max_fav >= 60.0: sl_2 = min(sl_2, entry_px - 40.0)
                            elif max_fav >= 40.0: sl_2 = min(sl_2, entry_px - 20.0)
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

print("Simulating trades on Training split...")
t_bank24_ratchet = simulate_fast_banker_trades(t1_pts=24.0, runner_tp=120.0, use_ratchet=True)
t_bank24_fixed = simulate_fast_banker_trades(t1_pts=24.0, runner_tp=120.0, use_ratchet=False)

def eval_candidate(name, daily_res, vix_split=16.0, max_horizon=100):
    passed = 0
    ruined = 0
    pass_tr = []
    max_dds = []
    dll_breaches = 0
    date_strs = [str(d) for d in dates]
    
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
            vix = vix_dict.get(pd.to_datetime(d_str).date(), 18.0)
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
    
    print(f"{name:58s} | Pass: {p_pct:5.1f}% | Ruin: {r_pct:4.1f}% | MeanTR: {mean_tr:4.1f}d | MedTR: {med_tr:4.1f}d | P25: {p25_tr:4.1f}d | P10: {p10_tr:4.1f}d | Min: {min_tr:2d}d | DLL: {dll_breaches:2d} | DD: ${avg_dd:.0f}")

print("\n" + "="*125)
print("TESTING CANDIDATES ON TRAINING SPLIT:")
print("="*125)
eval_candidate("1. Fast Banker (+24pt) + Ratchet Ladder + Vol-Adaptive (VIX>=16)", t_bank24_ratchet, vix_split=16.0)
eval_candidate("2. Fast Banker (+24pt) + Fixed 120 + Vol-Adaptive (VIX>=16)", t_bank24_fixed, vix_split=16.0)
eval_candidate("3. Fast Banker (+24pt) + Fixed 120 + Vol-Adaptive (VIX>=18)", t_bank24_fixed, vix_split=18.0)
