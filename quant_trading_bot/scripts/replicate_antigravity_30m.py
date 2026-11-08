"""Replicate Antigravity's MNQ_30m_Impulse_Breakout (lb 8 bars, 1.5 ATR14 above Donchian high shifted 1, stop 1.25 ATR, 5R, hold 8,
entries on 30m closes 10:00-12:00 ET, gap 60) on the fixed engine: NQ 2010-18 strict micro costs + MNQ 2019-23, then 2024-25 (seen by sender)."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import mass_1m_search as m1
from quant_futures import ensemble_paper as ep
from quant_futures.session_calendar import apply_early_close
eng = ep.engine()

def atr14(b):
    c, h, l = b.close.to_numpy(float), b.high.to_numpy(float), b.low.to_numpy(float)
    prev = np.r_[c[0], c[:-1]]
    return pd.Series(np.maximum(h - l, np.maximum(abs(h - prev), abs(l - prev)))).rolling(14, min_periods=14).mean().to_numpy()

def run(bars, sig, atr, p, entry_start, entry_end, gap_min):
    data = apply_early_close(eng["arrays"](bars), bars)
    cfg = eng["execution_cfg"](dict(p, instrument="MNQ", max_contracts=1, session_start=600, session_end=945))
    cfg.update(entry_start=entry_start, entry_end=entry_end, flat_minute=955, max_gap_minutes=gap_min)
    out = {}
    for y in sorted(set(data["year"])):
        idx = np.flatnonzero(data["year"] == y); a, b = int(idx[0]), int(idx[-1]) + 1
        d = {k: np.ascontiguousarray(v[a:b]) for k, v in data.items()}
        d["session"] = pd.factorize(d["session"], sort=False)[0].astype(np.int64); d["contract"] = pd.factorize(d["contract"], sort=False)[0].astype(np.int64)
        r = eng["execute"](d, np.ascontiguousarray(sig[a:b]), np.ascontiguousarray(np.nan_to_num(atr[a:b]).astype(np.float32)), cfg)
        peaks = np.maximum.accumulate(np.r_[50000.0, r["equity"]])[1:]
        out[int(y)] = dict(net=round(float(r["cash"][-1] - 50000.0), 2), dd=round(float(np.max(peaks - r["worst"])), 2), trades=int(len(r["trade_net"])), breach=bool(r["funded_failed"]))
    return out

res = {}
for split, lo, hi in (("train", "2009-12-01", "2024-01-01"), ("validation", "2023-12-01", "2026-01-01")):
    b = m1.load_bars("MNQ", 30, lo, hi, split).reset_index(drop=True)
    assert b.timestamp_utc.max() < pd.Timestamp("2026-01-01", tz="UTC")
    a = atr14(b); h, l, c = b.high.to_numpy(float), b.low.to_numpy(float), b.close.to_numpy(float)
    bh = pd.Series(h).rolling(8).max().shift(1).to_numpy(); bl = pd.Series(l).rolling(8).min().shift(1).to_numpy()
    sig = np.where(c > bh + 1.5 * a, 1, np.where(c < bl - 1.5 * a, -1, 0)).astype(np.int8)
    res[split] = run(b, sig, a, dict(family="breakout", lookback=8, threshold=1.5, stop_atr=1.25, target_r=5.0, hold_bars=8, trailing_atr=0.0), 570, 690, 60)
    print(split, {y: (v["net"], v["trades"], v["dd"]) for y, v in res[split].items()}, flush=True)
(ROOT / "reports" / "ANTIGRAVITY_30M_REPLICATION.json").write_text(json.dumps(res, indent=1))
