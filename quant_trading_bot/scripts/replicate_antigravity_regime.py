"""Replicate Antigravity's ER-regime pair (2026-11-09; search multiplicity 324) on the fixed engine. Adds ER-mask placebos: same on-count, random bars, sign(momentum).
Original docstring: Replicate Antigravity's four 1-contract 15-min rules (2026-11-08) on the fixed engine: ES/NQ 2010-23 strict bars at micro
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
 "AG_Regime_A": dict(instrument="MNQ", family="regime", lookback=24, threshold=1.5, stop_atr=2.0, target_r=3.0, hold_bars=24, session_start=585, session_end=945, max_contracts=1, trailing_atr=2.5),
 "AG_Trend_B": dict(instrument="MNQ", family="trend", lookback=16, threshold=0.75, stop_atr=2.0, target_r=3.0, hold_bars=8, session_start=600, session_end=720, max_contracts=1, trailing_atr=0.0),
}
PORTS = {"Dual_Regime": ["AG_Regime_A", "AG_Trend_B"]}
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
(ROOT / "reports" / "ANTIGRAVITY_REGIME_REPLICATION.json").write_text(json.dumps(res, indent=1, default=float))

# ER-mask placebo for sleeve A on training: keep the per-year count of eligible bars, place them at random valid session bars, direction = sign(momentum)
rng = np.random.default_rng(20261109); p = RULES["AG_Regime_A"]; bars = train_bars["NQ"]
data = apply_early_close(eng["arrays"](bars), bars); feats = eng["features"](bars, p["lookback"]); raw = eng["signal_for"](p, feats).astype(np.int8)
local = bars.timestamp_utc.dt.tz_convert("America/New_York"); dec = (local.dt.hour * 60 + local.dt.minute + 15).to_numpy()
valid = (dec >= p["session_start"]) & (dec < p["session_end"]) & (local.dt.day_of_week.to_numpy() < 5)
mom = np.sign(np.nan_to_num(feats["momentum"])).astype(np.int8); years = data["year"]
def total(sig):
    tot = 0.0
    for y in range(2010, 2024):
        idx = np.flatnonzero(years == y); a, b = int(idx[0]), int(idx[-1]) + 1
        d = {k: np.ascontiguousarray(v[a:b]) for k, v in data.items()}
        d["session"] = pd.factorize(d["session"], sort=False)[0].astype(np.int64); d["contract"] = pd.factorize(d["contract"], sort=False)[0].astype(np.int64)
        r = eng["execute"](d, np.ascontiguousarray(sig[a:b]), np.ascontiguousarray(feats["atr"][a:b]), eng["execution_cfg"](p)); tot += float(r["cash"][-1] - 50000.0)
    return tot
real_sig = np.where(valid, raw, 0).astype(np.int8); pl = []
for i in range(20):
    ps = np.zeros_like(real_sig)
    for y in range(2010, 2024):
        m = (years == y) & valid; n = int((real_sig[years == y] != 0).sum()); pick = rng.choice(np.flatnonzero(m), size=min(n, int(m.sum())), replace=False); ps[pick] = mom[pick]
    pl.append(total(ps)); print("placebo", i, round(pl[-1], 2), flush=True)
res["AG_Regime_A"]["placebo"] = dict(real_train_net=res["AG_Regime_A"]["train"]["net"], placebo_nets=[round(v, 2) for v in pl], pct_beaten=float(np.mean(np.array(pl) < res["AG_Regime_A"]["train"]["net"])), placebo_mean=round(float(np.mean(pl)), 2))
print("placebo summary", res["AG_Regime_A"]["placebo"]["pct_beaten"], res["AG_Regime_A"]["placebo"]["placebo_mean"], flush=True)
(ROOT / "reports" / "ANTIGRAVITY_REGIME_REPLICATION.json").write_text(json.dumps(res, indent=1, default=float)); print("DONE", flush=True)
