"""ovrv_3 (Claude fork B, 2026-11-11): exit overlays on the eval_8 book's EXISTING trades, judged by the evaluation. TRAINING 2010-23 only.

Why: the sensitivity check says cutting daily sd 10% at the same mean is worth about +4.5 pass points (20% about +10). Exit management has
not been judged on the evaluation objective (Antigravity's scale-out audit was a standalone fixed-point Crabel; v5.3's alpha audit judged net).

PRE-DECLARED (written before any result).
Trades: H.PRE (v5.3 + MNQ_BRK_E_2c + MES_MOM_3c, before routing), MNQ/MES. The overnight leg is unchanged. Entries identical.
Path: 1-minute bars of the same series the book's MAE uses (P10 m1 / mes1 = mass_1m_search 'train'); window = bars starting in [tin, tout)
  exactly as v53_improve_train.mae_pct. The engine stamps an exit at the start of the bar in which it exits, so the window never contains
  the original exit; an overlay exit applies only if it triggers inside the window, otherwise the original exit stands.
Prices: engine fills carry 0.5 pt adverse per side (payout_lib), raw entry e = entry - side x 0.5. R = stop_pct x entry (= stop_atr x ATR).
  Overlay portion exiting at raw price x, $ per micro at today's prices: ((side x (x - e)) x TODAY / entry - 2 x 0.5) x MULT - $1 (payout_lib
  form: every micro pays its own round trip and every exit fill, including a partial target fill, pays the same 0.5 pt adverse as any engine
  fill - no free limit fills). Breakeven level = e + side x (2 x 0.5 + 1 / MULT) x entry / TODAY (net $0 per micro).
Bar order (same-bar ambiguity, adverse side first): for each bar, (1) an active overlay stop (BE / trail) hit by the bar's adverse extreme
  exits the remainder at the stop (gap-through: at the bar open if worse); (2) a bar whose adverse extreme reaches the ORIGINAL stop level
  (e - side x R) ends the overlay walk (the original exit stands for whatever is still open); (3) only then favourable triggers: partial
  targets fill at their level; stop activations (BE at +1R, trail at +2R) take effect from the NEXT bar.
CELLS (6):
  E1 BE    : breakeven stop once the favourable excursion reaches +1R.
  E2 H1R   : half off at +1R, rest as original.
  E3 H2R   : half off at +2R, rest as original.
  E4 TR2   : once +2R is reached, stop at max(+1R, best favourable price - 1R), updated from the previous bars' best.
  E5 BE+H1R: E1 and E2 together (half off at +1R, breakeven stop on the rest).
  E6 TIME90: flat at the open of the next bar if the close of the bar ending 90 minutes after entry is not >= +0.5R in favour.
Half-off at size q micros (q = min(k x base, floor($900 / risk)) as the evaluator sizes it): floor(q / 2) micros come off, so the per-micro
  result is f x partial + (1 - f) x rest with f = floor(q / 2) / q; at q = 1 a half-off is not tradable (f = 0: E2/E3 = original trade,
  E5 = E1). Because q depends on k, the half-off cells build one book per k (routing is identical across k: the remainder's exit time does
  not depend on q). MAE per micro for the floor check = the position's worst point (all micros open before the partial, realised partial +
  the rest after) / q, same formula as mae_pct ((worst % x TODAY - 0.5) x MULT).
GATE 1: daily Sharpe of the k3 book (H._per_day + H.sim_day(k=3), as H.save_daily; baseline 0.1506) must rise >= +0.007 on all sessions
  AND rise in BOTH halves (2010-16, 2017-23).
GATE 2 (gate-1 passers only): pass rate with the incumbent rule (DEF + ENDGAME) on the rebuilt book; 2-fold: pick the best passer on
  2010-16 starts and report it on 2017-23, and vice versa; ADOPT only if both out-of-fold halves >= 55.5 / 66.6.
REPORTED: per cell, per-micro mean / sd per trade (routed book at k3 sizes), share of trades changed, daily Sharpe per half, pass rates.
"""
import json, sys
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import eval_harness as eh

