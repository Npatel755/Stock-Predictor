"""payout_27 (Claude, 2026-11-11): what the triple stack should contain. TRAINING 2010-23 only.

Context: payout_26 put the triple stack (TRI) and Fortress 4X on one footing (2019 hole filled, full calendar, posthoc router): TRI S0
$45,455 vs $35,870, same closures. TRI's K / gates were picked by Antigravity on all 14 years, so they are NOT tuned further here. This
asks only which sleeves the stack book (used at balance >= $8,700) should hold. Its 7 added sleeves (on top of the v5.3 base book):
MNQ_BRK_E_2c, MES_MOM_3c, AG_CRABEL15_D_GAP_v53, MNQ_VOL_1c, AG_BRK30_1c, AG_MORN30_1c, AG_TRD30PM_1c_v52 (several were picked on all
14 years too, so dropping one is the low-risk direction).

Cells (12): TRI baseline | drop each of the 7 | add each of Codex's 4 extras (AG_TRD60Q_1c, AG_MES_TRD30_1c, MNQ_E57_1c, MES_MOM_1c).
Everything else exactly as payout_26 TRI_POSTHOC (K $8,600, gates $8,700, ladder 4000 / 4600 / 5400, sprint P1 $500 at $6,000, payouts
$250-$1,500, posthoc router, S0 / S3 / S4 tables, 139 x 24-month windows, halves = starts 2010-07..2016-06 / 2016-07..2022-01).

PRE-DECLARED RULE (fixed before results):
  A single change QUALIFIES if vs baseline: S0 dollars >= +2% in BOTH halves; S3 and S4 dollars not lower; closure S0 / S3 / S4 <= baseline
  + 0.005 (i.e. not one extra closed window); conservative stop-risk flag S0 / S3 / S4 <= baseline + 0.02.
  If >= 2 changes qualify, ALL qualifying changes applied together form one combined cell, which must pass the same rule vs baseline; if it
  fails, the single qualifier with the largest min(half1 gain, half2 gain) is the pick. If none qualify, TRI stays as is.
  Also reported (not used to decide): ending balance (money still in the account at 24 months) and withdrawn + ending.
Validation / test / paper outcomes are not loaded (load_bars guarded to split='train', end <= 2024).
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
V = dict(__name__="payout_27", __file__=str(source)); exec(prefix, V)
pl, ep, bars_for, START, build_tables = V["pl"], V["ep"], V["bars_for"], V["START"], V["build_tables"]
base = V["df_base"]; cols = base.columns


def sleeve(name, key, prio):
    sl = next(s for s in ep.CANDIDATES[key]["sleeves"] if s["name"] == name)
    x = pl.price_normalize(pl.sleeve_trades(ep, bars_for, START, dict(sl), prio, False)); x["n_contracts"] = 1.0; x["mae_per_micro"] = 0.0
    return x[cols]


ADDED = {"MNQ_BRK_E_2c": ("portfolio_e", 10), "MES_MOM_3c": ("portfolio_e", 11), "AG_CRABEL15_D_GAP_v53": ("ag_arch_d_plus_v2_gap_addon_v53", 12),
         "MNQ_VOL_1c": ("ensemble_epsilon", 13), "AG_BRK30_1c": ("ag_all_weather", 16), "AG_MORN30_1c": ("ag_quad", 17),
         "AG_TRD30PM_1c_v52": ("ag_arch_d_plus_v2_1c_v52", 18)}
EXTRA = {"AG_TRD60Q_1c": ("ag_quad", 19), "AG_MES_TRD30_1c": ("ag_quad", 20), "MNQ_E57_1c": ("ensemble_epsilon", 20), "MES_MOM_1c": ("ensemble_epsilon", 20)}
X = {n: sleeve(n, k, p) for n, (k, p) in {**ADDED, **EXTRA}.items()}
print("sleeve trades", {n: len(x) for n, x in X.items()}, f"{time.time() - t0:.0f}s", flush=True)
BASE_T = build_tables(base)


def stack(names): return pd.concat([base] + [X[n] for n in names], ignore_index=True)


CELLS = {"baseline": list(ADDED)}
for n in ADDED: CELLS[f"drop {n}"] = [m for m in ADDED if m != n]
for n in EXTRA: CELLS[f"add {n}"] = list(ADDED) + [n]

A0, A1 = "2010-07-01", "2022-01-01"; HALVES = (("2010-07-01", "2016-06-01"), ("2016-07-01", "2022-01-01"))
LADDER, K, GATE = ((0, 1), (4000, 2), (4600, 3), (5400, 4)), 8600.0, 8700.0


def replay(T, kind):
    """T: {'base': (SER, RISK), 'stack': (SER, RISK)}; stack book from GATE; full calendar = union of both books' days."""
    days = sorted(set().union(*[set(T[b][0][k]) for b in T for k in T[b][0] if k[0] == kind]))
    ix = pd.to_datetime(pd.Series(days).astype(str)).to_numpy(); rows = []
    for s0 in pd.date_range(A0, A1, freq="MS"):
        a = int(np.searchsorted(ix, np.datetime64(s0))); b = int(np.searchsorted(ix, np.datetime64(s0 + pd.DateOffset(months=24))))
        y1 = np.datetime64(s0 + pd.DateOffset(months=12))
        bal = 0.0; paid = 0; since = 0.0; usd = 0.0; closed = False; cons = False; low = 0.0; first = 730.0; p1 = 0; u1 = 0.0
        for j in range(a, b):
            x = days[j]
            m = max((mm for th, mm in LADDER if bal >= th), default=1); floor = 0.0 if paid else -2000.0
            SER, RISK = T["stack" if bal >= GATE else "base"]
            if bal - RISK[(kind, m)].get(x, 0.0) <= floor: cons = True
            p = max(SER[(kind, m, bal >= 500.0)].get(x, 0.0), -1000.0); bal += p; since += p
            if not paid: low = min(low, bal)
            if bal <= floor: closed = True; break
            w = 0.0
            if not paid and bal >= 6000.0: w = 500.0
            elif (since > 0 or not paid) and bal - K >= 250.0: w = min(1500.0, bal - K)
            if w:
                bal -= w; usd += w; paid += 1; since = 0.0
                if first == 730.0: first = float((pd.Timestamp(x) - s0).days)
                if ix[j] < y1: p1 += 1; u1 += w
        rows.append(dict(start=str(s0.date()), usd=usd, closed=closed, cons=cons, near=low <= -1500.0, first=first, y1_pays=p1, y1_usd=u1,
                         end=0.0 if closed else bal))
    return pd.DataFrame(rows)


