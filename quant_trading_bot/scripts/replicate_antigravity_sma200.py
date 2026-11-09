"""Replicate Antigravity's 'Daily 200 SMA Gated Trend' (2026-11-08): MNQ 30m EWMA trend lb16 th0.75, stop 1.5 ATR, 4R, hold 8,
entries on 30m closes 10:00-12:00 ET, flat 15:55; direction gated by the prior session's RTH close vs its 200-session SMA
(above -> long only, below -> short only). Fixed engine, NQ 2010-18 + MNQ 2019-23 by year, then 2024-25 (seen by sender).
Placebo: 20 random long-only/short-only day masks with the same long share per year (direction gate placed at random)."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import mass_1m_search as m1
from quant_futures import ensemble_paper as ep
from quant_futures.session_calendar import apply_early_close
eng = ep.engine()
P = dict(family="trend", lookback=16, threshold=0.75, stop_atr=1.5, target_r=4.0, hold_bars=8, trailing_atr=0.0, instrument="MNQ", max_contracts=1, session_start=600, session_end=945)

def prep(bars):
    c = bars.close.astype(float); h, l = bars.high.astype(float), bars.low.astype(float); prev = c.shift(1)
    atr_s = pd.concat((h - l, (h - prev).abs(), (l - prev).abs()), axis=1).max(axis=1).rolling(14, min_periods=14).mean()
    trend = (c.ewm(span=8, adjust=False, min_periods=8).mean() - c.ewm(span=16, adjust=False, min_periods=16).mean()) / atr_s
    raw = np.where(trend >= P["threshold"], 1, np.where(trend <= -P["threshold"], -1, 0)).astype(np.int8)
    et = bars.timestamp_utc.dt.tz_convert("America/New_York"); sod = et.dt.hour * 60 + et.dt.minute
    day = et.dt.date
    rth = bars[(sod >= 570) & (sod < 960)]
    sess_close = rth.groupby(day[rth.index]).close.last()
    sma = sess_close.rolling(200, min_periods=200).mean()
    gate = np.sign(sess_close - sma).shift(1)          # known at the next session's open
    gate_by_day = day.map(gate).to_numpy(float)
    return raw, np.nan_to_num(atr_s.to_numpy()).astype(np.float32), gate_by_day, day.to_numpy()

def run(bars, sig, atr):
    data = apply_early_close(eng["arrays"](bars), bars)
    cfg = eng["execution_cfg"](P); cfg.update(entry_start=570, entry_end=690, flat_minute=955, max_gap_minutes=60)
    out = {}
    for y in sorted(set(data["year"])):
        idx = np.flatnonzero(data["year"] == y); a, b = int(idx[0]), int(idx[-1]) + 1
        d = {k: np.ascontiguousarray(v[a:b]) for k, v in data.items()}
        d["session"] = pd.factorize(d["session"], sort=False)[0].astype(np.int64); d["contract"] = pd.factorize(d["contract"], sort=False)[0].astype(np.int64)
        r = eng["execute"](d, np.ascontiguousarray(sig[a:b]), np.ascontiguousarray(atr[a:b]), cfg)
        peaks = np.maximum.accumulate(np.r_[50000.0, r["equity"]])[1:]
        out[int(y)] = dict(net=round(float(r["cash"][-1] - 50000.0), 2), dd=round(float(np.max(peaks - r["worst"])), 2), trades=int(len(r["trade_net"])))
    return out

def gated(raw, gate):
    return np.where(np.isnan(gate), 0, np.where(gate > 0, np.maximum(raw, 0), np.minimum(raw, 0))).astype(np.int8)

res = {}; rng = np.random.default_rng(11)
for split, lo, hi in (("train", "2009-01-01", "2024-01-01"), ("validation", "2023-01-01", "2026-01-01")):
    b = m1.load_bars("MNQ", 30, lo, hi, split).reset_index(drop=True)
    assert b.timestamp_utc.max() < pd.Timestamp("2026-01-01", tz="UTC")
    raw, atr, gate, day = prep(b)
    first_year = 2010 if split == "train" else 2024
    keep = lambda d: {y: v for y, v in d.items() if y >= first_year}
    res[split] = dict(ungated=keep(run(b, raw, atr)), gated=keep(run(b, gated(raw, gate), atr)))
    print(split, "ungated", {y: v["net"] for y, v in res[split]["ungated"].items()}); print(split, "gated  ", {y: (v["net"], v["trades"]) for y, v in res[split]["gated"].items()}, flush=True)
    if split == "train":
        days = pd.Series(gate, index=day).dropna(); dd = days.groupby(level=0).first(); years = pd.to_datetime(pd.Series(dd.index)).dt.year.values
        plc = []
        for r in range(20):
            rg = np.array(dd.values, dtype=float, copy=True)
            for y in np.unique(years):
                m = years == y; rg[m] = rng.permutation(rg[m])   # same long share per year, random placement
            gmap = pd.Series(rg, index=dd.index); pg = pd.Series(day).map(gmap).to_numpy(float)
            o = keep(run(b, gated(raw, pg), atr)); plc.append(dict(total=round(sum(v["net"] for v in o.values()), 2), pre2020=round(sum(v["net"] for y, v in o.items() if y < 2020), 2), pos_years=sum(v["net"] > 0 for v in o.values())))
            print("placebo", r, plc[-1], flush=True)
        res["placebo"] = plc
g = res["train"]["gated"]; tot = sum(v["net"] for v in g.values()); pre = sum(v["net"] for y, v in g.items() if y < 2020)
res["summary"] = dict(gated_train_total=round(tot, 2), gated_pre2020=round(pre, 2), gated_pos_years=sum(v["net"] > 0 for v in g.values()),
                      placebo_total_mean=round(float(np.mean([p["total"] for p in res["placebo"]])), 2), placebo_pre2020_mean=round(float(np.mean([p["pre2020"] for p in res["placebo"]])), 2),
                      beat_placebo_total=int(sum(tot > p["total"] for p in res["placebo"])), beat_placebo_pre2020=int(sum(pre > p["pre2020"] for p in res["placebo"])))
print("SUMMARY", res["summary"])
(ROOT / "reports" / "ANTIGRAVITY_SMA200_REPLICATION.json").write_text(json.dumps(res, indent=1)); print("DONE")
