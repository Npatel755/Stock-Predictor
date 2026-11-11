"""eval_9 (Claude, 2026-11-10): optimal-control sizing and risk plumbing for the $50K Static Combine. TRAINING 2010-23 only.

PRE-DECLARED (written before any result). Book = eval_8 "SLEEVES" (v5.3 + MNQ_BRK_E_2c + MES_MOM_3c + overnight leg), same simulator and
starts as eval_5/eval_8 (Static $4,000 with the 55% consistency rule, -$2,000 floor checked on 1-minute MAE, DLL $1,000, 90 calendar days).
Incumbent = eval_8 "SLEEVES + DEF + ENDGAME" (60.0%, 2010-16 54.5%, 2017-23 65.6%; itself chosen post hoc on all of 2010-23).

Idea: passing is a reach-the-target-before-the-floor-and-the-deadline problem, so the size multiplier k should depend on (balance, sessions
left). Dynamic programming gives the k that maximises P(pass) for each state, if days were independent draws from a fold's sessions.
  Day outcome per session and k: realised P&L (DLL-capped) and the worst intraday point (for the floor), simulated exactly as the evaluator does.
  DP state: balance on a $25 grid -$2,000..$4,000 (the 55% rule is folded in by shifting the balance by any target increase) and sessions left
  (1..64). Ties: a larger k must beat a smaller one by > 0.1 point of P(pass), else the smaller k is kept.
  At run time: sessions left = weekdays from the day to the deadline; balance shifted by (target - $4,000).
FAMILIES
  DP6: k in {1..6}.   DP4: k in {1..4}.
  CAP: incumbent with the per-trade risk cap $700 / $1,200 (vs $900).
  STOP: incumbent with the daily account stop above 1x at $500 / $1,000 (vs $700).
  PSTOP: incumbent plus a daily profit stop (no new entries once the day is up >= $1,500 / $2,200).
PROTOCOL (2-fold, both directions): fold A = starts 2010-06..2016-12, fold B = 2017-01..2023-09.
  DP: fit on A's sessions, run on B's starts; fit on B, run on A. Knob families: pick the best value on A, report it on B; pick on B, report on A.
  ADOPT a family only if BOTH out-of-fold halves are >= the incumbent's same half + 1.0 point. The out-of-fold overall number is reported
  (weighted by starts). DP fitted on all training is also reported (in-sample, for the policy table only).
"""
import json
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/eval_5_pass_rate_train.py").read_text(encoding="utf-8").split("\nTAB = {")[0]
E = {"__name__": "e9", "__file__": str(ROOT / "scripts/eval_5_pass_rate_train.py")}; exec(src, E)
pl, variant, table, mae_pct, base0, SESS = (E[k] for k in ("pl", "variant", "table", "mae_pct", "base0", "SESS"))
P10 = E["P10"]; ep, bars_for, START = P10["ep"], P10["bars_for"], P10["START"]
H1_END = pd.Timestamp("2017-01-01").date()
SLV = []
for prio, (name, key) in enumerate((("MNQ_BRK_E_2c", "portfolio_e"), ("MES_MOM_3c", "portfolio_e")), start=10):
    sl = next(s for s in ep.CANDIDATES[key]["sleeves"] if s["name"] == name)
    x = pl.price_normalize(pl.sleeve_trades(ep, bars_for, START, dict(sl), prio, False)); x["n_contracts"] = 1.0
    x["mae_per_micro"] = [(mae_pct(r.inst, r.tin, r.tout, r.side, r.entry) * pl.TODAY[r.inst] - pl.ADV) * pl.MULT[r.inst] for r in x.itertuples()]
    SLV.append(x[base0.columns])
TAB = table(pd.concat([variant("A")] + SLV, ignore_index=True))
A = [s for s in SESS if s < H1_END]; B = [s for s in SESS if s >= H1_END]


def run_day(per, mae, n, risk, k, cap=900.0, stop_hi=700.0, pstop=None):
    """One day exactly as eval_5.evaluate: returns (P&L capped at -$1,000, worst intraday point vs the day's start)."""
    q = np.minimum(k * n, np.floor(cap / risk)); stop = 400.0 if np.all(q <= n) else stop_hi; day = 0.0; w = 0.0
    for j in range(len(per)):
        if q[j] < 1: continue
        if day <= -stop or day <= -1000.0: break
        if pstop is not None and day >= pstop: break
        w = min(w, day + mae[j] * q[j])
        if day + mae[j] * q[j] <= -1000.0: day = -1000.0; break
        day += per[j] * q[j]
    return max(day, -1000.0), w


def evaluate2(rule, starts, cap=900.0, stop_hi=700.0, pstop=None):
    """rule(bal, calendar_day, target, sessions_left) -> k. Same logic as eval_5.evaluate."""
    by, td, tix = TAB; res = []
    for s in starts:
        end = (pd.Timestamp(s) + pd.Timedelta(days=90)).date(); i = int(np.searchsorted(tix, np.datetime64(pd.Timestamp(s))))
        bal = 0.0; best = 0.0; out = "timeout"; when = None
        for d in td[i:]:
            if d >= end: break
            tgt = max(4000.0, best / 0.55); k = rule(bal, (d - s).days, tgt, int(np.busday_count(d, end)))
            p, w = run_day(*by[d], k, cap, stop_hi, pstop)
            if bal + min(w, p) <= -2000.0: out = "fail"; when = d; break
            bal += p; best = max(best, p)
            if bal >= max(4000.0, best / 0.55): out = "pass"; when = d; break
        res.append((s, out, (when - s).days if (when and out == "pass") else None))
    r = pd.DataFrame(res, columns=["s", "o", "days"])
    return dict(pass_=round(100 * float((r.o == "pass").mean()), 1), fail=round(100 * float((r.o == "fail").mean()), 1),
                timeout=round(100 * float((r.o == "timeout").mean()), 1), median_days=float(r.days.dropna().median()) if r.days.notna().any() else None, n=len(r))


def DEF_END(bal, day, tgt, sleft):
    if day >= 60 and bal < tgt - 1000.0 and bal > -500.0: return 5
    return 1 if bal <= -1000.0 else (2 if bal <= -500.0 else 3)


# ---------------- DP
G = np.arange(-2000.0, 4000.0 + 1e-9, 25.0); H = 64


def outcomes(sessions, K):
    by = TAB[0]; P = np.zeros((len(sessions), len(K))); W = np.zeros_like(P)
    for i, s in enumerate(sessions):
        if s not in by: continue
        for j, k in enumerate(K): P[i, j], W[i, j] = run_day(*by[s], k)
    return P, W


def fit_dp(sessions, K):
    P, W = outcomes(sessions, K); V = np.zeros(len(G)); pol = np.full((H + 1, len(G)), K[0], int); Vs = [V.copy()]
    for t in range(1, H + 1):
        best = np.full(len(G), -1.0); arg = np.full(len(G), K[0], int)
        for j, k in enumerate(K):
            p = P[:, j][:, None]; nb = G[None, :] + p
            fail = G[None, :] + np.minimum(W[:, j], P[:, j])[:, None] <= -2000.0
            tgt = np.maximum(4000.0, p / 0.55); passed = (nb >= tgt) & ~fail
            cont = np.interp(nb - (tgt - 4000.0), G, V)
            val = np.where(fail, 0.0, np.where(passed, 1.0, cont)).mean(axis=0)
            better = val > best + 1e-3; best = np.where(better, val, best); arg = np.where(better, k, arg)
        V = best.copy(); V[G <= -2000.0] = 0.0; V[G >= 4000.0] = 1.0; pol[t] = arg; Vs.append(V.copy())
    return pol, Vs


def dp_rule(pol):
    def rule(bal, day, tgt, sleft):
        b = bal - (tgt - 4000.0); t = int(min(max(sleft, 1), H)); i = int(np.clip(np.round((b + 2000.0) / 25.0), 0, len(G) - 1))
        return int(pol[t, i])
    return rule


def halves(rule, **kw):
    a, b = evaluate2(rule, A, **kw), evaluate2(rule, B, **kw)
    return dict(h1=a, h2=b, all=round((a["pass_"] * a["n"] + b["pass_"] * b["n"]) / (a["n"] + b["n"]), 1))


out = {}
inc = out["incumbent SLEEVES+DEF+ENDGAME"] = halves(DEF_END); print("incumbent", inc, flush=True)
assert abs(inc["all"] - 60.0) <= 0.1, "simulator does not reproduce eval_8"
fam = {}
for name, K in (("DP6", (1, 2, 3, 4, 5, 6)), ("DP4", (1, 2, 3, 4))):
    polA, _ = fit_dp(A, K); polB, _ = fit_dp(B, K)
    onB = evaluate2(dp_rule(polA), B); onA = evaluate2(dp_rule(polB), A)
    fam[name] = dict(oof_h1=onA, oof_h2=onB, oof_all=round((onA["pass_"] * onA["n"] + onB["pass_"] * onB["n"]) / (onA["n"] + onB["n"]), 1),
                     insample_h1=evaluate2(dp_rule(polA), A)["pass_"], insample_h2=evaluate2(dp_rule(polB), B)["pass_"])
    print(name, fam[name], flush=True)
    polAll, VAll = fit_dp(A + B, K)
    fam[name]["policy_all_training"] = {f"{t} sessions left": {f"${int(b)}": int(polAll[t, int((b + 2000) / 25)]) for b in (-1500, -1000, -500, 0, 1000, 2000, 3000, 3500)}
                                        for t in (60, 45, 30, 15, 5, 1)}
    fam[name]["dp_value_at_start_all_training"] = round(float(np.interp(0.0, G, VAll[63])), 3)
    fam[name]["all_training_insample"] = halves(dp_rule(polAll))
    print(name, "policy (all training):", fam[name]["policy_all_training"], flush=True)
knobs = {"CAP": [dict(cap=700.0), dict(cap=1200.0)], "STOP": [dict(stop_hi=500.0), dict(stop_hi=1000.0)], "PSTOP": [dict(pstop=1500.0), dict(pstop=2200.0)]}
for f, opts in knobs.items():
    cells = []
    for kw in opts:
        h = halves(DEF_END, **kw); cells.append((kw, h)); print(f, kw, h, flush=True)
    pickA = max(cells, key=lambda c: c[1]["h1"]["pass_"]); pickB = max(cells, key=lambda c: c[1]["h2"]["pass_"])
    onB, onA = pickA[1]["h2"], pickB[1]["h1"]
    fam[f] = dict(cells=[dict(kw=c[0], **c[1]) for c in cells], picked_on_A=pickA[0], picked_on_B=pickB[0], oof_h1=onA, oof_h2=onB,
                  oof_all=round((onA["pass_"] * onA["n"] + onB["pass_"] * onB["n"]) / (onA["n"] + onB["n"]), 1))
for f, c in fam.items():
    c["adopt"] = bool(c["oof_h1"]["pass_"] >= inc["h1"]["pass_"] + 1.0 and c["oof_h2"]["pass_"] >= inc["h2"]["pass_"] + 1.0)
    print(f, "out-of-fold", c["oof_all"], "(H1", c["oof_h1"]["pass_"], "H2", c["oof_h2"]["pass_"], ") adopt:", c["adopt"], flush=True)
out["families"] = fam
(ROOT / "reports/EVAL_9_OPTIMAL_SIZING_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
