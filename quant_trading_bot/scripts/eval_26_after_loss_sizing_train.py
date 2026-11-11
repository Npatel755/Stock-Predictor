"""eval_26 (Claude, 2026-11-11): size by the PREVIOUS trading day's result, plus the 1-5 attempt budget table. TRAINING 2010-23 only.

(A) Why (written after a descriptive screen, before any pass-rate run): on the book's k3 daily P&L (reports/EVAL_BOOK_DAILY_TRAINING.csv,
active days only) the next active day's Sharpe is 0.258 / 0.297 after a day below -$300 and 0.164 / 0.216 after a winning day, vs 0.193 /
0.240 overall (2010-16 / 2017-23), with similar st.dev. (lag-1 autocorrelation -0.05 in both halves). The incumbent ladder only sizes DOWN
after losses (by balance); a day-level rule that leans the other way has not been tested (eval_9 DP sized by balance and day number only).
Mechanism guess: big book losses are failed breakouts / reversal days, and daily index returns mean-revert at a 1-day lag.
PRE-DECLARED. eval_8 plan (DEF_END) on the harness book; "prev" = the account's P&L on its last day with any trade in this attempt.
Only when DEF gives k = 3 (never inside the drawdown ladder or the late k5):
  L1  k = 4 if prev < 0          L2  k = 4 if prev <= -$300
  W1  k = 2 if prev > 0          LW  L2 and W1 together
2-fold: pick the best cell on 2010-16 starts and report it on 2017-23, and vice versa. ADOPT only if both out-of-fold halves >= 55.5 / 66.6
AND each picked cell beats its own timing placebo in both halves: the same +1 / -1 changes applied on random k = 3 days at the cell's own
trigger rate (mean over 20 seeds, seed base 26) - this separates "when" from "more / less size on average".
(B) Information only: the attempt budget. Sequential attempts (the next bought the session after a fail / timeout), up to 5 purchases
(Topstep's lifetime limit), incumbent plan; first decision days 2010-06 .. LAST - 450 days. P(pass by attempt n), mean purchases, $ spent at
$149 each, median and 90th percentile days from the first purchase to the pass. Starts whose window overlaps the Jan-May 2019 data hole
(no NQ after 2019-01-01, MNQ from 2019-05-06 in the training loader) are reported separately in (C).
"""
import json
import numpy as np, pandas as pd
from pathlib import Path
import eval_harness as eh

ROOT = Path(__file__).resolve().parents[1]
H = eh.Harness(); DEF = H.DEF_END
PD = H._per_day(H.BOOK[H.COLS].assign(noise=False)); TD = sorted(PD); TIX = pd.to_datetime(pd.Series(TD).astype(str)).to_numpy()
DAY = {k: {d: H.sim_day(PD[d], float(k)) for d in TD} for k in (1, 2, 3, 4, 5)}
LAST = TD[-1]; SESS = list(H.SESS); SIX = np.array(SESS, dtype=object)


def mod(cell, k, prev, rnd=None):
    if k != 3 or prev is None: return k
    if cell == "L1": return 4 if prev < 0 else 3
    if cell == "L2": return 4 if prev <= -300.0 else 3
    if cell == "W1": return 2 if prev > 0 else 3
    if cell == "LW": return 4 if prev <= -300.0 else (2 if prev > 0 else 3)
    if cell == "RND": up, dn, rng = rnd; u = rng.random(); return 4 if u < up else (2 if u < up + dn else 3)
    return 3


def run(start, cell=None, rnd=None, count=None):
    end = (pd.Timestamp(start) + pd.Timedelta(days=90)).date(); i = int(np.searchsorted(TIX, np.datetime64(pd.Timestamp(start))))
    bal = 0.0; best = 0.0; prev = None
    for d in TD[i:]:
        if d >= end: return "timeout", end
        k = DEF(bal, (d - start).days, max(4000.0, best / 0.55), 0)
        if cell is not None:
            k2 = mod(cell, k, prev, rnd)
            if count is not None and k == 3 and prev is not None: count["k3"] += 1; count["up"] += k2 == 4; count["dn"] += k2 == 2
            k = k2
        p, w = DAY[k][d]
        if bal + min(w, p) <= -2000.0: return "fail", d
        bal += p; best = max(best, p)
        if p != 0.0: prev = p
        if bal >= max(4000.0, best / 0.55): return "pass", d
    return "timeout", end


def rate(starts, cell=None, rnd=None, count=None):
    x = pd.Series([run(s, cell, rnd, count)[0] for s in starts])
    return dict(pass_=round(100 * float((x == "pass").mean()), 1), fail=round(100 * float((x == "fail").mean()), 1),
                timeout=round(100 * float((x == "timeout").mean()), 1), n=len(x))


