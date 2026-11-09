"""Replicate Antigravity's AG_NQ_Leader (2026-11-08): at the 10:00 ET close, spread = NQ 09:30->10:00 return minus ES 09:30->10:00 return,
z = spread / std(spread over the prior 20 sessions); z >= 1.25 -> long 1 MNQ at 10:00 (fill next 15m bar open), stop 2.0 ATR14(15m),
target 4R, hold 12 x 15m bars, flat 15:55. Fixed engine: NQ/ES 2010-18 + MNQ/MES 2019-23 by year; placebo = 20 random same-count-per-year
day sets, long at 10:00 with identical exits. Short side (z <= -1.25) reported for information. Validation 2024-25 run only if the
training gates pass (frozen rule, one shot); 2026 never loaded."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import mass_1m_search as m1
from quant_futures import ensemble_paper as ep
from quant_futures.session_calendar import apply_early_close
eng = ep.engine()
P = dict(family="trend", lookback=8, threshold=0.0, stop_atr=2.0, target_r=4.0, hold_bars=12, trailing_atr=0.0, instrument="MNQ", max_contracts=1, session_start=600, session_end=945)
Z = 1.25

def prep(nq, es):
    def open_ret(b):
        et = b.timestamp_utc.dt.tz_convert("America/New_York"); sod = et.dt.hour * 60 + et.dt.minute; day = et.dt.date
        o = b.open[sod == 570].groupby(day[sod == 570]).first(); c = b.close[sod == 585].groupby(day[sod == 585]).last()
        return (c / o - 1).dropna()
    spread = (open_ret(nq) - open_ret(es)).dropna()
    z = spread / spread.rolling(20, min_periods=20).std().shift(1)
    return z

def run(bars, sig, atr, lo_year):
    data = apply_early_close(eng["arrays"](bars), bars)
    cfg = eng["execution_cfg"](P); cfg.update(entry_start=585, entry_end=585, flat_minute=955, max_gap_minutes=20)
    out = {}
    for y in sorted(set(data["year"])):
        if y < lo_year: continue
        idx = np.flatnonzero(data["year"] == y); a, b = int(idx[0]), int(idx[-1]) + 1
        d = {k: np.ascontiguousarray(v[a:b]) for k, v in data.items()}
        d["session"] = pd.factorize(d["session"], sort=False)[0].astype(np.int64); d["contract"] = pd.factorize(d["contract"], sort=False)[0].astype(np.int64)
        r = eng["execute"](d, np.ascontiguousarray(sig[a:b]), np.ascontiguousarray(atr[a:b]), cfg)
        peaks = np.maximum.accumulate(np.r_[50000.0, r["equity"]])[1:]
        out[int(y)] = dict(net=round(float(r["cash"][-1] - 50000.0), 2), dd=round(float(np.max(peaks - r["worst"])), 2), trades=int(len(r["trade_net"])))
    return out

def total(o): return round(sum(v["net"] for v in o.values()), 2)
def pos(o): return int(sum(v["net"] > 0 for v in o.values()))

def evaluate(split, lo, hi, lo_year, n_placebo):
    nq = m1.load_bars("MNQ", 15, lo, hi, split).reset_index(drop=True); es = m1.load_bars("MES", 15, lo, hi, split).reset_index(drop=True)
    assert nq.timestamp_utc.max() < pd.Timestamp("2026-01-01", tz="UTC")
    z = prep(nq, es)
    et = nq.timestamp_utc.dt.tz_convert("America/New_York"); sod = (et.dt.hour * 60 + et.dt.minute).to_numpy(); day = et.dt.date
    zb = day.map(z).to_numpy(float)
    c, h, l = nq.close.astype(float), nq.high.astype(float), nq.low.astype(float); prev = c.shift(1)
    atr = np.nan_to_num(pd.concat((h - l, (h - prev).abs(), (l - prev).abs()), axis=1).max(axis=1).rolling(14, min_periods=14).mean().to_numpy()).astype(np.float32)
    at = sod == 585
    sig_long = np.where(at & (zb >= Z), 1, 0).astype(np.int8); sig_short = np.where(at & (zb <= -Z), -1, 0).astype(np.int8)
    res = dict(long=run(nq, sig_long, atr, lo_year), short=run(nq, sig_short, atr, lo_year))
    print(split, "long ", {y: (v["net"], v["trades"]) for y, v in res["long"].items()}, "total", total(res["long"]), "pos", pos(res["long"]), flush=True)
    print(split, "short", {y: v["net"] for y, v in res["short"].items()}, "total", total(res["short"]), flush=True)
    if n_placebo:
        rng = np.random.default_rng(5); days = pd.Series(sorted(set(day[at]))); yrs = pd.to_datetime(days).dt.year.values
        on = pd.Series(zb[at], index=day[at].values); on = on[on >= Z]; on_years = pd.to_datetime(pd.Series(on.index)).dt.year.values
        plc = []
        for r in range(n_placebo):
            pick = []
            for y in np.unique(yrs):
                n = int((on_years == y).sum()); cand = days[yrs == y].to_numpy()
                pick += list(rng.choice(cand, size=min(n, len(cand)), replace=False))
            m = at & np.isin(day.to_numpy(), pick); o = run(nq, np.where(m, 1, 0).astype(np.int8), atr, lo_year)
            plc.append(dict(total=total(o), pre2020=round(sum(v["net"] for y, v in o.items() if y < 2020), 2), pos_years=pos(o))); print("placebo", r, plc[-1], flush=True)
        res["placebo"] = plc
        t = total(res["long"]); res["summary"] = dict(total=t, pre2020=round(sum(v["net"] for y, v in res["long"].items() if y < 2020), 2), pos_years=pos(res["long"]), trades=sum(v["trades"] for v in res["long"].values()),
                                                   max_year_share=round(max(v["net"] for v in res["long"].values()) / t, 3) if t > 0 else None,
                                                   placebo_mean=round(float(np.mean([p["total"] for p in plc])), 2), placebo_sd=round(float(np.std([p["total"] for p in plc])), 2),
                                                   beat=int(sum(t > p["total"] for p in plc)), n_placebo=n_placebo)
        s = res["summary"]; s["pass"] = bool(t > 0 and s["pos_years"] >= 10 and s["trades"] >= 100 and s["beat"] >= 0.95 * n_placebo and (s["max_year_share"] or 1) <= 0.4)
        print("SUMMARY", s, flush=True)
    return res

out = dict(train=evaluate("train", "2009-11-01", "2024-01-01", 2010, 20))
(ROOT / "reports" / "ANTIGRAVITY_NQLEADER_REPLICATION.json").write_text(json.dumps(out, indent=1))
if out["train"]["summary"]["pass"]:
    print("TRAINING GATES PASSED -> frozen one-shot validation 2024-25", flush=True)
    out["validation"] = evaluate("validation", "2023-11-01", "2026-01-01", 2024, 0)
    (ROOT / "reports" / "ANTIGRAVITY_NQLEADER_REPLICATION.json").write_text(json.dumps(out, indent=1))
print("DONE")