def summ(r):
    h1 = r[r.start < HALVES[0][1]]; h2 = r[r.start >= HALVES[1][0]]
    return dict(usd=round(float(r.usd.mean()), 0), usd_h1=round(float(h1.usd.mean()), 0), usd_h2=round(float(h2.usd.mean()), 0),
                closed=round(float(r.closed.mean()), 4), cons=round(float(r.cons.mean()), 4), near=round(float(r.near.mean()), 4),
                first_median=float(r["first"].median()), y1_pays=round(float(r.y1_pays.mean()), 2), y1_usd=round(float(r.y1_usd.mean()), 0),
                end_bal=round(float(r.end.mean()), 0), usd_plus_end=round(float((r.usd + r.end).mean()), 0))


def score(names):
    T = {"base": BASE_T, "stack": build_tables(stack(names))}
    c = {kind: summ(replay(T, kind)) for kind in ("S0", "S3", "S4")}
    return c


def check(c, b):
    g1 = c["S0"]["usd_h1"] / b["S0"]["usd_h1"] - 1; g2 = c["S0"]["usd_h2"] / b["S0"]["usd_h2"] - 1
    ok = (g1 >= 0.02 and g2 >= 0.02 and all(c[s]["usd"] >= b[s]["usd"] for s in ("S3", "S4"))
          and all(c[s]["closed"] <= b[s]["closed"] + 0.005 for s in ("S0", "S3", "S4"))
          and all(c[s]["cons"] <= b[s]["cons"] + 0.02 for s in ("S0", "S3", "S4")))
    return dict(gain_h1=round(g1, 4), gain_h2=round(g2, 4), qualifies=bool(ok))


out = dict(cells={}, checks={}, validation_accessed=False, test_accessed=False)
for name, names in CELLS.items():
    out["cells"][name] = score(names)
    s = out["cells"][name]
    print(f"{name:32s}", " | ".join(f"{k} {s[k]['usd']:.0f} ({s[k]['usd_h1']:.0f}/{s[k]['usd_h2']:.0f}) cl {s[k]['closed']:.3f} cons {s[k]['cons']:.3f}"
                                     for k in ("S0", "S3", "S4")), f"end {s['S0']['end_bal']:.0f}", f"{time.time() - t0:.0f}s", flush=True)
B = out["cells"]["baseline"]
assert abs(B["S0"]["usd"] - 45455) <= 1, f"baseline must reproduce payout_26 TRI_POSTHOC S0 $45,455: {B['S0']['usd']}"
for name in CELLS:
    if name != "baseline": out["checks"][name] = check(out["cells"][name], B)
Q = [n for n, v in out["checks"].items() if v["qualifies"]]
out["qualifiers"] = Q
pick = None
if len(Q) >= 2:
    names = list(ADDED)
    for q in Q:
        verb, sl = q.split(" ", 1)
        names = [m for m in names if m != sl] if verb == "drop" else names + [sl]
    out["cells"]["combined"] = score(names); out["combined_sleeves"] = names
    out["checks"]["combined"] = check(out["cells"]["combined"], B)
    pick = "combined" if out["checks"]["combined"]["qualifies"] else max(Q, key=lambda n: min(out["checks"][n]["gain_h1"], out["checks"][n]["gain_h2"]))
elif Q:
    pick = Q[0]
out["pick"] = pick or "baseline (no change)"
print("QUALIFIERS", Q, "PICK", out["pick"], json.dumps(out["checks"].get(pick, {})), flush=True)
(ROOT / "reports/PAYOUT_27_STACK_CONTENT_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
print("saved", f"{time.time() - t0:.0f}s", flush=True)
