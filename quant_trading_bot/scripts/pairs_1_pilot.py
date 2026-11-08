"""pairs_1: intraday NQ/ES beta-hedged relative-value mean reversion on 15m bars, training 2010-2023 (research/pairs_1/PROTOCOL.md)."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from numba import njit
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts"))
import mass_1m_search as m1
COMM, SLIP = 0.61, 1.0
RT_NQ = (1.75 + 2 * SLIP) * 0.5 + 2 * COMM      # $ per MNQ round trip
RT_ES = (1.0 + 2 * SLIP) * 1.25 + 2 * COMM      # $ per MES round trip

def load(prod):
    b = m1.load_bars(prod, 15, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "close"]].copy()
    et = b.timestamp_utc.dt.tz_convert("America/New_York"); b["sod"] = et.dt.hour * 60 + et.dt.minute; b["date"] = et.dt.date; b["year"] = et.dt.year
    return b[(b.sod >= 570) & (b.sod < 960)]
nq, es = load("MNQ"), load("MES")
d = nq.merge(es[["timestamp_utc", "close"]].rename(columns={"close": "es"}), on="timestamp_utc").rename(columns={"close": "nq"}).reset_index(drop=True)
d["a"], d["b"] = np.log(d.nq), np.log(d.es)
# daily beta from prior 20 sessions of 15m log-returns (within-day returns only)
d["ra"] = d.groupby("date").a.diff(); d["rb"] = d.groupby("date").b.diff()
day = d.groupby("date").agg(sxy=("ra", lambda x: np.nansum(x * d.loc[x.index, "rb"])), sxx=("rb", lambda x: np.nansum(x * x)), nq0=("nq", "last"), es0=("es", "last"))
beta = (day.sxy.rolling(20).sum() / day.sxx.rolling(20).sum()).shift(1)
nmes = np.clip(np.round(beta * 2 * day.nq0.shift(1) / (5 * day.es0.shift(1))), 1, 3)
d["beta"] = d.date.map(beta); d["n"] = d.date.map(nmes)
res = {"N": {}}
# rolling moments (lagged one bar) for residual z with today's beta
for N in (26, 52, 130):
    r = d[["a", "b"]].copy(); r["aa"], r["bb"], r["ab"] = r.a ** 2, r.b ** 2, r.a * r.b
    m = r.rolling(N).mean().shift(1)
    mean_r = m.a - d.beta * m.b
    var_r = (m.aa - m.a ** 2) + d.beta ** 2 * (m.bb - m.b ** 2) - 2 * d.beta * (m.ab - m.a * m.b)
    d[f"z{N}"] = ((d.a - d.beta * d.b) - mean_r) / np.sqrt(var_r.clip(lower=1e-12))
d = d[d.beta.notna()].reset_index(drop=True)
nqp, esp, n_, sod, year = d.nq.values, d.es.values, d.n.values, d.sod.values, d.year.values
dates = pd.factorize(d.date)[0]
# predictive test: hedged $ change over next h bars, signed for 'short rich'
pred = {}
for N in (26, 52, 130):
    z = d[f"z{N}"].values; pred[N] = {}
    for h in (4, 8, 16):
        same = np.roll(dates, -h) == dates
        dnq, des = np.roll(nqp, -h) - nqp, np.roll(esp, -h) - esp
        pl = -np.sign(z) * (2 * dnq - n_ * 5 * des)   # $ for 1 MNQ vs n MES, fading z
        ok = same & np.isfinite(z) & (sod >= 585) & (sod <= 900)
        dec = pd.qcut(np.abs(z[ok]), 10, labels=False, duplicates="drop")
        g = pd.Series(pl[ok]).groupby(dec); top = pl[ok][dec == dec.max()]
        pred[N][h] = dict(by_decile=[round(float(v), 2) for v in g.mean()], top_mean=round(float(top.mean()), 2), top_t=round(float(top.mean() / top.std() * np.sqrt(len(top))), 2), n_top=int(len(top)))
res["predictive"] = {str(k): {str(h): v for h, v in d_.items()} for k, d_ in pred.items()}
print("PRED", json.dumps(res["predictive"])[:1500], flush=True)

@njit(cache=False)
def sim(z, nqp, esp, n_, sod, dates, year, k, H, e0, e1, direction):
    # direction: 0 => fade z (short rich), else array of random +-1 used only when z-entry would fire is handled outside via mask
    nb = len(z); pnl = np.zeros(nb); pos = 0; i_e = 0; dnq = 0.0
    for i in range(nb):
        if pos != 0:
            exit_ = (np.sign(z[i]) != np.sign(z[i_e])) or (abs(z[i]) >= k + 1.5) or (i - i_e >= H) or (sod[i] >= 930) or (dates[i] != dates[i_e])
            if exit_:
                pnl[i] = dnq * (nqp[i] - nqp[i_e]) * 2 - dnq * n_[i_e] * 5 * (esp[i] - esp[i_e]) - RT_NQ - n_[i_e] * RT_ES
                pos = 0
        if pos == 0 and sod[i] >= e0 and sod[i] <= e1 and np.isfinite(z[i]) and abs(z[i]) >= k:
            pos = 1; i_e = i; dnq = -np.sign(z[i]) * direction[i]
    return pnl

def summarize(pnl):
    y = pd.Series(pnl).groupby(year).sum(); return float(pnl.sum()), y, int((pnl != 0).sum())
def gate(net, yearly, trades, pl, min_trades=100):
    yearly = {int(k): float(v) for k, v in dict(yearly).items()}; pos = sum(v > 0 for v in yearly.values()); share = max(yearly.values()) / net if net > 0 else None
    return dict(net=round(net, 2), trades=int(trades), pos_years=int(pos), max_year_share=round(share, 2) if share else None, placebo_pct=float(np.mean(np.array(pl) < net)) if len(pl) else None,
                placebo_mean=round(float(np.mean(pl)), 2) if len(pl) else None, yearly={k: round(v, 2) for k, v in yearly.items()},
                passes=bool(net > 0 and pos >= 10 and (share or 1) <= 0.4 and (len(pl) == 0 or np.mean(np.array(pl) < net) >= 0.95) and trades >= min_trades))
rng = np.random.default_rng(20261108); ones = np.ones(len(d)); res["grid"] = []
for N in (26, 52, 130):
    z = d[f"z{N}"].values.astype(float)
    for k in (1.5, 2.0, 2.5):
        for H in (8, 16):
            for (e0, e1) in ((585, 900), (585, 690)):
                pnl = sim(z, nqp, esp, n_, sod, dates, year, k, H, e0, e1, ones); net, yr, tr = summarize(pnl)
                # placebo: random eligible bars with the same per-year entry count, random direction, same exit rules on the real z path
                elig = (sod >= e0) & (sod <= e1) & np.isfinite(z); pl = []
                for _ in range(20):
                    zp = np.full(len(z), np.nan); zp_dir = np.ones(len(z))
                    for yv in np.unique(year):
                        m = elig & (year == yv); cnt = int(((pnl != 0) & (year == yv)).sum())
                        idx = rng.choice(np.flatnonzero(m), size=min(cnt, int(m.sum())), replace=False); zp[idx] = k * np.sign(z[idx]) ; zp_dir[idx] = rng.choice([-1.0, 1.0], size=len(idx))
                    # entries at random bars (|zp|>=k), exits on the real z path: build hybrid series = real z but forced-entry bars flagged via direction array
                    zz = z.copy(); fire = np.isfinite(zp); zz[~fire & (np.abs(zz) >= k)] = np.sign(zz[~fire & (np.abs(zz) >= k)]) * (k - 1e-6); zz[fire] = np.sign(z[fire]) * max(k, 1e-6) if False else zz[fire]
                    zz[fire] = np.where(np.abs(z[fire]) >= k, z[fire], np.sign(np.where(z[fire] == 0, 1, z[fire])) * k)
                    pl.append(float(sim(zz, nqp, esp, n_, sod, dates, year, k, H, e0, e1, zp_dir).sum()))
                g = gate(net, yr, tr, pl); g.update(N=N, k=k, H=H, window=[e0, e1]); res["grid"].append(g)
                print("G", N, k, H, e0, g["net"], g["trades"], g["pos_years"], g["placebo_pct"], g["placebo_mean"], g["passes"], flush=True)
json.dump(res, open(ROOT / "reports/PAIRS_1_TRAINING.json", "w"), indent=1, default=float); print("DONE")
