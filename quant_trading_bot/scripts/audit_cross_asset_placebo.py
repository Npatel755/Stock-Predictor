"""Audit & Placebo Test for NQ Leading ES Cross-Asset Relative Strength Momentum.
Training Data (2010-2023, 14 years).
"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd
from numba import njit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import mass_1m_search as m1

COMM, SLIP = 0.61, 1.0
SPEC = {"MNQ": dict(tick=0.25, pv=0.5, spread=1.75), "MES": dict(tick=0.25, pv=1.25, spread=1.0)}
cost_mnq = (SPEC["MNQ"]["spread"] + 2 * SLIP) * SPEC["MNQ"]["pv"] + 2 * COMM
rng = np.random.default_rng(20261109)

b_mnq = m1.load_bars("MNQ", 15, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]].copy()
b_mes = m1.load_bars("MES", 15, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]].copy()

et_mnq = b_mnq.timestamp_utc.dt.tz_convert("America/New_York")
b_mnq["sod"] = et_mnq.dt.hour * 60 + et_mnq.dt.minute
b_mnq["date"] = et_mnq.dt.date
b_mnq["year"] = et_mnq.dt.year

et_mes = b_mes.timestamp_utc.dt.tz_convert("America/New_York")
b_mes["sod"] = et_mes.dt.hour * 60 + et_mes.dt.minute
b_mes["date"] = et_mes.dt.date

rth_mnq = b_mnq[(b_mnq.sod >= 570) & (b_mnq.sod < 960)].reset_index(drop=True)
rth_mes = b_mes[(b_mes.sod >= 570) & (b_mes.sod < 960)].reset_index(drop=True)

g_mnq = rth_mnq.groupby("date")
g_mes = rth_mes.groupby("date")

o930_mnq = g_mnq.apply(lambda d: d.loc[d.sod == 570, "open"].iloc[0] if (d.sod == 570).any() else np.nan)
c1000_mnq = g_mnq.apply(lambda d: d.loc[d.sod == 600, "close"].iloc[0] if (d.sod == 600).any() else np.nan)
o930_mes = g_mes.apply(lambda d: d.loc[d.sod == 570, "open"].iloc[0] if (d.sod == 570).any() else np.nan)
c1000_mes = g_mes.apply(lambda d: d.loc[d.sod == 600, "close"].iloc[0] if (d.sod == 600).any() else np.nan)

common_days = sorted(list(set(o930_mnq.dropna().index).intersection(set(o930_mes.dropna().index))))
df_days = pd.DataFrame(index=common_days)
df_days["ret_mnq"] = (c1000_mnq.loc[common_days] / o930_mnq.loc[common_days]) - 1.0
df_days["ret_mes"] = (c1000_mes.loc[common_days] / o930_mes.loc[common_days]) - 1.0
df_days["spread"] = df_days["ret_mnq"] - df_days["ret_mes"]
df_days["spread_z"] = df_days["spread"] / df_days["spread"].rolling(20, min_periods=20).std().shift(1)

rth_mnq["day"] = pd.factorize(rth_mnq.date)[0]
tr = np.maximum(rth_mnq.high - rth_mnq.low, np.maximum((rth_mnq.high - rth_mnq.close.shift(1)).abs(), (rth_mnq.low - rth_mnq.close.shift(1)).abs()))
atr = tr.rolling(14, min_periods=14).mean().bfill().to_numpy(float)

o = rth_mnq.open.to_numpy(float)
h = rth_mnq.high.to_numpy(float)
l = rth_mnq.low.to_numpy(float)
c = rth_mnq.close.to_numpy(float)
sod = rth_mnq.sod.to_numpy(np.int64)
day = rth_mnq.day.to_numpy(np.int64)
year = rth_mnq.year.to_numpy(np.int64)

date_to_z = df_days["spread_z"].to_dict()
z_per_bar = np.array([date_to_z.get(d, 0.0) for d in rth_mnq.date])

@njit(cache=True)
def sim_rs_fast(o, h, l, c, atr, z_arr, day, sod, z_th, stop_mult, tgt_r, hold, flat, cost):
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
            elif l[i] <= st: ex = True; px = st
            elif h[i] >= tg: ex = True; px = tg
            elif (i - ei >= hold) or (sod[i] + 15 >= flat): ex = True; px = c[i]
            if ex:
                pnl[i] += (px - ep) / 0.25 * 0.5 - cost
                pos = 0
                ntr += 1
                
        if pos == 0 and sod[i] == 600 and i + 1 < n and day[i + 1] == day[i] and atr[i] > 0:
            if z_arr[i] >= z_th:
                pos = 1
                ep = o[i + 1]
                risk = stop_mult * atr[i]
                st = ep - risk
                tg = ep + tgt_r * risk
                ei = i + 1
                eday = day[i]
                
    return pnl, ntr

# Run Real Strategy: z_th=1.25, stop=2.0, tgt=4.0, hold=12
real_pnl, real_ntr = sim_rs_fast(o, h, l, c, atr, z_per_bar, day, sod, 1.25, 2.0, 4.0, 12, 955, cost_mnq)
s_real = pd.Series(real_pnl)
tot_net = float(s_real.sum())
yearly = s_real.groupby(year).sum()
cum = s_real.cumsum()
max_dd = float((cum.cummax() - cum).max())

print("=" * 75)
print("REAL STRATEGY AUDIT: NQ/ES Cross-Asset Momentum Leader (10:00 ET)")
print("Rule: If 10:00 NQ-ES spread z >= 1.25 -> Long MNQ, stop 2.0 ATR, tgt 4.0R, hold 12")
print("=" * 75)
print(f"14-Year Total Net Profit:   +${tot_net:,.2f}")
print(f"Total Trades:               {real_ntr} trades (~25 trades/year)")
print(f"Per-Trade Expectancy:       +${tot_net/real_ntr:.2f} / trade")
print(f"Positive Years:             {int(sum(yearly > 0))}/14 years ({(sum(yearly > 0)/14)*100:.1f}%)")
print(f"14-Year Max Drawdown:       ${max_dd:,.2f} (Cushion: +${2000.0 - max_dd:,.2f} under $2,000 floor)")
print("-" * 75)
print("Yearly Breakdown (2010-2023):")
for y in sorted(yearly.index):
    status = "WIN" if yearly[y] > 0 else "LOSS"
    print(f"  {y}: +${yearly[y]:8.2f}  |  {status}")

# Run 100 Placebo Controls: shuffle valid entry days randomly within each year
print("\nRunning 100 Placebo Monte Carlo Controls...")
placebo_nets = []
placebo_dds = []
placebo_breaches = 0

valid_1000_bars = np.flatnonzero(sod == 600)
# Entry mask count per year
entries_per_year = {}
for y in range(2010, 2024):
    y_mask = (year == y) & (sod == 600) & (z_per_bar >= 1.25)
    entries_per_year[y] = int(y_mask.sum())

for i in range(100):
    # Construct random z mask with exact same number of entries per year
    rand_z = np.zeros_like(z_per_bar)
    for y in range(2010, 2024):
        y_valid = np.flatnonzero((year == y) & (sod == 600))
        n_picks = entries_per_year[y]
        if len(y_valid) > 0 and n_picks > 0:
            picks = rng.choice(y_valid, size=min(n_picks, len(y_valid)), replace=False)
            rand_z[picks] = 2.0 # trigger entry
            
    pl_pnl, _ = sim_rs_fast(o, h, l, c, atr, rand_z, day, sod, 1.25, 2.0, 4.0, 12, 955, cost_mnq)
    pl_s = pd.Series(pl_pnl)
    pl_net = float(pl_s.sum())
    pl_cum = pl_s.cumsum()
    pl_dd = float((pl_cum.cummax() - pl_cum).max())
    placebo_nets.append(pl_net)
    placebo_dds.append(pl_dd)
    if pl_dd >= 2000.0:
        placebo_breaches += 1

pl_mean_net = np.mean(placebo_nets)
pl_p_val = np.mean(np.array(placebo_nets) >= tot_net)

print("=" * 75)
print("PLACEBO MONTE CARLO TEST RESULTS (100 Iterations):")
print("=" * 75)
print(f"Real Net Profit:            +${tot_net:,.2f}")
print(f"Placebo Mean Net Profit:    ${pl_mean_net:,.2f}")
print(f"Statistical p-value:        p = {pl_p_val:.4f} (Beat {100 - int(pl_p_val*100)}/100 Placebos)")
print(f"Placebo Mean Max Drawdown:  ${np.mean(placebo_dds):,.2f}")
print(f"Placebos Breaching $2k DD:  {placebo_breaches}/100 ({placebo_breaches}%)")
print("=" * 75)
