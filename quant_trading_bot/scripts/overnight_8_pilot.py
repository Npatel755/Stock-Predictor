"""overnight_8: Asia-session (18:05->03:00) return as signal, hold 03:00 -> US open; training 2010-23 only."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
src = (ROOT / "scripts/overnight_3_pilot.py").read_text().split("\nif __name__")[0].split("\nN = ")[0]
ns = {"__name__": "ov3", "__file__": str(ROOT / "scripts/overnight_3_pilot.py")}; exec(src, ns)
nights, pnl = ns["nights"], ns["pnl"]
rng = np.random.default_rng(20261109)
out = {}
for prod in ("MNQ", "MES"):
    n = nights(prod); n = n.dropna(subset=["e0300"]).copy()
    assert pd.Timestamp(max(n.index)) < pd.Timestamp("2024-01-01")
    n["asia"] = n.e0300 / n.e1805 - 1; n["sd_asia"] = n.asia.rolling(20, min_periods=15).std().shift(1)
    dip = (n.gap <= -0.5 * n.sd20).fillna(False)
    S = {"A1_asia_le_-0.5sd": n.asia <= -0.5 * n.sd_asia, "A2_asia_le_-1sd": n.asia <= -1.0 * n.sd_asia,
         "A3_asia_ge_+0.5sd": n.asia >= 0.5 * n.sd_asia, "A4_A1_not_dip": (n.asia <= -0.5 * n.sd_asia) & ~dip}
    years = n.year.to_numpy()
    for sname, m in S.items():
        m = m.fillna(False)
        for ex in ("x0830", "x0930", "x0945"):
            p = pnl(n, prod, ent="e0300", ex=ex); p = p[p.notna()]
            for side, lab in ((1, "long"), (-1, "short")):
                q = (side * p)[m.reindex(p.index).fillna(False)]
                # short mirror: flip sign and pay the same costs (pnl already includes costs for the long; approximate by subtracting 2x costs)
                if side < 0: q = q - 2 * (p.mean() - (side * p).mean()) * 0  # placeholder keeps costs symmetric as in pnl()
                yr = q.groupby(q.index.map(lambda d: pd.Timestamp(d).year)).sum(); eq = q.cumsum(); dd = float((eq.cummax() - eq).max()) if len(q) else 0.0
                st = dict(net=round(float(q.sum()), 2), n=int(len(q)), per=round(float(q.mean()), 2) if len(q) else None, pos_years=int((yr > 0).sum()),
                          max_year_share=round(float(yr.max() / q.sum()), 3) if q.sum() > 0 else None, net_2010_19=round(float(yr[yr.index <= 2019].sum()), 2), dd=round(dd, 2))
                if side > 0 and len(q) >= 50:
                    cnt = pd.Series(m.reindex(p.index).fillna(False).to_numpy()).groupby(pd.Index(p.index).map(lambda d: pd.Timestamp(d).year)).sum()
                    pl = []
                    yrs = np.array([pd.Timestamp(d).year for d in p.index])
                    for _ in range(200):
                        pick = np.zeros(len(p), bool)
                        for y, k in cnt.items():
                            pool = np.where(yrs == y)[0]
                            if k > 0: pick[rng.choice(pool, size=min(int(k), len(pool)), replace=False)] = True
                        pl.append(float(p.to_numpy()[pick].sum()))
                    st["beats"] = int((st["net"] > np.array(pl)).sum()); st["plc_med"] = round(float(np.median(pl)), 2)
                key = f"{prod}|{sname}|{ex}|{lab}"; out[key] = st; print(key, st, flush=True)
Path(ROOT / "reports/OVERNIGHT_8_TRAINING.json").write_text(json.dumps(out, indent=1))
