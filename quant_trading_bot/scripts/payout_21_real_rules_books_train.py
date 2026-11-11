"""payout_21 (Claude, 2026-11-10): books x withdrawal policies under Topstep's real XFA rules (standard path). TRAINING 2010-23 only.

PRE-DECLARED (before results). Account model = payout_20 standard path: balance from $0; MLL -$2,000 trailing the end-of-day balance, locked
at $0 from a $2,000 balance and $0 permanently after the first payout (checked on realised day P&L: optimistic by intraday open loss); DLL
$1,000 pauses the day; 5 days >= $150 since the last payout (request day excluded), profit since last payout > 0; payout <= 50% of balance,
<= $2,000, >= $125.
Books (all 1 micro; 2 on gap-continuation Crabel; skip stop risk > $300/micro; $400 account stop on realised same-day P&L; overnight dip 0.55%
stop): B0 base R (v5.2, overnight while balance >= $500) | B1 v5.2, overnight every night | B2 v5.2 + TRD30_D + BRK30 (payout_6's replicated
sleeves, ranked after v5.2's), overnight >= $500 | B3 B2 with overnight every night | B4 B2 with up to 2 concurrent intraday positions (never the
same sleeve; Nick's "morning + afternoon + overnight at once"), overnight >= $500.
Withdrawal policies: keep K = $1,500 | $2,500 | $3,500 (take min(50%, $2,000, balance - K)); fixed $X = $125 | $250 | $500 per payout while
keeping >= $2,000. 30 cells. Stresses S0 / S3 / S4 as payout_13.
SELECTION: eligible = S0 closed <= 3%, S3 closed <= 8%, S4 closed <= 15% (12-month windows). Pick the most S0 payouts; it must beat B0's best
eligible cell in BOTH halves of the starts (2010-07..2016-12, 2017-01..2023-01). Report whether 8 payouts per 12 months is reached.
"""
import json
import numpy as np, pandas as pd
import payout_lib as pl
from payout_17_bond_filter_train import fast_day_series, scenario as sc17, N0, base_intra
from payout_18_two_positions_train import route2

H1, H2 = ("2010-07-01", "2016-12-01"), ("2017-01-01", "2023-01-01")

ep, bars_for, START, _ = pl.engine()
EXTRA = {"TRD30_D": (dict(ep._AG_TRD30_D, name="AG_TRD30_D_1c"), 4), "BRK30": (dict(ep._AG_BRK30, name="AG_BRK30_1c"), 5)}
ext = pd.concat([pl.price_normalize(pl.sleeve_trades(ep, bars_for, START, sl, prio, True)) for sl, prio in EXTRA.values()], ignore_index=True)
ext["n_contracts"] = 1.0
ALL = pd.concat([base_intra, ext[base_intra.columns]], ignore_index=True)
print("extra sleeve trades:", ext.groupby("sleeve").size().to_dict(), flush=True)


def stressed(df, kind):
    d = df.copy()
    if kind in ("S1", "S3"): d["net_today"] -= 1.0 * d.inst.map(pl.MULT) * d.n_contracts
    if kind in ("S2", "S3"):
        avg = d.groupby("sleeve").net_today.transform("mean"); d["net_today"] -= 0.25 * avg.clip(lower=0)
    if kind == "S4": d["risk_today"] *= 1.5; d["net_today"] *= 1.5
    return d[d.risk_today <= 300.0]


BOOKS = {"B0": (False, pl.route, 500.0), "B1": (False, pl.route, -1e12), "B2": (True, pl.route, 500.0), "B3": (True, pl.route, -1e12),
         "B4": (True, route2, 500.0)}
SER = {}
for kind in ("S0", "S3", "S4"):
    _, n = sc17(kind, N0)
    for b, (extra, rt, _) in BOOKS.items():
        i = rt(stressed(ALL if extra else base_intra, kind))[["tin", "tout", "net_today"]]
        SER[(kind, b)] = {False: fast_day_series(i).to_dict(), True: fast_day_series(pd.concat([i, n], ignore_index=True)).to_dict()}


