"""eval_10 (Claude, 2026-11-10): a calendar leg (turn-of-month / pre-holiday long) for the $50K Static Combine. TRAINING 2010-23 only.

PRE-DECLARED (written before any result).
Hypothesis (literature: Ariel 1987, Lakonishok & Smidt 1988, McConnell & Xu 2008 turn-of-the-month; pre-holiday effect): US index returns
are concentrated on the last trading day of the month plus the first three, and on the day before a market holiday. A long MNQ hold on those
sessions adds independent positive bets to the evaluation book.
Leg: long 1 micro MNQ per qualifying session; costs as payout_lib (0.5 pt per side, $1 fee), re-expressed at today's price (27,981.5);
  stop s% below the entry (gap-through fills at the bar open); flat by 15:55 ET (Topstep: flat by 3:10 PM CT).
Cells: hold RTH (09:35 -> 15:55 ET) | FULL (18:05 ET the evening before -> 15:55 ET, same Globex session)  x  stop 0.5% | 1.0%
  x  days TOM (last session of the month + first 3) | TOM+PRE (plus the session before a weekday market holiday) = 8 cells.
GATE 1 (edge beyond drift, per fold): the cell's mean net per trade > $0 AND > the same hold's mean on all other sessions (it must beat
  simply being long). Folds: A = 2010-06..2016-12, B = 2017-01..2023-12. A cell is eligible only if it passes in BOTH folds.
GATE 2 (evaluation, 2-fold as eval_9): eligible cell with the best fold-A excess is added to the eval_8 incumbent (SLEEVES + DEF + ENDGAME)
  and run on fold-B starts; best on fold B is run on fold-A starts. Size min(k, floor($900 / stop risk)), not routed (like the overnight leg).
  Floor and DLL are checked CONSERVATIVELY: while the leg is open, every intraday trade's adverse excursion is added to the leg's full MAE;
  the leg's P&L is booked at the end of the day. ADOPT only if both out-of-fold halves >= incumbent's same half + 1.0 point.
Placebo: the chosen cell's hold on randomly drawn non-qualifying sessions (same count, seed 7) also run through GATE 2's evaluation.
"""
import json
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/eval_9_optimal_sizing_train.py").read_text(encoding="utf-8").split("\nout = {}\n")[0]
E = {"__name__": "e10", "__file__": str(ROOT / "scripts/eval_9_optimal_sizing_train.py")}; exec(src, E)
pl, TAB, SESS, A, B, DEF_END, P10 = (E[k] for k in ("pl", "TAB", "SESS", "A", "B", "DEF_END", "P10"))
NY = pl.NY; FA_END = pd.Timestamp("2017-01-01").date()
m1 = P10["m1"]; ts = pd.to_datetime(m1.timestamp_utc, utc=True).dt.tz_convert(NY)
TSV = ts.dt.tz_localize(None).to_numpy(); O, Hh, L, C = (m1[c].to_numpy(float) for c in ("open", "high", "low", "close"))
DAYS = sorted(set(ts[(ts.dt.hour * 60 + ts.dt.minute >= 575) & (ts.dt.hour < 16)].dt.date))
DAYS = [d for d in DAYS if pd.Timestamp(d).dayofweek < 5 and pd.Timestamp("2010-06-07").date() <= d <= pd.Timestamp("2023-12-29").date()]
DSET = set(DAYS)

# qualifying sessions
mon = pd.Series([d.year * 12 + d.month for d in DAYS]); TOM = set()
for i, d in enumerate(DAYS):
    if i + 1 < len(DAYS) and mon[i + 1] != mon[i]: TOM.add(d)                       # last session of the month
    if i == 0 or mon[i - 1] != mon[i]: TOM.update(DAYS[i:i + 3])                     # first three of the month
PRE = {d for d in DAYS if (nxt := (pd.Timestamp(d) + pd.offsets.BDay(1)).date()) not in DSET and nxt <= DAYS[-1]}


def hold(d, prev, kind, stop):
    t1 = np.datetime64(pd.Timestamp(f"{d} 15:55")); i1 = int(np.searchsorted(TSV, t1)) - 1                   # last bar before 15:55
    t0 = np.datetime64(pd.Timestamp(f"{d} 09:35")) if kind == "RTH" else np.datetime64(pd.Timestamp(f"{prev} 18:05"))
    i0 = int(np.searchsorted(TSV, t0))
    if i1 <= i0 or pd.Timestamp(TSV[i0]).date() > d: return None
    e = O[i0]; st = e * (1 - stop); hit = np.nonzero(L[i0:i1 + 1] <= st)[0]
    if len(hit): j = i0 + int(hit[0]); x = min(st, O[j]) if j > i0 else st; low = x
    else: x = C[i1]; low = L[i0:i1 + 1].min()
    pm = (((x - e) / e) * pl.TODAY["MNQ"] - 2 * pl.ADV) * pl.MULT["MNQ"] - pl.FEE
    mae = min(pm, (min(0.0, (low - e) / e) * pl.TODAY["MNQ"] - pl.ADV) * pl.MULT["MNQ"])
    return dict(day=d, tin=pd.Timestamp(TSV[i0]).tz_localize(NY), tout=pd.Timestamp(TSV[i1]).tz_localize(NY), per_micro=pm, mae=mae,
                risk=stop * pl.TODAY["MNQ"] * pl.MULT["MNQ"] + 1.0 + 0.75 * pl.MULT["MNQ"])


