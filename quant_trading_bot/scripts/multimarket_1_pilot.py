"""multimarket_1 (research/multimarket_1/PROTOCOL.md): the frozen MNQ trend/breakout rules applied to crude traded as MCL, 2010-23 by year.
CL.c.0 1-min -> 15m/30m bars; MCL tick 0.01 = $1.00 (multiplier 100), spread 2 ticks, slippage 1 tick/side, $0.61/side, 1 contract.
Entries 09:30-13:30 ET on completed bars, flat 14:25 ET. Placebo: 20 random-direction same-count signal sets per rule."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
from quant_futures import ensemble_paper as ep
from quant_futures.session_calendar import apply_early_close
eng = ep.engine(); MCL = dict(tick=0.01, multiplier=100.0, spread_ticks=2, slippage_ticks=1, commission_per_side=0.61)
raw = pd.read_parquet(ROOT / "data/market/crossasset/CL_c_0_ohlcv1m_2010_2025.parquet")[["open", "high", "low", "close", "volume"]]
raw = raw[raw.index < "2024-01-01"]
def bars(tf):
    b = raw.resample(f"{tf}min", label="left", closed="left").agg(dict(open="first", high="max", low="min", close="last", volume="sum")).dropna().reset_index().rename(columns={"ts_event": "timestamp_utc"})
    et = b.timestamp_utc.dt.tz_convert("America/New_York"); b["session_id"] = (et + pd.Timedelta(hours=6)).dt.strftime("%Y-%m-%d"); b["contract"] = "CL.c.0"; b["instrument"] = "MNQ"
    return b, (et.dt.hour * 60 + et.dt.minute).to_numpy()
def atr(b):
    c = b.close.astype(float); h, l = b.high.astype(float), b.low.astype(float); prev = c.shift(1)
    return pd.concat((h - l, (h - prev).abs(), (l - prev).abs()), axis=1).max(axis=1).rolling(14, min_periods=14).mean()
def run(b, sig, a, p, entry_start, entry_end, gap):
    data = apply_early_close(eng["arrays"](b), b)
    cfg = eng["execution_cfg"](dict(p, instrument="MNQ", max_contracts=1, session_start=540, session_end=870, family="trend", lookback=8, threshold=0.0, trailing_atr=0.0))
    cfg.update(MCL); cfg.update(entry_start=entry_start, entry_end=entry_end, flat_minute=865, max_gap_minutes=gap); out = {}
    for y in sorted(set(data["year"])):
        if y < 2010: continue
        idx = np.flatnonzero(data["year"] == y); s, e = int(idx[0]), int(idx[-1]) + 1
        d = {k: np.ascontiguousarray(v[s:e]) for k, v in data.items()}; d["session"] = pd.factorize(d["session"], sort=False)[0].astype(np.int64); d["contract"] = pd.factorize(d["contract"], sort=False)[0].astype(np.int64)
        r = eng["execute"](d, np.ascontiguousarray(sig[s:e]), np.ascontiguousarray(a[s:e]), cfg)
        out[int(y)] = dict(net=round(float(r["cash"][-1] - 50000.0), 2), trades=int(len(r["trade_net"])))
    return out
rng = np.random.default_rng(7); res = {}
def score(name, b, sig, a, p, es, ee, gap):
    o = run(b, sig, a, p, es, ee, gap); net = round(sum(v["net"] for v in o.values()), 2); tr = sum(v["trades"] for v in o.values())
    plc = []
    for _ in range(20):
        s2 = sig.copy(); nz = np.flatnonzero(sig != 0); s2[nz] = rng.choice([-1, 1], size=len(nz)); plc.append(sum(v["net"] for v in run(b, s2, a, p, es, ee, gap).values()))
    pos = {y: v["net"] for y, v in o.items() if v["net"] > 0}; share = max(pos.values()) / net if net > 0 and pos else None
    res[name] = dict(net=net, trades=tr, per_trade=round(net / max(tr, 1), 2), pos_years=len(pos), pre2020=round(sum(v["net"] for y, v in o.items() if y < 2020), 2), max_year_share=None if share is None else round(share, 3), beat=int(sum(net > p_ for p_ in plc)), placebo_mean=round(float(np.mean(plc)), 2), by_year=o)
    res[name]["pass"] = bool(net > 0 and len(pos) >= 10 and (share or 9) <= 0.4 and res[name]["beat"] >= 19 and tr >= 100)
    print(name, {k: v for k, v in res[name].items() if k != "by_year"}, flush=True)
b30, sod30 = bars(30); a30 = atr(b30); c30 = b30.close.astype(float)
trend = (c30.ewm(span=8, adjust=False, min_periods=8).mean() - c30.ewm(span=16, adjust=False, min_periods=16).mean()) / a30
w30 = (sod30 >= 570) & (sod30 <= 810)
score("M1_ag_morning_trend_lb16", b30, np.where(w30, np.where(trend >= 0.75, 1, np.where(trend <= -0.75, -1, 0)), 0).astype(np.int8), np.nan_to_num(a30.to_numpy()).astype(np.float32), dict(stop_atr=1.5, target_r=3.5, hold_bars=8), 570, 810, 60)
bh = b30.high.rolling(8).max().shift(1); bl = b30.low.rolling(8).min().shift(1)
score("M2_ag_breakout_lb8_th1.5", b30, np.where(w30, np.where(c30 > bh + 1.5 * a30, 1, np.where(c30 < bl - 1.5 * a30, -1, 0)), 0).astype(np.int8), np.nan_to_num(a30.to_numpy()).astype(np.float32), dict(stop_atr=1.25, target_r=5.0, hold_bars=8), 570, 810, 60)
b15, sod15 = bars(15); a15 = atr(b15); c15 = b15.close.astype(float); w15 = (sod15 >= 570) & (sod15 <= 810)
score("M3_momentum15_lb24", b15, np.where(w15, np.sign(np.nan_to_num((c15 / c15.shift(24) - 1).to_numpy())), 0).astype(np.int8), np.nan_to_num(a15.to_numpy()).astype(np.float32), dict(stop_atr=2.0, target_r=3.0, hold_bars=24), 570, 810, 30)
json.dump(res, open(ROOT / "reports/MULTIMARKET_1_TRAINING.json", "w"), indent=1); print("PASSERS", [k for k, v in res.items() if v["pass"]]); print("DONE")
