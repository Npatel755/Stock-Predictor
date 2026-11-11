"""eval_30 (Claude, 2026-11-11): re-check the evaluation BOOK and the DP sizer under corrected day semantics (v2) and filled 2019 data.
TRAINING 2010-23 only.

Why (written before results): every evaluation decision since eval_5 was made with the v1 day simulator, whose look-ahead (an open
trade's final P&L could block the next entry) mostly flattered OVERLAPPING trades - and the posthoc_1c router lets trades overlap, and
adding sleeves adds overlaps. The book's make-up and eval_9's DP sizer were judged under v1. Re-judge them under v2.

PRE-DECLARED. Incumbent INC = harness book (v5.3 sleeves + MNQ_BRK_E_2c + MES_MOM_3c, posthoc routing, overnight leg) with DEF_END,
v2 semantics, TRAIN_MINI_UNTIL=2019-05-06: 49.7 / 59.4 (eval_29).
FAMILY A (book, rule DEF_END):  NO_<sleeve> for every sleeve in H.PRE | NO_NIGHT | STRICT (live strict_1c rule: skip a trade whose
  decision falls before the latest exit of any accepted trade - no overlaps) | CRAB_N1 (Crabel gap-continuation at 1 base micro, not 2).
FAMILY B (sizing, incumbent book): eval_9's DP (value iteration over balance x sessions left, i.i.d. bootstrap of the fold's v2 day
  outcomes per k, 55%-rule target shift) with K = (1,2,3,4) "DP4" and (1..6) "DP6"; fitted on one half's sessions, applied to the other.
Each family: 2-fold (pick on 2010-16 starts, report on 2017-23 and vice versa; DP: fit on one half, evaluate on the other). ADOPT only if
both out-of-fold halves >= INC + 1.0 (50.7 / 60.4). Also reported per A cell: v2 daily Sharpe at k3 (all sessions).
"""
import os, json
os.environ["TRAIN_MINI_UNTIL"] = "2019-05-06"
import numpy as np, pandas as pd
from pathlib import Path
import eval_harness as eh

ROOT = Path(__file__).resolve().parents[1]
H = eh.Harness(); pl = H.pl; DEF = H.DEF_END
print("PRE columns", list(H.PRE.columns), flush=True); print("sleeves", H.PRE.sleeve.value_counts().to_dict(), flush=True)


def route_strict(df):
    keep = []; until = None
    for r in df.sort_values(["dec", "prio"], kind="stable").itertuples():
        if until is not None and r.dec < until: continue
        until = r.tout if until is None else max(until, r.tout); keep.append(r.Index)
    return df.loc[keep]


def book_strict(pre):
    r = route_strict(pre[pre.risk_today <= 300.0]).copy(); r["per_micro"] = r.net_today / r.n_contracts
    nights = H.NIGHTS.assign(n_contracts=1.0, risk_today=H.NIGHT_RISK, sleeve="NIGHT")[H.COLS + ["sleeve"]]
    return pd.concat([r[H.COLS + ["sleeve"]], nights], ignore_index=True).assign(noise=False)


def daily_sr(book):
    f = book[H.COLS].assign(noise=False).sort_values(["tin", "tout", "per_micro"], kind="stable").reset_index(drop=True)
    PD = H._per_day(f); s = pd.Series({d: H.sim_day_v2(PD[d], 3.0)[0] for d in PD}).reindex(H.SESS, fill_value=0.0)
    return round(float(s.mean() / s.std()), 4)


out = {"A": {}, "B": {}}
A = {"INC": H.BOOK}
for s in sorted(H.PRE.sleeve.unique()): A[f"NO_{s}"] = H.build_book(H.PRE[H.PRE.sleeve != s])
A["NO_NIGHT"] = H.build_book(H.PRE, nights=False)
A["STRICT"] = book_strict(H.PRE)
c = H.PRE.copy(); m = c.sleeve.str.contains("CRABEL") & (c.n_contracts > 1)
c.loc[m, "net_today"] = c.loc[m, "net_today"] / c.loc[m, "n_contracts"]; c.loc[m, "n_contracts"] = 1.0
A["CRAB_N1"] = H.build_book(c); out["crabel_trades_resized"] = int(m.sum())
for nm, bk in A.items():
    r = H.pass_rate(book=bk, v2=True); r["trades"] = int(len(bk)); r["daily_sr_k3"] = daily_sr(bk)
    out["A"][nm] = r; print(nm, r, flush=True)
CA = out["A"]; INC = (CA["INC"]["h1"]["pass_"], CA["INC"]["h2"]["pass_"])
pA = max(CA, key=lambda k: CA[k]["h1"]["pass_"]); pB = max(CA, key=lambda k: CA[k]["h2"]["pass_"])
oA, oB = CA[pB]["h1"]["pass_"], CA[pA]["h2"]["pass_"]
out["A_result"] = dict(pick_h1=pA, pick_h2=pB, oof_h1=oA, oof_h2=oB, inc=INC, adopt=bool(oA >= INC[0] + 1.0 and oB >= INC[1] + 1.0))
print("A result", out["A_result"], flush=True)

