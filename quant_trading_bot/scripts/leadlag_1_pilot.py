"""leadlag_1 pilot (research/leadlag_1/PROTOCOL.md): ES/NQ 1-min residual lead-lag, predictive + 54-config executable test, training only."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from numba import njit
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts"))
import mass_1m_search as m1
TICK, PV, COMM, SLIP, HALF_SPREAD = 0.25, 0.5, 0.61, 1.0, 0.875   # MNQ; spread 1.75 ticks
rng = np.random.default_rng(20261109)

def load(sym):
    b = m1.load_bars(sym, 1, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]]
    et = b.timestamp_utc.dt.tz_convert("America/New_York"); b["sod"] = et.dt.hour * 60 + et.dt.minute; b["date"] = et.dt.date
    return b[(b.sod >= 570) & (b.sod < 960)].reset_index(drop=True)
es, nq = load("MES"), load("MNQ")   # loader maps to ES/NQ before 2019-01, micros after
d = nq.merge(es[["timestamp_utc", "close"]].rename(columns={"close": "es_close"}), on="timestamp_utc", how="inner")
d["day"] = pd.factorize(d.date)[0]; g = d.groupby("day", sort=False)
rE, rN = {}, {}
for k in (1, 3, 5):
    rE[k] = np.log(d.es_close) - np.log(g.es_close.shift(k)); rN[k] = np.log(d.close) - np.log(g.close.shift(k))
# rolling 20-session beta of 1-min NQ on ES returns, lagged one session
dd = pd.DataFrame(dict(day=d.day, xy=rE[1] * rN[1], xx=rE[1] ** 2)).groupby("day").sum()
beta = (dd.xy.rolling(20).sum() / dd.xx.rolling(20).sum()).shift(1); d["beta"] = d.day.map(beta)
z = {}
for k in (1, 3, 5):
    res = rN[k] - d.beta * rE[k]; sd = pd.DataFrame(dict(day=d.day, r2=res ** 2)).groupby("day").mean(); sd = np.sqrt(sd.r2.rolling(20).mean()).shift(1)
    z[k] = (res / d.day.map(sd)).to_numpy()
for h in (1, 5, 15):
    d[f"fwdN{h}"] = (g.close.shift(-h) - d.close) / TICK; d[f"fwdE{h}"] = (g.es_close.shift(-h) - d.es_close) / 0.25
tr = np.maximum(d.high - d.low, np.maximum((d.high - g.close.shift(1)).abs(), (d.low - g.close.shift(1)).abs())); d["atr"] = tr.groupby(d.day).transform(lambda s: s.rolling(14, min_periods=14).mean())
day, sod, year = d.day.to_numpy(np.int64), d.sod.to_numpy(np.int64), pd.to_datetime(d.date).dt.year.to_numpy()
o, h_, l_, c_ = d.open.to_numpy(float), d.high.to_numpy(float), d.low.to_numpy(float), d.close.to_numpy(float); atr = np.nan_to_num(d.atr.to_numpy(float))

def dbt(x, y, dayv):
    m = np.isfinite(x) & np.isfinite(y); x, y, dayv = x[m], y[m], dayv[m]
    b = np.polyfit(x, y, 1)[0]; e = y - np.polyval(np.polyfit(x, y, 1), x)
    s = pd.Series(x * e).groupby(dayv).sum(); se = np.sqrt((s ** 2).sum()) / (x ** 2).sum(); return float(b), float(b / se)
rth = (sod >= 585) & (sod < 930)
out = dict(rows=int(len(d)), sessions=int(d.day.nunique()), predictive={}, executable=[])
for k in (1, 3, 5):
    out["predictive"][f"z{k}"] = {}
    for tgt in ("N", "E"):
        for h in (1, 5, 15):
            y = d[f"fwd{tgt}{h}"].to_numpy(); m = rth & np.isfinite(z[k]) & np.isfinite(y)
            dec = pd.qcut(pd.Series(z[k][m]), 10, labels=False).to_numpy(); means = pd.Series(y[m]).groupby(dec).mean()
            slope, t = dbt((dec == 9).astype(float) - (dec == 0).astype(float), y[m], day[m])
            r = dict(top_minus_bottom_ticks=round(float(means.iloc[-1] - means.iloc[0]), 3), t=round(t, 2), rho=round(float(pd.Series(means.index).corr(pd.Series(means.to_numpy()), method="spearman")), 2), deciles=[round(float(v), 3) for v in means])
            out["predictive"][f"z{k}"][f"{tgt}{h}"] = r; print(f"z{k} -> {tgt} fwd{h}: spread {r['top_minus_bottom_ticks']:+.3f} ticks t {t:+.2f} rho {r['rho']:+.2f}", flush=True)

@njit(cache=True)
def sim(o, h, l, c, atr, sig, day, sod, hold, stop_mult, s0, s1, flat):
    n = len(o); pnl = np.zeros(n); pos = 0; ep = 0.0; st = 0.0; ei = 0; eday = -1; ntr = 0
    for i in range(n):
        if pos != 0:
            px = 0.0; ex = False
            if day[i] != eday: ex = True; px = o[i]
            elif pos > 0 and l[i] <= st: ex = True; px = st
            elif pos < 0 and h[i] >= st: ex = True; px = st
            elif i - ei >= hold or sod[i] >= flat: ex = True; px = c[i]
            if ex:
                px = px - (HALF_SPREAD + SLIP) * TICK if pos > 0 else px + (HALF_SPREAD + SLIP) * TICK
                pnl[i] += pos * (px - ep) / TICK * PV - 2 * COMM; pos = 0; ntr += 1
        if pos == 0 and sig[i] != 0 and sod[i] >= s0 and sod[i] < s1 and i + 1 < n and day[i + 1] == day[i] and atr[i] > 0:
            pos = sig[i]; ep = o[i + 1] + (HALF_SPREAD + SLIP) * TICK if pos > 0 else o[i + 1] - (HALF_SPREAD + SLIP) * TICK
            st = ep - stop_mult * atr[i] if pos > 0 else ep + stop_mult * atr[i]; ei = i + 1; eday = day[i]
    return pnl, ntr
def run(sig, hold):
    pnl, ntr = sim(o, h_, l_, c_, atr, sig, day, sod, hold, 1.5, 585, 930, 945)
    yr = pd.Series(pnl).groupby(year).sum(); return float(pnl.sum()), ntr, {int(k): round(float(v), 2) for k, v in yr.items()}
elig = np.flatnonzero(rth)
for k in (1, 3, 5):
    for q in (2.0, 2.5, 3.0):
        for mode in ("conv", "div"):
            zz = np.nan_to_num(z[k]); base = np.where(zz >= q, 1, np.where(zz <= -q, -1, 0)).astype(np.int8)
            sig = -base if mode == "conv" else base
            for hold in (5, 15, 30):
                net, ntr, yr = run(sig, hold); pos_years = sum(v > 0 for v in yr.values()); share = max(yr.values()) / net if net > 0 else None
                pl = []
                for _ in range(20):
                    p = np.zeros_like(sig); pick = rng.choice(elig, size=min(int((sig != 0).sum()), len(elig)), replace=False); p[pick] = rng.choice(np.array([-1, 1], dtype=np.int8), size=len(pick)); pl.append(run(p, hold)[0])
                rec = dict(k=k, q=q, mode=mode, hold=hold, net=round(net, 2), trades=ntr, per_trade=round(net / ntr, 2) if ntr else None, pos_years=int(pos_years), max_year_share=round(share, 2) if share else None,
                           placebo_pct=float(np.mean(np.array(pl) < net)), placebo_mean=round(float(np.mean(pl)), 2), yearly=yr,
                           passes=bool(net > 0 and pos_years >= 10 and (share or 1) <= 0.4 and np.mean(np.array(pl) < net) >= 0.95 and ntr >= 300))
                out["executable"].append(rec); print(f"z{k} q{q} {mode} hold{hold}: net {net:+,.0f} trades {ntr} +yrs {pos_years} maxshare {rec['max_year_share']} plc {rec['placebo_pct']:.2f} PASS={rec['passes']}", flush=True)
json.dump(out, open(ROOT / "reports/LEADLAG_1_TRAINING.json", "w"), indent=1); print("DONE", flush=True)
