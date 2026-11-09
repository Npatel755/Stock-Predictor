"""Research Protocol: Break-Even Stop Ratchet on Champion Quad Sleeve 1 (2010-2023 Training).
Hypothesis:
Moving the stop loss to Entry + 0.25R once MFE reaches >= +1.5R or +2.0R eliminates
catastrophic reversals from winning positions, reducing max continuous drawdown on Training data.

EVALUATED STRICTLY ON TRAINING DATA (2010-2023, 14 FULL YEARS).
DO NOT TOUCH VALIDATION (2024-2025) OR TEST (2026).
Micro costs: 0.61/side commission, 1.75 tick MNQ spread, 1.0 tick slippage.
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
from numba import njit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import mass_1m_search as m1

COMM, SLIP = 0.61, 1.0
SPEC = {"MNQ": dict(tick=0.25, pv=0.5, spread=1.75)}
cost = (SPEC["MNQ"]["spread"] + 2 * SLIP) * SPEC["MNQ"]["pv"] + 2 * COMM

print("Loading continuous 30m Training bars for MNQ (2010-2023)...")
b_mnq = m1.load_bars("MNQ", 30, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]].copy()

et = b_mnq.timestamp_utc.dt.tz_convert("America/New_York")
b_mnq["sod"] = et.dt.hour * 60 + et.dt.minute
b_mnq["date"] = et.dt.date
b_mnq["year"] = et.dt.year

rth = b_mnq[(b_mnq.sod >= 570) & (b_mnq.sod <= 955)].reset_index(drop=True)
rth["day"] = pd.factorize(rth.date)[0]

# Sleeve 1: EMA fast 8, slow 16 normalized by ATR14, lookback 16, threshold 0.75, stop 1.5 ATR, target 3.5R, hold 8, 09:45-12:00 ET
tr = np.maximum(rth.high - rth.low, np.maximum((rth.high - rth.close.shift(1)).abs(), (rth.low - rth.close.shift(1)).abs()))
atr = tr.rolling(14, min_periods=14).mean().bfill().to_numpy(float)

ema_fast = rth.close.ewm(span=8, adjust=False).mean()
ema_slow = rth.close.ewm(span=16, adjust=False).mean()
trend_raw = (ema_fast - ema_slow) / atr

sig = np.zeros(len(rth), dtype=np.int8)
sig[(trend_raw >= 0.75) & (rth.sod >= 585) & (rth.sod <= 720)] = 1
sig[(trend_raw <= -0.75) & (rth.sod >= 585) & (rth.sod <= 720)] = -1

o = rth.open.to_numpy(float)
h = rth.high.to_numpy(float)
l = rth.low.to_numpy(float)
c = rth.close.to_numpy(float)
sod = rth.sod.to_numpy(np.int64)
day = rth.day.to_numpy(np.int64)
year = rth.year.to_numpy(np.int64)

@njit(cache=True)
def sim_sleeve1_ratchet(o, h, l, c, atr, sig, day, sod, stop_mult, tgt_r, hold, ratchet_trigger_r, ratchet_lock_r):
    n = len(o)
    pnl = np.zeros(n)
    pos = 0
    ep = 0.0
    st = 0.0
    tg = 0.0
    ei = 0
    eday = -1
    ntr = 0
    ratcheted = False
    
    for i in range(n):
        if pos != 0:
            ex = False
            px = 0.0
            risk_dist = stop_mult * atr[ei - 1]
            
            # Check ratchet trigger: if MFE >= ratchet_trigger_r * risk_dist
            if not ratcheted and ratchet_trigger_r > 0:
                if pos > 0 and (h[i] - ep) >= ratchet_trigger_r * risk_dist:
                    st = ep + ratchet_lock_r * risk_dist
                    ratcheted = True
                elif pos < 0 and (ep - l[i]) >= ratchet_trigger_r * risk_dist:
                    st = ep - ratchet_lock_r * risk_dist
                    ratcheted = True
                    
            if day[i] != eday: ex = True; px = o[i]
            elif pos > 0 and l[i] <= st: ex = True; px = st
            elif pos < 0 and h[i] >= st: ex = True; px = st
            elif pos > 0 and h[i] >= tg: ex = True; px = tg
            elif pos < 0 and l[i] <= tg: ex = True; px = tg
            elif (i - ei >= hold) or (sod[i] + 30 >= 955): ex = True; px = c[i]
            if ex:
                pnl[i] += pos * (px - ep) / 0.25 * 0.5 - cost
                pos = 0
                ntr += 1
                ratcheted = False
                
        # Entry
        if pos == 0 and sig[i] != 0 and (585 <= sod[i] <= 720) and i + 1 < n and day[i + 1] == day[i] and atr[i] > 0:
            pos = sig[i]
            ep = o[i + 1]
            risk = stop_mult * atr[i]
            st = ep - risk if pos > 0 else ep + risk
            tg = ep + tgt_r * risk if pos > 0 else ep - tgt_r * risk
            ei = i + 1
            eday = day[i]
            ratcheted = False
            
    return pnl, ntr

print("\n--- Testing Break-Even Stop Ratchet on Sleeve 1 (2010-2023 Training) ---")
# Baseline: No ratchet
pnl_base, ntr_base = sim_sleeve1_ratchet(o, h, l, c, atr, sig, day, sod, 1.5, 3.5, 8, 0.0, 0.0)
s_base = pd.Series(pnl_base)
cum_base = s_base.cumsum()
mdd_base = float((cum_base.cummax() - cum_base).max())
print(f"BASELINE (No Ratchet): Net: ${s_base.sum():.2f} | Tr: {ntr_base} | Exp: ${s_base.sum()/ntr_base:.2f}/tr | Pre-2020: ${s_base[year < 2020].sum():.2f} | MaxDD: ${mdd_base:.2f}")

for trig in [1.25, 1.5, 1.75, 2.0]:
    for lock in [0.0, 0.25]:
        pnl_r, ntr_r = sim_sleeve1_ratchet(o, h, l, c, atr, sig, day, sod, 1.5, 3.5, 8, trig, lock)
        s_r = pd.Series(pnl_r)
        cum_r = s_r.cumsum()
        mdd_r = float((cum_r.cummax() - cum_r).max())
        pre_r = float(s_r[year < 2020].sum())
        pos_y = int((s_r.groupby(year).sum() > 0).sum())
        print(f"Trig: +{trig}R, Lock: +{lock}R | Net: ${s_r.sum():.2f} | Tr: {ntr_r} | Exp: ${s_r.sum()/ntr_r:.2f}/tr | Pre-2020: ${pre_r:.2f} | +Yrs: {pos_y}/14 | MaxDD: ${mdd_r:.2f}")