def run(ser, S_night, policy, start_from="2010-07-01", start_to="2023-01-01"):
    kind, v = policy
    days = sorted(set(ser[False]) | set(ser[True])); idx = pd.to_datetime(pd.Series(days).astype(str)).to_numpy(); res = []
    for s0 in pd.date_range(start_from, start_to, freq="MS"):
        a = int(np.searchsorted(idx, np.datetime64(s0))); b = int(np.searchsorted(idx, np.datetime64(s0 + pd.DateOffset(months=12))))
        bal = 0.0; peak = 0.0; paid = False; pays = []; closed = False; cnt = 0; since = 0.0; skip = False; dll = 0; q = 0
        for x in days[a:b]:
            p = (ser[True] if bal >= S_night else ser[False]).get(x, 0.0); dll += p <= -1000; p = max(p, -1000.0)
            bal += p; since += p
            if bal <= (0.0 if paid else min(0.0, peak - 2000.0)): closed = True; break
            peak = max(peak, bal); q += p >= 150
            if skip: skip = False; continue
            cnt += p >= 150
            if cnt >= 5 and (since > 0 or not paid):
                if kind == "keep": w = min(0.5 * bal, 2000.0, bal - v)
                else: w = v if (bal - v >= 2000.0 and 0.5 * bal >= v) else 0.0
                if w >= 125.0: pays.append(w); bal -= w; paid = True; cnt = 0; since = 0.0; skip = True
        res.append((len(pays), closed, float(sum(pays)), dll, q))
    r = pd.DataFrame(res, columns=["pays", "closed", "paid", "dll", "q"])
    return dict(payouts_12m_mean=round(float(r.pays.mean()), 2), payouts_12m_p10=float(r.pays.quantile(.1)), closed_12m=round(float(r.closed.mean()), 3),
                withdrawn_12m_mean=round(float(r.paid.mean()), 0), days_ge150_12m=round(float(r.q.mean()), 1), dll_days=int(r.dll.sum()))


POL = {"keep $1,500": ("keep", 1500.0), "keep $2,500": ("keep", 2500.0), "keep $3,500": ("keep", 3500.0),
       "fixed $125": ("fixed", 125.0), "fixed $250": ("fixed", 250.0), "fixed $500": ("fixed", 500.0)}
out = {}
for b, (_, _, S) in BOOKS.items():
    for pn, pol in POL.items():
        c = {k: run(SER[(k, b)], S, pol) for k in ("S0", "S3", "S4")}
        c["H1"] = run(SER[("S0", b)], S, pol, *H1); c["H2"] = run(SER[("S0", b)], S, pol, *H2)
        c["eligible"] = bool(c["S0"]["closed_12m"] <= 0.03 and c["S3"]["closed_12m"] <= 0.08 and c["S4"]["closed_12m"] <= 0.15)
        out[f"{b} | {pn}"] = c
        print(f"{b} | {pn:12s} S0 pays {c['S0']['payouts_12m_mean']:5} p10 {c['S0']['payouts_12m_p10']} closed {c['S0']['closed_12m']:.3f} $ {c['S0']['withdrawn_12m_mean']:>6} "
              f"d150 {c['S0']['days_ge150_12m']} | S3 cl {c['S3']['closed_12m']:.3f} | S4 cl {c['S4']['closed_12m']:.3f} | H1 {c['H1']['payouts_12m_mean']} H2 {c['H2']['payouts_12m_mean']} | elig {c['eligible']}", flush=True)
el = {k: v for k, v in out.items() if v["eligible"]}
b0 = {k: v for k, v in el.items() if k.startswith("B0")}
b0best = max(b0, key=lambda k: b0[k]["S0"]["payouts_12m_mean"]) if b0 else None
best = max(el, key=lambda k: el[k]["S0"]["payouts_12m_mean"]) if el else None
conf = bool(best and b0best and (best == b0best or (el[best]["H1"]["payouts_12m_mean"] > el[b0best]["H1"]["payouts_12m_mean"]
                                                    and el[best]["H2"]["payouts_12m_mean"] > el[b0best]["H2"]["payouts_12m_mean"])))
out["summary"] = dict(b0_best_eligible=b0best, best_eligible=best, best_confirmed_vs_b0_in_both_halves=conf,
                      reaches_8=bool(best and el[best]["S0"]["payouts_12m_mean"] >= 8.0))
print(out["summary"])
(pl.ROOT / "reports/PAYOUT_21_REAL_RULES_BOOKS_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
