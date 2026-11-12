"""payout_26 (Claude, 2026-11-11): one scoreboard for the funded payout rules, and a router question. TRAINING 2010-23 only.

Why: Codex's correction of Antigravity's triple stack (reports/GEMINI_STACK_CONTINUATION_TRAIN.json) moved $44,654 -> $29,082 by applying
two changes together: the 2019 data-hole fill and swapping payout_lib.route (the "posthoc" router) for one-position routing. payout_lib.route
is causal (a trade is skipped only when an ACCEPTED trade entered at or before its decision-bar start is still open; trades are processed by
decision time, so nothing is known early), so the swap is a strategy change, not a bug fix. And the paper incumbent, Fortress 4X, was last
scored with the 2019 hole. Nothing on the funded track has been compared on one footing.

Footing for every cell: TRAIN_MINI_UNTIL=2019-05-06 (hole filled), full calendar (union of all books' trading days, Codex's fix), Antigravity's
table builder (research_uncapped_and_sleeves.build_tables: stressed S0/S3/S4 costs, cap-aware size min(m x base, floor($900 / risk)), account
stop $400 at 1x / $700 above, overnight leg while balance >= $500, DLL clip -$1,000, end-of-day floor check), 139 monthly starts 2010-07..2022-01,
24 months each; halves = starts 2010-07..2016-06 / 2016-07..2022-01.

Cells (2 rules x 2 routers):
  F4X  Fortress 4X (paper incumbent): v5.3 base book only, 1x / 2x from $4,000 / 3x from $4,800 / 4x from $6,500, payouts above K $8,500
       ($250-$1,500 per day, net profit since the last payout > 0), no sprint.
  TRI  Antigravity's triple stack as Codex reproduced it: K $8,600; base book below $8,700, base+MNQ_BRK_E+MES_MOM from $8,700, the triple
       book (adds Crabel GAP, MNQ_VOL, BRK30, MORN30, TRD30PM) from $8,700; ladder 4000 / 4600 / 5400; sprint P1 $500 at $6,000.
  Routers: POSTHOC = payout_lib.route (what the paper funded card does), ONEPOS = one position at a time (eval_harness.route_strict_causal).
Parity: TRI + ONEPOS S0 must reproduce Codex's $29,081.60 (same books, priorities, data) before any result is read.

PRE-DECLARED READINGS (fixed before results):
  R1 attribution: report POSTHOC vs ONEPOS for TRI on the filled data, so Codex's -$15.6k step is split into gap fill vs router.
  R2 funded routing: switch the funded rule (F4X) to ONEPOS only if, vs F4X POSTHOC: S0 dollars >= 0.95x in BOTH halves, closure S3 and S4
     not higher, near-miss (lowest balance before the first payout <= -$1,500) S0/S3/S4 each not higher with at least one strictly lower.
  R3 champion vs stack: TRI beats F4X (same router) only if S0 dollars >= 1.05x in BOTH halves, closure S0/S3/S4 <= F4X + 0.005 and
     conservative stop-risk flag S0/S3/S4 <= F4X + 0.02. Reported for both routers; the decision uses the router R2 picks.
No parameter is searched; 4 cells. Validation / test / paper outcomes are not loaded (load_bars is guarded to split='train', end <= 2024).
"""
import os
os.environ["TRAIN_MINI_UNTIL"] = "2019-05-06"
import json, sys, time
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import mass_1m_search as m1
assert m1.MINI_UNTIL == "2019-05-06"
_old = m1.load_bars
def _guarded(product, res, start, end, split):
    if split != "train" or pd.Timestamp(end) > pd.Timestamp("2024-01-01"): raise PermissionError("TRAIN-only boundary")
    return _old(product, res, start, end, split)
m1.load_bars = _guarded

