"""Replicate Antigravity's AG_Crabel_OpenDrive and AG_VIX_Velocity_Crush (specs 2026-11-08) on the fixed engine, 15m MNQ bars,
NQ 2010-18 + MNQ 2019-23 by year, micro costs. Both are best-of-324 grids on 2010-23 (sender), so the training result is in-sample.
Placebo: 20 random day sets with the same number of long and short signals per year, entry at 10:00 with identical exits."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import mass_1m_search as m1
from quant_futures import ensemble_paper as ep
from quant_futures.session_calendar import apply_early_close
eng = ep.engine()

def cboe(name):
    d = pd.read_csv(ROOT / f"data/external/{name}_History.csv"); d["date"] = pd.to_datetime(d.DATE, format="%m/%d/%Y").dt.date; return d.set_index("date").CLOSE.astype(float)

def run(bars, sig, atr, p):
    data = apply_early_close(eng["arrays"](bars), bars)
    cfg = eng["execution_cfg"](dict(p, instrument="MNQ", max_contracts=1, session_start=600, session_end=945, family="trend", lookback=8, threshold=0.0, trailing_atr=0.0))
    cfg.update(entry_start=585, entry_end=585, flat_minute=955, max_gap_minutes=20)
    out = {}
    for y in sorted(set(data["year"])):
        if y < 2010: continue
        idx = np.flatnonzero(data["year"] == y); a, b = int(idx[0]), int(idx[-1]) + 1
        d = {k: np.ascontiguousarray(v[a:b]) for k, v in data.items()}
        d["session"] = pd.factorize(d["session"], sort=False)[0].astype(np.int64); d["contract"] = pd.factorize(d["contract"], sort=False)[0].astype(np.int64)
        r = eng["execute"](d, np.ascontiguousarray(sig[a:b]), np.ascontiguousarray(atr[a:b]), cfg)
        peaks = np.maximum.accumulate(np.r_[50000.0, r["equity"]])[1:]
        out[int(y)] = dict(net=round(float(r["cash"][-1] - 50000.0), 2), dd=round(float(np.max(peaks - r["worst"])), 2), trades=int(len(r["trade_net"])))
    return out
def total(o): return round(sum(v["net"] for v in o.values()), 2)

b = m1.load_bars("MNQ", 15, "2009-11-01", "2024-01-01", "train").reset_index(drop=True)
assert b.timestamp_utc.max() < pd.Timestamp("2024-01-02", tz="UTC")
et = b.timestamp_utc.dt.tz_convert("America/New_York"); sod = (et.dt.hour * 60 + et.dt.minute).to_numpy(); day = et.dt.date
c, h, l, o = (b[k].astype(float) for k in ("close", "high", "low", "open")); prev = c.shift(1)
atr_s = pd.concat((h - l, (h - prev).abs(), (l - prev).abs()), axis=1).max(axis=1).rolling(14, min_periods=14).mean(); ATR = np.nan_to_num(atr_s.to_numpy()).astype(np.float32)
at = sod == 585
# opening-range quantities per day: open of the 09:30 bar, high/low across 09:30 and 09:45 bars, close of the 09:45 bar (= "10:00 close")
g = pd.DataFrame(dict(day=day, sod=sod, o=o, h=h, l=l, c=c, atr=atr_s))
first = g[g.sod == 570].groupby("day").o.first(); rng_hi = g[(g.sod == 570) | (g.sod == 585)].groupby("day").h.max(); rng_lo = g[(g.sod == 570) | (g.sod == 585)].groupby("day").l.min()
c1000 = g[g.sod == 585].groupby("day").c.last(); atr_d = g[g.sod == 585].groupby("day").atr.last()
D = pd.DataFrame(dict(o=first, hi=rng_hi, lo=rng_lo, c=c1000, atr=atr_d)).dropna(); D["rng"] = D.hi - D.lo
bull = ((D.o - D.lo) / D.rng <= 0.20) & ((D.c - D.lo) / D.rng >= 0.85) & (D.rng >= 1.0 * D.atr)
bear = ((D.hi - D.o) / D.rng <= 0.20) & ((D.hi - D.c) / D.rng <= 0.15) & (D.rng >= 1.0 * D.atr)
crabel_dir = pd.Series(np.where(bull, 1, np.where(bear, -1, 0)), index=D.index)
vix, vix3m = cboe("VIX"), cboe("VIX3M"); ratio = (vix / vix3m).dropna(); d1 = ratio.diff(); crush_prev = (d1.shift(1) <= -0.015)   # ratio(t-1)-ratio(t-2), known before the open of day t
crush_by_day = pd.Series(crush_prev.values, index=crush_prev.index)
morn = (D.c / D.o - 1) >= 0.001
vix_dir = pd.Series(np.where(morn & pd.Series(D.index, index=D.index).map(crush_by_day).fillna(False).astype(bool), 1, 0), index=D.index)

RULES = dict(crabel=dict(dir=crabel_dir, p=dict(stop_atr=1.5, target_r=4.0, hold_bars=20), claim="+6,713 / 517 trades / 10 of 14 / pre-2020 +571 / DD 1,148"),
             vix_crush=dict(dir=vix_dir, p=dict(stop_atr=1.5, target_r=5.0, hold_bars=24), claim="+4,180 / 409 trades / 10 of 14 / pre-2020 +1,176 / DD 2,196"))
rng = np.random.default_rng(9); out = {}
days_all = pd.Series(sorted(set(day[at]))); yrs_all = pd.to_datetime(days_all).dt.year.values
for name, R in RULES.items():
    dirs = R["dir"]; sig = np.where(at, day.map(dirs).fillna(0).to_numpy(), 0).astype(np.int8)
    res = run(b, sig, ATR, R["p"]); t = total(res)
    yrs = pd.to_datetime(pd.Series(dirs.index)).dt.year.values; dv = dirs.values
    plc = []
    for r_ in range(20):
        s = pd.Series(0, index=days_all.values, dtype=int)
        for y in np.unique(yrs_all):
            nl, ns = int(((dv == 1) & (yrs == y)).sum()), int(((dv == -1) & (yrs == y)).sum()); cand = days_all[yrs_all == y].to_numpy()
            pick = rng.choice(cand, size=min(nl + ns, len(cand)), replace=False); s[pick[:nl]] = 1; s[pick[nl:]] = -1
        ps = np.where(at, day.map(s).fillna(0).to_numpy(), 0).astype(np.int8); plc.append(total(run(b, ps, ATR, R["p"])))
    summ = dict(total=t, pre2020=round(sum(v["net"] for y, v in res.items() if y < 2020), 2), pos_years=int(sum(v["net"] > 0 for v in res.values())), trades=int(sum(v["trades"] for v in res.values())),
                max_dd_year=max(v["dd"] for v in res.values()), placebo_mean=round(float(np.mean(plc)), 2), placebo_sd=round(float(np.std(plc)), 2), beat=int(sum(t > p for p in plc)), sender_claim=R["claim"])
    out[name] = dict(by_year=res, summary=summ)
    print(name, {y: (v["net"], v["trades"]) for y, v in res.items()}); print(name, "SUMMARY", summ, flush=True)
(ROOT / "reports" / "ANTIGRAVITY_CRABEL_VIX_REPLICATION.json").write_text(json.dumps(out, indent=1)); print("DONE")
