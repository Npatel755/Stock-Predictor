"""Replicate Antigravity's four 1-contract 15-min rules (2026-11-08) on the fixed engine: ES/NQ 2010-23 strict bars at micro
costs (training), MES/MNQ 2024-25 validation once, and the Duo / Tri portfolios as one continuous account (end-of-day DD)."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd, duckdb
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import unseen_years_replication as uy
from quant_futures import ensemble_paper as ep
from quant_futures.data import canonical
from quant_futures.session_calendar import apply_early_close

RULES = {
 "MNQ_Trend_1c": dict(instrument="MNQ", family="trend", lookback=6, threshold=1.0, stop_atr=1.75, target_r=2.25, hold_bars=6, session_start=585, session_end=945, max_contracts=1, trailing_atr=0.0),
 "MES_Mom_1c": dict(instrument="MES", family="momentum", lookback=6, threshold=2.0, stop_atr=1.5, target_r=2.25, hold_bars=20, session_start=585, session_end=945, max_contracts=1, trailing_atr=0.0),
 "MES_Trend_1c": dict(instrument="MES", family="trend", lookback=6, threshold=1.0, stop_atr=1.5, target_r=1.75, hold_bars=6, session_start=585, session_end=945, max_contracts=1, trailing_atr=0.0),
 "MNQ_MornBrk_1c": dict(instrument="MNQ", family="breakout", lookback=20, threshold=1.25, stop_atr=1.5, target_r=2.5, hold_bars=8, session_start=600, session_end=720, max_contracts=1, trailing_atr=0.0),
}
PORTS = {"Duo_Momentum": ["MNQ_Trend_1c", "MES_Mom_1c"], "Tri_Alpha": ["MES_Trend_1c", "MNQ_MornBrk_1c", "MNQ_Trend_1c"]}
MINI = {"MES": "ES", "MNQ": "NQ"}
eng = ep.engine()
CAT = json.load(open(uy.CATALOG))["instruments"]


def val_bars(inst):
    con = duckdb.connect()
    f = con.execute(uy.STRICT, [str(CAT[inst]["splits"]["validation"]["path"]), "2023-12-01", "2026-01-01"]).fetch_df(); con.close()
    f = f[f.timestamp_utc.notna()].copy()
    f["high"] = f[["open", "high", "low", "close"]].max(axis=1); f["low"] = f[["open", "high", "low", "close"]].min(axis=1); f["volume"] = f.volume.round()
    b = canonical(f); assert b.timestamp_utc.max() < pd.Timestamp("2026-01-01", tz="UTC"); return b


def run(bars, p, years):
    data = apply_early_close(eng["arrays"](bars), bars)
    feats = eng["features"](bars, p["lookback"])
    raw = eng["signal_for"](p, feats).astype(np.int8)
    local = bars.timestamp_utc.dt.tz_convert("America/New_York")
    dec = (local.dt.hour * 60 + local.dt.minute + 15).to_numpy()
    valid = (dec >= p["session_start"]) & (dec < p["session_end"]) & (local.dt.day_of_week.to_numpy() < 5)
    sig = np.where(valid, raw, 0).astype(np.int8)
    out, daily = {}, []
    for y in years:
        idx = np.flatnonzero(data["year"] == y)
        if not len(idx):
            continue
        a, b = int(idx[0]), int(idx[-1]) + 1
        d = {k: np.ascontiguousarray(v[a:b]) for k, v in data.items()}
        sess = d["session"].copy()
        d["session"] = pd.factorize(d["session"], sort=False)[0].astype(np.int64); d["contract"] = pd.factorize(d["contract"], sort=False)[0].astype(np.int64)
        r = eng["execute"](d, np.ascontiguousarray(sig[a:b]), np.ascontiguousarray(feats["atr"][a:b]), eng["execution_cfg"](p))
        peaks = np.maximum.accumulate(np.r_[50000.0, r["equity"]])[1:]
        out[y] = dict(net=round(float(r["cash"][-1] - 50000.0), 2), dd=round(float(np.max(peaks - r["worst"])), 2), trades=int(len(r["trade_net"])), breach=bool(r["funded_failed"]))
        eod = pd.Series(r["equity"]).groupby(pd.Series(sess)).last()
        daily.append(eod.diff().fillna(eod.iloc[0] - 50000.0) if len(eod) else eod)
    return out, pd.concat(daily) if daily else pd.Series(dtype=float)


res, val_daily = {}, {}
train_bars = {m: uy.load(m, "2009-12-01", "2024-01-01", "strict") for m in ("ES", "NQ")}
vb = {i: val_bars(i) for i in ("MES", "MNQ")}
for name, p in RULES.items():
    tr, _ = run(train_bars[MINI[p["instrument"]]], p, range(2010, 2024))
    va, dly = run(vb[p["instrument"]], p, (2024, 2025))
    val_daily[name] = dly
    ann = np.array([v["net"] for v in tr.values()])
    res[name] = dict(params=p, train=dict(net=round(float(ann.sum()), 2), years_pos=int((ann > 0).sum()), n_years=len(ann), worst_dd=max(v["dd"] for v in tr.values()),
                     trades=sum(v["trades"] for v in tr.values()), annual={y: v["net"] for y, v in tr.items()}), validation=va)
    print(name, "train", res[name]["train"], "val", va, flush=True)
for pn, legs in PORTS.items():
    df = pd.concat([val_daily[l] for l in legs], axis=1).fillna(0.0)
    tot = df.sum(axis=1); eq = 50000 + tot.cumsum(); dd = float((eq.cummax() - eq).max())
    byy = tot.groupby(pd.to_datetime(tot.index).year).sum()
    res[pn] = dict(legs=legs, val_net=round(float(tot.sum()), 2), val_eod_dd=round(dd, 2), by_year={int(k): round(float(v), 2) for k, v in byy.items()})
    print(pn, res[pn], flush=True)
(ROOT / "reports" / "ANTIGRAVITY_RULES_REPLICATION.json").write_text(json.dumps(res, indent=1, default=float))