t0 = time.time()
source = ROOT / "scripts/research_uncapped_and_sleeves.py"
prefix = source.read_text(encoding="utf-8").split('print("Building tables')[0]
V = dict(__name__="payout_26", __file__=str(source)); exec(prefix, V)
pl, ep, bars_for, START, build_tables = V["pl"], V["ep"], V["bars_for"], V["START"], V["build_tables"]
cols = V["df_base"].columns
EXTRAS = [("AG_BRK30_1c", "ag_all_weather", 16), ("AG_MORN30_1c", "ag_quad", 17), ("AG_TRD30PM_1c_v52", "ag_arch_d_plus_v2_1c_v52", 18)]
triple = V["df_vol"]
for name, key, prio in EXTRAS:
    sl = next(s for s in ep.CANDIDATES[key]["sleeves"] if s["name"] == name)
    x = pl.price_normalize(pl.sleeve_trades(ep, bars_for, START, dict(sl), prio, False)); x["n_contracts"] = 1.0; x["mae_per_micro"] = 0.0
    triple = pd.concat([triple, x[cols]], ignore_index=True)
BOOKS = {"base": V["df_base"], "both": V["df_both"], "triple": triple}
print("books", {k: len(v) for k, v in BOOKS.items()}, f"{time.time() - t0:.0f}s", flush=True)

POSTHOC = pl.route


def onepos(df):
    keep = []; until = None; last = None
    for r in df.sort_values(["tin", "prio"], kind="stable").itertuples():
        if until is not None and (r.tin < until or r.tin == last): continue
        until = r.tout if until is None else max(until, r.tout); last = r.tin; keep.append(r.Index)
    return df.loc[keep]


TABLES = {}
for rname, rfun in (("POSTHOC", POSTHOC), ("ONEPOS", onepos)):
    pl.route = rfun
    TABLES[rname] = {b: build_tables(d) for b, d in BOOKS.items()}
    print("tables", rname, f"{time.time() - t0:.0f}s", flush=True)
pl.route = POSTHOC

A0, A1 = "2010-07-01", "2022-01-01"
HALVES = (("2010-07-01", "2016-06-01"), ("2016-07-01", "2022-01-01"))


def replay(T, kind, ladder, K, gates=None, sprint=False, max_p4=1500.0):
    """T: book -> (SER, RISK). gates=(g1, g2): 'both' from g1, 'triple' from g2; None = base book only. Full calendar = union of T's days."""
    books = ("base",) if gates is None else ("base", "both", "triple")
    days = sorted(set().union(*[set(T[b][0][k]) for b in books for k in T[b][0] if k[0] == kind]))
    ix = pd.to_datetime(pd.Series(days).astype(str)).to_numpy(); rows = []
    for s0 in pd.date_range(A0, A1, freq="MS"):
        a = int(np.searchsorted(ix, np.datetime64(s0))); b = int(np.searchsorted(ix, np.datetime64(s0 + pd.DateOffset(months=24))))
        y1 = np.datetime64(s0 + pd.DateOffset(months=12))
        bal = 0.0; paid = 0; since = 0.0; usd = 0.0; closed = False; cons = False; low = 0.0; first = 730.0; p1 = 0; u1 = 0.0; pnl = 0.0
        for j in range(a, b):
            x = days[j]
            m = max((mm for th, mm in ladder if bal >= th), default=ladder[0][1]); floor = 0.0 if paid else -2000.0
            bk = "base" if gates is None else ("triple" if bal >= gates[1] else "both" if bal >= gates[0] else "base")
            SER, RISK = T[bk]
            if bal - RISK[(kind, m)].get(x, 0.0) <= floor: cons = True
            p = max(SER[(kind, m, bal >= 500.0)].get(x, 0.0), -1000.0); bal += p; since += p; pnl += p
            if not paid: low = min(low, bal)
            if bal <= floor: closed = True; break
            w = 0.0
            if sprint and not paid and bal >= 6000.0: w = 500.0
            elif (since > 0 or not paid) and bal - K >= 250.0: w = min(1500.0 if paid < 3 else max_p4, bal - K)
            if w:
                bal -= w; usd += w; paid += 1; since = 0.0
                if first == 730.0: first = float((pd.Timestamp(x) - s0).days)
                if ix[j] < y1: p1 += 1; u1 += w
        rows.append(dict(start=str(s0.date()), usd=usd, closed=closed, cons=cons, near=low <= -1500.0, first=first, y1_pays=p1, y1_usd=u1,
                         pnl=pnl, pays=paid, low=low))
    return pd.DataFrame(rows)


