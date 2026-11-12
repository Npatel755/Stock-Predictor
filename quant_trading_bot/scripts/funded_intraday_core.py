"""Funded-account simulator with INTRADAY daily-loss-limit and floor checks (Claude, 2026-11-11; used from payout_30 on).

Why: the older funded tables (research_uncapped_and_sleeves.build_tables + `max(net, -1000)`) clip only the day's FINAL P&L at -$1,000.
A day that fell below -$1,000 and then recovered keeps its recovery, although Topstep's DLL would have liquidated it. That one-sided clip is a
free put that grows with variance (payout_29: +$9,419 per 24-month window for the triple stack, +$1,534 for Fortress 4X).

Day semantics (as eval_harness.sim_day_v2, the evaluation track's corrected day):
- trades of one trading day (grouped by exit date; the overnight leg belongs to the day it exits) are taken in entry order;
- a trade is realised for a later entry only if it closed before that entry (or at the same minute with an earlier entry);
- open trades' MAE stacks with the new trade's MAE (conservative: their worst points are assumed to coincide);
- account stop: no new entry while realised <= -stop ($400 at 1x, $700 above);
- DLL first passage: if realised + open MAE + the new trade's MAE <= -$1,000 at an entry, the day is liquidated at -$1,000 and ends;
- MAE is capped at the trade's final P&L, so the final day total is never below the last check's worst (p >= -$1,000 without a clip);
  on a liquidated day the reported worst is -$1,000 (first passage), not the full MAE (fixed 2026-11-11 in payout_33; no F4X closure moves,
  all of them are at 1x where no day is liquidated).
- sim_day_path / day_tables_path (payout_33): EXACT combined minute marks instead of coincident worst points on days with >= 2 trades.
Optional `budget`: shrink a new entry so that realised - (stop risk of open trades) - (its own stop risk) stays above -$1,000.
"""
import numpy as np
import pandas as pd


def sim_day(a, b, per, mae, risk, q, stop, budget=False, dll=1000.0):
    """a, b: entry / exit times (int); per, mae, risk: per-micro final P&L, MAE (<= 0) and stop risk; q: planned micros (0 = skip).
    Returns (p, worst, hit): day P&L, worst intraday point (<= min(0, p)), and whether the DLL liquidated the day."""
    acc = []; qs = {}; w = 0.0; hit = False
    for j in range(len(per)):
        if q[j] < 1: continue
        done = [i for i in acc if b[i] < a[j] or (b[i] == a[j] and a[i] < a[j])]
        realised = float(sum(per[i] * qs[i] for i in done))
        if realised <= -stop: continue
        opn = [i for i in acc if i not in done]
        qj = float(q[j])
        if budget:
            room = dll + realised - float(sum(risk[i] * qs[i] for i in opn))
            qj = min(qj, float(np.floor(room / risk[j]))) if risk[j] > 0 else qj
            if qj < 1: continue
        worst = realised + float(sum(min(0.0, mae[i]) * qs[i] for i in opn)) + min(0.0, mae[j]) * qj
        w = min(w, worst)
        if worst <= -dll: hit = True; break
        acc.append(j); qs[j] = qj
    p = -dll if hit else float(sum(per[i] * qs[i] for i in acc))
    # liquidation at the first passage through -dll: the day's equity never goes below -dll (worst capped there, payout_33 fix)
    return max(p, -dll), max(min(w, p, 0.0), -dll), hit


def mae_per_micro(trades, bars, today, mult, adv):
    """MAE in today's dollars per micro from 1-minute bars: worst low (long) / high (short) in [tin, tout), as v53_improve_train.mae_pct.
    bars: {inst: (ts_ns int64 array, high, low)}. trades needs inst, side, entry, tin, tout."""
    out = np.zeros(len(trades))
    for k, r in enumerate(trades.itertuples()):
        ts, H, L = bars[r.inst]; i0, i1 = int(np.searchsorted(ts, r.tin.value)), int(np.searchsorted(ts, r.tout.value))
        if i1 <= i0: pct = 0.0
        else:
            wv = L[i0:i1].min() if r.side > 0 else H[i0:i1].max(); pct = min(0.0, r.side * (wv - r.entry) / r.entry)
        out[k] = (pct * today[r.inst] - adv) * mult[r.inst]
    return out


