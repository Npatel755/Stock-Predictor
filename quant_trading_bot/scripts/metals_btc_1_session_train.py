"""metals_btc_1 (Claude, 2026-11-10): session-drift and trend screens for gold / silver / bitcoin futures (MGC / SIL / MBT). TRAINING ONLY.

PRE-DECLARED (written before these hourly files were opened).
Data: Databento CME ohlcv-1h GC.v.0, SI.v.0 (2010-06..2023-12), BTC.v.0 (2017-12..2023-12); volume-front, unadjusted. Trading day = Topstep
session 18:00 ET (prior evening) -> 16:00 ET (flat before 16:10 ET). A window is skipped if its first or last hourly bar is missing, if under
75% of its bars exist, or if the contract changes inside it (no trade spans a roll).
Hypotheses (8 configs per market):
  F1 session drift, direction fixed by the hypothesis that metals rise in Asian/London hours and fall in US hours:
     long 18:00-02:00 | long 02:00-08:00 | long 18:00-08:00 | short 08:00-16:00.
  F2 trend (time-series momentum), direction = sign(prior session close - close N sessions earlier), N in {20, 60}, held 18:00-08:00 or
     18:00-16:00 (full session).
Fills: entry at the window's first bar open, exit at its last bar close; protective stop 1.5% (gold, silver) / 4% (bitcoin) checked
stop-first on each hourly bar, a bar opening through it fills at the open. 1 micro.
Costs per micro round trip in basis points of notional (1.75 ticks spread + 1 tick slippage per side + $1.22): MGC 1.20 bp ($4.97 on
10 oz x $4,150), SIL 2.50 bp (~$20 on 1,000 oz x $80), MBT 8.7 bp (~$7 on 0.1 BTC x $80,000; crypto micro fees are higher). Stress: +2 ticks
per side (MGC +0.96 bp, SIL +2.5 bp, MBT +2.5 bp).
SELECTION per market on the first half (GC/SI 2010-06..2016-12; BTC 2018-2020): among configs with PF >= 1.10 after costs, the highest net bp
per year. CONFIRMATION on the second half (GC/SI 2017-2023; BTC 2021-2023), all required: net > 0, PF >= 1.10, >= 60% of years positive,
net > 0 under the cost stress, and beats >= 190 of 200 placebos (F1: same direction and length, random start hour inside the same session;
F2: same windows, random direction; seed 20261110). Silver is a cross-check for gold: the gold-selected config is also reported on silver.
Only confirmed configs go to a book test (payout_24 account + base R, a sleeve at 1 micro), pre-declared later before it is run.
"""
import json
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NY = "America/New_York"; SEED = 20261110
MK = {"GC": dict(file="GC_v_0", cost=1.20, stress=0.96, stop=0.015, notional=41500.0, halves=("2010-06-01", "2017-01-01", "2024-01-01")),
      "SI": dict(file="SI_v_0", cost=2.50, stress=2.50, stop=0.015, notional=80000.0, halves=("2010-06-01", "2017-01-01", "2024-01-01")),
      "BTC": dict(file="BTC_v_0", cost=8.70, stress=2.50, stop=0.04, notional=8000.0, halves=("2018-01-01", "2021-01-01", "2024-01-01"))}
WIN = {"18-02": (0, 8), "02-08": (8, 14), "18-08": (0, 14), "08-16": (14, 22), "18-16": (0, 22)}   # hours after 18:00 ET
F1 = [("F1 long 18-02", "18-02", 1), ("F1 long 02-08", "02-08", 1), ("F1 long 18-08", "18-08", 1), ("F1 short 08-16", "08-16", -1)]
F2 = [(f"F2 trend{N} {w}", w, N) for N in (20, 60) for w in ("18-08", "18-16")]


def sessions(name):
    df = pd.read_parquet(ROOT / f"data/market/crossasset_train/{MK[name]['file']}_ohlcv1h_2010_2023.parquet")
    assert df.index.max() < pd.Timestamp("2024-01-01", tz="UTC")
    et = df.index.tz_convert(NY); hr = np.asarray(et.hour)
    day = pd.Series(et.normalize().tz_localize(None).date, index=df.index)
    day = np.where(hr >= 18, (pd.to_datetime(day) + pd.Timedelta(days=1)).dt.date, day)
    rel = (hr - 18) % 24
    d = pd.DataFrame({"day": day, "rel": rel, "o": df.open.to_numpy(float), "h": df.high.to_numpy(float), "l": df.low.to_numpy(float),
                      "c": df.close.to_numpy(float), "iid": df.instrument_id.to_numpy()})
    d = d[d.rel <= 21]
    return {k: g.sort_values("rel") for k, g in d.groupby("day") if pd.Timestamp(k).dayofweek < 5}


def window(g, a, b, side, stop):
    w = g[(g.rel >= a) & (g.rel < b)]
    if len(w) < 0.75 * (b - a) or w.rel.iloc[0] != a or w.rel.iloc[-1] != b - 1 or w.iid.nunique() != 1: return None
    e = w.o.iloc[0]; st = e * (1 - side * stop)
    for j, r in enumerate(w.itertuples()):
        if side > 0:
            if j and r.o <= st: return side * (r.o / e - 1)
            if r.l <= st: return side * (st / e - 1)
        else:
            if j and r.o >= st: return side * (r.o / e - 1)
            if r.h >= st: return side * (st / e - 1)
    return side * (w.c.iloc[-1] / e - 1)


