"""ovrv_1 (Claude fork B, 2026-11-11): market-neutral NQ vs ES relative-strength CONTINUATION intraday. TRAINING 2010-23 only.

Motivation: pairs_1 found the beta-hedged NQ/ES ratio continues rather than reverts over 1-4 hours (fading it lost more than random
direction). pairs_1 said trading the continuation side needs a fresh pre-registration and has a low prior (a few $ per hedged unit vs a
$8-18 two-leg round trip). This is that pre-registration. A market-neutral stream is structurally uncorrelated with the book's direction.

PRE-DECLARED (written before any result).
Data: RTH 09:30-16:00 ET 1-minute bars of NQ->MNQ and ES->MES (mass_1m_search 'train'), full sessions only on BOTH (eval_12 rth_panel:
  >= 385 bars, one contract inside RTH), common dates. m = minute index from 09:30; bar m closes at 09:31+m.
Pair unit at today's prices (payout_lib TODAY): qN MNQ vs qE MES, opposite sides.
  DN (dollar-neutral): qN = 2, qE = 3 ($111.9k vs $113.8k notional).
  BETA: qN = 2, qE = clip(round(beta x 2 x 2 x TODAY_N / (5 x TODAY_E)), 2, 5), beta = OLS slope of NQ on ES RTH open->close returns over
        the previous 60 common sessions (prior sessions only).
  Spread s(m) = rN(m) - h x rE(m), r = close(m) / RTH open - 1, h = (qE x 5 x TODAY_E) / (qN x 2 x TODAY_N) (so s tracks the unit's P&L).
  side = +1: long qN MNQ / short qE MES; side = -1 the reverse.
Unit P&L per leg exactly as payout_lib on raw bar fills: qN x ((legN% x TODAY_N - 2 x 0.5) x 2 - 1) + qE x ((legE% x TODAY_E - 2 x 0.5) x 5 - 1)
  (four fills; DN round trip costs $24 per unit). Entries at the open of bar m+1 after a decision at the close of bar m; final exit at the
  close of bar 384 (15:55). MAE per unit from 1-minute closes of both legs over the hold, after round-trip costs, capped at the final P&L.
CELLS (10):
  FIX_T_H  : at the close of T in {10:00, 10:30, 11:00} go with sign(s(T)) (the outperformer since the open), hold to 15:55, no stop.
             H in {DN, BETA} -> 6 cells. risk_today = 2 x sd of the unit's RTH open->close P&L over the previous 20 sessions (floor $50).
  BAND_H   : sigma(m) = mean over the previous 14 sessions of |s_k(m)| (their rN, rE with today's h). At the closes of 10:00..15:30 (every 30
             min): in a position and side x s(m) <= sigma(m) -> exit; flat and |s(m)| > sigma(m) -> enter sign(s(m)). H in {DN, BETA} -> 2.
             risk_today = (side x s - sigma) x qN x 2 x TODAY_N at entry (floor $50) + round-trip costs.
  STOP_H   : FIX at 10:00 plus a resting stop one band width adverse (side x s(j) <= side x s(10:00) - sigma(10:00)) on 1-minute closes,
             exit at the next bar open. H in {DN, BETA} -> 2. risk_today = sigma(10:00) x qN x 2 x TODAY_N + costs.
REPORTED per cell: n, net, mean, PF and years positive per half (2010-16 / 2017-23); random pair-direction placebo (same entry/exit times,
  200 draws, seed 101), count of placebos beaten; eval_harness.screen() on the daily series ($ per unit, exit day).
GATE: screen_pass (eval_harness definition). A screen passer goes to Harness().pass_rate(extra=ledger, nsize="F1") under the 2-fold protocol:
  pick the best passer on 2010-16 starts, report it on 2017-23, and vice versa; ADOPT only if both out-of-fold halves >= 55.5 / 66.6.
"""
import json, sys
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import payout_lib as pl
import eval_harness as eh

s12 = (ROOT / "scripts/eval_12_noise_area_train.py").read_text(encoding="utf-8").split('\nout = {"cells": {}}')[0]
N12 = {"__name__": "ovrv1", "__file__": str(ROOT / "scripts/eval_12_noise_area_train.py")}; exec(s12, N12)
H1_END = pd.Timestamp("2017-01-01").date(); START = pd.Timestamp("2010-06-07").date()
TN, TE = pl.TODAY["MNQ"], pl.TODAY["MES"]; ADV, FEE = pl.ADV, pl.FEE
CHECKS = [29 + 30 * j for j in range(12)]

