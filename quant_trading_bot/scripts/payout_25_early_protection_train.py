"""payout_25 (Claude, 2026-11-10): protect the funded account before its first payout. TRAINING 2010-23 only (2024-26 is spent for this book).

PRE-DECLARED (before results). Motivation: both one-shot holdout paths fell to ~-$1,600 before the first payout (static floor -$2,000).
Base = payout_24 adopted rule (1x below $4,000, 2x from $4,000, withdraw daily above $6,000; overnight while balance >= $500).
Protective variants, active only before the first payout and while the balance at the prior close is below T:
  A1 Crabel gap-continuation trades at 1 micro instead of 2 | A2 skip trades with stop risk > $200 per micro (instead of $300) |
  A4 = A1 + A2; each at T = $0 and T = $1,000 | A3 overnight leg only from a $1,000 balance (instead of $500), no T. 7 cells.
Metrics (139 monthly 24-month starts, S0 / S3 / S4): closed within 24 months, NEAR-MISS = lowest balance before the first payout <= -$1,500,
dollars withdrawn, payouts in year 1 / year 2, both halves of the starts.
ADOPT the cell with the lowest S0 near-miss share among those with: closure (S0, S3, S4) <= base's, near-miss share <= 75% of base's (S0),
and dollars withdrawn >= 90% of base's in BOTH halves. Only training can say this; the forward paper ledger is the test.
"""
import json
import numpy as np, pandas as pd
import payout_lib as pl

src = (pl.ROOT / "scripts/payout_24_static_daily_sizing_train.py").read_text(encoding="utf-8").split("\nout = {}\n")[0]
P24 = {"__name__": "p24"}; exec(src, P24)
SER, stressed_intra, sc17, N0, fast_day_series = P24["SER"], P24["stressed_intra"], P24["sc17"], P24["N0"], P24["fast_day_series"]
HALVES = P24["HALVES"]

VAR = {}
for kind in ("S0", "S3", "S4"):
    _, n = sc17(kind, N0)
    for v in ("A1", "A2", "A4"):
        e = stressed_intra(kind).copy()
        if v in ("A1", "A4"):
            two = e.n_contracts >= 2; e.loc[two, "net_today"] /= e.loc[two, "n_contracts"]; e.loc[two, "n_contracts"] = 1.0
        if v in ("A2", "A4"): e = e[e.risk_today <= 200.0]
        i = pl.route(e)[["tin", "tout", "net_today"]]
        VAR[(kind, v, False)] = fast_day_series(i, 400.0).to_dict()
        VAR[(kind, v, True)] = fast_day_series(pd.concat([i, n], ignore_index=True), 400.0).to_dict()


def run(kind, v=None, T=0.0, S_night=500.0, start_from="2010-07-01", start_to="2022-01-01"):
    keys = [k for k in SER if k[0] == kind]
    days = sorted(set().union(*[set(SER[k]) for k in keys])); ix = pd.to_datetime(pd.Series(days).astype(str)).to_numpy(); rows = []
    for s0 in pd.date_range(start_from, start_to, freq="MS"):
        a = int(np.searchsorted(ix, np.datetime64(s0))); b = int(np.searchsorted(ix, np.datetime64(s0 + pd.DateOffset(months=24))))
        cut = np.datetime64(s0 + pd.DateOffset(months=12))
        bal = 0.0; paid = False; since = 0.0; p1 = p2 = 0; usd = 0.0; closed = False; low = 0.0
        for x, t in zip(days[a:b], ix[a:b]):
            m = 2 if bal >= 4000 else 1; night = bal >= S_night
            p = VAR[(kind, v, night)].get(x, 0.0) if (v and not paid and bal < T and m == 1) else SER[(kind, m, night)].get(x, 0.0)
            p = max(p, -1000.0); bal += p; since += p
            if not paid: low = min(low, bal)
            if bal <= (0.0 if paid else -2000.0): closed = True; break
            if (since > 0 or not paid) and bal - 6000.0 >= 250.0:
                w = min(1500.0, bal - 6000.0); bal -= w; usd += w; paid = True; since = 0.0
                if t < cut: p1 += 1
                else: p2 += 1
        rows.append((p1, p2, usd, closed, low <= -1500.0))
    r = pd.DataFrame(rows, columns=["p1", "p2", "usd", "closed", "near"])
    return dict(withdrawn_24m=round(float(r.usd.mean()), 0), payouts_y1=round(float(r.p1.mean()), 2), payouts_y2=round(float(r.p2.mean()), 2),
                closed_24m=round(float(r.closed.mean()), 3), near_miss=round(float(r.near.mean()), 3))


def cell(v=None, T=0.0, S_night=500.0):
    c = {k: run(k, v, T, S_night) for k in ("S0", "S3", "S4")}
    c["half1"] = run("S0", v, T, S_night, *HALVES[0]); c["half2"] = run("S0", v, T, S_night, *HALVES[1]); return c


out = {"base (payout_24 adopted)": cell()}; b = out["base (payout_24 adopted)"]
print("base", {k: b[k] for k in ("S0", "S3", "S4")}, "| halves $", b["half1"]["withdrawn_24m"], b["half2"]["withdrawn_24m"], flush=True)
cells = [("A1", 0.0, 500.0), ("A1", 1000.0, 500.0), ("A2", 0.0, 500.0), ("A2", 1000.0, 500.0), ("A4", 0.0, 500.0), ("A4", 1000.0, 500.0), (None, 0.0, 1000.0)]
for v, T, Sn in cells:
    name = f"{v} below ${int(T):,}" if v else "A3 overnight from $1,000"; c = out[name] = cell(v, T, Sn)
    c["eligible"] = bool(all(c[k]["closed_24m"] <= b[k]["closed_24m"] for k in ("S0", "S3", "S4")) and c["S0"]["near_miss"] <= 0.75 * b["S0"]["near_miss"]
                         and all(c[h]["withdrawn_24m"] >= 0.9 * b[h]["withdrawn_24m"] for h in ("half1", "half2")))
    s = c["S0"]
    print(f"{name:24s} S0 $ {s['withdrawn_24m']:>7} near {s['near_miss']:.3f} closed {s['closed_24m']:.3f} y1 {s['payouts_y1']} y2 {s['payouts_y2']} | S3 cl {c['S3']['closed_24m']:.3f} near {c['S3']['near_miss']:.3f} "
          f"| S4 cl {c['S4']['closed_24m']:.3f} near {c['S4']['near_miss']:.3f} | halves $ {c['half1']['withdrawn_24m']} / {c['half2']['withdrawn_24m']} | elig {c['eligible']}", flush=True)
el = {k: v for k, v in out.items() if isinstance(v, dict) and v.get("eligible")}
out["selected"] = min(el, key=lambda k: el[k]["S0"]["near_miss"]) if el else None
print("selected:", out["selected"])
(pl.ROOT / "reports/PAYOUT_25_EARLY_PROTECTION_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
