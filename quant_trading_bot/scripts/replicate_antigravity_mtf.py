"""Replicate Antigravity's 60m macro-trend and 5m MTF breakout rules (research/antigravity/mtf_rules_2026-11-08.json) on the
fixed engine, by year, 2010-2023 training (NQ 2010-18 strict-bar micro costs, MNQ 2019-23) and 2024-25 (already seen by sender).
60m trend is joined to 5m bars by backward as-of on bar CLOSE time (zero lookahead)."""
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
    tr = np.maximum(h - l, np.maximum(abs(h - prev), abs(l - prev)))
    return pd.Series(tr).rolling(14, min_periods=14).mean().to_numpy()

def trend60(b60):
    c = b60.close
    return ((c.ewm(span=6, adjust=False).mean() - c.ewm(span=12, adjust=False).mean()) / atr14(b60)).to_numpy()

def run(bars, sig, atr, p, entry_start, entry_end, gap_min=20):
    data = apply_early_close(eng["arrays"](bars), bars)
    cfg = eng["execution_cfg"](dict(p, instrument="MNQ", max_contracts=1, session_start=600, session_end=945))
    cfg.update(entry_start=entry_start, entry_end=entry_end, flat_minute=955, max_gap_minutes=gap_min)
    out, daily = {}, []
    for y in sorted(set(data["year"])):
        idx = np.flatnonzero(data["year"] == y); a, b = int(idx[0]), int(idx[-1]) + 1
        d = {k: np.ascontiguousarray(v[a:b]) for k, v in data.items()}
        sess = d["session"].copy()
        d["session"] = pd.factorize(d["session"], sort=False)[0].astype(np.int64); d["contract"] = pd.factorize(d["contract"], sort=False)[0].astype(np.int64)
        r = eng["execute"](d, np.ascontiguousarray(sig[a:b]), np.ascontiguousarray(np.nan_to_num(atr[a:b]).astype(np.float32)), cfg)
        peaks = np.maximum.accumulate(np.r_[50000.0, r["equity"]])[1:]
        out[int(y)] = dict(net=round(float(r["cash"][-1] - 50000.0), 2), dd=round(float(np.max(peaks - r["worst"])), 2), trades=int(len(r["trade_net"])), breach=bool(r["funded_failed"]))
        eod = pd.Series(r["equity"]).groupby(pd.Series(sess)).last()
        daily.append(eod.diff().fillna(eod.iloc[0] - 50000.0))
    return out, pd.concat(daily)

def build(split, lo, hi):
    b5 = m1.load_bars("MNQ", 5, lo, hi, split).reset_index(drop=True)
    b60 = m1.load_bars("MNQ", 60, lo, hi, split).reset_index(drop=True)
    b60["close_time"] = b60.timestamp_utc + pd.Timedelta(minutes=60); b60["trend60"] = trend60(b60)
    b5["close_time"] = b5.timestamp_utc + pd.Timedelta(minutes=5)
    b5 = pd.merge_asof(b5, b60[["close_time", "trend60"]].sort_values("close_time"), on="close_time", direction="backward")
    a5 = atr14(b5); h, l, c = b5.high.to_numpy(float), b5.low.to_numpy(float), b5.close.to_numpy(float)
    bh = pd.Series(h).rolling(24).max().shift(1).to_numpy(); bl = pd.Series(l).rolling(24).min().shift(1).to_numpy()
    t60 = b5.trend60.to_numpy()
    sig5 = np.where((c > bh + 0.75 * a5) & (t60 > 0), 1, np.where((c < bl - 0.75 * a5) & (t60 < 0), -1, 0)).astype(np.int8)
    a60 = atr14(b60); tr = b60.trend60.to_numpy()
    sig60 = np.where(tr >= 0.75, 1, np.where(tr <= -0.75, -1, 0)).astype(np.int8)
    return b5, sig5, a5, b60, sig60, a60

res = {}
for split, lo, hi in (("train", "2009-12-01", "2024-01-01"), ("validation", "2023-12-01", "2026-01-01")):
    b5, sig5, a5, b60, sig60, a60 = build(split, lo, hi)
    assert b5.timestamp_utc.max() < pd.Timestamp("2026-01-01", tz="UTC")
    # 5m: signal bar closes within 09:45-11:45 ET -> bar open minute 580..700; 60m: entries 10:00-12:00 closes -> open 540..660
    r5, d5 = run(b5, sig5, a5, dict(family="breakout", lookback=24, threshold=0.75, stop_atr=1.5, target_r=5.0, hold_bars=24, trailing_atr=0.0), 580, 700)
    r60, d60 = run(b60, sig60, a60, dict(family="trend", lookback=12, threshold=0.75, stop_atr=1.25, target_r=4.0, hold_bars=8, trailing_atr=0.0), 540, 660, gap_min=90)
    duo = d5.add(d60, fill_value=0.0); eq = duo.cumsum(); dd = float((eq.cummax() - eq).max())
    res[split] = dict(MNQ_5m_MTF=r5, MNQ_60m_Trend=r60, duo_net=round(float(duo.sum()), 2), duo_eod_dd=round(dd, 2), corr_daily=round(float(d5.corr(d60)), 3))
    for k in ("MNQ_5m_MTF", "MNQ_60m_Trend"):
        print(split, k, {y: (v["net"], v["trades"]) for y, v in res[split][k].items()}, flush=True)
    print(split, "duo", res[split]["duo_net"], "dd", res[split]["duo_eod_dd"], "corr", res[split]["corr_daily"], flush=True)
(ROOT / "reports" / "ANTIGRAVITY_MTF_REPLICATION.json").write_text(json.dumps(res, indent=1))
