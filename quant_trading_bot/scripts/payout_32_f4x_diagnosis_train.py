"""payout_32 (Claude, 2026-11-11): DIAGNOSIS of Fortress 4X on the intraday funded simulator. TRAINING only, no strategy change.

Nick: "see if you can improve it". Before changing anything (failure-learning): where does F4X lose money on funded_intraday_core?
1. DLL-liquidated days per table: triggered by ONE open trade (exact) or by STACKED open trades (depends on the core's conservative
   assumption that open trades' worst points coincide); night leg involved?; counterfactual day P&L with no DLL (cost of the liquidation).
2. Closed windows (S3 / S4): when, at what multiplier, and which days drove them.
3. Inactivity: longest calendar gap between trading days (Topstep XFA inactivity rule, flagged by Codex).
Exploratory: nothing here is selected or tuned.
"""
import json, sys, time
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/payout_30_intraday_funded_train.py").read_text(encoding="utf-8").split("STACK = pd.concat")[0]
G = dict(__name__="payout_32", __file__=str(ROOT / "scripts/payout_30_intraday_funded_train.py")); exec(src, G)
pl, fc, prep, base, STOP = G["pl"], G["fc"], G["prep"], G["base"], G["STOP"]
t0 = time.time()


def sim_day_detail(a, b, per, mae, q, prio, stop, dll=1000.0):
    acc = []; qs = {}; w = 0.0
    for j in range(len(per)):
        if q[j] < 1: continue
        done = [i for i in acc if b[i] < a[j] or (b[i] == a[j] and a[i] < a[j])]
        realised = float(sum(per[i] * qs[i] for i in done))
        if realised <= -stop: continue
        opn = [i for i in acc if i not in done]
        omae = float(sum(min(0.0, mae[i]) * qs[i] for i in opn)); nm = min(0.0, mae[j]) * float(q[j])
        worst = realised + omae + nm; w = min(w, worst)
        if worst <= -dll:
            return dict(hit=True, n_open=len(opn), realised=realised, open_mae=omae, new_mae=nm,
                        night=bool(any(prio[i] == 99 for i in opn) or prio[j] == 99), single_exact=len(opn) == 0, n_acc=len(acc), overlap=len(opn) > 0)
        acc.append(j); qs[j] = float(q[j])
    return dict(hit=False, n_open=0, realised=0.0, open_mae=0.0, new_mae=0.0, night=False, single_exact=False, n_acc=len(acc),
                overlap=any(a[k] < b[i] and i != k for i in acc for k in acc if a[i] <= a[k]))


