"""payout_19 (Claude, 2026-11-10): plain size multiplier for the payout book ("can't you increase risk?"). TRAINING 2010-23 only.

PRE-DECLARED (before results). Base R = v5.2 (1 micro, 2 on gap-continuation Crabel, skip stop risk > $300 per micro, research routing,
$400 account stop on realised same-day P&L) + overnight dip 0.55% stop staged at a $500 balance; static -$2,000; $1k DLL; $1,000 buffer;
151 monthly 12-month starts. Change: every contract (intraday and overnight) x m, m in {2, 3}, either always or only while the balance at the
prior close is >= $1,000 (house money: above the buffer). Fixed safety rules at size m (not tuned): account stop = min($400 x m, $700) so a
second loss cannot reach the $1k DLL; a trade whose total stop risk at size m exceeds $900 is skipped (before routing, like v5.2's rule).
Stresses as payout_13 (S3 costs +2 ticks/side and edge -25%; S4 volatility x1.5). ADOPT only if: S0 breach <= 2%, S3 breach <= 5%, S4 breach
<= base R's, 0 days <= -$1,000, S0 payouts >= base + 0.5, and payouts up vs base in both halves of the starts. 4 cells.
"""
import json
import numpy as np, pandas as pd
import payout_lib as pl
from payout_17_bond_filter_train import fast_day_series, scenario as sc17, N0, base_intra, stop_loss_level

H1, H2 = ("2010-07-01", "2016-12-01"), ("2017-01-01", "2023-01-01")
NIGHT_RISK = abs(stop_loss_level)                      # stopped-night loss per micro


def stressed_intra(kind):
    d = base_intra.copy()
    if kind in ("S1", "S3"): d["net_today"] -= 1.0 * d.inst.map(pl.MULT) * d.n_contracts
    if kind in ("S2", "S3"):
        avg = d.groupby("sleeve").net_today.transform("mean"); d["net_today"] -= 0.25 * avg.clip(lower=0)
    if kind == "S4": d["risk_today"] *= 1.5; d["net_today"] *= 1.5
    return d[d.risk_today <= 300.0]


SER = {}
for kind in ("S0", "S3", "S4"):
    e = stressed_intra(kind); _, n = sc17(kind, N0)
    for m in (1, 2, 3):
        em = e[e.risk_today * e.n_contracts * m <= (900.0 if m > 1 else 1e9)]
        i = pl.route(em)[["tin", "tout", "net_today"]].assign(net_today=lambda x: x.net_today * m)
        nm = n.assign(net_today=n.net_today * m) if (m == 1 or NIGHT_RISK * (1.5 if kind == "S4" else 1) * m <= 900.0) else n.iloc[0:0]
        stop = 400.0 if m == 1 else min(400.0 * m, 700.0)
        SER[(kind, m, False)] = fast_day_series(i, stop).to_dict()
        SER[(kind, m, True)] = fast_day_series(pd.concat([i, nm], ignore_index=True), stop).to_dict()


def evaluate(kind, m, S_big, S_night=500.0, C=1000.0, start_from="2010-07-01", start_to="2023-01-01"):
    ser = {k[1:]: v for k, v in SER.items() if k[0] == kind}
    days = sorted(set().union(*[set(s) for s in ser.values()])); idx = pd.to_datetime(pd.Series(days).astype(str)).to_numpy(); res = []
    for s0 in pd.date_range(start_from, start_to, freq="MS"):
        a = int(np.searchsorted(idx, np.datetime64(s0))); b = int(np.searchsorted(idx, np.datetime64(s0 + pd.DateOffset(months=12))))
        bal = 0.0; good = 0; pays = []; breach = False; dll = 0; q = 0
        for x in days[a:b]:
            p = ser[(m if bal >= S_big else 1, bal >= S_night)].get(x, 0.0)
            dll += p <= -1000; bal += max(p, -1000.0)
            if bal <= -2000.0: breach = True; break
            good += p >= 150; q += p >= 150
            if good >= 5 and bal - C > 0: pays.append(bal - C); bal = C; good = 0
        res.append((len(pays), breach, dll, q, float(np.sum(pays))))
    r = pd.DataFrame(res, columns=["pays", "breach", "dll", "q", "paid"])
    return dict(payouts_12m_mean=round(float(r.pays.mean()), 2), payouts_12m_p10=float(r.pays.quantile(.1)), p_breach_12m=round(float(r.breach.mean()), 3),
                dll_days=int(r.dll.sum()), days_ge150_12m=round(float(r.q.mean()), 1), withdrawn_12m_mean=round(float(r.paid.mean()), 0))


def cell(m, S):
    return dict(S0=evaluate("S0", m, S), S3=evaluate("S3", m, S), S4=evaluate("S4", m, S),
                H1=evaluate("S0", m, S, start_from=H1[0], start_to=H1[1]), H2=evaluate("S0", m, S, start_from=H2[0], start_to=H2[1]))


out = {"base R (1x)": cell(1, 0.0)}; b = out["base R (1x)"]; print("base", b, flush=True)
for m in (2, 3):
    for tag, S in (("always", -1e12), ("above $1,000", 1000.0)):
        name = f"{m}x {tag}"; c = out[name] = cell(m, S)
        c["adopt"] = bool(c["S0"]["p_breach_12m"] <= 0.02 and c["S3"]["p_breach_12m"] <= 0.05 and c["S4"]["p_breach_12m"] <= b["S4"]["p_breach_12m"]
                          and c["S0"]["dll_days"] == 0 and c["S0"]["payouts_12m_mean"] >= b["S0"]["payouts_12m_mean"] + 0.5
                          and c["H1"]["payouts_12m_mean"] > b["H1"]["payouts_12m_mean"] and c["H2"]["payouts_12m_mean"] > b["H2"]["payouts_12m_mean"])
        print(name, c, flush=True)
(pl.ROOT / "reports/PAYOUT_19_SIZE_MULTIPLIER_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
