"""payout_12 (Claude, 2026-11-10): how much does the account's drawdown size limit payouts? HYPOTHETICAL floors. TRAINING 2010-23 only.

PRE-DECLARED (before results): static floor F in {$2,000 (Nick's 50K static), $3,000, $4,500} with the daily loss limit at F/2 - these larger
accounts are HYPOTHETICAL (verify Topstep's actual rules per account size before using). Books at today's price, 1 micro, $300 budget,
research routing, $400 account stop, $1,000 buffer: v5.2 | v5.2 + TRD30_D + BRK30 | v5.2 + overnight (0.55% stop, always on) |
v5.2 + TRD30_D + BRK30 + overnight. For each floor, the book with the most payouts per 12 months at <= 2% 12-month breach is reported.
"""
import json
import numpy as np, pandas as pd
import payout_lib as pl

src = (pl.ROOT / "scripts/payout_10_overnight_stop_train.py").read_text(encoding="utf-8").split("\nout = {}")[0]
ns = {"__name__": "p10"}; exec(src, ns)
ep, bars_for, START, gs, T, nights = ns["ep"], ns["bars_for"], ns["START"], ns["gs"], ns["T"], ns["nights"]
for k, sl in (("TRD30_D", dict(ep._AG_TRD30_D, name="AG_TRD30_D_1c")), ("BRK30", dict(ep._AG_BRK30, name="AG_BRK30_1c"))):
    T[k] = pl.price_normalize(pl.sleeve_trades(ep, bars_for, START, sl, len(T), True))
ov = nights(0.0055)[["tin", "tout", "net_today"]]


def intraday(keys):
    return pl.route(pd.concat([T[k] for k in keys], ignore_index=True).pipe(lambda d: d[d.risk_today <= 300.0]))[["tin", "tout", "net_today"]]


V52 = ["CRABEL", "TRD60", "MES30", "TRD30PM"]
BOOKS = {"v5.2": intraday(V52), "v5.2 + TRD30_D + BRK30": intraday(V52 + ["TRD30_D", "BRK30"])}
BOOKS["v5.2 + overnight"] = pd.concat([BOOKS["v5.2"], ov], ignore_index=True)
BOOKS["v5.2 + TRD30_D + BRK30 + overnight"] = pd.concat([BOOKS["v5.2 + TRD30_D + BRK30"], ov], ignore_index=True)
DAYS = {k: pl.day_series(v, stop=400.0) for k, v in BOOKS.items()}


def evaluate(day, F, dll, C=1000.0):
    s = pd.Series(day.to_numpy(), index=pd.to_datetime(pd.Series(day.index).astype(str)).to_numpy()); res = []
    for s0 in pd.date_range("2010-07-01", "2023-01-01", freq="MS"):
        w = s[(s.index >= s0) & (s.index < s0 + pd.DateOffset(months=12))].to_numpy()
        bal = 0.0; good = 0; pays = 0; breach = False
        for p in w:
            bal += max(p, -dll)
            if bal <= -F: breach = True; break
            good += p >= 150
            if good >= 5 and bal - C > 0: pays += 1; bal = C; good = 0
        res.append((pays, breach))
    r = pd.DataFrame(res, columns=["pays", "breach"])
    return dict(payouts_12m_mean=round(float(r.pays.mean()), 2), payouts_12m_p10_p90=[float(r.pays.quantile(.1)), float(r.pays.quantile(.9))],
                p_breach_12m=round(float(r.breach.mean()), 3))


out = {}
for F in (2000.0, 3000.0, 4500.0):
    out[f"floor ${int(F)}"] = {}
    for k, d in DAYS.items():
        out[f"floor ${int(F)}"][k] = r = evaluate(d, F, F / 2)
        print(f"floor ${int(F):>5} | {k:36s} {r}", flush=True)
    ok = {k: v for k, v in out[f"floor ${int(F)}"].items() if v["p_breach_12m"] <= 0.02}
    out[f"floor ${int(F)}"]["best_within_2pct"] = max(ok, key=lambda k: ok[k]["payouts_12m_mean"]) if ok else None
    print("   best within 2% breach:", out[f"floor ${int(F)}"]["best_within_2pct"], flush=True)
# ADDENDUM (declared after the table above, before running): 2 micros on every leg (per-micro budget still $300, so <= $600 per trade),
# account stop $800, on the hypothetical $3,000 and $4,500 floors (DLL = F/2). Same 2% breach rule.
for F in (3000.0, 4500.0):
    for k, v in BOOKS.items():
        v2 = v.copy(); v2["net_today"] = v2.net_today * 2.0
        r = evaluate(pl.day_series(v2, stop=800.0), F, F / 2)
        out[f"floor ${int(F)}"][f"2 micros: {k}"] = r
        print(f"floor ${int(F):>5} | 2 micros: {k:36s} {r}", flush=True)
(pl.ROOT / "reports/PAYOUT_12_FLOOR_SIZE_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
