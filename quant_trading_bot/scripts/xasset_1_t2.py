"""xasset_1 T2 (research/xasset_1/PROTOCOL.md): executable rules on the qualifying channel (CL -> NQ; T1 qualified CL_L15_h30).
Registered direction: continuation of implied risk-on/off (CL up -> long MNQ). T1 found the OPPOSITE sign, so the registered direction
is primary and the inverse (CL up -> short MNQ) is reported as a post-hoc exploratory variant (multiplicity 2). Training 2010-2023 only.
Signal at minute t (completed): z = CL log-return over the prior L minutes / std of that window's returns over the prior 20 sessions;
|z| >= k (k in 1, 1.5, 2); hold H minutes (15, 30, 60) or stop 2*ATR14(1m)*sqrt(H) adverse mid move; entries 09:45-15:00 ET; flat 15:55;
marketable fills at next-minute open +- 1 tick slippage, 1.75-tick spread, $0.61/side; 1 contract; one position at a time.
Placebo: 20 random signal sets per config (same count per session, random direction)."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from numba import njit
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts"))
import mass_1m_search as m1
TICK, TV, COMM, SLIP, SPREAD = 0.25, 0.5, 0.61, 1, 1.75
RT = (SPREAD + 2 * SLIP) * TV + 2 * COMM          # full round-trip cost per contract, charged on each trade
L = 15
cl = pd.read_parquet(ROOT / "data/market/crossasset/CL_c_0_ohlcv1m_2010_2025.parquet")[["close", "instrument_id"]]; cl.index = pd.to_datetime(cl.index, utc=True); cl = cl[~cl.index.duplicated()]
nq = m1.load_bars("MNQ", 1, "2010-06-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]]
nq["timestamp_utc"] = pd.to_datetime(nq.timestamp_utc, utc=True); df = nq.set_index("timestamp_utc")
df["clpx"] = cl["close"].reindex(df.index).ffill(limit=5); df["clid"] = cl["instrument_id"].reindex(df.index).ffill(limit=5)
et = df.index.tz_convert("America/New_York"); df["sod"] = (et.hour * 60 + et.minute).astype(int); df["year"] = et.year; df["date"] = et.date; df["day"] = pd.factorize(df.date)[0]
same = df.clid == df.clid.shift(L); r = np.log(df.clpx).diff(L).where(same)
daily_sd = r.groupby(df.date).std(); sd20 = daily_sd.rolling(20, min_periods=15).mean().shift(1)
df["z"] = (r / df.date.map(sd20)).shift(1)                          # completed window, known at minute open
prev = df.close.shift(1); tr = pd.concat([df.high - df.low, (df.high - prev).abs(), (df.low - prev).abs()], axis=1).max(axis=1)
df["atr"] = tr.groupby(df.day).transform(lambda s: s.rolling(14, min_periods=14).mean()).shift(1)
O, H_, L_, C = (df[c].to_numpy(float) for c in ("open", "high", "low", "close")); Z = df.z.to_numpy(float); ATR = np.nan_to_num(df.atr.to_numpy(float)); SOD = df.sod.to_numpy(np.int64); DAY = df.day.to_numpy(np.int64); YEAR = df.year.to_numpy(np.int64)

@njit(cache=True)
def sim(sig, o, h, l, c, atr, sod, day, H, stop_mult):
    n = len(sig); pnl = np.zeros(n); yrs_idx = np.zeros(n, np.int64); k = 0; pos = 0; entry = 0.0; ent_i = -1; stop = 0.0
    for i in range(1, n):
        if pos != 0:
            done = False; px = 0.0
            if day[i] != day[i - 1]: px = c[i - 1]; done = True
            elif pos > 0 and l[i] <= stop: px = stop; done = True
            elif pos < 0 and h[i] >= stop: px = stop; done = True
            elif i - ent_i >= H or sod[i] >= 955: px = o[i]; done = True
            if done:
                pnl[k] = pos * (px - entry) / TICK * TV - RT; yrs_idx[k] = i; k += 1; pos = 0
            continue
        if sig[i - 1] != 0 and sod[i] >= 585 and sod[i] <= 900 and atr[i] > 0:
            pos = sig[i - 1]; entry = o[i]; ent_i = i
            stop = entry - stop_mult * atr[i] if pos > 0 else entry + stop_mult * atr[i]
    return pnl[:k], yrs_idx[:k]

def evaluate(sig, H):
    pnl, idx = sim(sig, O, H_, L_, C, ATR, SOD, DAY, H, 2.0 * np.sqrt(H))
    yearly = pd.Series(pnl).groupby(YEAR[idx]).sum() if len(pnl) else pd.Series(dtype=float)
    return float(pnl.sum()), int(len(pnl)), yearly

rng = np.random.default_rng(3); results = []
win = (SOD >= 585) & (SOD <= 900)
for k in (1.0, 1.5, 2.0):
    base = np.where(win & (np.abs(np.nan_to_num(Z)) >= k), np.sign(np.nan_to_num(Z)), 0).astype(np.int8)
    cnt = pd.Series(base != 0).groupby(DAY).sum(); days_with = cnt[cnt > 0]
    plc_sets = []
    for r_ in range(20):
        s = np.zeros(len(Z), np.int8)
        for d, n in days_with.items():
            cand = np.flatnonzero(win & (DAY == d)); pick = rng.choice(cand, size=min(int(n), len(cand)), replace=False); s[pick] = rng.choice(np.array([-1, 1], np.int8), size=len(pick))
        plc_sets.append(s)
    for H in (15, 30, 60):
        pl = [evaluate(s, H)[0] for s in plc_sets]
        for name, sg in (("registered_cl_up_long", base), ("exploratory_cl_up_short", (-base).astype(np.int8))):
            net, ntr, yearly = evaluate(sg, H)
            rec = dict(variant=name, k=k, H=H, net=round(net, 2), trades=ntr, pos_years=int((yearly > 0).sum()), years=int(len(yearly)), max_year_share=round(float(yearly.max() / net), 3) if net > 0 else None,
                       placebo_mean=round(float(np.mean(pl)), 2), placebo_sd=round(float(np.std(pl)), 2), beat=int(sum(net > p for p in pl)), yearly={int(y): round(float(v), 2) for y, v in yearly.items()})
            rec["pass"] = bool(net > 0 and rec["pos_years"] >= 10 and ntr >= 100 and rec["beat"] >= 19 and (rec["max_year_share"] or 1) <= 0.4)
            results.append(rec); print(name, k, H, "net", rec["net"], "trades", ntr, "pos", rec["pos_years"], "plc", rec["placebo_mean"], rec["beat"], "PASS" if rec["pass"] else "", flush=True)
json.dump(results, open(ROOT / "reports/XASSET_1_T2.json", "w"), indent=1); print("DONE", sum(r["pass"] for r in results), "pass of", len(results))
