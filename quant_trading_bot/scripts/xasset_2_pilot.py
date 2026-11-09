"""xasset_2 (b: coverage fix - Sunday nights use Friday day return via 3-day forward fill; declared, no parameter change): ZN/CL/6E day and reopen states as conditioners for overnight_dip_v2 nights; training 2010-23 only."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
rng = np.random.default_rng(20261109)
src = (ROOT / "scripts/overnight_3_pilot.py").read_text().split("\nif __name__")[0].split("\nN = ")[0]
ns = {"__name__": "ov3", "__file__": str(ROOT / "scripts/overnight_3_pilot.py")}; exec(src, ns)
mn, me = ns["nights"]("MNQ"), ns["nights"]("MES")
p_all = ns["pnl"](mn, "MNQ", ex="x0945"); dip = ((mn.gap <= -0.5 * mn.sd20) & (me.gap.reindex(mn.index) <= -0.5 * me.sd20.reindex(mn.index))).fillna(False)
p = p_all[dip & p_all.notna()]; years = mn.year.reindex(p.index); print("dip nights", len(p), round(p.sum(), 2), flush=True)
def states(sym):
    d = pd.read_parquet(ROOT / f"data/market/crossasset/{sym}_c_0_ohlcv1m_2010_2025.parquet", columns=["open", "close"]); d = d[d.index < pd.Timestamp("2024-01-01", tz="UTC")]
    et = d.index.tz_convert("America/New_York"); sod = et.hour * 60 + et.minute; date = pd.Series(et.date, index=d.index)
    c16 = d.close[(sod >= 955) & (sod < 960)].groupby(date[(sod >= 955) & (sod < 960)]).last()
    o18 = d.open[sod == 1080].groupby(date[sod == 1080]).first(); c1804 = d.close[sod == 1084].groupby(date[sod == 1084]).last()
    D = (c16 / c16.shift(1) - 1); R = (c1804 / o18 - 1)
    return D, R
def gate(q):
    yr = q.groupby(years.reindex(q.index)).sum(); eq = q.cumsum()
    return dict(net=round(float(q.sum()), 2), nights=int(len(q)), pos_years=int((yr > 0).sum()), max_year_share=round(float(yr.max() / q.sum()), 3) if q.sum() > 0 else None, dd=round(float((eq.cummax() - eq).max()), 2))
out = {}; arr = p.to_numpy()
for sym in ("ZN", "CL", "6E"):
    D, R = states(sym)
    for fname, f in (("day", D), ("reopen", R)):
        f = f.dropna(); f.index = pd.to_datetime(f.index); idx = pd.to_datetime(pd.Index(p.index)); fv = f.reindex(f.index.union(idx)).ffill(limit=3); v = fv.reindex(idx); v.index = p.index
        for sname, m in ((">0", v > 0), ("<0", v < 0)):
            m = m.fillna(False).to_numpy(); k = int(m.sum()); rem = float(p[m].sum())
            rand = np.array([arr[rng.choice(len(arr), size=k, replace=False)].sum() for _ in range(200)]) if k else np.array([0.0])
            keep = gate(p[~m]); r = dict(n=k, per=round(float(p[m].mean()), 2) if k else None, removed_net=round(rem, 2), random_removals_worse=int((rand < rem).sum()), remaining=keep,
                                         coverage=round(float(v.notna().mean()), 3))
            r["adoptable"] = bool(rem < 0 and r["random_removals_worse"] <= 10 and keep["pos_years"] >= 11 and (keep["max_year_share"] or 1) <= 0.4 and keep["dd"] < 2000 and keep["nights"] >= 100)
            out[f"{sym}_{fname}{sname}"] = r; print(f"{sym} {fname}{sname}", r, flush=True)
Path(ROOT / "reports/XASSET_2B_TRAINING.json").write_text(json.dumps(out, indent=1, default=str)); print("done")
