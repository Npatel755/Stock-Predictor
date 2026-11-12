"""payout_29 (Claude, 2026-11-11): is the triple stack's gain over Fortress 4X signal or variance? TRAINING 2010-23 only.

payout_28 found that adding a sleeve's trades with RANDOM sides to the stack book (used at balance >= $8,700, floor $0) raises 24-month
withdrawals almost as much as the real sleeve (TRD60Q random median +$4,390 in half 2): withdrawals ratchet (gains above K are paid out,
losses come out of the retained balance), and the day is clipped at the -$1,000 DLL. So "dollars withdrawn" rewards variance. payout_26's
R3 (triple stack +27% over Fortress 4X) used that metric. This checks it.

Cells (posthoc router, filled 2019, full calendar, S0 unless stated):
  F4X          Fortress 4X (base book, 1x/2x 4000/3x 4800/4x 6500, K $8,500, no sprint).
  TRI          triple stack (payout_26 TRI_POSTHOC: K $8,600, stack book from $8,700, ladder 4000/4600/5400, sprint P1 $500 at $6,000).
  TRI_RANDOM   TRI with the 7 stack sleeves' sides drawn at random (seeds 0..19; same times, prices, stops, priorities).
  TRI_LONG     TRI with the 7 stack sleeves always long.
  TRI_EMPTY    TRI's ladder / K / sprint / gate with NO stack sleeves (stack book = base book): isolates the non-sleeve differences.
  Clip check: F4X and TRI with the day NOT clipped at -$1,000 (p = net), S0.
Metrics: withdrawn (as before) and VALUE = withdrawn + max(0, ending balance - $2,000) (what is left above the daily-path buffer).
PRE-DECLARED READINGS:
  R1 stack signal: TRI beats the 19th of 20 TRI_RANDOM on S0 withdrawn in BOTH halves AND beats TRI_LONG in BOTH halves.
  R2 switch recommendation (paper funded rule F4X -> TRI) only if R1 holds AND TRI's S0 VALUE >= 1.05 x F4X in BOTH halves AND TRI's S0
     withdrawn >= 1.05 x F4X in BOTH halves. Otherwise Fortress 4X stays and the stack is reported as variance harvesting.
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
V = dict(__name__="payout_29", __file__=str(source)); exec(prefix, V)
pl, ep, bars_for, START, build_tables = V["pl"], V["ep"], V["bars_for"], V["START"], V["build_tables"]
base = V["df_base"]; cols = list(base.columns)
TRI = {"MNQ_BRK_E_2c": ("portfolio_e", 10), "MES_MOM_3c": ("portfolio_e", 11), "AG_CRABEL15_D_GAP_v53": ("ag_arch_d_plus_v2_gap_addon_v53", 12),
       "MNQ_VOL_1c": ("ensemble_epsilon", 13), "AG_BRK30_1c": ("ag_all_weather", 16), "AG_MORN30_1c": ("ag_quad", 17),
       "AG_TRD30PM_1c_v52": ("ag_arch_d_plus_v2_1c_v52", 18)}
RAW = pd.concat([pl.sleeve_trades(ep, bars_for, START, dict(next(s for s in ep.CANDIDATES[k]["sleeves"] if s["name"] == n)), p, False)
                 for n, (k, p) in TRI.items()], ignore_index=True)


def norm(x):
    y = pl.price_normalize(x); y["n_contracts"] = 1.0; y["mae_per_micro"] = 0.0; return y[cols]


BASE_T = build_tables(base)
print("ready", len(RAW), f"{time.time() - t0:.0f}s", flush=True)
A0, A1 = "2010-07-01", "2022-01-01"; HALVES = (("2010-07-01", "2016-06-01"), ("2016-07-01", "2022-01-01"))
F4X = dict(ladder=((0, 1), (4000, 2), (4800, 3), (6500, 4)), K=8500.0, gate=None, sprint=False)
TRIR = dict(ladder=((0, 1), (4000, 2), (4600, 3), (5400, 4)), K=8600.0, gate=8700.0, sprint=True)


def replay(T, kind, ladder, K, gate, sprint, clip=True):
    days = sorted(set().union(*[set(T[b][0][k]) for b in T for k in T[b][0] if k[0] == kind]))
    ix = pd.to_datetime(pd.Series(days).astype(str)).to_numpy(); rows = []
    for s0 in pd.date_range(A0, A1, freq="MS"):
        a = int(np.searchsorted(ix, np.datetime64(s0))); b = int(np.searchsorted(ix, np.datetime64(s0 + pd.DateOffset(months=24))))
        bal = 0.0; paid = 0; since = 0.0; usd = 0.0; closed = False; clipped = 0.0
        for j in range(a, b):
            x = days[j]
            m = max((mm for th, mm in ladder if bal >= th), default=1); floor = 0.0 if paid else -2000.0
            SER = T["stack" if (gate is not None and bal >= gate) else "base"][0]
            raw = SER[(kind, m, bal >= 500.0)].get(x, 0.0); p = max(raw, -1000.0) if clip else raw; clipped += p - raw
            bal += p; since += p
            if bal <= floor: closed = True; break
            w = 0.0
            if sprint and not paid and bal >= 6000.0: w = 500.0
            elif (since > 0 or not paid) and bal - K >= 250.0: w = min(1500.0, bal - K)
            if w: bal -= w; usd += w; paid += 1; since = 0.0
        end = 0.0 if closed else bal
        rows.append(dict(start=str(s0.date()), usd=usd, value=usd + max(0.0, end - 2000.0), closed=closed, end=end, clipped=clipped))
    return pd.DataFrame(rows)


def summ(r):
    h1 = r[r.start < HALVES[0][1]]; h2 = r[r.start >= HALVES[1][0]]
    return dict(usd=round(float(r.usd.mean()), 0), usd_h1=round(float(h1.usd.mean()), 0), usd_h2=round(float(h2.usd.mean()), 0),
                value=round(float(r.value.mean()), 0), value_h1=round(float(h1.value.mean()), 0), value_h2=round(float(h2.value.mean()), 0),
                closed=round(float(r.closed.mean()), 4), end=round(float(r.end.mean()), 0), clip_added=round(float(r.clipped.mean()), 0))


def stack_T(sleeves): return {"base": BASE_T, "stack": build_tables(pd.concat([base, sleeves], ignore_index=True)) if len(sleeves) else BASE_T}


out = dict(cells={}, validation_accessed=False, test_accessed=False)
T_real = stack_T(norm(RAW))
out["cells"]["F4X"] = {k: summ(replay({"base": BASE_T}, k, **F4X)) for k in ("S0", "S3", "S4")}
out["cells"]["TRI"] = {k: summ(replay(T_real, k, **TRIR)) for k in ("S0", "S3", "S4")}
assert abs(out["cells"]["TRI"]["S0"]["usd"] - 45455) <= 1 and abs(out["cells"]["F4X"]["S0"]["usd"] - 35870) <= 1, "parity with payout_26 failed"
out["cells"]["TRI_EMPTY"] = {"S0": summ(replay({"base": BASE_T, "stack": BASE_T}, "S0", **TRIR))}
out["cells"]["TRI_LONG"] = {"S0": summ(replay(stack_T(norm(RAW.assign(side=1))), "S0", **TRIR))}
rnd = []
for seed in range(20):
    sd = np.random.default_rng(seed).choice([-1, 1], size=len(RAW))
    rnd.append(summ(replay(stack_T(norm(RAW.assign(side=sd))), "S0", **TRIR)))
out["cells"]["TRI_RANDOM"] = dict(runs=rnd, **{f"{m}_{q}": float(np.sort([r[m] for r in rnd])[i]) for m in ("usd_h1", "usd_h2", "value_h1", "value_h2", "usd", "value")
                                               for q, i in (("median", 9), ("19th", 18))})
out["cells"]["F4X_NOCLIP"] = {"S0": summ(replay({"base": BASE_T}, "S0", **F4X, clip=False))}
out["cells"]["TRI_NOCLIP"] = {"S0": summ(replay(T_real, "S0", **TRIR, clip=False))}
for name, c in out["cells"].items():
    if name == "TRI_RANDOM": continue
    s = c["S0"]; print(f"{name:11s} S0 withdrawn {s['usd']:.0f} ({s['usd_h1']:.0f}/{s['usd_h2']:.0f}) value {s['value']:.0f} ({s['value_h1']:.0f}/{s['value_h2']:.0f})"
                       f" end {s['end']:.0f} closed {s['closed']:.3f} clip+ {s['clip_added']:.0f}", flush=True)
R = out["cells"]["TRI_RANDOM"]
print("TRI_RANDOM  withdrawn median", R["usd_median"], "h1/h2 19th", R["usd_h1_19th"], R["usd_h2_19th"], "| value median", R["value_median"],
      "h1/h2 19th", R["value_h1_19th"], R["value_h2_19th"], flush=True)
T, Fx, L = out["cells"]["TRI"]["S0"], out["cells"]["F4X"]["S0"], out["cells"]["TRI_LONG"]["S0"]
r1 = bool(T["usd_h1"] > R["usd_h1_19th"] and T["usd_h2"] > R["usd_h2_19th"] and T["usd_h1"] > L["usd_h1"] and T["usd_h2"] > L["usd_h2"])
r2 = bool(r1 and all(T[f"value_{h}"] >= 1.05 * Fx[f"value_{h}"] for h in ("h1", "h2")) and all(T[f"usd_{h}"] >= 1.05 * Fx[f"usd_{h}"] for h in ("h1", "h2")))
out["R1_stack_signal"] = r1; out["R2_switch_to_TRI"] = r2
print("R1", r1, "R2", r2, flush=True)
(ROOT / "reports/PAYOUT_29_STACK_PLACEBO_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
print("saved", f"{time.time() - t0:.0f}s", flush=True)