dn = {x["d"]: x for x in N12["rth_panel"]("MNQ")}; de = {x["d"]: x for x in N12["rth_panel"]("MES")}
D = sorted(set(dn) & set(de)); print("common full sessions", len(D), D[0], D[-1], flush=True)
assert max(D) < pd.Timestamp("2024-01-01").date()
RN = np.array([dn[d]["c"] / dn[d]["o"][0] - 1 for d in D]); RE = np.array([de[d]["c"] / de[d]["o"][0] - 1 for d in D])
OCN, OCE = RN[:, 384], RE[:, 384]


def unit(hedge, i):
    if hedge == "DN": return 2, 3
    lo = max(0, i - 60); b = np.polyfit(OCE[lo:i], OCN[lo:i], 1)[0]
    return 2, int(np.clip(round(b * 2 * 2 * TN / (5 * TE)), 2, 5))


def leg_pnl(q, mult, today, side, e, x):
    return q * ((side * (x - e) / e * today - 2 * ADV) * mult - FEE)


def rt_cost(qN, qE):
    return qN * (2 * ADV * 2 + FEE) + qE * (2 * ADV * 5 + FEE)


def trade(i, qN, qE, side, a, b_exit, b_kind):
    """entry at the open of bar a; exit at the open of bar b_exit (b_kind 'open') or the close of bar b_exit ('close')."""
    n, e_ = dn[D[i]], de[D[i]]
    eN, eE = n["o"][a], e_["o"][a]
    xN, xE = (n["o"][b_exit], e_["o"][b_exit]) if b_kind == "open" else (n["c"][b_exit], e_["c"][b_exit])
    pnl = leg_pnl(qN, 2, TN, side, eN, xN) + leg_pnl(qE, 5, TE, -side, eE, xE)
    hi = b_exit if b_kind == "open" else b_exit + 1
    marks = qN * 2 * TN * side * (n["c"][a:hi] - eN) / eN - qE * 5 * TE * side * (e_["c"][a:hi] - eE) / eE
    mae = min(pnl, min(0.0, float(marks.min()) if len(marks) else 0.0) - rt_cost(qN, qE))
    t0 = n["t0"]
    return dict(day=D[i], side=side, qN=qN, qE=qE, eN=eN, xN=xN, eE=eE, xE=xE, per_micro=pnl, mae_per_micro=mae,
                tin=t0 + pd.Timedelta(minutes=a), tout=t0 + pd.Timedelta(minutes=(b_exit if b_kind == "open" else b_exit + 1)))


def run(kind, hedge, T=None):
    rows = []
    for i in range(60, len(D)):
        if D[i] < START: continue
        qN, qE = unit(hedge, i); h = (qE * 5 * TE) / (qN * 2 * TN); s = RN[i] - h * RE[i]; notion = qN * 2 * TN
        sig = np.abs(RN[i - 14:i] - h * RE[i - 14:i]).mean(axis=0)
        prev = [leg_pnl(qN, 2, TN, 1, 1.0, 1.0 + OCN[k]) + leg_pnl(qE, 5, TE, -1, 1.0, 1.0 + OCE[k]) for k in range(i - 20, i)]
        if kind == "FIX":
            if s[T] == 0: continue
            t = trade(i, qN, qE, int(np.sign(s[T])), T + 1, 384, "close"); t["risk_today"] = max(2 * float(np.std(prev)), 50.0); rows.append(t)
        elif kind == "STOP":
            T = 29; side = int(np.sign(s[T]))
            if side == 0: continue
            lvl = side * s[T] - sig[T]; ex = None
            for j in range(T + 1, 384):
                if side * s[j] <= lvl: ex = j + 1; break
            t = trade(i, qN, qE, side, T + 1, ex if ex is not None else 384, "open" if ex is not None else "close")
            t["risk_today"] = max(sig[T] * notion, 50.0) + rt_cost(qN, qE); rows.append(t)
        else:  # BAND
            pos = 0; ein = None; risk = None
            for m in CHECKS:
                if pos and pos * s[m] <= sig[m]:
                    t = trade(i, qN, qE, pos, ein, m + 1, "open"); t["risk_today"] = risk; rows.append(t); pos = 0
                if not pos and abs(s[m]) > sig[m] and m + 1 < 384:
                    pos = int(np.sign(s[m])); ein = m + 1; risk = max((abs(s[m]) - sig[m]) * notion, 50.0) + rt_cost(qN, qE)
            if pos:
                t = trade(i, qN, qE, pos, ein, 384, "close"); t["risk_today"] = risk; rows.append(t)
    t = pd.DataFrame(rows)
    assert t.tout.max() < pd.Timestamp("2024-01-01", tz="America/New_York")
    return t


