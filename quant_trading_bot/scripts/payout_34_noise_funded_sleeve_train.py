"""payout_34 (Claude, 2026-11-11): the published noise-area momentum as an ADD-ON sleeve on the funded account. TRAINING only.

Nick: "see if you can improve it". payout_33: Fortress 4X's honest number on exact combined minute marks is $32,597 per 24 months and no
rule change beats it; the DLL liquidations are real stacking. What is left is a genuinely new edge.
Hypothesis (written down in lessons.md on 2026-11-11 after eval_12/13, before this test): the noise-area intraday momentum (Zarattini,
Aziz & Barbon 2024; eval_12 MNQ "P": published parameters, PF 1.14 / 1.32 by half, 200/200 random-side placebos, the drift control
passed: its shorts make money where the same windows held long lose) failed for the EVALUATION because a fixed -$2,000 floor turns extra
variance at the same Sharpe into fails; on the funded account at deep cushion the floor does not bind, so it should add dollars.

DESIGN (pre-declared; nothing tuned; eval_12's trades reproduced exactly from its own code):
- Separate concurrent position (NOT routed with the book, so it never blocks a book trade), fixed micros by ladder multiplier m,
  same costs / today-price normalisation as the book, same <= $300 risk filter and stresses (S3: -1 pt x MULT and -25% of its positive
  average; S4: P&L and risk x 1.5), account stop applies to its entries, exact combined minute marks (payout_33).
- Fortress 4X ladder and K unchanged. Cells (micros at m = 1/2/3/4): NA 1/1/1/1 | NB 0/1/1/1 | NC 0/0/0/1 | ND 0/1/1/2.
- QUALIFY (payout_30's bar, vs F4X on the same simulator): S0 withdrawn >= 1.03x F4X in BOTH halves; S0 value >= F4X in BOTH halves;
  S3 and S4 withdrawn >= F4X; closures S0 / S3 / S4 <= F4X + 0.5 pt. Pick = most S0 withdrawn among qualifiers.
- SIGNAL CHECK on the pick (pre-declared; both must pass or nothing is adopted): (i) S0 withdrawn above the 19th of 20 random-side
  noise sleeves (seeds 0-19; same entries / exits, side drawn at random) in BOTH halves; (ii) above the always-long noise sleeve in BOTH
  halves. Otherwise the gain is variance / drift, not the signal (payout_28-29 lesson).
Validation / test not loaded (TRAIN-only loader guard from payout_30).
"""
import json, time
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/payout_33_exact_marks_rescore_train.py").read_text(encoding="utf-8").split('\nSTACK = pd.concat([base, G["stack_sleeves"]')[0]
H = dict(__name__="payout_34", __file__=str(ROOT / "scripts/payout_33_exact_marks_rescore_train.py")); exec(src, H)
G, prep2, stress_marks = H["G"], H["prep2"], H["stress_marks"]
pl, fc, base, STOP, BARS, stressed = G["pl"], G["fc"], G["base"], G["STOP"], G["BARS"], G["stressed"]
t0 = time.time()

src12 = (ROOT / "scripts/eval_12_noise_area_train.py").read_text(encoding="utf-8").split('\nout = {"cells": {}}')[0]
E = dict(__name__="e12", __file__=str(ROOT / "scripts/eval_12_noise_area_train.py")); exec(src12, E)
NT = E["trades"](E["rth_panel"]("MNQ"), "MNQ", "P")
NT = NT[NT.tout.dt.date >= pd.Timestamp("2010-06-07").date()].reset_index(drop=True)
assert NT.tout.max() < pd.Timestamp("2024-01-01", tz="America/New_York")
# Reproduction: without the 2019 fill this code gives eval_12's 2,786 trades / $59,914 exactly (checked 2026-11-11, trade by trade);
# with TRAIN_MINI_UNTIL the only differences are Jan-May 2019 (the filled hole and the 14 sessions whose lookback it feeds).
OUT_N, OUT_NET = 2768, 60817.41
_d = NT.tout.dt.date; _out = NT[(_d < pd.Timestamp("2019-01-01").date()) | (_d >= pd.Timestamp("2019-06-01").date())]
assert len(_out) == OUT_N and abs(_out.per_micro.sum() - OUT_NET) < 0.01, ("noise trades do not reproduce eval_12 outside Jan-May 2019", len(_out), _out.per_micro.sum())
print("noise trades", len(NT), round(NT.per_micro.sum()), f"{time.time() - t0:.0f}s", flush=True)