out = {"A": {}, "placebo": {}}
inc = dict(h1=rate(H.A), h2=rate(H.B)); out["A"]["INC"] = inc; print("INC", inc, flush=True)
assert inc["h1"]["pass_"] == 54.5 and inc["h2"]["pass_"] == 65.6
TRIG = {}
for c in ("L1", "L2", "W1", "LW"):
    cnt = dict(k3=0, up=0, dn=0); out["A"][c] = dict(h1=rate(H.A, c, count=cnt), h2=rate(H.B, c, count=cnt))
    TRIG[c] = (cnt["up"] / max(cnt["k3"], 1), cnt["dn"] / max(cnt["k3"], 1)); out["A"][c]["trigger_up_dn"] = [round(v, 3) for v in TRIG[c]]
    print(c, out["A"][c], flush=True)
cells = ("L1", "L2", "W1", "LW")
pA = max(cells, key=lambda c: out["A"][c]["h1"]["pass_"]); pB = max(cells, key=lambda c: out["A"][c]["h2"]["pass_"])
oA, oB = out["A"][pB]["h1"]["pass_"], out["A"][pA]["h2"]["pass_"]
plac_ok = True
for c in sorted({pA, pB}):
    res = {"h1": [], "h2": []}
    for sd in range(20):
        for h, st in (("h1", H.A), ("h2", H.B)):
            res[h].append(rate(st, "RND", rnd=(TRIG[c][0], TRIG[c][1], np.random.default_rng(26 + sd)))["pass_"])
    out["placebo"][c] = {h: dict(mean=round(float(np.mean(v)), 1), max=float(np.max(v)), cell=out["A"][c][h]["pass_"]) for h, v in res.items()}
    plac_ok &= all(out["A"][c][h]["pass_"] > out["placebo"][c][h]["mean"] for h in ("h1", "h2"))
    print("placebo", c, out["placebo"][c], flush=True)
out["A_result"] = dict(pick_h1=pA, pick_h2=pB, oof_h1=oA, oof_h2=oB, placebo_ok=bool(plac_ok),
                       adopt=bool(oA >= 55.5 and oB >= 66.6 and plac_ok))
print("A result", out["A_result"], flush=True)

# ---------------- (B) attempt budget, incumbent plan, sequential purchases
CACHE = {}
def plain(s):
    if s not in CACHE: CACHE[s] = run(s)
    return CACHE[s]


def nxt(d):
    j = int(np.searchsorted(SIX, d, side="right")); return SESS[j] if j < len(SESS) else None


HOLE0, HOLE1 = pd.Timestamp("2019-01-01").date(), pd.Timestamp("2019-05-06").date()
firsts = [s for s in SESS if (pd.Timestamp(s) + pd.Timedelta(days=450)).date() <= LAST and s >= H.A[0]]
rows = []
for s0 in firsts:
    s = s0; n = 0; passed_at = None; days = None; touched = False
    while s is not None and n < 5:
        n += 1; o, e = plain(s)
        touched |= (s < HOLE1 and (pd.Timestamp(s) + pd.Timedelta(days=90)).date() > HOLE0)
        if o == "pass": passed_at = n; days = (e - s0).days; break
        s = nxt(e)
    rows.append(dict(s0=s0, h1=s0 < eh.H1_END, passed_at=passed_at, buys=n, days=days, hole=touched))
R = pd.DataFrame(rows)


def table(x):
    d = dict(n=len(x))
    for k in range(1, 6): d[f"by_{k}"] = round(100 * float(((x.passed_at.notna()) & (x.passed_at <= k)).mean()), 1)
    d["mean_purchases"] = round(float(x.buys.mean()), 2); d["mean_spend_usd"] = round(149 * float(x.buys.mean()), 0)
    dd = x.days.dropna(); d["median_days"] = float(dd.median()) if len(dd) else None; d["p90_days"] = float(dd.quantile(0.9)) if len(dd) else None
    return d


out["B_budget"] = dict(h1=table(R[R.h1]), h2=table(R[~R.h1]), all=table(R))
out["C_hole"] = dict(h2_without_hole_chains=table(R[(~R.h1) & (~R.hole)]), hole_chains=table(R[R.hole]),
                     single_attempt_h2_without_hole=round(100 * float(np.mean([plain(s)[0] == "pass" for s in H.B
                                                         if not (s < HOLE1 and (pd.Timestamp(s) + pd.Timedelta(days=90)).date() > HOLE0)])), 1),
                     single_attempt_h2_hole_starts=round(100 * float(np.mean([plain(s)[0] == "pass" for s in H.B
                                                         if (s < HOLE1 and (pd.Timestamp(s) + pd.Timedelta(days=90)).date() > HOLE0)])), 1))
print("B", out["B_budget"], flush=True); print("C", out["C_hole"], flush=True)
(ROOT / "reports/EVAL_26_AFTER_LOSS_SIZING_AND_BUDGET_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
