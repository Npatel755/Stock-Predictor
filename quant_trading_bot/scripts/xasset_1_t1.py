"""xasset_1 T1 (research/xasset_1/PROTOCOL.md): does the lagged 5/15/30-min move of ZN / 6E / CL predict the next 1/5/15/30-min MNQ (NQ) RTH move?
Training 2010-2023 only (NQ 2010-18, MNQ 2019-23). Non-overlapping samples every h minutes; by-year OLS slope t-stats and decile spreads in ticks."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts"))
import mass_1m_search as m1
TICK = 0.25
def _load_xa(k):
    v = pd.read_parquet(ROOT / f"data/market/crossasset/{k}_c_0_ohlcv1m_2010_2025.parquet")[["close", "instrument_id"]]
    return v.rename(columns={"close": k, "instrument_id": f"{k}_id"})
XA = {k: _load_xa(k) for k in ("ZN", "6E", "CL")}
nq = m1.load_bars("MNQ", 1, "2010-06-01", "2024-01-01", "train")[["timestamp_utc", "close"]].rename(columns={"close": "nq"})
nq["timestamp_utc"] = pd.to_datetime(nq.timestamp_utc, utc=True)
df = nq.set_index("timestamp_utc")
for k, v in XA.items():
    v.index = pd.to_datetime(v.index, utc=True); df = df.join(v[~v.index.duplicated()], how="left")
df[[c for v in XA.values() for c in v.columns]] = df[[c for v in XA.values() for c in v.columns]].ffill(limit=5)
et = df.index.tz_convert("America/New_York"); df["sod"] = et.hour * 60 + et.minute; df["year"] = et.year; df["date"] = et.date
out = {}
for L in (5, 15, 30):
    for k in XA:
        same = df[f"{k}_id"] == df[f"{k}_id"].shift(L)             # no roll inside the window (continuous c.0 jumps at rolls)
        df[f"{k}_l{L}"] = np.log(df[k]).diff(L).where(same).shift(1)   # lagged, completed minutes only
for h in (1, 5, 15, 30):
    fwd = (df.nq.shift(-h) - df.nq) / TICK                          # forward MNQ move in ticks
    ok = (df.sod >= 585) & (df.sod + h <= 955)
    for L in (5, 15, 30):
        for k in XA:
            x = df[f"{k}_l{L}"]; m = ok & x.notna() & fwd.notna()
            sub = pd.DataFrame(dict(x=x[m], y=fwd[m], year=df.year[m], sod=df.sod[m]))
            sub = sub[(sub.sod - 585) % h == 0]                     # non-overlapping forward windows
            if len(sub) < 1000: continue
            z = (sub.x - sub.x.mean()) / sub.x.std(); b = np.polyfit(z, sub.y, 1)[0]; resid = sub.y - np.polyval(np.polyfit(z, sub.y, 1), z)
            se = resid.std() / np.sqrt(len(sub)) / z.std(); t = b / se
            dec = pd.qcut(sub.x, 10, labels=False, duplicates="drop"); spread = sub.y[dec == dec.max()].mean() - sub.y[dec == 0].mean()
            yr = sub.groupby("year").apply(lambda g: np.polyfit((g.x - g.x.mean()) / g.x.std(), g.y, 1)[0] if g.x.std() > 0 and len(g) > 50 else np.nan)
            rec = dict(channel=k, lag=L, horizon=h, n=int(len(sub)), slope_ticks_per_sd=round(float(b), 3), t=round(float(t), 2), decile_spread_ticks=round(float(spread), 2),
                       years_same_sign=int((np.sign(yr.dropna()) == np.sign(b)).sum()), years=int(yr.notna().sum()),
                       qualifies=bool(abs(t) > 4 and abs(spread) > 5.4 and (np.sign(yr.dropna()) == np.sign(b)).sum() >= 10))
            out[f"{k}_L{L}_h{h}"] = rec; print(rec, flush=True)
json.dump(out, open(ROOT / "reports/XASSET_1_T1.json", "w"), indent=1)
q = [k for k, v in out.items() if v["qualifies"]]; print("QUALIFYING", q); print("DONE")