ts, Hh, Ll = BARS["MNQ"]
I0 = np.searchsorted(ts, NT.tin.map(lambda t: t.value).to_numpy(np.int64)); I1 = np.searchsorted(ts, NT.tout.map(lambda t: t.value).to_numpy(np.int64))
LO = np.array([(Ll[i:j].min() if j > i else e) for i, j, e in zip(I0, I1, NT.entry)]); HI = np.array([(Hh[i:j].max() if j > i else e) for i, j, e in zip(I0, I1, NT.entry)])


def noise_book(side):
    """The noise sleeve with the given sides (real, random or always long): per micro, MAE, risk as eval_12 / payout_lib."""
    e, x = NT.entry.to_numpy(float), NT.exit.to_numpy(float)
    per = ((side * (x - e) / e) * pl.TODAY["MNQ"] - 2 * pl.ADV) * pl.MULT["MNQ"] - pl.FEE
    worst = np.where(side > 0, (LO - e) / e, (e - HI) / e)
    mae = np.minimum(per, (np.minimum(0.0, worst) * pl.TODAY["MNQ"] - pl.ADV) * pl.MULT["MNQ"])
    return NT.assign(side=side, per_micro=per, mae_per_micro=mae, net_today=per, n_contracts=1.0, sleeve="NOISE_MNQ_P", prio=12.0)


def noise_frame(nb, kind, offset):
    e = stressed(nb, kind)
    mpm = e.mae_per_micro.astype(float).to_numpy()
    if kind in ("S1", "S3"): mpm = mpm - 1.0 * pl.MULT["MNQ"]
    if kind == "S4": mpm = mpm * 1.5
    per = e.net_today.to_numpy(float); mae = np.minimum(mpm, per)
    a = e.tin.map(lambda t: t.value).to_numpy(np.int64); b = e.tout.map(lambda t: t.value).to_numpy(np.int64); marks = []
    for k, (s, en) in enumerate(zip(e.side.to_numpy(), e.entry.to_numpy(float))):
        tt, v = fc.trade_marks(ts, Hh, Ll, int(s), en, a[k], b[k], pl.TODAY["MNQ"], pl.MULT["MNQ"], pl.ADV)
        marks.append((tt, stress_marks(v, "MNQ", kind)))
    fr = pd.DataFrame(dict(a=a, b=b, per=per, mae=mae, risk=e.risk_today.to_numpy(float), n=1.0, prio=12.0,
                           day=e.tout.dt.date.to_numpy(), mk=offset + np.arange(len(e))))
    return fr, marks


PREP = {k: prep2(base, k) for k in ("S0", "S3", "S4")}


def tables_with(nb, kind, q):
    intra, nights, nr, marks = PREP[kind]
    fr, mk = noise_frame(nb, kind, len(marks))
    return fc.day_tables_path(intra, nights, nr, STOP, marks + mk, extra=fr, extra_q=q)