H = eh.Harness(); pl = H.pl; P10 = H.E9["P10"]
BAR = {}
for inst, b in (("MNQ", P10["m1"]), ("MES", P10["mes1"])):
    assert pd.to_datetime(b.timestamp_utc, utc=True).max() < pd.Timestamp("2024-01-01", tz="UTC")
    BAR[inst] = (pd.to_datetime(b.timestamp_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy(), b.open.to_numpy(float),
                 b.high.to_numpy(float), b.low.to_numpy(float), b.close.to_numpy(float))
PRE = H.PRE.copy().reset_index(drop=True)
assert set(PRE.inst) <= {"MNQ", "MES"}
H1_END = eh.H1_END; KS = (1, 2, 3, 5)


def pm_at(r, x):
    return ((r.side * (x - (r.entry - r.side * pl.ADV))) * pl.TODAY[r.inst] / r.entry - 2 * pl.ADV) * pl.MULT[r.inst] - pl.FEE


def adv_pm(r, worst_px):
    return (min(0.0, r.side * (worst_px - r.entry) / r.entry) * pl.TODAY[r.inst] - pl.ADV) * pl.MULT[r.inst]


def walk(r, cell):
    """-> dict(partial=(price, bar) | None, rest=(price, bar, exit_ns) | None [None = original exit], worst_b / worst_a adverse prices)."""
    ts, O, Hh, L, C = BAR[r.inst]; i0, i1 = int(np.searchsorted(ts, r.tin.value)), int(np.searchsorted(ts, r.tout.value))
    s = r.side; e = r.entry - s * pl.ADV; R = r.stop_pct * r.entry; ostop = e - s * R
    be = e + s * (2 * pl.ADV + pl.FEE / pl.MULT[r.inst]) * r.entry / pl.TODAY[r.inst]
    part_lvl = {"E2": 1.0, "E3": 2.0, "E5": 1.0}.get(cell); act = None; best = e; partial = None; rest = None
    worse = (lambda u, v: min(u, v)) if s > 0 else (lambda u, v: max(u, v))
    worst_b = e; worst_a = None; t90 = r.tin.value + 90 * 60 * 10**9; checked = False; j_end = i1
    for j in range(i0, i1):
        a = L[j] if s > 0 else Hh[j]; f = Hh[j] if s > 0 else L[j]
        if act is not None and s * (a - act) <= 0:                      # (1) overlay stop, adverse side first
            px = min(act, O[j]) if s > 0 else max(act, O[j]); rest = (px, j, int(ts[j]) + 60 * 10**9)
            if partial is None: worst_b = worse(worst_b, px)
            else: worst_a = px if worst_a is None else worse(worst_a, px)
            break
        if partial is None: worst_b = worse(worst_b, a)
        else: worst_a = a if worst_a is None else worse(worst_a, a)
        if s * (a - ostop) <= 0: j_end = j + 1; break                  # (2) original stop level touched: original exit stands
        if part_lvl is not None and partial is None and s * (f - (e + s * part_lvl * R)) >= 0:
            partial = (e + s * part_lvl * R, j)                          # (3) favourable triggers
        best = max(best, f) if s > 0 else min(best, f)
        if cell in ("E1", "E5") and act is None and s * (best - (e + s * R)) >= 0: act = be
        if cell == "E4" and s * (best - (e + s * 2 * R)) >= 0:
            act = max(e + R, best - R) if s > 0 else min(e - R, best + R)
        if cell == "E6" and not checked and ts[j] + 60 * 10**9 >= t90:
            checked = True
            if s * (C[j] - e) < 0.5 * R and j + 1 < i1: rest = (O[j + 1], j + 1, int(ts[j + 1])); break
    if rest is None and j_end < i1:                                      # original exit: keep tracking the worst point to tout
        seg = L[j_end:i1] if s > 0 else Hh[j_end:i1]
        if len(seg):
            ext = seg.min() if s > 0 else seg.max()
            if partial is None: worst_b = worse(worst_b, ext)
            else: worst_a = ext if worst_a is None else worse(worst_a, ext)
    return dict(partial=partial, rest=rest, worst_b=worst_b, worst_a=worst_a)


def frame_for(cell, W, k):
    """Overlayed PRE for one k. Per-micro result f x partial + (1 - f) x rest; q as the evaluator sizes it."""
    d = PRE.copy(); per = np.array(d.net_today / d.n_contracts, dtype=float); mae = np.array(d.mae_per_micro, dtype=float); tout = d.tout.copy()
    changed = 0
    for i, r in enumerate(d.itertuples()):
        w = W[i]
        if w["partial"] is None and w["rest"] is None: continue
        q = min(k * r.n_contracts, np.floor(900.0 / r.risk_today)) if r.risk_today > 0 else k * r.n_contracts
        f = (np.floor(q / 2) / q) if (w["partial"] is not None and q >= 2) else 0.0
        if w["rest"] is not None:
            rest_pm = pm_at(r, w["rest"][0])
            new_tout = min(pd.Timestamp(w["rest"][2], tz="UTC").tz_convert(r.tout.tz), r.tout)
        else:
            rest_pm = per[i]; new_tout = r.tout
        part_pm = pm_at(r, w["partial"][0]) if (w["partial"] is not None and f > 0) else 0.0
        if f == 0 and w["rest"] is None: continue
        per[i] = f * part_pm + (1 - f) * rest_pm
        wb = adv_pm(r, w["worst_b"])
        if f > 0:
            wa = adv_pm(r, w["worst_a"]) if w["worst_a"] is not None else 0.0
            mae[i] = min(wb, f * part_pm + (1 - f) * wa, per[i])
        else:
            mae[i] = min(wb, per[i]) if w["rest"] is not None else mae[i]
        tout.iloc[i] = new_tout; changed += 1
    d["net_today"] = per * d.n_contracts; d["mae_per_micro"] = mae; d["tout"] = tout
    return d, changed


def books(cell):
    W = [walk(r, cell) for r in PRE.itertuples()]
    out = {}; ch = {}
    for k in KS:
        d, c = frame_for(cell, W, k); out[k] = H.build_book(d); ch[k] = c
    return out, ch, W


def day_sr(bk3):
    PD = H._per_day(bk3[H.COLS].assign(noise=False))
    s = pd.Series({dd: H.sim_day(PD[dd], 3.0)[0] for dd in PD}).reindex(H.SESS, fill_value=0.0)
    h1 = np.array([dd < H1_END for dd in s.index])
    return dict(all=round(eh._sr(s), 4), h1=round(eh._sr(s[h1]), 4), h2=round(eh._sr(s[~h1]), 4), mean=round(float(s.mean()), 1), sd=round(float(s.std()), 0))


def pass_rate_k(bk):
    """H.pass_rate with a k-specific book (half-off results depend on q)."""
    DAY = {}; td_all = set()
    PDs = {k: H._per_day(bk[k][H.COLS].assign(noise=False)) for k in KS}
    td = sorted(set().union(*[set(p) for p in PDs.values()])); tix = pd.to_datetime(pd.Series(td).astype(str)).to_numpy()
    for k in KS: DAY[k] = {dd: (H.sim_day(PDs[k][dd], float(k)) if dd in PDs[k] else (0.0, 0.0)) for dd in td}
    return dict(h1=H._evaluate(DAY, H.A, td, tix, H.DEF_END), h2=H._evaluate(DAY, H.B, td, tix, H.DEF_END))


def trade_stats(bk3):
    q = np.minimum(3 * bk3.n_contracts, np.floor(900.0 / bk3.risk_today)); x = bk3.per_micro
    return dict(n=len(bk3), mean_pm=round(float(x.mean()), 2), sd_pm=round(float(x.std()), 1), mean_k3=round(float((x * q).mean()), 1),
                sd_k3=round(float((x * q).std()), 0))


out = {"baseline": {}}
base = {k: H.BOOK for k in KS}
out["baseline"]["daily"] = day_sr(H.BOOK); out["baseline"]["trades"] = trade_stats(H.BOOK); print("baseline", out["baseline"], flush=True)
assert abs(out["baseline"]["daily"]["all"] - 0.1506) < 0.0005, "baseline daily Sharpe does not reproduce"
chk = pass_rate_k(base); assert chk["h1"]["pass_"] == 54.5 and chk["h2"]["pass_"] == 65.6, chk
inc = chk; out["incumbent"] = inc
CELLS = {"E1": "BE", "E2": "H1R", "E3": "H2R", "E4": "TR2", "E5": "BE+H1R", "E6": "TIME90"}
out["cells"] = {}; BK = {}
for cell, nm in CELLS.items():
    bk, ch, W = books(cell); BK[cell] = bk
    dsr = day_sr(bk[3]); b0 = out["baseline"]["daily"]
    g1 = bool(dsr["all"] - b0["all"] >= 0.007 and dsr["h1"] > b0["h1"] and dsr["h2"] > b0["h2"])
    c = dict(name=nm, changed_trades_k3=ch[3], changed_trades_k1=ch[1], partial_hits=int(sum(w["partial"] is not None for w in W)),
             early_exits=int(sum(w["rest"] is not None for w in W)), trades=trade_stats(bk[3]), daily=dsr, gate1=g1)
    out["cells"][cell] = c; print(cell, nm, c, flush=True)
passers = [k for k, c in out["cells"].items() if c["gate1"]]; out["gate1_passers"] = passers
if passers:
    pr = {k: pass_rate_k(BK[k]) for k in passers}
    for k in passers: out["cells"][k]["pass_rate"] = pr[k]; print("pass_rate", k, pr[k], flush=True)
    pA = max(pr, key=lambda k: pr[k]["h1"]["pass_"]); pB = max(pr, key=lambda k: pr[k]["h2"]["pass_"])
    out["result"] = dict(picked_on_A=pA, oof_h2=pr[pA]["h2"], picked_on_B=pB, oof_h1=pr[pB]["h1"],
                         adopt=bool(pr[pB]["h1"]["pass_"] >= inc["h1"]["pass_"] + 1.0 and pr[pA]["h2"]["pass_"] >= inc["h2"]["pass_"] + 1.0))
    print("result", out["result"], flush=True)
else:
    print("no cell passed gate 1", flush=True)
(ROOT / "reports/OVRV_3_EXIT_OVERLAYS_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