def build(name):
    S = sessions(name); days = sorted(S); stop = MK[name]["stop"]
    close = pd.Series({d: S[d][S[d].rel <= 21].c.iloc[-1] for d in days})
    rows = []
    for k, d in enumerate(days):
        g = S[d]
        for cfg, w, side in F1:
            r = window(g, *WIN[w], side, stop)
            if r is not None: rows.append(dict(cfg=cfg, day=d, side=side, g=r * 1e4, fam="F1", w=w))
        for cfg, w, N in F2:
            if k <= N: continue
            sgn = np.sign(close.iloc[k - 1] - close.iloc[k - 1 - N])
            if sgn == 0: continue
            r = window(g, *WIN[w], int(sgn), stop)
            rm = window(g, *WIN[w], -int(sgn), stop)
            if r is not None and rm is not None: rows.append(dict(cfg=cfg, day=d, side=int(sgn), g=r * 1e4, gm=rm * 1e4, fam="F2", w=w))
    return S, pd.DataFrame(rows)


def stats(x, cost, yrs):
    n = x.g.to_numpy() - cost; pos, neg = n[n > 0].sum(), -n[n < 0].sum()
    return dict(trades=int(len(n)), net_bp_per_year=round(float(n.sum()) / yrs, 1), avg_bp=round(float(n.mean()), 2) if len(n) else None,
                pf=round(float(pos / neg), 3) if neg > 0 else None)


def f1_placebo(S, cfg_w, side, days, stop, cost, rng, n=200):
    a, b = WIN[cfg_w]; L = b - a; starts = list(range(0, 22 - L + 1)); res = []
    for _ in range(n):
        tot = 0.0
        for d in days:
            s0 = int(rng.choice(starts)); r = window(S[d], s0, s0 + L, side, stop)
            if r is not None: tot += r * 1e4 - cost
        res.append(tot)
    return np.array(res)


def main():
    out = {}; rng = np.random.default_rng(SEED)
    for name in ("GC", "SI", "BTC"):
        m = MK[name]; S, T = build(name); lo, mid, hi = (pd.Timestamp(x).date() for x in m["halves"])
        y1 = (pd.Timestamp(m["halves"][1]) - pd.Timestamp(max(m["halves"][0], str(min(T.day))))).days / 365.25
        y2 = (pd.Timestamp(m["halves"][2]) - pd.Timestamp(m["halves"][1])).days / 365.25
        h1 = T[(T.day >= lo) & (T.day < mid)]; h2 = T[(T.day >= mid) & (T.day < hi)]
        grid = {c: stats(g, m["cost"], y1) for c, g in h1.groupby("cfg")}
        ok = {c: v for c, v in grid.items() if v["pf"] and v["pf"] >= 1.10}
        pick = max(ok, key=lambda c: ok[c]["net_bp_per_year"]) if ok else None
        o = out[name] = dict(h1_grid=grid, selected=pick, trading_days=len(S))
        print(name, "H1:", {c: (v["net_bp_per_year"], v["pf"]) for c, v in grid.items()}, "->", pick, flush=True)
        if pick is None: continue
        x2 = h2[h2.cfg == pick]; st = stats(x2, m["cost"], y2); stress = stats(x2, m["cost"] + m["stress"], y2)
        yr = (x2.g - m["cost"]).groupby(pd.to_datetime(x2.day).dt.year).sum()
        if x2.fam.iloc[0] == "F1":
            pl = f1_placebo(S, x2.w.iloc[0], int(x2.side.iloc[0]), list(x2.day), m["stop"], m["cost"], rng)
        else:
            pl = np.array([float((np.where(rng.random(len(x2)) < 0.5, x2.gm, x2.g) - m["cost"]).sum()) for _ in range(200)])
        beaten = int((pl < (x2.g - m["cost"]).sum()).sum())
        gates = dict(net=st["net_bp_per_year"] > 0, pf=bool(st["pf"] and st["pf"] >= 1.10), years=bool((yr > 0).mean() >= 0.6),
                     stress=stress["net_bp_per_year"] > 0, placebo=beaten >= 190)
        o.update(h2=st, h2_stress=stress, h2_by_year={int(k): round(float(v), 0) for k, v in yr.items()}, placebo_beaten=f"{beaten}/200",
                 gates=gates, confirmed=all(gates.values()), h2_usd_per_year_1_micro=round(st["net_bp_per_year"] * m["notional"] / 1e4, 0))
        print(name, pick, "H2:", st, "stress", stress["net_bp_per_year"], "years", o["h2_by_year"], "placebo", f"{beaten}/200", "gates", gates, flush=True)
    if out["GC"].get("selected"):
        S, T = build("SI"); x = T[(T.cfg == out["GC"]["selected"]) & (T.day >= pd.Timestamp("2017-01-01").date())]
        out["SI_with_gold_config_h2"] = stats(x, MK["SI"]["cost"], 7.0)
        print("silver with gold's config, 2017-23:", out["SI_with_gold_config_h2"])
    (ROOT / "reports/METALS_BTC_1_SESSION_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
