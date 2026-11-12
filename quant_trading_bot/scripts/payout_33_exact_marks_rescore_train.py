"""payout_33 (Claude, 2026-11-11): funded rules re-scored with EXACT combined minute marks. TRAINING only. Measurement update, no selection.

Why (payout_32 diagnosis): on payout_30's simulator nearly all of Fortress 4X's DLL cost comes from STACKED days (4x, S0: 53 stacked
liquidations cost $22.2k over 2010-23; the 45 single-trade liquidations cost ~$0), and a stacked liquidation rests on the core's
conservative assumption that every open trade's worst point happens at the same minute. funded_intraday_core.sim_day_path replaces it
on days with >= 2 trades: each open trade is marked at every 1-minute bar's adverse extreme (low for longs, high for shorts; the overnight
leg's stop truncates its marks at the stop-out value), the marks are summed with realised P&L, and the DLL liquidates at the first
passage through -$1,000. Single-trade days keep sim_day (exact for one trade). Stresses as payout_30: S3 marks - 1 pt x MULT, S4 x 1.5
(stopped overnight trades unscaled). Also fixed in the core: a liquidated day's worst is -$1,000 (it reported the full MAE).

Parity cells first: (1) payout_30's core recomputed after the worst-cap fix vs the saved payout_30 JSON (expected identical for F4X);
(2) the path code with marks FLAT at each trade's MAE must equal the core exactly. Then F4X, B3X, P24, TRI on exact marks, same windows
(139 x 24 months), S0 / S3 / S4. payout_30's qualification rule is re-applied vs F4X on the same simulator; TRI also needs payout_29's
random-side placebo (it failed half 1 there), so a TRI "qualifies" here is reported, not adopted.
Also: inactivity (Topstep: "XFAs with no trading activity for more than 30 days may be closed"; Combine: "If there are no trades placed
for 30 days, the account will close") - share of F4X windows with a > 30-day gap between trading days.
"""
import json, time
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/payout_30_intraday_funded_train.py").read_text(encoding="utf-8").split("STACK = pd.concat")[0]
G = dict(__name__="payout_33", __file__=str(ROOT / "scripts/payout_30_intraday_funded_train.py")); exec(src, G)
pl, fc, base, STOP, BARS, find, Vm = G["pl"], G["fc"], G["base"], G["STOP"], G["BARS"], G["find"], G["Vm"]
stressed, sc17, N0, NI, NIGHT_RISK, STOP_LEVEL = G["stressed"], G["sc17"], G["N0"], G["NI"], G["NIGHT_RISK"], G["STOP_LEVEL"]
t0 = time.time()

# overnight leg entry prices and stop levels (v53_improve_train's derivation: entry_raw = entry_price - ADV, stop 0.55% below)
OV = {}
for t in find(Vm, "ov"):
    e_raw = float(t["entry_price"]) - pl.ADV; OV[pd.Timestamp(t["entry_ts"]).value] = (e_raw, e_raw * (1 - 0.0055))


def stress_marks(v, inst, kind):
    if kind in ("S1", "S3"): return v - 1.0 * pl.MULT[inst]
    if kind == "S4": return v * 1.5
    return v