def tables_detail(intra, nights, nr, m, night):
    qi = intra.n.to_numpy(float) if m == 1 else np.minimum(m * intra.n.to_numpy(float), np.floor(900.0 / intra.risk.to_numpy(float)))
    qn = 1.0 if m == 1 else float(min(m, int(900.0 // nr)))
    parts = [intra.assign(q=qi)]
    if night and qn >= 1: parts.append(nights.assign(q=qn))
    t = pd.concat(parts, ignore_index=True).sort_values(["a", "prio"], kind="stable")
    rows = []
    for d, g in t.groupby("day", sort=False):
        A, B, P, M, Q, PR = (g[c].to_numpy() for c in ("a", "b", "per", "mae", "q", "prio"))
        det = sim_day_detail(A, B, P.astype(float), M.astype(float), Q.astype(float), PR, STOP(m))
        p_cf = fc.sim_day(A, B, P.astype(float), M.astype(float), g.risk.to_numpy(float), Q.astype(float), STOP(m), dll=1e12)[0]
        rows.append(dict(day=d, p_nodll=p_cf, n_trades=len(g), **det))
    return pd.DataFrame(rows)


out = dict(validation_accessed=False, test_accessed=False, dll={}, closures={}, inactivity={})
PREP = {k: prep(base, k) for k in ("S0", "S3", "S4")}
for kind in ("S0", "S3", "S4"):
    intra, nights, nr = PREP[kind]
    for m, night in ((1, False), (1, True), (2, True), (3, True), (4, True)):
        d = tables_detail(intra, nights, nr, m, night)
        h = d[d.hit == True]
        nh = d[d.hit == False]
        out["dll"][f"{kind}_m{m}_n{int(night)}"] = dict(
            days=len(d), hit_days=len(h), single_exact=int(h.single_exact.sum()), stacked=int((~h.single_exact.astype(bool)).sum()),
            night_involved=int(h.night.sum()), mean_p_nodll_on_hits=round(float(h.p_nodll.mean()), 1) if len(h) else None,
            hits_that_end_positive_nodll=int((h.p_nodll > 0).sum()), cost_vs_nodll=round(float((h.p_nodll + 1000.0).sum()), 0),
            cost_stacked_only=round(float((h[~h.single_exact.astype(bool)].p_nodll + 1000.0).sum()), 0),
            overlap_days_no_hit=int(nh.overlap.sum()))
        print(kind, m, night, out["dll"][f"{kind}_m{m}_n{int(night)}"], flush=True)

# closed windows: replay F4X with a day log
F4X = dict(ladder=((0, 1), (4000, 2), (4800, 3), (6500, 4)), K=8500.0)


def replay_log(tab, ladder, K, a0="2010-07-01", a1="2022-01-01", months=24):
    days = sorted(set().union(*[set(v) for v in tab.values()]))
    ix = pd.to_datetime(pd.Series(days).astype(str)).to_numpy(); res = []
    for s0 in pd.date_range(a0, a1, freq="MS"):
        a = int(np.searchsorted(ix, np.datetime64(s0))); b = int(np.searchsorted(ix, np.datetime64(s0 + pd.DateOffset(months=months))))
        bal = 0.0; paid = 0; since = 0.0; peak = 0.0; log = []
        for j in range(a, b):
            x = days[j]; m = max((mm for th, mm in ladder if bal >= th), default=1); floor = 0.0 if paid else -2000.0
            p, w, hit = tab[(m, bal >= 500.0)].get(x, (0.0, 0.0, False))
            log.append((str(x), m, round(bal, 0), round(p, 0), round(w, 0), bool(hit)))
            if bal + min(w, p) <= floor:
                res.append(dict(start=str(s0.date()), closed_on=str(x), days_in=j - a, m=m, paid=paid, peak=round(peak, 0), bal_before=round(bal, 0),
                                worst_day=round(min(w, p), 0), last20=log[-20:], big_losses=sorted([r for r in log if r[3] <= -400], key=lambda r: r[3])[:8]))
                break
            bal += p; since += p; peak = max(peak, bal)
            if (since > 0 or not paid) and bal - K >= 250.0:
                bal -= min(1500.0, bal - K); paid += 1; since = 0.0
    return res


for kind in ("S3", "S4"):
    tab = G["tables"](base, kind)
    cl = replay_log(tab, **F4X)
    out["closures"][kind] = cl
    print(kind, "closed", len(cl), [(c["start"], c["closed_on"], c["m"], c["paid"], c["peak"], c["bal_before"], c["worst_day"]) for c in cl], flush=True)

# inactivity: longest gap between trading days (intraday only; with the overnight leg)
intra, nights, _ = PREP["S0"]
for name, dd in (("intra_only", sorted(set(intra.day))), ("with_night", sorted(set(intra.day) | set(nights.day)))):
    s = pd.to_datetime(pd.Series(dd).astype(str)); g = s.diff().dt.days
    k = int(g.idxmax())
    out["inactivity"][name] = dict(max_gap_days=int(g.max()), ending=str(s.iloc[k].date()), gaps_over_20=int((g > 20).sum()), gaps_over_30=int((g > 30).sum()))
print("inactivity", out["inactivity"], flush=True)
(ROOT / "reports/PAYOUT_32_F4X_DIAGNOSIS_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
print("saved", f"{time.time() - t0:.0f}s", flush=True)
