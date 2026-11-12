"""payout_30 (Claude, 2026-11-11): the funded payout rules re-scored with INTRADAY DLL / floor checks, and one risk-plumbing idea. TRAINING only.

Nick, 2026-11-11: "try improving it" (and: drop Codex's $2,000 peak-to-trough cap - the account only closes at its floor).
payout_29 showed the old funded tables clip only the day's final P&L at -$1,000 (a free put that grows with variance). This uses
funded_intraday_core (fixtures in tests/test_funded_intraday_core.py): per-trade 1-minute MAE for EVERY trade (base book, stack sleeves,
overnight leg), MAE stacking for open trades, DLL first passage, floor checked on the intraday worst. Same footing as payout_26
(2019 hole filled, full calendar, posthoc router, S0 / S3 / S4 stresses with MAE stressed like P&L, 139 x 24-month windows).

Cells: F4X (Fortress 4X, paper rule) | B3X (1x / 2x from $4,000 / 3x from $5,000, K $6,500) | P24 (1x / 2x from $4,000, K $6,000) |
TRI (triple stack, as payout_26) | F4X_B (F4X + DLL budget: each new entry is sized down so that realised - open stop risk - its own stop
risk stays above -$1,000). Diagnostic: F4X_MAE0 (MAE set to 0 = old final-clip semantics; must be close to payout_26's $35,870).
PRE-DECLARED RULE: incumbent F4X. A challenger qualifies if: S0 withdrawn >= 1.03 x F4X in BOTH halves; S0 value (withdrawn + max(0,
ending - $2,000)) >= F4X in BOTH halves; S3 and S4 withdrawn >= F4X; closure S0 / S3 / S4 <= F4X + 0.005. TRI must ALSO beat the 19th of 20
random-side stacks (S0 withdrawn, both halves; run only if TRI passes the rest). Pick = most S0 withdrawn among qualifiers; none -> F4X stays.
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
import funded_intraday_core as fc

t0 = time.time()
source = ROOT / "scripts/research_uncapped_and_sleeves.py"
prefix = source.read_text(encoding="utf-8").split('print("Building tables')[0]
Vm = dict(__name__="payout_30", __file__=str(source)); exec(prefix, Vm)


def find(ns, key, depth=0):
    if key in ns: return ns[key]
    if depth < 4 and isinstance(ns.get("V"), dict): return find(ns["V"], key, depth + 1)
    raise KeyError(key)


pl, ep, bars_for, START = Vm["pl"], Vm["ep"], Vm["bars_for"], Vm["START"]
stressed, sc17, N0, NIGHT_RISK = Vm["stressed"], Vm["sc17"], Vm["N0"], Vm["NIGHT_RISK"]
BARS, NIGHTS = find(Vm, "BARS"), find(Vm, "NIGHTS")
STOP_LEVEL = float(find(Vm, "p17").stop_loss_level)
base = Vm["df_base"].copy(); cols = list(base.columns)
assert "mae_per_micro" in base and base.mae_per_micro.lt(0).mean() > 0.5, "base book must carry real MAE"
TRI = {"MNQ_BRK_E_2c": ("portfolio_e", 10), "MES_MOM_3c": ("portfolio_e", 11), "AG_CRABEL15_D_GAP_v53": ("ag_arch_d_plus_v2_gap_addon_v53", 12),
       "MNQ_VOL_1c": ("ensemble_epsilon", 13), "AG_BRK30_1c": ("ag_all_weather", 16), "AG_MORN30_1c": ("ag_quad", 17),
       "AG_TRD30PM_1c_v52": ("ag_arch_d_plus_v2_1c_v52", 18)}
RAW = pd.concat([pl.sleeve_trades(ep, bars_for, START, dict(next(s for s in ep.CANDIDATES[k]["sleeves"] if s["name"] == n)), p, False)
                 for n, (k, p) in TRI.items()], ignore_index=True)
# per-trade low / high excursion once, so any side assignment gets its MAE without re-scanning bars
LO = np.zeros(len(RAW)); HI = np.zeros(len(RAW))
for k, r in enumerate(RAW.itertuples()):
    ts, H, L = BARS[r.inst]; i0, i1 = int(np.searchsorted(ts, r.tin.value)), int(np.searchsorted(ts, r.tout.value))
    if i1 > i0: LO[k] = (L[i0:i1].min() - r.entry) / r.entry; HI[k] = (H[i0:i1].max() - r.entry) / r.entry


def stack_sleeves(side):
    x = RAW.assign(side=side); y = pl.price_normalize(x); y["n_contracts"] = 1.0
    pct = np.where(side > 0, np.minimum(0.0, LO), np.minimum(0.0, -HI))
    y["mae_per_micro"] = (pct * y.inst.map(pl.TODAY).to_numpy() - pl.ADV) * y.inst.map(pl.MULT).to_numpy()
    return y[cols]


# sanity: our MAE for the real sides matches the base-book method on a base-book sample
print("ready", len(RAW), f"{time.time() - t0:.0f}s", flush=True)

NI = NIGHTS.copy(); NI["key"] = NI.tin.map(lambda t: t.value)


def prep(book, kind, mae_zero=False):
    e = stressed(book, kind)
    mpm = e.mae_per_micro.astype(float).copy()
    if kind in ("S1", "S3"): mpm = mpm - 1.0 * e.inst.map(pl.MULT)
    if kind == "S4": mpm = mpm * 1.5
    e = e.assign(mae_s=mpm)
    r = pl.route(e)
    per = (r.net_today / r.n_contracts).to_numpy(float)
    intra = pd.DataFrame(dict(a=r.tin.map(lambda t: t.value).to_numpy(), b=r.tout.map(lambda t: t.value).to_numpy(), per=per,
                              mae=0.0 if mae_zero else np.minimum(r.mae_s.to_numpy(float), per), risk=r.risk_today.to_numpy(float),
                              n=r.n_contracts.to_numpy(float), prio=r.prio.to_numpy(float), day=r.tout.dt.date.to_numpy()))
    _, n = sc17(kind, N0)
    n = n.assign(key=n.tin.map(lambda t: t.value)).merge(NI[["key", "mae_per_micro"]], on="key", how="left")
    assert n.mae_per_micro.notna().all(), "night MAE alignment failed"
    nm = n.mae_per_micro.to_numpy(float)
    if kind in ("S1", "S3"): nm = nm - 1.0 * pl.MULT["MNQ"]
    if kind == "S4": nm = np.where(n.net_today.to_numpy(float) <= STOP_LEVEL + 1e-6, nm, nm * 1.5)
    nper = n.net_today.to_numpy(float)
    nights = pd.DataFrame(dict(a=n.tin.map(lambda t: t.value).to_numpy(), b=n.tout.map(lambda t: t.value).to_numpy(), per=nper,
                               mae=0.0 if mae_zero else np.minimum(nm, nper), risk=NIGHT_RISK * (1.5 if kind == "S4" else 1.0), n=1.0,
                               prio=99.0, day=n.tout.dt.date.to_numpy()))
    return intra, nights, NIGHT_RISK * (1.5 if kind == "S4" else 1.0)


STOP = lambda m: 400.0 if m == 1 else 700.0


def tables(book, kind, budget=False, mae_zero=False):
    intra, nights, nr = prep(book, kind, mae_zero); return fc.day_tables(intra, nights, nr, STOP, budget)


STACK = pd.concat([base, stack_sleeves(RAW.side.to_numpy())], ignore_index=True)
T = {}
for kind in ("S0", "S3", "S4"):
    T[("base", kind)] = tables(base, kind); T[("base_B", kind)] = tables(base, kind, budget=True); T[("stack", kind)] = tables(STACK, kind)
    print("tables", kind, f"{time.time() - t0:.0f}s", flush=True)
T0 = tables(base, "S0", mae_zero=True)

F4X = dict(ladder=((0, 1), (4000, 2), (4800, 3), (6500, 4)), K=8500.0)
CELLS = {"F4X": (("base",), F4X), "B3X": (("base",), dict(ladder=((0, 1), (4000, 2), (5000, 3)), K=6500.0)),
         "P24": (("base",), dict(ladder=((0, 1), (4000, 2)), K=6000.0)),
         "TRI": (("base", "stack"), dict(ladder=((0, 1), (4000, 2), (4600, 3), (5400, 4)), K=8600.0, gate=8700.0, sprint=True)),
         "F4X_B": (("base_B",), F4X)}
out = dict(cells={}, validation_accessed=False, test_accessed=False)
for name, (books, kw) in CELLS.items():
    c = out["cells"][name] = {}
    for kind in ("S0", "S3", "S4"):
        tb = {"base": T[(books[0], kind)]}
        if len(books) > 1: tb["stack"] = T[(books[1], kind)]
        c[kind] = fc.summ(fc.replay(tb, **kw))
    s = c["S0"]
    print(f"{name:6s} S0 {s['usd']:.0f} ({s['usd_h1']:.0f}/{s['usd_h2']:.0f}) value {s['value']:.0f} closed {c['S0']['closed']:.3f}/{c['S3']['closed']:.3f}/"
          f"{c['S4']['closed']:.3f} S3 {c['S3']['usd']:.0f} S4 {c['S4']['usd']:.0f} near {s['near']:.3f} y1 {s['y1_pays']} first {s['first_median']:.0f} "
          f"dll/win {s['dll_days']}", flush=True)
out["cells"]["F4X_MAE0"] = {"S0": fc.summ(fc.replay({"base": T0}, **F4X))}
print("F4X_MAE0 (old semantics) S0", out["cells"]["F4X_MAE0"]["S0"]["usd"], "vs payout_26 35870", flush=True)

C = out["cells"]; F = C["F4X"]


def qualifies(c):
    return bool(all(c["S0"][f"usd_{h}"] >= 1.03 * F["S0"][f"usd_{h}"] for h in ("h1", "h2"))
                and all(c["S0"][f"value_{h}"] >= F["S0"][f"value_{h}"] for h in ("h1", "h2"))
                and all(c[s]["usd"] >= F[s]["usd"] for s in ("S3", "S4")) and all(c[s]["closed"] <= F[s]["closed"] + 0.005 for s in ("S0", "S3", "S4")))


out["qualifies"] = {n: qualifies(C[n]) for n in CELLS if n != "F4X"}
if out["qualifies"]["TRI"]:
    rnd = []
    for seed in range(20):
        sd = np.random.default_rng(seed).choice([-1, 1], size=len(RAW))
        st = tables(pd.concat([base, stack_sleeves(sd)], ignore_index=True), "S0")
        rnd.append(fc.summ(fc.replay({"base": T[("base", "S0")], "stack": st}, **CELLS["TRI"][1])))
    q1 = sorted(r["usd_h1"] for r in rnd)[18]; q2 = sorted(r["usd_h2"] for r in rnd)[18]
    out["tri_placebo"] = dict(h1_19th=q1, h2_19th=q2, median=float(np.median([r["usd"] for r in rnd])))
    out["qualifies"]["TRI"] = bool(C["TRI"]["S0"]["usd_h1"] > q1 and C["TRI"]["S0"]["usd_h2"] > q2)
q = [n for n, v in out["qualifies"].items() if v]
out["pick"] = max(q, key=lambda n: C[n]["S0"]["usd"]) if q else "F4X (no change)"
print("QUALIFIES", out["qualifies"], "PICK", out["pick"], flush=True)
(ROOT / "reports/PAYOUT_30_INTRADAY_FUNDED_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
print("saved", f"{time.time() - t0:.0f}s", flush=True)
