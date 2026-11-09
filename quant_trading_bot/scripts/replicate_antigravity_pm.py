"""Replicate Antigravity's MNQ 30m Afternoon Trend (family trend, lb 8, th 0.50, stop 1.5 ATR, 4R, hold 4, entries on 30m closes
13:30-15:00 ET, flat 15:55) on the fixed engine: NQ 2010-18 strict micro costs + MNQ 2019-23 by year, then 2024-25 (already seen by sender).
Trend = (EMA(lb/2) - EMA(lb)) / ATR14 computed by hand (engine features() NaN on 30m bars); same formula as mass_features trend family."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import mass_1m_search as m1
from quant_futures import ensemble_paper as ep
from quant_futures.session_calendar import apply_early_close
eng = ep.engine()
P = dict(family="trend", lookback=8, threshold=0.5, stop_atr=1.5, target_r=4.0, hold_bars=4, trailing_atr=0.0, instrument="MNQ", max_contracts=1, session_start=600, session_end=945)

def run(bars, entry_start, entry_end, gap_min):
    data = apply_early_close(eng["arrays"](bars), bars)
    # engine features() segments on >20-min gaps, so on 30m bars everything is NaN; compute the same formulas by hand
    c = bars.close.astype(float); h, l = bars.high.astype(float), bars.low.astype(float); prev = c.shift(1)
    atr_s = pd.concat((h - l, (h - prev).abs(), (l - prev).abs()), axis=1).max(axis=1).rolling(14, min_periods=14).mean()
    trend = (c.ewm(span=max(2, P["lookback"] // 2), adjust=False, min_periods=4).mean() - c.ewm(span=P["lookback"], adjust=False, min_periods=8).mean()) / atr_s
    sig = np.where(trend >= P["threshold"], 1, np.where(trend <= -P["threshold"], -1, 0)).astype(np.int8); atr = np.nan_to_num(atr_s.to_numpy()).astype(np.float32)
    cfg = eng["execution_cfg"](P); cfg.update(entry_start=entry_start, entry_end=entry_end, flat_minute=955, max_gap_minutes=gap_min)
    out = {}
    for y in sorted(set(data["year"])):
        idx = np.flatnonzero(data["year"] == y); a, b = int(idx[0]), int(idx[-1]) + 1
        d = {k: np.ascontiguousarray(v[a:b]) for k, v in data.items()}
        d["session"] = pd.factorize(d["session"], sort=False)[0].astype(np.int64); d["contract"] = pd.factorize(d["contract"], sort=False)[0].astype(np.int64)
        r = eng["execute"](d, np.ascontiguousarray(sig[a:b]), np.ascontiguousarray(atr[a:b]), cfg)
        peaks = np.maximum.accumulate(np.r_[50000.0, r["equity"]])[1:]
        out[int(y)] = dict(net=round(float(r["cash"][-1] - 50000.0), 2), dd=round(float(np.max(peaks - r["worst"])), 2), trades=int(len(r["trade_net"])), breach=bool(r["funded_failed"]))
    return out

res = {}
for split, lo, hi in (("train", "2009-12-01", "2024-01-01"), ("validation", "2023-12-01", "2026-01-01")):
    b = m1.load_bars("MNQ", 30, lo, hi, split).reset_index(drop=True)
    assert b.timestamp_utc.max() < pd.Timestamp("2026-01-01", tz="UTC")
    res[split] = run(b, 780, 870, 60)
    print(split, {y: (v["net"], v["trades"], v["dd"]) for y, v in res[split].items()}, flush=True)
tr = res["train"]; print("train total", round(sum(v["net"] for v in tr.values())), "2010-19", round(sum(v["net"] for y, v in tr.items() if y < 2020)), "2020-23", round(sum(v["net"] for y, v in tr.items() if y >= 2020)), "pos yrs", sum(v["net"] > 0 for v in tr.values()), "/", len(tr))
(ROOT / "reports" / "ANTIGRAVITY_PM_REPLICATION.json").write_text(json.dumps(res, indent=1))
print("DONE")
