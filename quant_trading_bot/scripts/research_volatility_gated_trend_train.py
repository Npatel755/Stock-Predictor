"""Research Hypothesis: Volatility-Gated High-Expectancy Trend Continuation.
Hypothesis:
Intraday trend edges fail pre-2020 on micro futures when trading on low-volatility/compressed days,
because the total daily range (10-20 points) is too small relative to fixed $3.10 micro friction.
By conditioning entries on a minimum intraday expansion potential:
- ATR14 relative to price >= percentile threshold (filtering out fee-eating dead chop)
- Capturing high-R expansions (target 3.0R - 4.5R)
Does this lift pre-2020 expectancy to >= $25-$50+/trade and reduce drawdowns?

EVALUATED STRICTLY ON TRAINING DATA (2010-2023, 14 FULL YEARS).
DO NOT TOUCH VALIDATION (2024-2025) OR TEST (2026).
Micro costs: 0.61/side commission, 1.75 tick MNQ, 1.0 tick MES, 1.0 tick slippage.
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
from numba import njit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import mass_1m_search as m1

COMM, SLIP = 0.61, 1.0
SPEC = {"MNQ": dict(tick=0.25, pv=0.5, spread=1.75), "MES": dict(tick=0.25, pv=1.25, spread=1.0)}

def rt_cost(prod):
    s = SPEC[prod]
    return (s["spread"] + 2 * SLIP) * s["pv"] + 2 * COMM

print("Loading continuous 30m Training bars for MNQ and MES (2010-2023)...")
b_mnq = m1.load_bars("MNQ", 30, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]].copy()
b_mes = m1.load_bars("MES", 30, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]].copy()

for b in (b_mnq, b_mes):
    et = b.timestamp_utc.dt.tz_convert("America/New_York")
    b["sod"] = et.dt.hour * 60 + et.dt.minute
    b["date"] = et.dt.date
    b["year"] = et.dt.year

@njit(cache=True)
def sim_gated_trend(o, h, l, c, atr, trend_sig, vol_gate, day, sod, stop_mult, tgt_r, hold, flat, cost, tick_size, point_val):
    n = len(o)
    pnl = np.zeros(n)
    pos = 0
    ep = 0.0
    st = 0.0
    tg = 0.0
    ei = 0
    eday = -1
    ntr = 0
    
    for i in range(n):
        if pos != 0:
            ex = False
            px = 0.0
            if day[i] != eday: ex = True; px = o[i]
            elif pos > 0 and l[i] <= st: ex = True; px = st
            elif pos < 0 and h[i] >= st: ex = True; px = st
            elif pos > 0 and h[i] >= tg: ex = True; px = tg
            elif pos < 0 and l[i] <= tg: ex = True; px = tg
            elif (i - ei >= hold) or (sod[i] + 30 >= flat): ex = True; px = c[i]
            if ex:
                pnl[i] += pos * (px - ep) / tick_size * point_val - cost
                pos = 0
                ntr += 1
                
        # Entry window: 10:00 to 12:00 ET (sod 600 to 720)
        if pos == 0 and (600 <= sod[i] <= 720) and trend_sig[i] != 0 and vol_gate[i] and i + 1 < n and day[i + 1] == day[i] and atr[i] > 0:
            pos = trend_sig[i]
            ep = o[i + 1]
            risk = stop_mult * atr[i]
            st = ep - risk if pos > 0 else ep + risk
            tg = ep + tgt_r * risk if pos > 0 else ep - tgt_r * risk
            ei = i + 1
            eday = day[i]
            
    return pnl, ntr

def run_vol_gated_search(prod, b):
    rth = b[(b.sod >= 570) & (b.sod <= 955)].reset_index(drop=True)
    rth["day"] = pd.factorize(rth.date)[0]
    
    # Calculate True Range and ATR
    tr = np.maximum(rth.high - rth.low, np.maximum((rth.high - rth.close.shift(1)).abs(), (rth.low - rth.close.shift(1)).abs()))
    atr = tr.rolling(14, min_periods=14).mean().bfill().to_numpy(float)
    
    # ATR as percentage of price
    atr_pct = atr / rth.close.to_numpy(float)
    
    # Rolling 60-day median of atr_pct
    s_atr_pct = pd.Series(atr_pct)
    rolling_med_atr = s_atr_pct.rolling(60 * 13, min_periods=50).median().bfill().to_numpy(float)
    
    # Fast / Slow EMA trend signal (lb16 / lb32 on 30m)
    ema_fast = rth.close.ewm(span=8, adjust=False).mean()
    ema_slow = rth.close.ewm(span=16, adjust=False).mean()
    trend_raw = (ema_fast - ema_slow) / atr
    trend_sig = np.zeros(len(rth), dtype=np.int8)
    trend_sig[trend_raw >= 0.75] = 1
    trend_sig[trend_raw <= -0.75] = -1
    
    o = rth.open.to_numpy(float)
    h = rth.high.to_numpy(float)
    l = rth.low.to_numpy(float)
    c = rth.close.to_numpy(float)
    sod = rth.sod.to_numpy(np.int64)
    day = rth.day.to_numpy(np.int64)
    year = rth.year.to_numpy(np.int64)
    cost = rt_cost(prod)
    spec = SPEC[prod]
    
    print(f"\n=======================================================")
    print(f"Volatility-Gated Trend Search on {prod} (2010-2023 Train)")
    print(f"=======================================================")
    
    # Baseline: No gate (all days)
    all_gate = np.ones(len(rth), dtype=bool)
    pnl_base, ntr_base = sim_gated_trend(o, h, l, c, atr, trend_sig, all_gate, day, sod, 1.5, 4.0, 8, 955, cost, spec["tick"], spec["pv"])
    s_base = pd.Series(pnl_base)
    cum_base = s_base.cumsum()
    mdd_base = float((cum_base.cummax() - cum_base).max())
    print(f"UNGATED BASELINE: Net: ${s_base.sum():.2f} | Tr: {ntr_base} | Exp: ${s_base.sum()/ntr_base:.2f}/tr | Pre-2020: ${s_base[year < 2020].sum():.2f} | +Yrs: {(s_base.groupby(year).sum() > 0).sum()}/14 | MaxDD: ${mdd_base:.2f}")
    
    # Test Volatility Gates:
    # 1. atr_pct >= rolling_med_atr (only trade above-median volatility regimes)
    # 2. atr_pct >= 1.25 * rolling_med_atr
    # 3. absolute dollar ATR per point: atr * pv / cost >= 10.0 (ensuring ATR is at least 10x the round-turn cost!)
    for gate_name, gate_mask in [
        ("ATR >= Rolling Median", atr_pct >= rolling_med_atr),
        ("ATR >= 1.2x Median", atr_pct >= (1.2 * rolling_med_atr)),
        ("Dollar ATR >= 8x Round-Trip Cost", (atr / spec["tick"] * spec["pv"]) >= (8.0 * cost)),
        ("Dollar ATR >= 12x Round-Trip Cost", (atr / spec["tick"] * spec["pv"]) >= (12.0 * cost)),
    ]:
        for stop_mult in [1.25, 1.5]:
            for tgt_r in [3.0, 4.0, 5.0]:
                for hold in [6, 8, 10]:
                    pnl, ntr = sim_gated_trend(o, h, l, c, atr, trend_sig, gate_mask, day, sod, stop_mult, tgt_r, hold, 955, cost, spec["tick"], spec["pv"])
                    if ntr < 50: continue
                    s_pnl = pd.Series(pnl)
                    tot = float(s_pnl.sum())
                    pre = float(s_pnl[year < 2020].sum())
                    post = float(s_pnl[year >= 2020].sum())
                    yearly = s_pnl.groupby(year).sum()
                    pos_y = int((yearly > 0).sum())
                    cum = s_pnl.cumsum()
                    mdd = float((cum.cummax() - cum).max())
                    exp_tr = tot / ntr
                    
                    if tot > s_base.sum() * 0.7 and pre > 1000 and pos_y >= 10 and mdd < 1000 and exp_tr >= 20.0:
                        print(f"[{gate_name}] Stop: {stop_mult} | Tgt: {tgt_r}R | Hold: {hold} | Net: ${tot:.2f} | Tr: {ntr} | Exp: ${exp_tr:.2f}/tr | Pre-2020: ${pre:.2f} | Post-2020: ${post:.2f} | +Yrs: {pos_y}/14 | MaxDD: ${mdd:.2f}")

run_vol_gated_search("MNQ", b_mnq)
run_vol_gated_search("MES", b_mes)
