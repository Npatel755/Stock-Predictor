"""payout_24 (Claude, 2026-11-10): size ladder x cushion on the $50K Static Daily Payouts+ funded account. TRAINING 2010-23 only.

PRE-DECLARED (before results). Account as payout_23 (static -$2,000 until the first payout, then $0; DLL $1,000; daily payouts of profit
above the kept cushion K, $250-$1,500, one per trading day, net profit since the last payout > 0). Book = base R (v5.2 + overnight dip staged
at a $500 balance). Change: every contract x m, where m steps up with the balance at the prior close: 1x below $4,000, 2x from $4,000, 3x from
$6,000, capped at M_MAX. Safety rules at size m (fixed, payout_19): account stop min($400 x m, $700); a trade (or the overnight leg) whose total
stop risk at size m exceeds $900 is skipped before routing.
Cells: K in {$4,000, $6,000, $8,000} x M_MAX in {1, 2, 3} = 9. 24-month windows (139 monthly starts 2010-07..2022-01), stresses S0 / S3 / S4.
OBJECTIVE: mean dollars withdrawn over 24 months (S0). ELIGIBLE: closed within 24 months S0 <= 3%, S3 <= 8%, S4 <= 15%; S0 payouts >= 8 in
year 1 and >= 8 in year 2. ADOPT the best eligible cell only if its 24-month dollars beat the K=$4,000 / 1x reference by >= 15% AND it beats
the reference in both halves of the starts (2010-07..2016-06, 2016-07..2022-01). Also reported: a conservative closure count that assumes
each day's largest trade hits its full stop before any gain (Topstep checks the floor on unrealised P&L in real time).
"""
import json
import numpy as np, pandas as pd
import payout_lib as pl
from payout_17_bond_filter_train import fast_day_series, scenario as sc17, N0, base_intra, stop_loss_level

NIGHT_RISK = abs(stop_loss_level)
HALVES = (("2010-07-01", "2016-06-01"), ("2016-07-01", "2022-01-01"))


def stressed_intra(kind):
    d = base_intra.copy()
    if kind in ("S1", "S3"): d["net_today"] -= 1.0 * d.inst.map(pl.MULT) * d.n_contracts
    if kind in ("S2", "S3"):
        avg = d.groupby("sleeve").net_today.transform("mean"); d["net_today"] -= 0.25 * avg.clip(lower=0)
    if kind == "S4": d["risk_today"] *= 1.5; d["net_today"] *= 1.5
    return d[d.risk_today <= 300.0]


SER, RISK = {}, {}
for kind in ("S0", "S3", "S4"):
    e = stressed_intra(kind); _, n = sc17(kind, N0)
    for m in (1, 2, 3):
        em = e[e.risk_today * e.n_contracts * m <= (900.0 if m > 1 else 1e9)]
        r = pl.route(em)
        i = r[["tin", "tout", "net_today"]].assign(net_today=lambda x: x.net_today * m)
        night_ok = m == 1 or NIGHT_RISK * (1.5 if kind == "S4" else 1) * m <= 900.0
        nm = n.assign(net_today=n.net_today * m) if night_ok else n.iloc[0:0]
        stop = 400.0 if m == 1 else min(400.0 * m, 700.0)
        SER[(kind, m, False)] = fast_day_series(i, stop).to_dict()
        SER[(kind, m, True)] = fast_day_series(pd.concat([i, nm], ignore_index=True), stop).to_dict()
        rk = (r.risk_today * r.n_contracts * m).groupby(r.tout.dt.date).max()
        if night_ok:
            rn = pd.Series(NIGHT_RISK * (1.5 if kind == "S4" else 1) * m, index=pd.Index(n.tout.dt.date)).groupby(level=0).max()
            rk = pd.concat([rk, rn]).groupby(level=0).max()
        RISK[(kind, m)] = rk.to_dict()