LEGS = {}
for kind in ("RTH", "FULL"):
    for stop in (0.005, 0.010):
        rows = [hold(d, DAYS[i - 1], kind, stop) for i, d in enumerate(DAYS) if i > 0]
        LEGS[(kind, stop)] = pd.DataFrame([r for r in rows if r is not None]).set_index("day")
out = {"cells": {}}; elig = []
for (kind, stop), df in LEGS.items():
    for name, days in (("TOM", TOM), ("TOM+PRE", TOM | PRE)):
        cell = f"{kind} stop {stop:.1%} {name}"; res = {}
        ok = True
        for fold, (lo, hi) in (("A", ("2010-06-07", "2016-12-31")), ("B", ("2017-01-01", "2023-12-31"))):
            f = df[(df.index >= pd.Timestamp(lo).date()) & (df.index <= pd.Timestamp(hi).date())]
            q = f[f.index.isin(days)].per_micro; o = f[~f.index.isin(days)].per_micro
            res[fold] = dict(n=len(q), mean=round(float(q.mean()), 1), others_mean=round(float(o.mean()), 1), excess=round(float(q.mean() - o.mean()), 1),
                             pf=round(float(q[q > 0].sum() / -q[q < 0].sum()), 2), total=round(float(q.sum()), 0))
            ok &= res[fold]["mean"] > 0 and res[fold]["excess"] > 0
        res["gate1"] = bool(ok); out["cells"][cell] = res; print(cell, res, flush=True)
        if ok: elig.append((cell, kind, stop, days, res))

by, td, tix = TAB


def evaluate_leg(leg, starts, rule=DEF_END):
    """eval_9.evaluate2 plus the calendar leg: conservative concurrent MAE, leg P&L booked at the end of the day."""
    res = []
    legd = {d: r for d, r in leg.iterrows()} if leg is not None else {}
    days_all = sorted(set(td) | set(legd)); dix = pd.to_datetime(pd.Series(days_all).astype(str)).to_numpy()
    for s in starts:
        end = (pd.Timestamp(s) + pd.Timedelta(days=90)).date(); i = int(np.searchsorted(dix, np.datetime64(pd.Timestamp(s))))
        bal = 0.0; best = 0.0; out_ = "timeout"
        for d in days_all[i:]:
            if d >= end: break
            tgt = max(4000.0, best / 0.55); k = rule(bal, (d - s).days, tgt, int(np.busday_count(d, end)))
            lg = legd.get(d); lq = int(min(k, np.floor(900.0 / lg["risk"]))) if lg is not None else 0
            lmae = lg["mae"] * lq if lq else 0.0; day = 0.0; w = lmae; dll = lmae <= -1000.0
            if d in by and not dll:
                per, mae, n, risk = by[d]; q = np.minimum(k * n, np.floor(900.0 / risk)); stop = 400.0 if np.all(q <= n) else 700.0
                for j in range(len(per)):
                    if q[j] < 1: continue
                    if day <= -stop or day <= -1000.0: break
                    w = min(w, day + mae[j] * q[j] + lmae)
                    if day + mae[j] * q[j] + lmae <= -1000.0: dll = True; break
                    day += per[j] * q[j]
            p = -1000.0 if dll else max(day + (lg["per_micro"] * lq if lq else 0.0), -1000.0)
            if bal + min(w, p) <= -2000.0: out_ = "fail"; break
            bal += p; best = max(best, p)
            if bal >= max(4000.0, best / 0.55): out_ = "pass"; break
        res.append(out_)
    r = pd.Series(res)
    return dict(pass_=round(100 * float((r == "pass").mean()), 1), fail=round(100 * float((r == "fail").mean()), 1),
                timeout=round(100 * float((r == "timeout").mean()), 1), n=len(r))


inc = dict(h1=evaluate_leg(None, A), h2=evaluate_leg(None, B)); out["incumbent"] = inc; print("incumbent", inc, flush=True)
if elig:
    pickA = max(elig, key=lambda c: c[4]["A"]["excess"]); pickB = max(elig, key=lambda c: c[4]["B"]["excess"])
    def leg_of(c): df = LEGS[(c[1], c[2])]; return df[df.index.isin(c[3])]
    onB = evaluate_leg(leg_of(pickA), B); onA = evaluate_leg(leg_of(pickB), A)
    adopt = bool(onA["pass_"] >= inc["h1"]["pass_"] + 1.0 and onB["pass_"] >= inc["h2"]["pass_"] + 1.0)
    out["gate2"] = dict(picked_on_A=pickA[0], picked_on_B=pickB[0], oof_h1=onA, oof_h2=onB,
                        oof_all=round((onA["pass_"] * onA["n"] + onB["pass_"] * onB["n"]) / (onA["n"] + onB["n"]), 1), adopt=adopt)
    rng = np.random.default_rng(7); df = LEGS[(pickA[1], pickA[2])]; pool = df[~df.index.isin(pickA[3])]
    plc = pool.iloc[np.sort(rng.choice(len(pool), size=int(df.index.isin(pickA[3]).sum()), replace=False))]
    out["placebo_random_days"] = dict(h1=evaluate_leg(plc, A), h2=evaluate_leg(plc, B))
    print("gate2", out["gate2"], "placebo", out["placebo_random_days"], flush=True)
else:
    out["gate2"] = "no cell passed gate 1 in both folds"; print(out["gate2"])
(ROOT / "reports/EVAL_10_CALENDAR_LEG_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
