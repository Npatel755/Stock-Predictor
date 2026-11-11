"""
Generate TJR ES CHoCH Trades for the 14-Year Training Split (2010-2023)
Matches the exact logic of choch.py from friend's Claude:
- Unit A: 6fe8aae66be4 (30m, n=1, leg stop + 1 tick, min stop 16 ticks, 1R target, max 1 trade/day)
- Unit B: 2a56c6c23d02 (30m, n=1, leg stop + 4 ticks, min stop 48 ticks, 1R target, max 3 trades/day)
"""
import sys, time
from pathlib import Path
import numpy as np
import pandas as pd
from numba import njit

ROOT = Path(r"c:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor Codex ETH BNB\quant_trading_bot")

t0 = time.time()
print("Loading ES 1-minute training bars...")
df = pd.read_parquet(ROOT / "data/market/GLBX-20261106-FX6FM5XWUX-v3/splits/ES/train.parquet")
print(f"Loaded {len(df)} ES bars in {time.time()-t0:.1f}s")

# Convert timestamps to NY time
ts = pd.to_datetime(df.timestamp_utc, utc=True).dt.tz_convert("America/New_York")
df["ny_time"] = ts
df["session_date"] = ts.dt.date

# CME session starts at 18:00 ET: bars from 18:00 to 23:59 belong to next calendar date's session
cme_shift = ts.dt.hour >= 18
cme_session_date = ts.dt.date.copy()
# Shift next day
next_days = ts + pd.Timedelta(days=1)
cme_session_date[cme_shift] = next_days[cme_shift].dt.date
df["cme_session"] = cme_session_date

# Minute of session (mos): 18:00 is minute 0
df["et_minute"] = ts.dt.hour * 60 + ts.dt.minute
# mos = (et_minute - 18*60) % 1440
df["mos"] = (df["et_minute"] - 18 * 60) % 1440

# Map cme_session to contiguous integers
unique_sessions = sorted(df.cme_session.unique())
sess_map = {s: i for i, s in enumerate(unique_sessions)}
df["sidx"] = df.cme_session.map(sess_map).to_numpy()

# Find last bar of RTH (15:59 or 16:00 ET, which is et_minute <= 960)
# rth_last per session
rth_bars = df[df.et_minute <= 960].groupby("sidx").tail(1).index.to_numpy()
rth_sidx = df.loc[rth_bars, "sidx"].to_numpy()
rth_last = np.full(len(unique_sessions), -1, dtype=np.int64)
for s, idx in zip(rth_sidx, rth_bars):
    rth_last[s] = idx

o = df.open.to_numpy(dtype=np.float64)
h = df.high.to_numpy(dtype=np.float64)
l = df.low.to_numpy(dtype=np.float64)
c = df.close.to_numpy(dtype=np.float64)
sidx = df.sidx.to_numpy(dtype=np.int64)
mos = df.mos.to_numpy(dtype=np.int64)
m = df.et_minute.to_numpy(dtype=np.int64)

