"""overnight_2 (research/overnight_2/PROTOCOL.md): reopen-dip overnight hold follow-up. Reuses nights()/pnl() from overnight_1_pilot.py."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/overnight_1_pilot.py").read_text().split("rng = np.random.default_rng(31)")[0]
src = src.replace('def nights(prod):\n    b = m1.load_bars(prod, 1, "2010-01-01", "2024-01-01", "train")', 'def nights(prod, lo="2010-01-01", hi="2024-01-01", split="train"):\n    b = m1.load_bars(prod, 1, lo, hi, split)')
ns = {"__file__": str(ROOT / "scripts/overnight_1_pilot.py")}; exec(src, ns); nights, pnl, cboe = ns["nights"], ns["pnl"], ns["cboe"]
vix = cboe("VIX"); rng = np.random.default_rng(41)
def enrich(n):
    n["vix_prev"] = pd.Series(n.index, index=n.index).map(vix); n["gap_std20"] = n.reopen_gap.rolling(20, min_periods=15).std().shift(1); return n
def masks(n):
    g, d0 = n.reopen_gap, n.reopen_gap < 0
    return {"D0_gap_lt_0": d0, "D1_gap_le_-0.05pct": g <= -0.0005, "D2_gap_le_-0.10pct": g <= -0.001, "D3_gap_le_-0.20pct": g <= -0.002, "D4_gap_le_-0.5sd": g <= -0.5 * n.gap_std20, "D5_gap_le_-1.0sd": g <= -1.0 * n.gap_std20,
            "X1_dip_backwardation": d0 & (n.ratio_prev > 1), "X2_dip_contango": d0 & (n.ratio_prev <= 1), "X3_dip_vix_gt_20": d0 & (n.vix_prev > 20), "X4_dip_vix_le_20": d0 & (n.vix_prev <= 20),
            "S1_dip_stop2sd": d0, "S2_dip_exit0935": d0, "S3_dip_after_down_day": d0 & (n.rth_ret < 0), "S4_dip_after_up_day": d0 & (n.rth_ret > 0), "Q1_dip_mon_thu": d0 & (n.dow <= 3), "Q2_dip_sunday": d0 & (n.dow == 6)}
def variant_pnl(n, prod, name):
    return pnl(n, prod, 1, "exit_0935" if name.startswith("S2") else "exit_open", name.startswith("S1"))
def evaluate(n, prod, name, mask, n_plc, min_years):
    p = variant_pnl(n, prod, name)[mask & variant_pnl(n, prod, name).notna()]; yrs = n.year[p.index]; yr = p.groupby(yrs).sum(); t = float(p.sum())
    if len(p) == 0:
        rec = {"net": 0.0, "nights": 0, "pass": False}; print(prod, name, "no nights", flush=True); return rec
    eq = p.cumsum(); dd = float((eq.cummax() - eq).max()) if len(p) else 0.0
    rec = dict(net=round(t, 2), nights=int(len(p)), per_night=round(t / len(p), 2) if len(p) else None, pos_years=int((yr > 0).sum()), years=int(len(yr)), pre2020=round(float(yr[yr.index < 2020].sum()), 2),
               max_year_share=round(float(yr.max() / t), 3) if t > 0 else None, max_dd=round(dd, 2), worst_night=round(float(p.min()), 2) if len(p) else None, by_year={int(y): round(float(v), 2) for y, v in yr.items()})
    if n_plc:
        cnt = yrs.groupby(yrs).size(); full = variant_pnl(n, prod, name); plc = []
        for _ in range(n_plc):
            pick = np.concatenate([rng.choice(n.index[n.year == y], size=min(int(c), int((n.year == y).sum())), replace=False) for y, c in cnt.items()])
            plc.append(float(full.loc[pick].fillna(0).sum()))
        rec.update(beat=int(sum(t > x for x in plc)), n_plc=n_plc, placebo_mean=round(float(np.mean(plc)), 2))
    rec["pass"] = bool(t > 0 and rec["pos_years"] >= min_years and len(p) >= 100 and (rec["max_year_share"] or 1) <= 0.4 and dd < 2000 and (not n_plc or rec["beat"] >= 0.95 * n_plc))
    print(prod, name, {k: v for k, v in rec.items() if k != "by_year"}, flush=True); return rec
out = {"train": {}}
for prod in ("MNQ", "MES"):
    n = enrich(nights(prod))
    for name, mask in masks(n).items(): out["train"][f"{prod}_{name}"] = evaluate(n, prod, name, mask.fillna(False), 200, 10)
passers = [k for k, v in out["train"].items() if v["pass"]]; print("PASSERS", passers, flush=True); out["frozen_passers"] = passers
if passers:
    out["validation"] = {}
    for prod in ("MNQ", "MES"):
        mine = [k for k in passers if k.startswith(prod + "_")]
        if not mine: continue
        n = enrich(nights(prod, "2023-10-01", "2026-01-01", "validation")); n = n[n.year >= 2024]; assert n.year.max() <= 2025
        for k in mine:
            name = k[len(prod) + 1:]; r = evaluate(n, prod, name, masks(n)[name].fillna(False), 0, 2); r["validated"] = bool(r["net"] > 0 and r["pos_years"] == 2); out["validation"][k] = r
json.dump(out, open(ROOT / "reports/OVERNIGHT_2_TRAINING.json", "w"), indent=1, default=float); print("DONE")