def summ(r):
    h1 = r[r.start < HALVES[0][1]]; h2 = r[r.start >= HALVES[1][0]]
    return dict(usd=round(float(r.usd.mean()), 2), usd_h1=round(float(h1.usd.mean()), 0), usd_h2=round(float(h2.usd.mean()), 0),
                closed=round(float(r.closed.mean()), 4), cons=round(float(r.cons.mean()), 4), near=round(float(r.near.mean()), 4),
                first_median=float(r["first"].median()), y1_pays=round(float(r.y1_pays.mean()), 2), y1_usd=round(float(r.y1_usd.mean()), 0),
                pays=round(float(r.pays.mean()), 2), pnl=round(float(r.pnl.mean()), 0), worst_low=round(float(r.low.min()), 0), windows=len(r))


RULES = {"F4X": dict(ladder=((0, 1), (4000, 2), (4800, 3), (6500, 4)), K=8500.0),
         "TRI": dict(ladder=((0, 1), (4000, 2), (4600, 3), (5400, 4)), K=8600.0, gates=(8700.0, 8700.0), sprint=True)}
out = dict(spec=__doc__.split("PRE-DECLARED")[0].strip()[:300], mini_until=m1.MINI_UNTIL, cells={}, paths={})
for rname in ("POSTHOC", "ONEPOS"):
    for cname, kw in RULES.items():
        c = out["cells"][f"{cname}_{rname}"] = {}
        for kind in ("S0", "S3", "S4"):
            r = replay(TABLES[rname], kind, **kw); c[kind] = summ(r)
            if kind == "S0": out["paths"][f"{cname}_{rname}"] = r[["start", "usd", "closed", "low"]].to_dict("list")
        print(cname, rname, json.dumps({k: c[k] for k in ("S0", "S3", "S4")}), flush=True)

C = out["cells"]
out["parity_codex_tri_onepos_S0"] = dict(mine=C["TRI_ONEPOS"]["S0"]["usd"], codex=29081.60, diff=round(C["TRI_ONEPOS"]["S0"]["usd"] - 29081.60, 2))


def r2(inc, ch):
    a, b = C[inc], C[ch]
    dollars = all(b["S0"][h] >= 0.95 * a["S0"][h] for h in ("usd_h1", "usd_h2"))
    closure = all(b[s]["closed"] <= a[s]["closed"] for s in ("S3", "S4"))
    near = all(b[s]["near"] <= a[s]["near"] for s in ("S0", "S3", "S4")) and any(b[s]["near"] < a[s]["near"] for s in ("S0", "S3", "S4"))
    return dict(dollars_ok=dollars, closure_ok=closure, near_ok=near, switch=bool(dollars and closure and near))


def r3(rt):
    a, b = C[f"F4X_{rt}"], C[f"TRI_{rt}"]
    dollars = all(b["S0"][h] >= 1.05 * a["S0"][h] for h in ("usd_h1", "usd_h2"))
    closure = all(b[s]["closed"] <= a[s]["closed"] + 0.005 for s in ("S0", "S3", "S4"))
    cons = all(b[s]["cons"] <= a[s]["cons"] + 0.02 for s in ("S0", "S3", "S4"))
    return dict(dollars_ok=dollars, closure_ok=closure, cons_ok=cons, tri_beats_f4x=bool(dollars and closure and cons))


out["R1_tri_router_effect_S0"] = round(C["TRI_ONEPOS"]["S0"]["usd"] - C["TRI_POSTHOC"]["S0"]["usd"], 0)
out["R2_funded_routing"] = r2("F4X_POSTHOC", "F4X_ONEPOS")
rt = "ONEPOS" if out["R2_funded_routing"]["switch"] else "POSTHOC"
out["R3_router_used"] = rt
out["R3_by_router"] = {k: r3(k) for k in ("POSTHOC", "ONEPOS")}
out["R3_decision"] = out["R3_by_router"][rt]
out["validation_accessed"] = False; out["test_accessed"] = False
print("PARITY", out["parity_codex_tri_onepos_S0"], flush=True)
print("R1", out["R1_tri_router_effect_S0"], "R2", out["R2_funded_routing"], "R3", out["R3_decision"], flush=True)
(ROOT / "reports/PAYOUT_26_ROUTER_SCOREBOARD_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
print("saved", f"{time.time() - t0:.0f}s", flush=True)