def day_tables(intra, nights, night_risk, stop_for_m, budget=False):
    """intra: routed, stressed trades with per (per micro), mae (per micro, capped), risk (per micro), n (base micros), a/b ints, day.
    nights: same columns with n = 1. Returns {(m, night): {day: (p, worst, hit)}} for m = 1..4."""
    out = {}
    for m in (1, 2, 3, 4):
        qi = intra.n.to_numpy(float) if m == 1 else np.minimum(m * intra.n.to_numpy(float), np.floor(900.0 / intra.risk.to_numpy(float)))
        qn = 1.0 if m == 1 else float(min(m, int(900.0 // night_risk)))
        for night in (False, True):
            parts = [intra.assign(q=qi)]
            if night and qn >= 1: parts.append(nights.assign(q=qn))
            t = pd.concat(parts, ignore_index=True).sort_values(["a", "prio"], kind="stable")
            res = {}
            for d, g in t.groupby("day", sort=False):
                res[d] = sim_day(g.a.to_numpy(), g.b.to_numpy(), g.per.to_numpy(float), g.mae.to_numpy(float), g.risk.to_numpy(float),
                                 g.q.to_numpy(float), stop_for_m(m), budget)
            out[(m, night)] = res
    return out


def trade_marks(ts, H, L, side, entry, tin_ns, tout_ns, today, mult, adv, stop_px=None, stop_val=None):
    """Per-micro marks of one trade at each 1-minute bar's ADVERSE extreme (low for a long, high for a short) for bars starting in
    [tin, tout) - the bars mae_per_micro scans - in today's dollars, entry slippage included, NOT clipped at 0 (a trade in profit offsets
    the others). stop_px (long only, the overnight leg): from the first bar whose low reaches it the trade is out at stop_val.
    Returns (stamps ns int64, values)."""
    i0, i1 = int(np.searchsorted(ts, tin_ns)), int(np.searchsorted(ts, tout_ns))
    if i1 <= i0: return np.array([tin_ns], dtype=np.int64), np.array([-adv * mult])
    ext = L[i0:i1] if side > 0 else H[i0:i1]
    t = ts[i0:i1].astype(np.int64); v = (side * (ext - entry) / entry * today - adv) * mult
    if stop_px is not None:
        hit = np.nonzero(L[i0:i1] <= stop_px)[0]
        if len(hit):
            k = int(hit[0]); t = t[:k + 1]; v = v[:k + 1].copy(); v[k] = stop_val
    return t, v


def sim_day_path(a, b, per, q, stop, marks, dll=1000.0):
    """EXACT combined mark-to-market for a day (trades in entry order). marks[j] = (stamps, per-micro values) during [a_j, b_j).
    Day equity at each stamp = realised P&L of closed trades + sum of open trades' marks x size; the DLL liquidates the day at its
    first passage through -dll (no later entries, day = -dll). Account stop as sim_day. With marks flat at each trade's MAE this
    reduces exactly to sim_day (tests). Returns (p, worst, hit) like sim_day."""
    live = [j for j in range(len(per)) if q[j] >= 1]
    if not live: return 0.0, 0.0, False
    a = np.asarray(a, dtype=np.int64); b = np.asarray(b, dtype=np.int64)
    T = np.unique(np.concatenate([marks[j][0] for j in live] + [a[live], b[live]]))

    def vec(j):
        t, v = marks[j]; o = np.zeros(len(T)); k0 = int(np.searchsorted(T, a[j])); k1 = int(np.searchsorted(T, b[j]))
        if k1 > k0:
            idx = np.searchsorted(t, T[k0:k1], side="right") - 1
            o[k0:k1] = v[np.maximum(idx, 0)]
        o[k1:] = per[j]
        return o

    E = np.zeros(len(T)); acc = []; qs = {}; hit = False; w = 0.0; ck = 0
    for j in live:
        kj = int(np.searchsorted(T, a[j]))
        if kj > ck:
            mn = float(E[ck:kj].min()); w = min(w, mn)
            if mn <= -dll: hit = True; break
            ck = kj
        realised = float(sum(per[i] * qs[i] for i in acc if b[i] < a[j] or (b[i] == a[j] and a[i] < a[j])))
        if realised <= -stop: continue
        acc.append(j); qs[j] = float(q[j]); E += qs[j] * vec(j)
    if not hit and ck < len(T):
        mn = float(E[ck:].min()); w = min(w, mn); hit = mn <= -dll
    p = -dll if hit else float(sum(per[i] * qs[i] for i in acc))
    return max(p, -dll), max(min(w, p, 0.0), -dll), hit


def day_tables_path(intra, nights, night_risk, stop_for_m, marks, extra=None, extra_q=None, ms=(1, 2, 3, 4)):
    """day_tables with EXACT combined marks: days with >= 2 trades use sim_day_path, single-trade days sim_day (exact for one trade).
    intra / nights / extra need column 'mk' (index into `marks`). extra = an add-on sleeve NOT routed with the book, extra_q[m] micros
    at ladder multiplier m (0 = off). Returns {(m, night): {day: (p, worst, hit)}}."""
    out = {}
    for m in ms:
        qi = intra.n.to_numpy(float) if m == 1 else np.minimum(m * intra.n.to_numpy(float), np.floor(900.0 / intra.risk.to_numpy(float)))
        qn = 1.0 if m == 1 else float(min(m, int(900.0 // night_risk)))
        for night in (False, True):
            parts = [intra.assign(q=qi)]
            if night and qn >= 1: parts.append(nights.assign(q=qn))
            if extra is not None and (extra_q or {}).get(m, 0) >= 1: parts.append(extra.assign(q=float(extra_q[m])))
            t = pd.concat(parts, ignore_index=True).sort_values(["a", "prio"], kind="stable")
            res = {}
            for d, g in t.groupby("day", sort=False):
                A, B = g.a.to_numpy(), g.b.to_numpy(); P, Q = g.per.to_numpy(float), g.q.to_numpy(float)
                if len(g) == 1:
                    res[d] = sim_day(A, B, P, g.mae.to_numpy(float), g.risk.to_numpy(float), Q, stop_for_m(m))
                else:
                    res[d] = sim_day_path(A, B, P, Q, stop_for_m(m), [marks[k] for k in g.mk.to_numpy()])
            out[(m, night)] = res
    return out


def replay(tables, ladder, K, gate=None, sprint=False, a0="2010-07-01", a1="2022-01-01", months=24):
    """tables: {'base': {(m, night): {day: (p, w, hit)}}, optional 'stack': ...}. Static Daily Payouts+: floor -$2,000 until the first
    payout, then $0, checked on the intraday worst; daily path payouts $250-$1,500 above K while net profit since the last payout > 0;
    optional sprint P1 $500 at $6,000; overnight leg while balance >= $500; stack book from `gate`. Full calendar (union of all days)."""
    days = sorted(set().union(*[set(d) for t in tables.values() for d in t.values()]))
    ix = pd.to_datetime(pd.Series(days).astype(str)).to_numpy(); rows = []
    for s0 in pd.date_range(a0, a1, freq="MS"):
        a = int(np.searchsorted(ix, np.datetime64(s0))); b = int(np.searchsorted(ix, np.datetime64(s0 + pd.DateOffset(months=months))))
        y1 = np.datetime64(s0 + pd.DateOffset(months=12))
        bal = 0.0; paid = 0; since = 0.0; usd = 0.0; closed = False; low = 0.0; first = 730.0; p1 = 0; dll_days = 0
        for j in range(a, b):
            x = days[j]
            m = max((mm for th, mm in ladder if bal >= th), default=1); floor = 0.0 if paid else -2000.0
            T = tables["stack" if (gate is not None and bal >= gate) else "base"]
            p, w, hit = T[(m, bal >= 500.0)].get(x, (0.0, 0.0, False)); dll_days += hit
            if not paid: low = min(low, bal + min(w, p))
            if bal + min(w, p) <= floor: closed = True; bal = floor; break
            bal += p; since += p
            wd = 0.0
            if sprint and not paid and bal >= 6000.0: wd = 500.0
            elif (since > 0 or not paid) and bal - K >= 250.0: wd = min(1500.0, bal - K)
            if wd:
                bal -= wd; usd += wd; paid += 1; since = 0.0
                if first == 730.0: first = float((pd.Timestamp(x) - s0).days)
                if ix[j] < y1: p1 += 1
        end = 0.0 if closed else bal
        rows.append(dict(start=str(s0.date()), usd=usd, value=usd + max(0.0, end - 2000.0), closed=closed, near=low <= -1500.0,
                         first=first, y1_pays=p1, pays=paid, end=end, dll_days=dll_days))
    return pd.DataFrame(rows)


def summ(r, h1_end="2016-06-01", h2_start="2016-07-01"):
    h1 = r[r.start < h1_end]; h2 = r[r.start >= h2_start]
    return dict(usd=round(float(r.usd.mean()), 0), usd_h1=round(float(h1.usd.mean()), 0), usd_h2=round(float(h2.usd.mean()), 0),
                value=round(float(r.value.mean()), 0), value_h1=round(float(h1.value.mean()), 0), value_h2=round(float(h2.value.mean()), 0),
                closed=round(float(r.closed.mean()), 4), near=round(float(r.near.mean()), 4), first_median=float(r["first"].median()),
                y1_pays=round(float(r.y1_pays.mean()), 2), pays=round(float(r.pays.mean()), 2), end=round(float(r.end.mean()), 0),
                dll_days=round(float(r.dll_days.mean()), 2), windows=len(r))
