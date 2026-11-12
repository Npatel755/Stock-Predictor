"""payout_28 (Claude, 2026-11-11): (A) are payout_27's two added sleeves signal or drift? (B) sweep the stuck balance with the 5-winning-day
path. TRAINING 2010-23 only.

Context: payout_27 adopted TRI+2 (triple stack + AG_TRD60Q_1c + MNQ_E57_1c in the book used at balance >= $8,700): S0 $51,036 per 24 months
withdrawn, but $23,671 is still in the account at 24 months on average, because the daily path pays at most $1,500 per day. Nick's account
card (screenshot 2026-11-11): "Both payout paths included. Once eligible, you can request payouts from either path at any time. Daily payouts
up to $1,500. 5 winning days up to $8,000." 5WD path rules as read on 2026-11-10 (payout_23): 5 days with P&L >= $150 since the last payout
(request day excluded), payout <= 50% of balance, <= $8,000, >= $125; any payout resets the count.

PART A - placebo test of the two adds (diagnostic, S0 only). For S in {AG_TRD60Q_1c, MNQ_E57_1c}, added to TRI: (i) the real sleeve;
(ii) ALWAYS-LONG: same entry/exit times and prices, side +1; (iii) RANDOM side: same times, side +-1 at random, 20 seeds (0..19).
Net recomputed with payout_lib.price_normalize; stop risk unchanged; routing identical (same times and priorities).
PRE-DECLARED reading: S is SIGNAL if its gain over TRI beats the always-long gain in BOTH halves AND beats the 19th of 20 random-side
gains in BOTH halves. A sleeve that fails is removed from the adopted stack before Part B (Part B then runs on the reduced stack).
Also reported: per-half trades, net per micro and PF by side.

PART B - withdrawal policy on the stack Part A leaves. Same account model as payout_27 (K $8,600, stack from $8,700, ladder 4000/4600/5400,
sprint P1 $500 at $6,000, DLL clip, end-of-day floor, posthoc router, S0/S3/S4, 139 x 24 months).
  D      daily path only (baseline; with TRI+2 it must reproduce payout_27's $51,036).
  H1500 / H4000 / H8000  hybrid: daily path while balance - K < B; once balance - K >= B, take no daily payouts and wait until the 5WD
         path is eligible, then take min(50% of balance, $8,000, balance - K) (>= $125).
  W      5WD path only after the sprint P1.
  Qualifies vs D if: S0 withdrawn >= 1.03 x D in BOTH halves; S3 and S4 withdrawn >= D; closure S0/S3/S4 <= D + 0.005. Pick = most S0
  withdrawn among qualifiers; none -> D stays. Reported too: payouts in year 1 / year 2, ending balance, withdrawn + ending.
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
V = dict(__name__="payout_28", __file__=str(source)); exec(prefix, V)
pl, ep, bars_for, START, build_tables = V["pl"], V["ep"], V["bars_for"], V["START"], V["build_tables"]
base = V["df_base"]; cols = list(base.columns)


def sleeve_raw(name, key, prio):
    sl = next(s for s in ep.CANDIDATES[key]["sleeves"] if s["name"] == name)
    x = pl.sleeve_trades(ep, bars_for, START, dict(sl), prio, False); return x


def norm(x):
    y = pl.price_normalize(x); y["n_contracts"] = 1.0; y["mae_per_micro"] = 0.0; return y[cols]


TRI = {"MNQ_BRK_E_2c": ("portfolio_e", 10), "MES_MOM_3c": ("portfolio_e", 11), "AG_CRABEL15_D_GAP_v53": ("ag_arch_d_plus_v2_gap_addon_v53", 12),
       "MNQ_VOL_1c": ("ensemble_epsilon", 13), "AG_BRK30_1c": ("ag_all_weather", 16), "AG_MORN30_1c": ("ag_quad", 17),
       "AG_TRD30PM_1c_v52": ("ag_arch_d_plus_v2_1c_v52", 18)}
ADDS = {"AG_TRD60Q_1c": ("ag_quad", 19), "MNQ_E57_1c": ("ensemble_epsilon", 20)}
RAW = {n: sleeve_raw(n, k, p) for n, (k, p) in {**TRI, **ADDS}.items()}
X = {n: norm(r) for n, r in RAW.items()}
BASE_T = build_tables(base)
print("ready", f"{time.time() - t0:.0f}s", flush=True)

A0, A1 = "2010-07-01", "2022-01-01"; HALVES = (("2010-07-01", "2016-06-01"), ("2016-07-01", "2022-01-01"))
LADDER, K, GATE = ((0, 1), (4000, 2), (4600, 3), (5400, 4)), 8600.0, 8700.0


def replay(T, kind, policy="D", B=None):
    days = sorted(set().union(*[set(T[b][0][k]) for b in T for k in T[b][0] if k[0] == kind]))
    ix = pd.to_datetime(pd.Series(days).astype(str)).to_numpy(); rows = []
    for s0 in pd.date_range(A0, A1, freq="MS"):
        a = int(np.searchsorted(ix, np.datetime64(s0))); b = int(np.searchsorted(ix, np.datetime64(s0 + pd.DateOffset(months=24))))
        y1 = np.datetime64(s0 + pd.DateOffset(months=12))
        bal = 0.0; paid = 0; since = 0.0; usd = 0.0; closed = False; cons = False; low = 0.0; first = 730.0
        p1 = p2 = 0; u1 = 0.0; wins = 0; n5 = 0
        for j in range(a, b):
            x = days[j]
            m = max((mm for th, mm in LADDER if bal >= th), default=1); floor = 0.0 if paid else -2000.0
            SER, RISK = T["stack" if bal >= GATE else "base"]
            if bal - RISK[(kind, m)].get(x, 0.0) <= floor: cons = True
            p = max(SER[(kind, m, bal >= 500.0)].get(x, 0.0), -1000.0); bal += p; since += p
            if not paid: low = min(low, bal)
            if bal <= floor: closed = True; break
            w = 0.0; five = False
            if not paid and bal >= 6000.0: w = 500.0                                      # sprint P1 (daily path)
            elif paid:
                eligible5 = wins >= 5                                                      # 5 qualifying days before today
                amt5 = min(0.5 * bal, 8000.0, bal - K)
                use5 = policy == "W" or (policy == "H" and bal - K >= B)
                if use5:
                    if eligible5 and amt5 >= 125.0: w = amt5; five = True
                elif since > 0 and bal - K >= 250.0: w = min(1500.0, bal - K)
            elif bal - K >= 250.0: w = min(1500.0, bal - K)                               # first payout without sprint (not reached with sprint)
            if w:
                bal -= w; usd += w; paid += 1; since = 0.0; wins = 0; n5 += five
                if first == 730.0: first = float((pd.Timestamp(x) - s0).days)
                if ix[j] < y1: p1 += 1; u1 += w
                else: p2 += 1
            elif p >= 150.0: wins += 1
        rows.append(dict(start=str(s0.date()), usd=usd, closed=closed, cons=cons, near=low <= -1500.0, first=first, y1_pays=p1, y2_pays=p2,
                         y1_usd=u1, end=0.0 if closed else bal, n5=n5))
    return pd.DataFrame(rows)


def summ(r):
    h1 = r[r.start < HALVES[0][1]]; h2 = r[r.start >= HALVES[1][0]]
    return dict(usd=round(float(r.usd.mean()), 0), usd_h1=round(float(h1.usd.mean()), 0), usd_h2=round(float(h2.usd.mean()), 0),
                closed=round(float(r.closed.mean()), 4), cons=round(float(r.cons.mean()), 4), near=round(float(r.near.mean()), 4),
                first_median=float(r["first"].median()), y1_pays=round(float(r.y1_pays.mean()), 2), y2_pays=round(float(r.y2_pays.mean()), 2),
                y1_usd=round(float(r.y1_usd.mean()), 0), end_bal=round(float(r.end.mean()), 0), usd_plus_end=round(float((r.usd + r.end).mean()), 0),
                big_payouts=round(float(r.n5.mean()), 2))


def tables_for(extra):
    return {"base": BASE_T, "stack": build_tables(pd.concat([base] + [X[n] for n in TRI] + list(extra), ignore_index=True))}


# ---------------- PART A ----------------
out = dict(part_a={}, part_b={}, validation_accessed=False, test_accessed=False)
tri0 = summ(replay(tables_for([]), "S0"))
out["part_a"]["TRI_S0"] = tri0


def gain(s): return (s["usd_h1"] - tri0["usd_h1"], s["usd_h2"] - tri0["usd_h2"])


keep = []
for n in ADDS:
    raw = RAW[n]; a = dict()
    for h, (lo, hi) in (("h1", ("2010-01-01", "2017-01-01")), ("h2", ("2017-01-01", "2024-01-01"))):
        q = X[n][(X[n].tin >= pd.Timestamp(lo, tz=pl.NY)) & (X[n].tin < pd.Timestamp(hi, tz=pl.NY))]
        for side, nm in ((1, "long"), (-1, "short")):
            z = q[raw.loc[q.index, "side"] == side].net_today
            a[f"{h}_{nm}"] = dict(n=int(len(z)), per_micro=round(float(z.mean()), 2) if len(z) else None,
                                 pf=round(float(z[z > 0].sum() / -z[z < 0].sum()), 3) if (z < 0).any() else None)
    real = gain(summ(replay(tables_for([X[n]]), "S0")))
    lng = gain(summ(replay(tables_for([norm(raw.assign(side=1))]), "S0")))
    rnd = []
    for seed in range(20):
        sd = np.random.default_rng(seed).choice([-1, 1], size=len(raw))
        rnd.append(gain(summ(replay(tables_for([norm(raw.assign(side=sd))]), "S0"))))
    r1 = sorted(g[0] for g in rnd); r2 = sorted(g[1] for g in rnd)
    signal = bool(real[0] > lng[0] and real[1] > lng[1] and real[0] > r1[18] and real[1] > r2[18])
    a.update(real_gain=real, always_long_gain=lng, random_gain_19th=(r1[18], r2[18]), random_gain_median=(r1[9], r2[9]), signal=signal)
    out["part_a"][n] = a
    if signal: keep.append(n)
    print("A", n, json.dumps({k: a[k] for k in ("real_gain", "always_long_gain", "random_gain_19th", "random_gain_median", "signal")}),
          f"{time.time() - t0:.0f}s", flush=True)
out["part_a"]["kept_adds"] = keep

# ---------------- PART B ----------------
T = tables_for([X[n] for n in keep])
cells = {"D": ("D", None), "H1500": ("H", 1500.0), "H4000": ("H", 4000.0), "H8000": ("H", 8000.0), "W": ("W", None)}
for name, (pol, B) in cells.items():
    out["part_b"][name] = {kind: summ(replay(T, kind, pol, B)) for kind in ("S0", "S3", "S4")}
    s = out["part_b"][name]
    print("B", f"{name:6s}", " | ".join(f"{k} {s[k]['usd']:.0f} ({s[k]['usd_h1']:.0f}/{s[k]['usd_h2']:.0f}) cl {s[k]['closed']:.3f} end {s[k]['end_bal']:.0f}"
                                     for k in ("S0", "S3", "S4")), f"y1 {s['S0']['y1_pays']} y2 {s['S0']['y2_pays']} big {s['S0']['big_payouts']}", flush=True)
D = out["part_b"]["D"]
if keep == list(ADDS): assert abs(D["S0"]["usd"] - 51036) <= 1, f"D must reproduce payout_27 combined $51,036: {D['S0']['usd']}"
quals = {}
for name in cells:
    if name == "D": continue
    c = out["part_b"][name]
    ok = (c["S0"]["usd_h1"] >= 1.03 * D["S0"]["usd_h1"] and c["S0"]["usd_h2"] >= 1.03 * D["S0"]["usd_h2"]
          and all(c[s]["usd"] >= D[s]["usd"] for s in ("S3", "S4")) and all(c[s]["closed"] <= D[s]["closed"] + 0.005 for s in ("S0", "S3", "S4")))
    quals[name] = bool(ok)
out["part_b_qualifies"] = quals
q = [n for n, v in quals.items() if v]
out["part_b_pick"] = max(q, key=lambda n: out["part_b"][n]["S0"]["usd"]) if q else "D"
print("PICK", out["part_b_pick"], quals, flush=True)
(ROOT / "reports/PAYOUT_28_PLACEBO_AND_SWEEP_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
print("saved", f"{time.time() - t0:.0f}s", flush=True)
