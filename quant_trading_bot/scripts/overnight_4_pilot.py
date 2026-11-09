"""overnight_4 (research/overnight_4/PROTOCOL.md): stress diagnostics of overnight_dip_v2 on 2010-2023 training. No parameter selection."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/overnight_3_pilot.py").read_text().split("out = {")[0]; ns = {"__file__": str(ROOT / "scripts/overnight_3_pilot.py")}; exec(src, ns)
nights, pnl, SPEC, COMM = ns["nights"], ns["pnl"], ns["SPEC"], ns["COMM"]
rng = np.random.default_rng(67); out = {}
mn, ms = nights("MNQ"), nights("MES")
mes_gap, mes_sd = ms.gap.reindex(mn.index), ms.sd20.reindex(mn.index)
def rule_mask(k=0.5, w=20):
    sdq = mn.gap.rolling(w, min_periods=max(10, int(0.75 * w))).std().shift(1); sdm = ms.gap.rolling(w, min_periods=max(10, int(0.75 * w))).std().shift(1).reindex(mn.index)
    return ((mn.gap <= -k * sdq) & (mes_gap <= -k * sdm)).fillna(False)
def stats(p):
    yr = p.groupby(mn.year.loc[p.index]).sum(); eq = p.cumsum()
    return dict(net=round(float(p.sum()), 2), nights=int(len(p)), pos_years=int((yr > 0).sum()), max_dd=round(float((eq.cummax() - eq).max()), 2), pre2020=round(float(yr[yr.index < 2020].sum()), 2))
base = pnl(mn, "MNQ", ex="x0945"); m0 = rule_mask(); p0 = base[m0 & base.notna()]
out["rule"] = stats(p0); print("rule", out["rule"], flush=True)
# 1 plateau
out["plateau"] = {}
for k in (0.25, 0.375, 0.5, 0.625, 0.75, 1.0):
    for w in (10, 15, 20, 30, 40):
        m = rule_mask(k, w); r = stats(base[m & base.notna()]); out["plateau"][f"k{k}_w{w}"] = r
print("plateau", {kk: (v["net"], v["pos_years"], v["max_dd"]) for kk, v in out["plateau"].items()}, flush=True)
neigh = [out["plateau"][f"k{k}_w{w}"] for k in (0.375, 0.5, 0.625) for w in (15, 20, 30)]
out["plateau_ok"] = all(r["net"] > 0 and r["pos_years"] >= 10 and r["max_dd"] < 2000 for r in neigh)
# 2 intrabar DD: nightly worst = low_night - entry (ticks) * tv - cost
s = SPEC["MNQ"]; cost = (s["spread"] + 2) * s["tv"] + 2 * COMM
worst = ((mn.low_night - mn.e1805) / s["tick"] * s["tv"] - cost).loc[p0.index]
eq = p0.cumsum(); peak = eq.cummax(); intrabar_eq = eq - p0 + worst; dd_intra = (peak.shift(1).fillna(0) - intrabar_eq).clip(lower=0)
out["intrabar_dd"] = dict(max=round(float(dd_intra.max()), 2), by_year={int(y): round(float(v), 2) for y, v in dd_intra.groupby(mn.year.loc[p0.index]).max().items()})
print("intrabar", out["intrabar_dd"], flush=True)
# 3 block bootstrap MC
def mc(p, wst, n_nights, paths=5000, L=10):
    x = p.to_numpy(); wv = wst.to_numpy(); n = len(x); res = dict(closed=0, intra=0, nets=[])
    for _ in range(paths):
        idx = []
        while len(idx) < n_nights:
            st = rng.integers(n); ln = rng.geometric(1 / L); idx.extend(((st + np.arange(ln)) % n).tolist())
        idx = np.array(idx[:n_nights]); e = np.cumsum(x[idx]); pk = np.maximum.accumulate(np.concatenate([[0], e]))[:-1]
        res["closed"] += int((pk - e).max() >= 2000); res["intra"] += int((pk - (e - x[idx] + wv[idx])).max() >= 2000); res["nets"].append(float(e[-1]))
    nets = np.array(res["nets"]); return dict(p_closed_dd_2k=round(res["closed"] / paths, 3), p_intrabar_dd_2k=round(res["intra"] / paths, 3), net_p5=round(float(np.percentile(nets, 5)), 0), net_p50=round(float(np.percentile(nets, 50)), 0), net_p95=round(float(np.percentile(nets, 95)), 0))
per_year = len(p0) / 14
out["mc"] = {"all_1y": mc(p0, worst, int(per_year)), "all_2y": mc(p0, worst, int(2 * per_year))}
sel = ~mn.year.loc[p0.index].isin([2020, 2021, 2022]); out["mc"]["ex2020_22_1y"] = mc(p0[sel], worst[sel], int(per_year)); out["mc"]["ex2020_22_2y"] = mc(p0[sel], worst[sel], int(2 * per_year))
print("mc", out["mc"], flush=True)
# 4 tail
srt = p0.sort_values(); top = p0.nlargest(max(1, int(0.05 * len(p0)))).sum()
out["tail"] = dict(worst10={str(k): round(float(v), 1) for k, v in srt.head(10).items()}, n_le_400=int((p0 <= -400).sum()), n_le_500=int((p0 <= -500).sum()), top5pct_share=round(float(top / p0.sum()), 3), worst_intrabar_night=round(float(worst.min()), 1))
print("tail", out["tail"], flush=True)
# 5 calendar
dow = mn.dow.loc[p0.index]; out["calendar"] = dict(sunday_net=round(float(p0[dow == 6].sum()), 2), sunday_nights=int((dow == 6).sum()), weekday_net=round(float(p0[dow != 6].sum()), 2),
                                                 nights_no_0945_exit=int((m0 & base.isna()).sum()), by_dow={int(d): round(float(v), 2) for d, v in p0.groupby(dow).sum().items()})
print("calendar", out["calendar"], flush=True)
# 6 slippage sensitivity
for slip in (2, 3):
    extra = 2 * (slip - 1) * s["tv"]; out[f"slip{slip}"] = stats(p0 - extra); print(f"slip{slip}", out[f"slip{slip}"], flush=True)
out["fragile"] = bool((not out["plateau_ok"]) or out["mc"]["all_1y"]["p_intrabar_dd_2k"] > 0.25)
json.dump(out, open(ROOT / "reports/OVERNIGHT_4_STRESS.json", "w"), indent=1, default=float); print("FRAGILE", out["fragile"]); print("DONE")