# ---------------- family B: DP sizer on v2 day outcomes
f = H.BOOK[H.COLS].assign(noise=False).sort_values(["tin", "tout", "per_micro"], kind="stable").reset_index(drop=True)
PD = H._per_day(f); TD = sorted(PD); TIX = pd.to_datetime(pd.Series(TD).astype(str)).to_numpy()
KS = (1, 2, 3, 4, 5, 6)
DAY = {k: {d: H.sim_day_v2(PD[d], float(k)) for d in TD} for k in KS}
SESS = list(H.SESS); SIX = np.array(SESS, dtype=object)
G = np.arange(-2000.0, 4000.0 + 1e-9, 25.0); T = 64


def fit_dp(sessions, K):
    P = np.array([[DAY[k].get(s, (0.0, 0.0))[0] for k in K] for s in sessions]); W = np.array([[DAY[k].get(s, (0.0, 0.0))[1] for k in K] for s in sessions])
    V = np.zeros(len(G)); pol = np.full((T + 1, len(G)), K[0], int)
    for t in range(1, T + 1):
        best = np.full(len(G), -1.0); arg = np.full(len(G), K[0], int)
        for j, k in enumerate(K):
            p = P[:, j][:, None]; nb = G[None, :] + p
            fail = G[None, :] + np.minimum(W[:, j], P[:, j])[:, None] <= -2000.0
            tgt = np.maximum(4000.0, p / 0.55); passed = (nb >= tgt) & ~fail
            cont = np.interp(nb - (tgt - 4000.0), G, V)
            val = np.where(fail, 0.0, np.where(passed, 1.0, cont)).mean(axis=0)
            better = val > best + 1e-3; best = np.where(better, val, best); arg = np.where(better, k, arg)
        V = best.copy(); V[G <= -2000.0] = 0.0; V[G >= 4000.0] = 1.0; pol[t] = arg
    return pol


def evaluate(starts, rule):
    res = []
    for s in starts:
        end = (pd.Timestamp(s) + pd.Timedelta(days=90)).date(); i = int(np.searchsorted(TIX, np.datetime64(pd.Timestamp(s))))
        j0 = int(np.searchsorted(SIX, s, side="left")); j1 = int(np.searchsorted(SIX, end, side="left"))
        bal = 0.0; best = 0.0; o = "timeout"
        for d in TD[i:]:
            if d >= end: break
            sleft = j1 - int(np.searchsorted(SIX, d, side="left"))
            tgt = max(4000.0, best / 0.55); k = rule(bal, (d - s).days, tgt, sleft); p, w = DAY[k][d]
            if bal + min(w, p) <= -2000.0: o = "fail"; break
            bal += p; best = max(best, p)
            if bal >= max(4000.0, best / 0.55): o = "pass"; break
        res.append(o)
    x = pd.Series(res)
    return dict(pass_=round(100 * float((x == "pass").mean()), 1), fail=round(100 * float((x == "fail").mean()), 1),
                timeout=round(100 * float((x == "timeout").mean()), 1), n=len(x))


def dp_rule(pol):
    def rule(bal, day, tgt, sleft):
        b = bal - (tgt - 4000.0); t = int(min(max(sleft, 1), T)); i = int(np.clip(np.round((b + 2000.0) / 25.0), 0, len(G) - 1))
        return int(pol[t, i])
    return rule


chk = dict(h1=evaluate(H.A, DEF), h2=evaluate(H.B, DEF)); out["B"]["INC_check"] = chk; print("INC check", chk, flush=True)
SA = [s for s in SESS if s < eh.H1_END]; SB = [s for s in SESS if s >= eh.H1_END]
for name, K in (("DP4", (1, 2, 3, 4)), ("DP6", KS)):
    polA, polB = fit_dp(SA, K), fit_dp(SB, K)
    r = dict(oof_h1=evaluate(H.A, dp_rule(polB)), oof_h2=evaluate(H.B, dp_rule(polA)),
             insample_h1=evaluate(H.A, dp_rule(polA))["pass_"], insample_h2=evaluate(H.B, dp_rule(polB))["pass_"])
    r["policy_fit_2010_16"] = {f"{t} left": {f"${int(b)}": int(polA[t, int((b + 2000) / 25)]) for b in (-1500, -1000, -500, 0, 1000, 2000, 3000)}
                               for t in (60, 30, 10)}
    r["adopt"] = bool(r["oof_h1"]["pass_"] >= INC[0] + 1.0 and r["oof_h2"]["pass_"] >= INC[1] + 1.0)
    out["B"][name] = r; print(name, r, flush=True)
(ROOT / "reports/EVAL_30_BOOK_DP_RECHECK_V2_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
print("saved", flush=True)
