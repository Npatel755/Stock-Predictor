"""eval_13 (Claude, 2026-11-11): the noise-area MNQ sleeve as a CONCURRENT stream next to the eval_8 book. TRAINING 2010-23 only.

NEW PHASE, declared after eval_12. eval_12 gate 1: noise-area MNQ has standalone edge (P: PF 1.14 / 1.32, R: 1.13 / 1.40, 200/200 placebos);
gate 2 FAILED (routed one-position at priority 12 and k-sized: 46.8% / 52.4% vs 54.5% / 65.6%, fails 20% -> 41%). Diagnosis written before
this run: (a) a 10:01 noise entry held to 16:00 blocks the book's later decisions in the one-position router; (b) k3 sizing on a nominal
$62 stop while the real per-trade swing is several times that. This phase tests the remedy for (a)+(b) only; eval_12's failure stands.

PRE-DECLARED (before any eval_13 result). Book, simulator, starts, incumbent rule (DEF + ENDGAME) and 2-fold protocol as eval_9/eval_11.
The noise trades (eval_12 code, MNQ, published parameters) run as a SEPARATE position next to the routed book (same-direction or opposite
MNQ positions net inside the one account; P&L is the sum). Day simulation with overlap: trades in entry order; no new entry once realised
day P&L (trades closed before the entry) <= -stop ($400 when every book trade is at its base size, else $700; book-only rule, as before);
worst point at each entry = realised + this trade's MAE + the MAE of every accepted trade it overlaps (assumed simultaneous, conservative);
worst <= -$1,000 -> flatten the day at -$1,000. Book trades keep the incumbent's sequential semantics among themselves (the research router
  lets some book trades overlap and the incumbent sums them in entry order); the overlap rule applies to noise trades only. Without noise
  trades this reproduces the incumbent exactly (asserted; a first all-overlap version gave 49.8 / 61.1 and was corrected before any cell ran).
CELLS (6 candidates): stop mode {P, R} x noise size {F1 = 1 micro, F2 = 2 micros, K = the book's multiplier k}, each capped at floor($900 /
  stop risk). Reported only (not candidates): NOISE ALONE P / R at k (the whole account on the noise sleeve).
PROTOCOL: pick the best candidate on fold A (2010-06..2016-12 starts) and report it on fold B; pick on B, report on A.
ADOPT only if BOTH out-of-fold halves >= incumbent's same half + 1.0 point (54.5 -> 55.5, 65.6 -> 66.6).
"""
import json
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
s12 = (ROOT / "scripts/eval_12_noise_area_train.py").read_text(encoding="utf-8").split('\nout = {"cells": {}}')[0]
N12 = {"__name__": "e13n", "__file__": str(ROOT / "scripts/eval_12_noise_area_train.py")}; exec(s12, N12)
days_ = N12["rth_panel"]("MNQ")
NT = {}
for mode in ("P", "R"):
    t = N12["trades"](days_, "MNQ", mode); NT[mode] = t[t.tout.dt.date >= pd.Timestamp("2010-06-07").date()].reset_index(drop=True)
    print("noise", mode, len(NT[mode]), "per micro mean", round(NT[mode].per_micro.mean(), 2), "sd", round(NT[mode].per_micro.std(), 1),
          "MAE p5", round(NT[mode].mae_per_micro.quantile(0.05), 0), flush=True)
NT["P"].to_csv(ROOT / "reports/EVAL_13_NOISE_MNQ_P_TRADES_TRAINING.csv", index=False)
NT["R"].to_csv(ROOT / "reports/EVAL_13_NOISE_MNQ_R_TRADES_TRAINING.csv", index=False)

s9 = (ROOT / "scripts/eval_9_optimal_sizing_train.py").read_text(encoding="utf-8").split("\n# ---------------- DP")[0]
E9 = {"__name__": "e13", "__file__": str(ROOT / "scripts/eval_9_optimal_sizing_train.py")}; exec(s9, E9)
pl, variant, SLV, A, B, DEF_END, evaluate2 = (E9[k] for k in ("pl", "variant", "SLV", "A", "B", "DEF_END", "evaluate2"))
E5 = E9["E"]; NIGHTS, NIGHT_RISK = E5["NIGHTS"], E5["NIGHT_RISK"]
inc = dict(h1=evaluate2(DEF_END, A), h2=evaluate2(DEF_END, B)); print("incumbent", inc, flush=True)
assert abs(inc["h1"]["pass_"] - 54.5) <= 0.1 and abs(inc["h2"]["pass_"] - 65.6) <= 0.1

d = pd.concat([variant("A")] + SLV, ignore_index=True)
r = pl.route(d[d.risk_today <= 300.0]).copy(); r["per_micro"] = r.net_today / r.n_contracts
COLS = ["tin", "tout", "per_micro", "mae_per_micro", "n_contracts", "risk_today"]
BOOK = pd.concat([r[COLS], NIGHTS.assign(n_contracts=1.0, risk_today=NIGHT_RISK)[COLS]], ignore_index=True).assign(noise=False)


def per_day(df):
    df = df.copy(); df["day"] = df.tout.dt.date; df = df.sort_values("tin")
    df["a"] = df.tin.map(lambda x: x.value); df["b"] = df.tout.map(lambda x: x.value)
    return {k: (g.a.to_numpy(), g.b.to_numpy(), g.per_micro.to_numpy(), g.mae_per_micro.to_numpy(), g.n_contracts.to_numpy(),
                g.risk_today.to_numpy(), g.noise.to_numpy()) for k, g in df.groupby("day")}