def run(kind, K, M_MAX, start_from="2010-07-01", start_to="2022-01-01"):
    keys = [k for k in SER if k[0] == kind]
    days = sorted(set().union(*[set(SER[k]) for k in keys])); ix = pd.to_datetime(pd.Series(days).astype(str)).to_numpy(); rows = []
    for s0 in pd.date_range(start_from, start_to, freq="MS"):
        a = int(np.searchsorted(ix, np.datetime64(s0))); b = int(np.searchsorted(ix, np.datetime64(s0 + pd.DateOffset(months=24))))
        cut = np.datetime64(s0 + pd.DateOffset(months=12))
        bal = 0.0; paid = False; since = 0.0; p1 = p2 = 0; usd = 0.0; closed = False; cons = False
        for x, t in zip(days[a:b], ix[a:b]):
            m = min(M_MAX, 3 if bal >= 6000 else 2 if bal >= 4000 else 1)
            floor = 0.0 if paid else -2000.0
            if not cons and bal - RISK[(kind, m)].get(x, 0.0) <= floor: cons = True
            p = max(SER[(kind, m, bal >= 500.0)].get(x, 0.0), -1000.0); bal += p; since += p
            if bal <= floor: closed = True; cons = True; break
            if (since > 0 or not paid) and bal - K >= 250.0:
                w = min(1500.0, bal - K); bal -= w; usd += w; paid = True; since = 0.0
                if t < cut: p1 += 1
                else: p2 += 1
        rows.append((p1, p2, usd, closed, cons))
    r = pd.DataFrame(rows, columns=["p1", "p2", "usd", "closed", "cons"])
    return dict(withdrawn_24m=round(float(r.usd.mean()), 0), payouts_y1=round(float(r.p1.mean()), 2), payouts_y2=round(float(r.p2.mean()), 2),
                payouts_y1_p10=float(r.p1.quantile(.1)), closed_24m=round(float(r.closed.mean()), 3), closed_24m_conservative=round(float(r.cons.mean()), 3))


out = {}
for K in (4000.0, 6000.0, 8000.0):
    for M in (1, 2, 3):
        c = {k: run(k, K, M) for k in ("S0", "S3", "S4")}
        c["half1"] = run("S0", K, M, *HALVES[0]); c["half2"] = run("S0", K, M, *HALVES[1])
        c["eligible"] = bool(c["S0"]["closed_24m"] <= 0.03 and c["S3"]["closed_24m"] <= 0.08 and c["S4"]["closed_24m"] <= 0.15
                             and c["S0"]["payouts_y1"] >= 8 and c["S0"]["payouts_y2"] >= 8)
        out[f"keep ${int(K):,} | max {M}x"] = c
        s = c["S0"]
        print(f"keep ${int(K):,} | max {M}x  S0 $24m {s['withdrawn_24m']:>7} pays y1 {s['payouts_y1']:5} (p10 {s['payouts_y1_p10']}) y2 {s['payouts_y2']:5} "
              f"closed {s['closed_24m']:.3f} (cons {s['closed_24m_conservative']:.3f}) | S3 $ {c['S3']['withdrawn_24m']:>6} cl {c['S3']['closed_24m']:.3f} "
              f"| S4 $ {c['S4']['withdrawn_24m']:>6} cl {c['S4']['closed_24m']:.3f} | halves $ {c['half1']['withdrawn_24m']} / {c['half2']['withdrawn_24m']} | elig {c['eligible']}", flush=True)
ref = out["keep $4,000 | max 1x"]
el = {k: v for k, v in out.items() if v["eligible"]}
best = max(el, key=lambda k: el[k]["S0"]["withdrawn_24m"]) if el else None
adopt = bool(best and el[best]["S0"]["withdrawn_24m"] >= 1.15 * ref["S0"]["withdrawn_24m"]
             and all(el[best][h]["withdrawn_24m"] > ref[h]["withdrawn_24m"] for h in ("half1", "half2")))
out["summary"] = dict(best_eligible=best, adopt=adopt, reference="keep $4,000 | max 1x")
print(out["summary"])
(pl.ROOT / "reports/PAYOUT_24_STATIC_DAILY_SIZING_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
