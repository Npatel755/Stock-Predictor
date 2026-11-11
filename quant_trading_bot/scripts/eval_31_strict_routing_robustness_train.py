"""eval_31 (Claude, 2026-11-11): is STRICT routing's gain (eval_30: 54.4 / 61.1 vs 49.7 / 59.4) real or an artifact of v2's conservative
overlap assumption? TRAINING 2010-23 only. Diagnostic, nothing chosen.

v2 adds every OPEN trade's full MAE to the worst case of the next entry (assumes overlapping trades hit their worst points together).
STRICT routing has no overlaps, so it never pays that charge. If the charge is too harsh, INC is understated and STRICT's gain shrinks.
PRE-DECLARED checks:
  1. INC and STRICT under v2_OPT: identical to v2 except open trades add NOTHING to the worst case (optimistic bound).
  2. INC and STRICT under v1 (the old look-ahead simulator) for reference.
  3. Overlap anatomy of INC: entries made while another trade is open - same instrument family / same direction shares, and the realised
     P&L of overlapping pairs (both trades' outcome correlation).
Reading: if STRICT >= INC + 1 in both halves even under v2_OPT, the gain does not depend on the overlap assumption.
"""
import os, json
os.environ["TRAIN_MINI_UNTIL"] = "2019-05-06"
import numpy as np, pandas as pd
from pathlib import Path
import eval_harness as eh

ROOT = Path(__file__).resolve().parents[1]
H = eh.Harness()


def route_strict(df):
    keep = []; until = None
    for r in df.sort_values(["dec", "prio"], kind="stable").itertuples():
        if until is not None and r.dec < until: continue
        until = r.tout if until is None else max(until, r.tout); keep.append(r.Index)
    return df.loc[keep]


r = route_strict(H.PRE[H.PRE.risk_today <= 300.0]).copy(); r["per_micro"] = r.net_today / r.n_contracts
nights = H.NIGHTS.assign(n_contracts=1.0, risk_today=H.NIGHT_RISK, sleeve="NIGHT")[H.COLS + ["sleeve"]]
STRICT = pd.concat([r[H.COLS + ["sleeve"]], nights], ignore_index=True).assign(noise=False)


def sim_opt(x, k, nsize="F1"):
    a, b, per, mae, n, risk, nz = x
    mae = np.minimum(mae, per); cap = np.floor(900.0 / risk); q = np.minimum(k * n, cap)
    stop = 400.0 if np.all(q <= n) else 700.0; acc = []; w = 0.0; dll = False
    for j in range(len(per)):
        if q[j] < 1: continue
        done = [i for i in acc if b[i] < a[j] or (b[i] == a[j] and a[i] < a[j])]
        realised = sum(per[i] * q[i] for i in done)
        if realised <= -stop or realised <= -1000.0: break
        worst = realised + mae[j] * q[j]
        w = min(w, worst)
        if worst <= -1000.0: dll = True; break
        acc.append(j)
    p = -1000.0 if dll else max(sum(per[i] * q[i] for i in acc), -1000.0)
    return p, min(w, p)


def rate(book, sim):
    f = book[H.COLS].assign(noise=False).sort_values(["tin", "tout", "per_micro"], kind="stable").reset_index(drop=True)
    PD = H._per_day(f); td = sorted(PD); tix = pd.to_datetime(pd.Series(td).astype(str)).to_numpy()
    DAY = {k: {d: sim(PD[d], float(k)) for d in td} for k in (1, 2, 3, 5)}
    return dict(h1=H._evaluate(DAY, H.A, td, tix, H.DEF_END), h2=H._evaluate(DAY, H.B, td, tix, H.DEF_END))


out = {}
for nm, bk in (("INC", H.BOOK), ("STRICT", STRICT)):
    out[nm] = dict(v2=H.pass_rate(book=bk, v2=True), v2_opt=rate(bk, sim_opt), v1=H.pass_rate(book=bk))
    print(nm, {k: (v["h1"]["pass_"], v["h2"]["pass_"], v["h1"]["fail"], v["h2"]["fail"]) for k, v in out[nm].items()}, flush=True)

# overlap anatomy of the INC book (intraday routed trades only)
R = H.pl.route(H.PRE[H.PRE.risk_today <= 300.0]).copy().sort_values("tin", kind="stable").reset_index(drop=True)
R["day"] = R.tin.dt.date; R["per_micro"] = R.net_today / R.n_contracts; pairs = []
for d, g in R.groupby("day"):
    g = g.reset_index(drop=True)
    for j in range(1, len(g)):
        for i in range(j):
            if g.tout[i] > g.tin[j]:
                pairs.append(dict(same_side=bool(g.side[i] == g.side[j]), same_inst=bool(g.inst[i] == g.inst[j]), p_i=g.per_micro[i], p_j=g.per_micro[j],
                                  both_lose=bool(g.per_micro[i] < 0 and g.per_micro[j] < 0)))
P = pd.DataFrame(pairs)
out["overlaps"] = dict(pairs=len(P), same_side=round(float(P.same_side.mean()), 3), same_inst=round(float(P.same_inst.mean()), 3),
                       corr_pnl=round(float(P.p_i.corr(P.p_j)), 3), both_lose=round(float(P.both_lose.mean()), 3),
                       mean_second_trade_per_micro=round(float(P.p_j.mean()), 1), mean_all_trades_per_micro=round(float(R.per_micro.mean()), 1))
print("overlaps", out["overlaps"], flush=True)
(ROOT / "reports/EVAL_31_STRICT_ROUTING_ROBUSTNESS_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
print("saved", flush=True)