def stats(t):
    w = t.per_micro[t.per_micro > 0].sum(); l = -t.per_micro[t.per_micro < 0].sum(); yrs = t.groupby(t.tout.dt.year).per_micro.sum()
    return dict(n=len(t), net=round(float(t.per_micro.sum()), 0), mean=round(float(t.per_micro.mean()), 2),
                pf=round(float(w / l), 3) if l > 0 else None, years_pos=f"{int((yrs > 0).sum())}/{len(yrs)}")


def placebo(t, n=200, seed=101):
    rng = np.random.default_rng(seed); act = t.per_micro.sum(); beat = 0
    for _ in range(n):
        s = rng.choice([-1, 1], size=len(t))
        tot = (leg_pnl(t.qN.to_numpy(), 2, TN, s, t.eN.to_numpy(), t.xN.to_numpy()) + leg_pnl(t.qE.to_numpy(), 5, TE, -s, t.eE.to_numpy(), t.xE.to_numpy())).sum()
        beat += int(act > tot)
    return beat


CELLS = [("FIX", H, T) for T in (29, 59, 89) for H in ("DN", "BETA")] + [("BAND", H, None) for H in ("DN", "BETA")] + [("STOP", H, None) for H in ("DN", "BETA")]
out = {"cells": {}}; LED = {}
for kind, H, T in CELLS:
    name = f"{kind}_{({29: '1000', 59: '1030', 89: '1100'}[T] + '_') if T else ''}{H}"
    t = run(kind, H, T); h1 = t.tout.dt.date < H1_END
    daily = t.per_micro.groupby(t.tout.dt.date).sum()
    c = dict(h1=stats(t[h1]), h2=stats(t[~h1]), all=stats(t), placebo_beaten=placebo(t), med_risk=round(float(t.risk_today.median()), 0),
             mean_qE=round(float(t.qE.mean()), 2), screen=eh.screen(daily, name))
    out["cells"][name] = c; LED[name] = t
    sc = c["screen"]; print(name, c["h1"], c["h2"], "placebo", c["placebo_beaten"], "| screen sr", sc["sr"], "rho", sc["rho"], "lift", sc["lift"],
                            {h: sc["halves"][h]["lift_at_best_w"] for h in ("h1", "h2")}, "PASS" if sc["screen_pass"] else "fail", flush=True)

passers = [k for k, c in out["cells"].items() if c["screen"]["screen_pass"]]; out["screen_passers"] = passers
if passers:
    Hn = eh.Harness(); inc = Hn.pass_rate(); out["incumbent"] = inc; print("incumbent", inc, flush=True)
    pr = {}
    for k in passers:
        L = LED[k][["tin", "tout", "per_micro", "mae_per_micro", "risk_today"]].assign(n_contracts=1.0)
        pr[k] = Hn.pass_rate(extra=L, nsize="F1"); print("pass_rate", k, pr[k], flush=True)
    out["pass_rate"] = pr
    pA = max(pr, key=lambda k: pr[k]["h1"]["pass_"]); pB = max(pr, key=lambda k: pr[k]["h2"]["pass_"])
    out["result"] = dict(picked_on_A=pA, oof_h2=pr[pA]["h2"], picked_on_B=pB, oof_h1=pr[pB]["h1"],
                         adopt=bool(pr[pB]["h1"]["pass_"] >= inc["h1"]["pass_"] + 1.0 and pr[pA]["h2"]["pass_"] >= inc["h2"]["pass_"] + 1.0))
    print("result", out["result"], flush=True)
else:
    print("no cell passed the screen", flush=True)
(ROOT / "reports/OVRV_1_RS_CONTINUATION_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