F4X = dict(ladder=((0, 1), (4000, 2), (4800, 3), (6500, 4)), K=8500.0)
CELLS = {"NA": {1: 1, 2: 1, 3: 1, 4: 1}, "NB": {1: 0, 2: 1, 3: 1, 4: 1}, "NC": {1: 0, 2: 0, 3: 0, 4: 1}, "ND": {1: 0, 2: 1, 3: 1, 4: 2}}
REAL = noise_book(NT.side.to_numpy())
out = dict(noise_trades=dict(n=len(NT), net_per_micro=round(float(NT.per_micro.sum()), 0)), cells={}, validation_accessed=False, test_accessed=False)
c = out["cells"]["F4X"] = {k: fc.summ(fc.replay({"base": fc.day_tables_path(*PREP[k][:3], STOP, PREP[k][3])}, **F4X)) for k in ("S0", "S3", "S4")}
print("F4X", c["S0"]["usd"], "(payout_33: 32597)", flush=True)
for name, q in CELLS.items():
    c = out["cells"][name] = {k: fc.summ(fc.replay({"base": tables_with(REAL, k, q)}, **F4X)) for k in ("S0", "S3", "S4")}
    s = c["S0"]
    print(f"{name} S0 {s['usd']:.0f} ({s['usd_h1']:.0f}/{s['usd_h2']:.0f}) value {s['value']:.0f} ({s['value_h1']:.0f}/{s['value_h2']:.0f}) closed "
          f"{c['S0']['closed']:.3f}/{c['S3']['closed']:.3f}/{c['S4']['closed']:.3f} S3 {c['S3']['usd']:.0f} S4 {c['S4']['usd']:.0f} y1 {s['y1_pays']} "
          f"first {s['first_median']:.0f} dll/win {s['dll_days']} {time.time() - t0:.0f}s", flush=True)
F = out["cells"]["F4X"]


def qualifies(c):
    return bool(all(c["S0"][f"usd_{h}"] >= 1.03 * F["S0"][f"usd_{h}"] for h in ("h1", "h2"))
                and all(c["S0"][f"value_{h}"] >= F["S0"][f"value_{h}"] for h in ("h1", "h2"))
                and all(c[s]["usd"] >= F[s]["usd"] for s in ("S3", "S4")) and all(c[s]["closed"] <= F[s]["closed"] + 0.005 for s in ("S0", "S3", "S4")))


out["qualifies"] = {n: qualifies(out["cells"][n]) for n in CELLS}
qual = [n for n, v in out["qualifies"].items() if v]
print("qualifies", out["qualifies"], flush=True)
if qual:
    pick = max(qual, key=lambda n: out["cells"][n]["S0"]["usd"]); q = CELLS[pick]; P = out["cells"][pick]["S0"]
    rnd = []
    for seed in range(20):
        sd = np.random.default_rng(seed).choice([-1, 1], size=len(NT))
        rnd.append(fc.summ(fc.replay({"base": tables_with(noise_book(sd), "S0", q)}, **F4X)))
        print("placebo", seed, rnd[-1]["usd"], rnd[-1]["usd_h1"], rnd[-1]["usd_h2"], flush=True)
    lng = fc.summ(fc.replay({"base": tables_with(noise_book(np.ones(len(NT))), "S0", q)}, **F4X))
    q1 = sorted(r["usd_h1"] for r in rnd)[18]; q2 = sorted(r["usd_h2"] for r in rnd)[18]
    out["signal_check"] = dict(pick=pick, random_19th_h1=q1, random_19th_h2=q2, random_median=float(np.median([r["usd"] for r in rnd])),
                               always_long=lng, beats_random=bool(P["usd_h1"] > q1 and P["usd_h2"] > q2),
                               beats_long=bool(P["usd_h1"] > lng["usd_h1"] and P["usd_h2"] > lng["usd_h2"]), random=rnd)
    out["adopt"] = pick if (out["signal_check"]["beats_random"] and out["signal_check"]["beats_long"]) else None
    print("signal check", {k: v for k, v in out["signal_check"].items() if k not in ("random", "always_long")}, "long", lng["usd"], lng["usd_h1"], lng["usd_h2"], flush=True)
else:
    out["adopt"] = None
print("ADOPT", out["adopt"], flush=True)
(ROOT / "reports/PAYOUT_34_NOISE_FUNDED_SLEEVE_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
print("saved", f"{time.time() - t0:.0f}s", flush=True)