def prep2(book, kind, flat=False):
    """payout_30.prep plus exact marks (or marks flat at each trade's MAE when flat=True, the parity cell)."""
    e = stressed(book, kind)
    mpm = e.mae_per_micro.astype(float).copy()
    if kind in ("S1", "S3"): mpm = mpm - 1.0 * e.inst.map(pl.MULT)
    if kind == "S4": mpm = mpm * 1.5
    r = pl.route(e.assign(mae_s=mpm))
    per = (r.net_today / r.n_contracts).to_numpy(float); mae = np.minimum(r.mae_s.to_numpy(float), per)
    a = r.tin.map(lambda t: t.value).to_numpy(np.int64); b = r.tout.map(lambda t: t.value).to_numpy(np.int64)
    marks = []
    for k, x in enumerate(r.itertuples()):
        if flat: marks.append((np.array([a[k]]), np.array([mae[k]]))); continue
        ts, H, L = BARS[x.inst]
        tt, v = fc.trade_marks(ts, H, L, x.side, x.entry, a[k], b[k], pl.TODAY[x.inst], pl.MULT[x.inst], pl.ADV)
        marks.append((tt, stress_marks(v, x.inst, kind)))
    intra = pd.DataFrame(dict(a=a, b=b, per=per, mae=mae, risk=r.risk_today.to_numpy(float), n=r.n_contracts.to_numpy(float),
                              prio=r.prio.to_numpy(float), day=r.tout.dt.date.to_numpy(), mk=np.arange(len(r))))
    _, n = sc17(kind, N0)
    n = n.assign(key=n.tin.map(lambda t: t.value)).merge(NI[["key", "mae_per_micro"]], on="key", how="left")
    assert n.mae_per_micro.notna().all() and n.key.isin(list(OV)).all(), "night alignment failed"
    nm = n.mae_per_micro.to_numpy(float); nper = n.net_today.to_numpy(float); stopped = nper <= STOP_LEVEL + 1e-6
    if kind in ("S1", "S3"): nm = nm - 1.0 * pl.MULT["MNQ"]
    if kind == "S4": nm = np.where(stopped, nm, nm * 1.5)
    nmae = np.minimum(nm, nper); na = n.key.to_numpy(np.int64); nb = n.tout.map(lambda t: t.value).to_numpy(np.int64)
    ts, H, L = BARS["MNQ"]; off = len(marks)
    for k in range(len(n)):
        if flat: marks.append((np.array([na[k]]), np.array([nmae[k]]))); continue
        e_raw, spx = OV[int(na[k])]
        tt, v = fc.trade_marks(ts, H, L, 1, e_raw, na[k], nb[k], pl.TODAY["MNQ"], pl.MULT["MNQ"], pl.ADV, stop_px=spx, stop_val=np.nan)
        v = v.copy(); s_end = np.isnan(v[-1])
        if s_end: v[:-1] = v[:-1] if kind == "S4" and stopped[k] else stress_marks(v[:-1], "MNQ", kind); v[-1] = nper[k]
        else: v = v if (kind == "S4" and stopped[k]) else stress_marks(v, "MNQ", kind)
        marks.append((tt, v))
    nr = NIGHT_RISK * (1.5 if kind == "S4" else 1.0)
    nights = pd.DataFrame(dict(a=na, b=nb, per=nper, mae=nmae, risk=nr, n=1.0, prio=99.0, day=n.tout.dt.date.to_numpy(),
                               mk=off + np.arange(len(n))))
    return intra, nights, nr, marks


def tables_path(book, kind, flat=False):
    intra, nights, nr, marks = prep2(book, kind, flat); return fc.day_tables_path(intra, nights, nr, STOP, marks)


def dll_count(tab):
    return {f"m{m}": int(sum(v[2] for v in tab[(m, True)].values())) for m in (2, 3, 4)}


STACK = pd.concat([base, G["stack_sleeves"](G["RAW"].side.to_numpy())], ignore_index=True)
F4X = dict(ladder=((0, 1), (4000, 2), (4800, 3), (6500, 4)), K=8500.0)
CELLS = {"F4X": ("base", F4X), "B3X": ("base", dict(ladder=((0, 1), (4000, 2), (5000, 3)), K=6500.0)),
         "P24": ("base", dict(ladder=((0, 1), (4000, 2)), K=6000.0)),
         "TRI": ("stack", dict(ladder=((0, 1), (4000, 2), (4600, 3), (5400, 4)), K=8600.0, gate=8700.0, sprint=True))}
P30 = json.loads((ROOT / "reports/PAYOUT_30_INTRADAY_FUNDED_TRAINING.json").read_text())["cells"]
out = dict(parity={}, cells={}, dll_days_table={}, validation_accessed=False, test_accessed=False)

T = {}
for kind in ("S0", "S3", "S4"):
    core = G["tables"](base, kind)                                   # payout_30 core, after the worst-cap fix
    flat = tables_path(base, kind, flat=True)
    rc, rf = fc.summ(fc.replay({"base": core}, **F4X)), fc.summ(fc.replay({"base": flat}, **F4X))
    out["parity"][kind] = dict(core_now=rc, flat_path=rf, payout30_saved=P30["F4X"][kind],
                               flat_equals_core=bool(all(rc[k] == rf[k] for k in rc)),
                               core_equals_saved=bool(all(rc[k] == P30["F4X"][kind][k] for k in ("usd", "closed", "value", "y1_pays", "dll_days"))))
    print("parity", kind, out["parity"][kind]["flat_equals_core"], out["parity"][kind]["core_equals_saved"], rc["usd"], rf["usd"],
          P30["F4X"][kind]["usd"], flush=True)
    T[("base", kind)] = tables_path(base, kind); T[("stack", kind)] = tables_path(STACK, kind)
    out["dll_days_table"][kind] = dict(core=dll_count(core), exact=dll_count(T[("base", kind)]))
    print("tables", kind, out["dll_days_table"][kind], f"{time.time() - t0:.0f}s", flush=True)
