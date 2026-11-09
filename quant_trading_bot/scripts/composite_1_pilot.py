"""composite_1 (research/composite_1/PROTOCOL.md): composite selected-day 10:00 MNQ entries, training 2010-23; fixed exits; 6 variants; placebos."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import mass_1m_search as m1
from quant_futures import ensemble_paper as ep
from quant_futures.session_calendar import apply_early_close
eng = ep.engine(); P = dict(stop_atr=1.5, target_r=4.0, hold_bars=20)
def cboe(n):
    d = pd.read_csv(ROOT / f"data/external/{n}_History.csv"); d["date"] = pd.to_datetime(d.DATE, format="%m/%d/%Y").dt.date; return d.set_index("date").CLOSE.astype(float)
def run(bars, sig, atr, lo_year):
    data = apply_early_close(eng["arrays"](bars), bars)
    cfg = eng["execution_cfg"](dict(P, instrument="MNQ", max_contracts=1, session_start=600, session_end=945, family="trend", lookback=8, threshold=0.0, trailing_atr=0.0))
    cfg.update(entry_start=585, entry_end=585, flat_minute=955, max_gap_minutes=20); out = {}
    for y in sorted(set(data["year"])):
        if y < lo_year: continue
        idx = np.flatnonzero(data["year"] == y); a, b = int(idx[0]), int(idx[-1]) + 1
        d = {k: np.ascontiguousarray(v[a:b]) for k, v in data.items()}; d["session"] = pd.factorize(d["session"], sort=False)[0].astype(np.int64); d["contract"] = pd.factorize(d["contract"], sort=False)[0].astype(np.int64)
        r = eng["execute"](d, np.ascontiguousarray(sig[a:b]), np.ascontiguousarray(atr[a:b]), cfg)
        out[int(y)] = dict(net=round(float(r["cash"][-1] - 50000.0), 2), trades=int(len(r["trade_net"])))
    return out
def total(o): return round(sum(v["net"] for v in o.values()), 2)
def signals(split, lo, hi):
    nq = m1.load_bars("MNQ", 15, lo, hi, split).reset_index(drop=True); es = m1.load_bars("MES", 15, lo, hi, split).reset_index(drop=True)
    assert nq.timestamp_utc.max() < pd.Timestamp("2026-01-01", tz="UTC")
    def frame(b):
        et = b.timestamp_utc.dt.tz_convert("America/New_York"); sod = (et.dt.hour * 60 + et.dt.minute).to_numpy(); day = et.dt.date
        c, h, l, o = (b[k].astype(float) for k in ("close", "high", "low", "open")); prev = c.shift(1)
        atr = pd.concat((h - l, (h - prev).abs(), (l - prev).abs()), axis=1).max(axis=1).rolling(14, min_periods=14).mean()
        g = pd.DataFrame(dict(day=day, sod=sod, o=o, h=h, l=l, c=c, atr=atr))
        D = pd.DataFrame(dict(o=g[g.sod == 570].groupby("day").o.first(), hi=g[(g.sod == 570) | (g.sod == 585)].groupby("day").h.max(), lo=g[(g.sod == 570) | (g.sod == 585)].groupby("day").l.min(),
                              c=g[g.sod == 585].groupby("day").c.last(), atr=g[g.sod == 585].groupby("day").atr.last())).dropna()
        return D, sod, day, np.nan_to_num(atr.to_numpy()).astype(np.float32)
    Dn, sod, day, ATR = frame(nq); De = frame(es)[0]
    spread = ((Dn.c / Dn.o - 1) - (De.c / De.o - 1)).dropna(); z = spread / spread.rolling(20, min_periods=20).std().shift(1)
    s1 = pd.Series(np.where(z >= 1.25, 1, np.where(z <= -1.25, -1, 0)), index=z.index)
    rng_ = Dn.hi - Dn.lo
    bull = ((Dn.o - Dn.lo) / rng_ <= 0.20) & ((Dn.c - Dn.lo) / rng_ >= 0.85) & (rng_ >= Dn.atr); bear = ((Dn.hi - Dn.o) / rng_ <= 0.20) & ((Dn.hi - Dn.c) / rng_ <= 0.15) & (rng_ >= Dn.atr)
    s2 = pd.Series(np.where(bull, 1, np.where(bear, -1, 0)), index=Dn.index)
    ratio = (cboe("VIX") / cboe("VIX3M")).dropna(); crush = (ratio.diff().shift(1) <= -0.015)
    s3 = pd.Series(np.where(((Dn.c / Dn.o - 1) >= 0.001) & pd.Series(Dn.index, index=Dn.index).map(crush).fillna(False).astype(bool), 1, 0), index=Dn.index)
    S = pd.DataFrame(dict(s1=s1, s2=s2, s3=s3)).reindex(Dn.index).fillna(0).astype(int)
    return nq, sod, day, ATR, S
def variants(S):
    tot = S.sum(axis=1); nfire = (S != 0).sum(axis=1); agree2 = (S.clip(lower=0).sum(axis=1) >= 2) | ((-S).clip(lower=0).sum(axis=1) >= 2)
    V = dict(A_any_two_sided=np.sign(tot), B_any_long_only=(tot > 0).astype(int), C_two_agree_two_sided=np.where(agree2, np.sign(tot), 0), D_two_agree_long_only=np.where(agree2 & (tot > 0), 1, 0),
             E_s1_and_s2_agree=np.where((S.s1 != 0) & (S.s1 == S.s2), S.s1, 0), F_exactly_one=np.where(nfire == 1, np.sign(tot), 0))
    return {k: pd.Series(np.asarray(v, dtype=int), index=S.index) for k, v in V.items()}
def evaluate(split, lo, hi, lo_year, n_plc):
    nq, sod, day, ATR, S = signals(split, lo, hi); at = sod == 585; res = {}; rng = np.random.default_rng(21)
    days_all = pd.Series(sorted(set(day[at]))); yrs_all = pd.to_datetime(days_all).dt.year.values
    for name, dirs in variants(S).items():
        sig = np.where(at, day.map(dirs).fillna(0).to_numpy(), 0).astype(np.int8); o = run(nq, sig, ATR, lo_year); t = total(o); tr = sum(v["trades"] for v in o.values())
        rec = dict(by_year=o, total=t, trades=tr, per_trade=round(t / tr, 2) if tr else None, pos_years=int(sum(v["net"] > 0 for v in o.values())), pre2020=round(sum(v["net"] for y, v in o.items() if y < 2020), 2),
                   max_year_share=round(max(v["net"] for v in o.values()) / t, 3) if t > 0 else None)
        if n_plc:
            yrs = pd.to_datetime(pd.Series(dirs.index)).dt.year.values; dv = dirs.values; plc = []
            for _ in range(n_plc):
                s = pd.Series(0, index=days_all.values, dtype=int)
                for y in np.unique(yrs_all):
                    nl, ns = int(((dv == 1) & (yrs == y)).sum()), int(((dv == -1) & (yrs == y)).sum()); cand = days_all[yrs_all == y].to_numpy()
                    pick = rng.choice(cand, size=min(nl + ns, len(cand)), replace=False); s[pick[:nl]] = 1; s[pick[nl:]] = -1
                plc.append(total(run(nq, np.where(at, day.map(s).fillna(0).to_numpy(), 0).astype(np.int8), ATR, lo_year)))
            rec.update(placebo_mean=round(float(np.mean(plc)), 2), beat=int(sum(t > p for p in plc)))
            rec["pass"] = bool(t > 0 and rec["pos_years"] >= 10 and tr >= 100 and rec["beat"] >= 19 and (rec["max_year_share"] or 1) <= 0.4 and (rec["per_trade"] or 0) >= 8)
        res[name] = rec; print(split, name, {k: v for k, v in rec.items() if k != "by_year"}, flush=True)
    return res
out = dict(train=evaluate("train", "2009-11-01", "2024-01-01", 2010, 20))
passers = [k for k, v in out["train"].items() if v["pass"]]; print("PASSERS", passers, flush=True)
if passers:
    val = evaluate("validation", "2023-11-01", "2026-01-01", 2024, 0); out["validation"] = {k: val[k] for k in passers}
json.dump(out, open(ROOT / "reports/COMPOSITE_1_TRAINING.json", "w"), indent=1); print("DONE")