def sim_day(x, k, nsize):
    a, b, per, mae, n, risk, nz = x
    cap = np.floor(900.0 / risk)
    q = np.where(nz, np.minimum({"K": k, "F1": 1.0, "F2": 2.0}[nsize], cap), np.minimum(k * n, cap))
    bk = ~nz; stop = 400.0 if np.all(q[bk] <= n[bk]) else 700.0
    acc = []; w = 0.0; dll = False
    for j in range(len(per)):
        if q[j] < 1: continue
        if not nz[j]:   # book trade: the incumbent's sequential semantics over book trades, plus closed / open noise trades
            realised = sum(per[i] * q[i] for i in acc if not nz[i]) + sum(per[i] * q[i] for i in acc if nz[i] and b[i] <= a[j])
            opn = sum(min(0.0, mae[i] * q[i]) for i in acc if nz[i] and b[i] > a[j])
        else:           # noise trade: closed trades count in full, every still-open trade at its worst
            realised = sum(per[i] * q[i] for i in acc if b[i] <= a[j])
            opn = sum(min(0.0, mae[i] * q[i]) for i in acc if b[i] > a[j])
        if realised <= -stop or realised <= -1000.0: break
        worst = realised + mae[j] * q[j] + opn
        w = min(w, worst)
        if worst <= -1000.0: dll = True; break
        acc.append(j)
    p = -1000.0 if dll else max(sum(per[i] * q[i] for i in acc), -1000.0)
    return p, w


def evaluate(DAY, starts, td, tix):
    res = []
    for s in starts:
        end = (pd.Timestamp(s) + pd.Timedelta(days=90)).date(); i = int(np.searchsorted(tix, np.datetime64(pd.Timestamp(s))))
        bal = 0.0; best = 0.0; out = "timeout"
        for dd in td[i:]:
            if dd >= end: break
            k = DEF_END(bal, (dd - s).days, max(4000.0, best / 0.55), 0); p, w = DAY[k][dd]
            if bal + min(w, p) <= -2000.0: out = "fail"; break
            bal += p; best = max(best, p)
            if bal >= max(4000.0, best / 0.55): out = "pass"; break
        res.append(out)
    x = pd.Series(res)
    return dict(pass_=round(100 * float((x == "pass").mean()), 1), fail=round(100 * float((x == "fail").mean()), 1),
                timeout=round(100 * float((x == "timeout").mean()), 1), n=len(x))


def run(frame, nsize):
    PD = per_day(frame); td = sorted(PD); tix = pd.to_datetime(pd.Series(td).astype(str)).to_numpy()
    DAY = {k: {dd: sim_day(PD[dd], float(k), nsize) for dd in td} for k in (1, 2, 3, 5)}
    return dict(h1=evaluate(DAY, A, td, tix), h2=evaluate(DAY, B, td, tix))


out = {"incumbent": inc, "cells": {}, "reference": {}}
chk = run(BOOK, "F1"); print("reproduce", chk, flush=True)
assert chk["h1"]["pass_"] == inc["h1"]["pass_"] and chk["h2"]["pass_"] == inc["h2"]["pass_"], "overlap simulator does not reproduce"
for mode in ("P", "R"):
    nt = NT[mode].assign(n_contracts=1.0, noise=True)[COLS + ["noise"]]
    for nsize in ("F1", "F2", "K"):
        c = run(pd.concat([BOOK, nt], ignore_index=True), nsize); out["cells"][f"{mode}_{nsize}"] = c; print(mode, nsize, c, flush=True)
    out["reference"][f"ALONE_{mode}"] = run(nt.assign(noise=False), "F1"); print("alone", mode, out["reference"][f"ALONE_{mode}"], flush=True)

# daily correlation of the noise sleeve (1 micro) with the book at 1x, training days with either trading
bd = BOOK.groupby(BOOK.tout.dt.date).per_micro.sum()
for mode in ("P", "R"):
    nd = NT[mode].groupby(NT[mode].tout.dt.date).per_micro.sum(); j = pd.concat([bd.rename("book"), nd.rename("noise")], axis=1).fillna(0.0)
    out[f"corr_daily_{mode}"] = round(float(j.book.corr(j.noise)), 3)
C = out["cells"]; pA = max(C, key=lambda k: C[k]["h1"]["pass_"]); pB = max(C, key=lambda k: C[k]["h2"]["pass_"])
onB, onA = C[pA]["h2"], C[pB]["h1"]
out["result"] = dict(picked_on_A=pA, picked_on_B=pB, oof_h1=onA, oof_h2=onB,
                     oof_all=round((onA["pass_"] * onA["n"] + onB["pass_"] * onB["n"]) / (onA["n"] + onB["n"]), 1),
                     adopt=bool(onA["pass_"] >= inc["h1"]["pass_"] + 1.0 and onB["pass_"] >= inc["h2"]["pass_"] + 1.0))
print("corr", out["corr_daily_P"], out["corr_daily_R"], "result", out["result"], flush=True)
(ROOT / "reports/EVAL_13_NOISE_CONCURRENT_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
