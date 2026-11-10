"""Compare Target Profiles & Dynamic Staging on Training Split (2010-2023) ONLY.
METHODOLOGICAL INVARIANT:
- 100% STRICTLY ON TRAINING DATA.
- ZERO TUNING ON VALIDATION OR TEST.
"""
import sys, json, gc
from pathlib import Path
import numpy as np, pandas as pd, duckdb

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")
p_train = ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/NQ/train.parquet"

# VIX
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
    high::DOUBLE AS high,
    low::DOUBLE AS low,
    close::DOUBLE AS close
FROM read_parquet('{p_train}')
WHERE (date_part('hour', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))*60 + 
       date_part('minute', timezone('America/New_York', timestamp_utc::TIMESTAMPTZ))) BETWEEN 570 AND 960
ORDER BY date, sod
"""
rth = con.execute(q).fetch_df()
con.close()

dates = sorted(rth["date"].unique())
daily_eod = rth[rth.sod == 960].groupby("date")["close"].last()
daily_sod = rth[rth.sod == 570].groupby("date")["high"].first() # approx open
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

print(f"Loaded {len(dates)} calendar sessions in Training Split.")

def simulate_crabel_trades(initial_stop=16.0, t1_pts=20.0, runner_profile="adaptive"):
    # runner_profile: "adaptive" (+40->25, +60->45, +85 TP) vs "runner120" (BE at T1, +120 TP)
    daily_res = {}
    for d in dates:
        vix = get_vix(d)
        gap = gap_dict.get(d, 0.0)
        if vix < 15.0 or d not in grouped:
            daily_res[d] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        bars = grouped[d]
        sod, high, low, close = bars["sod"], bars["high"], bars["low"], bars["close"]
        mask_15 = sod < 585
        if not mask_15.any():
            daily_res[d] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        hi_15 = high[mask_15].max()
        lo_15 = low[mask_15].min()
        rng_15 = hi_15 - lo_15
        if rng_15 < 15.0:
            daily_res[d] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
            continue
            
        idx_trade = np.where((sod >= 585) & (sod <= 955))[0]
        if len(idx_trade) == 0:
            daily_res[d] = {"net_1c": 0.0, "mae_1c": 0.0, "traded": False}
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
                    sl_1 = entry_px - initial_stop
                    sl_2 = sl_1
                    tp_1 = entry_px + t1_pts
                elif gap <= 0.0 and px_l < lo_15:
                    in_pos = True; pos_dir = -1; entry_px = lo_15
                    sl_1 = entry_px + initial_stop
                    sl_2 = sl_1
                    tp_1 = entry_px - t1_pts
            else:
                if pos_dir == 1:
                    adv = max(px_l - entry_px, -initial_stop)
                    fav = px_h - entry_px
                    if not leg1_closed and adv < trade_mae_pts: 
                        trade_mae_pts = adv
                    if fav > max_fav: 
                        max_fav = fav
                    
                    if not leg1_closed:
                        if px_h >= tp_1:
                            trade_net_pts += (t1_pts - FRICTION_PTS) * 0.5
                            leg1_closed = True
                            sl_2 = entry_px + 1.0 # Breakeven
                        elif px_l <= sl_1:
                            trade_net_pts += (-initial_stop - FRICTION_PTS)
                            in_pos = False; break
                    else:
                        if runner_profile == "adaptive":
                            if max_fav >= 85.0:
                                trade_net_pts += (85.0 - FRICTION_PTS) * 0.5
                                in_pos = False; break
                            elif max_fav >= 60.0:
                                sl_2 = max(sl_2, entry_px + 45.0)
                            elif max_fav >= 40.0:
                                sl_2 = max(sl_2, entry_px + 25.0)
                        elif runner_profile == "runner120":
                            if max_fav >= 120.0:
                                trade_net_pts += (120.0 - FRICTION_PTS) * 0.5
                                in_pos = False; break
                                
                        if px_l <= sl_2:
                            pts_exit = sl_2 - entry_px
                            trade_net_pts += (pts_exit - FRICTION_PTS) * 0.5
                            in_pos = False; break
                else: # Short
                    adv = max(entry_px - px_h, -initial_stop)
                    fav = entry_px - px_l
                    if not leg1_closed and adv < trade_mae_pts: 
                        trade_mae_pts = adv
                    if fav > max_fav: 
                        max_fav = fav
                    
                    if not leg1_closed:
                        if px_l <= tp_1:
                            trade_net_pts += (t1_pts - FRICTION_PTS) * 0.5
                            leg1_closed = True
                            sl_2 = entry_px - 1.0 # Breakeven
                        elif px_h >= sl_1:
                            trade_net_pts += (-initial_stop - FRICTION_PTS)
                            in_pos = False; break
                    else:
                        if runner_profile == "adaptive":
                            if max_fav >= 85.0:
                                trade_net_pts += (85.0 - FRICTION_PTS) * 0.5
                                in_pos = False; break
                            elif max_fav >= 60.0:
                                sl_2 = min(sl_2, entry_px - 45.0)
                            elif max_fav >= 40.0:
                                sl_2 = min(sl_2, entry_px - 25.0)
                        elif runner_profile == "runner120":
                            if max_fav >= 120.0:
                                trade_net_pts += (120.0 - FRICTION_PTS) * 0.5
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
            
        daily_res[d] = {
            "net_1c": trade_net_pts * PT_VAL,
            "mae_1c": trade_mae_pts * PT_VAL,
            "traded": in_pos or trade_net_pts != 0.0
        }
    return daily_res

# Cache trades for both profiles
print("Simulating Crabel trades across Training split...")
trades_adaptive = simulate_crabel_trades(t1_pts=20.0, runner_profile="adaptive")
trades_runner120 = simulate_crabel_trades(t1_pts=28.0, runner_profile="runner120")

active_ad = [d for d in dates if trades_adaptive[d]["traded"]]
active_120 = [d for d in dates if trades_runner120[d]["traded"]]

print(f"Adaptive Profile: {len(active_ad)} active days | Net on 1c: ${sum(trades_adaptive[d]['net_1c'] for d in active_ad):.2f}")
print(f"Runner120 Profile: {len(active_120)} active days | Net on 1c: ${sum(trades_runner120[d]['net_1c'] for d in active_120):.2f}")

# Save cached trades to json for ultra fast grid evaluation
def sanitize_dict(d):
    return {
        str(k): {
            "net_1c": float(v["net_1c"]),
            "mae_1c": float(v["mae_1c"]),
            "traded": bool(v["traded"])
        }
        for k, v in d.items()
    }

with open(ROOT / "data/processed/crabel_train_adaptive.json", "w") as f:
    json.dump(sanitize_dict(trades_adaptive), f)
with open(ROOT / "data/processed/crabel_train_runner120.json", "w") as f:
    json.dump(sanitize_dict(trades_runner120), f)
print("Cached training trade profiles successfully.")