print("Building 30m bars...")
tf = 30
key = sidx * (1440 // tf + 1) + mos // tf
starts = np.flatnonzero(np.r_[True, key[1:] != key[:-1]])
ends = np.r_[starts[1:] - 1, len(key) - 1]

to = o[starts]
th = np.maximum.reduceat(h, starts)
tl = np.minimum.reduceat(l, starts)
tc = c[ends]
tend = ends

print(f"Total 30m bars: {len(to)}")

# Run _events for n=1
@njit
def _events(th, tl, tc, tend, n):
    m = th.shape[0]
    k_i = np.empty(m, np.int64)
    k_d = np.empty(m, np.int8)
    k_sw = np.empty(m)
    k_leg = np.empty(m)
    sh, sl = np.nan, np.nan
    sh_j, sl_j = -1, -1
    tr = 0
    k = 0
    for j in range(m):
        p = j - n
        if p - n >= 0:
            ok_h, ok_l = True, True
            for q in range(p - n, p + n + 1):
                if q != p:
                    if th[q] >= th[p]:
                        ok_h = False
                    if tl[q] <= tl[p]:
                        ok_l = False
            if ok_h:
                sh, sh_j = th[p], p
            if ok_l:
                sl, sl_j = tl[p], p
        if not np.isnan(sh) and tc[j] > sh and tr != 1:
            if tr == -1:
                leg = tl[sh_j]
                for q in range(sh_j, j + 1):
                    leg = min(leg, tl[q])
                k_i[k], k_d[k], k_sw[k], k_leg[k] = tend[j], 1, sl, leg
                k += 1
            tr = 1
        elif not np.isnan(sl) and tc[j] < sl and tr != -1:
            if tr == 1:
                leg = th[sl_j]
                for q in range(sl_j, j + 1):
                    leg = max(leg, th[q])
                k_i[k], k_d[k], k_sw[k], k_leg[k] = tend[j], -1, sh, leg
                k += 1
            tr = -1
    return k_i[:k], k_d[:k], k_sw[:k], k_leg[:k]

print("Detecting 30m CHoCH structure events...")
e_i, e_d, e_sw, e_leg = _events(th, tl, tc, tend, 1)
print(f"Total raw CHoCH signals: {len(e_i)}")

# Simulate trades using _kernel
@njit
def run_choch_sim(o, h, l, c, m, sidx, rth_last, e_i, e_d, e_leg,
                  ws, we, buf_pts, min_stop_pts, max_trades, target_r, slip_pts):
    nt = 0
    cap = len(e_i) + 1
    # output arrays: entry_idx, exit_idx, dir, entry_px, stop_px, exit_px, r_net, pnl_pts
    out = np.zeros((cap, 8))
    busy_until = -1
    cur_s, n_today = -1, 0
    
    for k in range(e_i.shape[0]):
        i = e_i[k]
        if i + 1 >= o.shape[0] or i <= busy_until:
            continue
        mi = m[i]
        # RTH entry hours: CHoCH candle closes inside entry hours (9:30 to 16:00 ET -> ws=570, we=960)
        if mi < ws or mi >= we:
            continue
        s = sidx[i]
        if s != cur_s:
            cur_s, n_today = s, 0
        if n_today >= max_trades or sidx[i + 1] != s:
            continue
        
        d = e_d[k]
        lvl = e_leg[k]
        if np.isnan(lvl):
            continue
        end = rth_last[s]
        if end <= i + 1:
            continue
        
        entry = o[i + 1] + d * slip_pts
        stop = lvl - d * buf_pts
        risk = (entry - stop) * d
        if risk <= 0 or risk < min_stop_pts - 1e-9:
            continue
        
        tgt = entry + d * target_r * risk
        px, j_exit = c[end], end
        
        for j in range(i + 1, end + 1):
            # Check stop
            if (l[j] <= stop) if d == 1 else (h[j] >= stop):
                gap = (o[j] <= stop) if d == 1 else (o[j] >= stop)
                px, j_exit = (o[j] if gap else stop) - d * slip_pts, j
                break
            # Check target (trade through)
            if j > i + 1 and ((h[j] > tgt) if d == 1 else (l[j] < tgt)):
                px, j_exit = (max(o[j], tgt) if d == 1 else min(o[j], tgt)), j
                break
                
        pnl = (px - entry) * d
        r_net = pnl / risk
        
        out[nt, 0] = i + 1
        out[nt, 1] = j_exit
        out[nt, 2] = d
        out[nt, 3] = entry
        out[nt, 4] = stop
        out[nt, 5] = px
        out[nt, 6] = r_net
        out[nt, 7] = pnl
        
        nt += 1
        n_today += 1
        busy_until = j_exit
        
    return out[:nt]

# Run Unit A: 6fe8 (buf=1 tick = 0.25 pt, min_stop=16 ticks = 4.0 pts, max_trades=1)
print("\nRunning Unit A (6fe8aae66be4)...")
res_a = run_choch_sim(o, h, l, c, m, sidx, rth_last, e_i, e_d, e_leg,
                      ws=570, we=960, buf_pts=0.25, min_stop_pts=4.0, max_trades=1, target_r=1.0, slip_pts=0.25)
print(f"Unit A trades: {len(res_a)}, WinRate: {(res_a[:, 6] > 0).mean()*100:.1f}%, Mean R: {res_a[:, 6].mean():.3f}")

# Run Unit B: 2a56 (buf=4 ticks = 1.0 pt, min_stop=48 ticks = 12.0 pts, max_trades=3)
print("\nRunning Unit B (2a56c6c23d02)...")
res_b = run_choch_sim(o, h, l, c, m, sidx, rth_last, e_i, e_d, e_leg,
                      ws=570, we=960, buf_pts=1.0, min_stop_pts=12.0, max_trades=3, target_r=1.0, slip_pts=0.25)
print(f"Unit B trades: {len(res_b)}, WinRate: {(res_b[:, 6] > 0).mean()*100:.1f}%, Mean R: {res_b[:, 6].mean():.3f}")

# Save trades to parquet
def make_trade_df(res, name):
    entry_idx = res[:, 0].astype(np.int64)
    exit_idx = res[:, 1].astype(np.int64)
    tdf = pd.DataFrame({
        "sleeve": name,
        "sleeve_key": "ES_CHOCH",
        "inst": "MES",
        "side": res[:, 2].astype(int),
        "tin": df.timestamp_utc.iloc[entry_idx].to_numpy(),
        "tout": df.timestamp_utc.iloc[exit_idx].to_numpy(),
        "entry": res[:, 3],
        "exit": res[:, 5],
        "stop": res[:, 4],
        "risk_pts": (res[:, 3] - res[:, 4]) * res[:, 2],
        "pnl_pts": res[:, 7],
        "r_net": res[:, 6]
    })
    # MES economics: $5 per point, commission $1.24/round turn, slippage 1 tick = $1.25
    # net_today in dollars for 1 MES contract
    tdf["risk_today"] = tdf["risk_pts"] * 5.0
    tdf["net_today"] = tdf["pnl_pts"] * 5.0 - 1.24 # $1.24 MES commission
    tdf["r_net_realistic"] = tdf["net_today"] / tdf["risk_today"].clip(lower=1.0)
    tdf["tin_str"] = tdf.tin.astype(str)
    tdf["tout_str"] = tdf.tout.astype(str)
    tdf["is_gap_cont"] = False
    return tdf

df_a = make_trade_df(res_a, "CHOCH_6FE8")
df_b = make_trade_df(res_b, "CHOCH_2A56")
choch_trades = pd.concat([df_a, df_b], ignore_index=True).sort_values("tin").reset_index(drop=True)

out_path = ROOT / "data/processed/es_choch_trades_train.parquet"
choch_trades.to_parquet(out_path)
print(f"\nSaved {len(choch_trades)} ES CHoCH trades to {out_path}")