assert all(v["flat_equals_core"] for v in out["parity"].values()), "path code with flat marks must reproduce the core"

for name, (bk, kw) in CELLS.items():
    c = out["cells"][name] = {}
    for kind in ("S0", "S3", "S4"):
        tb = {"base": T[("base", kind)]}
        if bk == "stack": tb["stack"] = T[("stack", kind)]
        c[kind] = fc.summ(fc.replay(tb, **kw))
    s = c["S0"]
    print(f"{name:4s} S0 {s['usd']:.0f} ({s['usd_h1']:.0f}/{s['usd_h2']:.0f}) value {s['value']:.0f} closed {c['S0']['closed']:.3f}/"
          f"{c['S3']['closed']:.3f}/{c['S4']['closed']:.3f} S3 {c['S3']['usd']:.0f} S4 {c['S4']['usd']:.0f} y1 {s['y1_pays']} first "
          f"{s['first_median']:.0f} dll/win {s['dll_days']} | payout_30 {P30[name]['S0']['usd']:.0f}", flush=True)
F = out["cells"]["F4X"]


def qualifies(c):
    return bool(all(c["S0"][f"usd_{h}"] >= 1.03 * F["S0"][f"usd_{h}"] for h in ("h1", "h2"))
                and all(c["S0"][f"value_{h}"] >= F["S0"][f"value_{h}"] for h in ("h1", "h2"))
                and all(c[s]["usd"] >= F[s]["usd"] for s in ("S3", "S4")) and all(c[s]["closed"] <= F[s]["closed"] + 0.005 for s in ("S0", "S3", "S4")))


out["qualifies_vs_F4X"] = {n: qualifies(out["cells"][n]) for n in CELLS if n != "F4X"}
print("qualifies vs F4X (exact marks):", out["qualifies_vs_F4X"], flush=True)


# inactivity: F4X state machine, trading days = days present in the table used that day
def gaps(tab, ladder, K, a0="2010-07-01", a1="2022-01-01", months=24, limit=30):
    days = sorted(set().union(*[set(v) for v in tab.values()])); ix = pd.to_datetime(pd.Series(days).astype(str)).to_numpy(); res = []
    for s0 in pd.date_range(a0, a1, freq="MS"):
        a = int(np.searchsorted(ix, np.datetime64(s0))); b = int(np.searchsorted(ix, np.datetime64(s0 + pd.DateOffset(months=months))))
        bal = 0.0; paid = 0; since = 0.0; last = s0; worst_gap = 0; n_over = 0
        for j in range(a, b):
            x = days[j]; m = max((mm for th, mm in ladder if bal >= th), default=1); key = (m, bal >= 500.0)
            if x not in tab[key]: continue
            p, w, hit = tab[key][x]; floor = 0.0 if paid else -2000.0
            g = (pd.Timestamp(x) - last).days; worst_gap = max(worst_gap, g); n_over += g > limit; last = pd.Timestamp(x)
            if bal + min(w, p) <= floor: break
            bal += p; since += p
            if (since > 0 or not paid) and bal - K >= 250.0: bal -= min(1500.0, bal - K); paid += 1; since = 0.0
        res.append((worst_gap, n_over))
    g = np.array(res)
    return dict(windows_with_gap_over_30=round(float((g[:, 1] > 0).mean()), 4), gaps_over_30_per_window=round(float(g[:, 1].mean()), 2),
                max_gap=int(g[:, 0].max()), median_window_max_gap=float(np.median(g[:, 0])))


out["inactivity_F4X_S0"] = gaps(T[("base", "S0")], **F4X)
print("inactivity F4X S0", out["inactivity_F4X_S0"], flush=True)
(ROOT / "reports/PAYOUT_33_EXACT_MARKS_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
print("saved", f"{time.time() - t0:.0f}s", flush=True)
