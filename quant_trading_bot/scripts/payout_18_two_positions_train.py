"""payout_18 (Claude, 2026-11-10): allow a second concurrent intraday position in the payout book. TRAINING 2010-23 only.

PRE-DECLARED (before results). Diagnostic (same training trades, no grid): the 1-position research router drops 515 of 2,353 eligible v5.2
trades; they net +$772/yr (+11% on the routed book's $6,745/yr), all on days the book already trades (no new days), so the gain can only come
from more >= $150 days and more profit on existing days.
Base R = v5.2 (1 micro, 2 on gap-continuation Crabel, skip stop risk > $300/micro, $400 account stop on realised P&L) + overnight dip
0.55% stop staged at a $500 balance; $1,000 buffer; static -$2,000; $1k DLL.
Router change: accept a trade if fewer than 2 accepted trades are open at its decision time and none of them is the same sleeve (research
[entry, exit) semantics, ranked by decision then priority as before). Cells: P2 always | P2 only while the balance at the prior close >= $500.
ADOPT only if: S0 breach <= 2%, S3 breach <= 5%, S4 breach <= base R's, 0 days <= -$1,000, S0 payouts >= base + 0.3, and payouts up vs base in
both halves of the starts (2010-07..2016-12, 2017-01..2023-01). Caveat stated in advance: the account model checks the floor on realised
daily P&L; with two open stops the intraday mark can be up to two stops deep (each stop-capped), slightly more than the 1-position book.
"""
import json
import numpy as np, pandas as pd
import payout_lib as pl
from payout_17_bond_filter_train import fast_day_series, scenario as sc17, N0, base_intra, stop_loss_level   # same data + stresses

H1, H2 = ("2010-07-01", "2016-12-01"), ("2017-01-01", "2023-01-01")


def route2(df, maxpos=2):
    acc = []; keep = []
    for r in df.sort_values(["dec", "prio"]).itertuples():
        open_ = [a for a in acc[-12:] if a[0] <= r.dec < a[1]]
        if len(open_) >= maxpos or any(a[2] == r.sleeve for a in open_): continue
        acc.append((r.tin, r.tout, r.sleeve)); keep.append(r.Index)
    return df.loc[keep]


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
    for tag, rt in (("P1", pl.route), ("P2", route2)):
        i = rt(e)[["tin", "tout", "net_today"]]
        SER[(kind, tag, False)] = fast_day_series(i).to_dict()
        SER[(kind, tag, True)] = fast_day_series(pd.concat([i, n], ignore_index=True)).to_dict()


def evaluate(kind, S_p2, S_night=500.0, C=1000.0, start_from="2010-07-01", start_to="2023-01-01"):
    ser = {k[1:]: v for k, v in SER.items() if k[0] == kind}
    days = sorted(set().union(*[set(s) for s in ser.values()])); idx = pd.to_datetime(pd.Series(days).astype(str)).to_numpy(); res = []
    for s0 in pd.date_range(start_from, start_to, freq="MS"):
        a = int(np.searchsorted(idx, np.datetime64(s0))); b = int(np.searchsorted(idx, np.datetime64(s0 + pd.DateOffset(months=12))))
        bal = 0.0; good = 0; pays = 0; breach = False; dll = 0; q = 0
        for x in days[a:b]:
            p = ser[("P2" if bal >= S_p2 else "P1", bal >= S_night)].get(x, 0.0)
            dll += p <= -1000; bal += max(p, -1000.0)
            if bal <= -2000.0: breach = True; break
            good += p >= 150; q += p >= 150
            if good >= 5 and bal - C > 0: pays += 1; bal = C; good = 0
        res.append((pays, breach, dll, q))
    r = pd.DataFrame(res, columns=["pays", "breach", "dll", "q"])
    return dict(payouts_12m_mean=round(float(r.pays.mean()), 2), payouts_12m_p10=float(r.pays.quantile(.1)), p_breach_12m=round(float(r.breach.mean()), 3),
                dll_days=int(r.dll.sum()), days_ge150_12m=round(float(r.q.mean()), 1))


def cell(S_p2):
    return dict(S0=evaluate("S0", S_p2), S3=evaluate("S3", S_p2), S4=evaluate("S4", S_p2),
                H1=evaluate("S0", S_p2, start_from=H1[0], start_to=H1[1]), H2=evaluate("S0", S_p2, start_from=H2[0], start_to=H2[1]))


out = {"base R (P1)": cell(1e12)}
b = out["base R (P1)"]; print("base", b, flush=True)
for name, S in (("P2 always", 0.0), ("P2 above $500", 500.0)):
    c = out[name] = cell(S)
    c["adopt"] = bool(c["S0"]["p_breach_12m"] <= 0.02 and c["S3"]["p_breach_12m"] <= 0.05 and c["S4"]["p_breach_12m"] <= b["S4"]["p_breach_12m"]
                      and c["S0"]["dll_days"] == 0 and c["S0"]["payouts_12m_mean"] >= b["S0"]["payouts_12m_mean"] + 0.3
                      and c["H1"]["payouts_12m_mean"] > b["H1"]["payouts_12m_mean"] and c["H2"]["payouts_12m_mean"] > b["H2"]["payouts_12m_mean"])
    print(name, c, flush=True)
(pl.ROOT / "reports/PAYOUT_18_TWO_POSITIONS_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
