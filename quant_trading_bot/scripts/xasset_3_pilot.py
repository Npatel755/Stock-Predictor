"""xasset_3: ZN day-return conditioned overnight leg inside Book A, scored with book_1 marks; training 2010-23 only."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
rng = np.random.default_rng(20261110)
src = (ROOT / "scripts/book_1_pilot.py").read_text().split("\nev.sort(")[0]
ns = {"__file__": str(ROOT / "scripts/book_1_pilot.py")}; exec(src, ns); ev = ns["ev"]
def leg_of(t): return "ov" if (t.hour, t.minute) in ((18, 5), (9, 45)) else "in"
events = sorted([(t, k, w, r, leg_of(t)) for (t, k, w, r) in ev], key=lambda x: x[0])
d = pd.read_parquet(ROOT / "data/market/crossasset/ZN_c_0_ohlcv1m_2010_2025.parquet", columns=["close"]); d = d[d.index < pd.Timestamp("2024-01-01", tz="UTC")]
et = d.index.tz_convert("America/New_York"); sod = et.hour * 60 + et.minute; import os; _h = int(os.environ.get("ZN_DEF", "16")) * 60; sel = (sod >= _h - 5) & (sod < _h)
c16 = d.close[sel].groupby(pd.Series(et.date, index=d.index)[sel]).last(); D = (c16 / c16.shift(1) - 1).dropna(); D.index = pd.to_datetime(D.index)
night_idx = [i for i, e in enumerate(events) if e[4] == "ov" and e[1] == "worst"]
night_dates = pd.to_datetime([events[i][0].date() for i in night_idx])
Dn = D.reindex(D.index.union(night_dates)).ffill(limit=3).reindex(night_dates).to_numpy()
print("nights", len(night_idx), "ZN<0", int((Dn < 0).sum()), "ZN>0", int((Dn > 0).sum()), "missing", int(np.isnan(Dn).sum()), flush=True)
def run(skip_mask):
    skip_open = set()
    for n, i in enumerate(night_idx):
        if skip_mask[n]:
            skip_open.add(i); j = i + 1
            while j < len(events) and not (events[j][4] == "ov" and events[j][1] == "close"): j += 1
            skip_open.add(j)
    closed = 0.0; hwm = 0.0; worst = 0.0; when = None; br = {2000: 0, 2500: 0}; inb = {2000: False, 2500: False}
    for i, (t, k, w, r, leg) in enumerate(events):
        if i in skip_open: continue
        eq = closed + w if k == "worst" else closed + r
        if k == "close": closed += r
        hwm = max(hwm, eq); tdd = hwm - eq
        if tdd > worst: worst, when = tdd, str(t)
        for f in br:
            if tdd >= f and not inb[f]: br[f] += 1; inb[f] = True
            if tdd < f * 0.5: inb[f] = False
    return dict(closed_net=round(closed, 2), marked_dd=round(worst, 2), when=when, breaches=br, skipped=int(np.sum(skip_mask)))
base = run(np.zeros(len(night_idx), bool)); print("book_a", base, flush=True)
b1 = run(Dn < 0); c1 = run(Dn > 0)
k = int((Dn < 0).sum()); plac = []
for _ in range(200):
    m = np.zeros(len(night_idx), bool); m[rng.choice(len(night_idx), size=k, replace=False)] = True; plac.append(run(m))
pdd = np.array([p["marked_dd"] for p in plac]); pnet = np.array([p["closed_net"] for p in plac])
for name, r in (("B1_skip_ZN_down", b1), ("C1_skip_ZN_up", c1)):
    r["retained"] = round(r["closed_net"] / base["closed_net"], 3); print(name, r, flush=True)
b1["placebo_dd_worse_than_B1"] = int((pdd > b1["marked_dd"]).sum()); b1["placebo_net_below_B1"] = int((pnet < b1["closed_net"]).sum())
b1["placebo_dd_median"] = round(float(np.median(pdd)), 2); b1["placebo_net_median"] = round(float(np.median(pnet)), 2)
b1["pass"] = bool(b1["marked_dd"] < 2000 and b1["retained"] >= 0.8 and b1["placebo_dd_worse_than_B1"] >= 190 and c1["retained"] < b1["retained"] and c1["marked_dd"] >= b1["marked_dd"])
print("B1 placebo", {k_: b1[k_] for k_ in ("placebo_dd_worse_than_B1", "placebo_net_below_B1", "placebo_dd_median", "placebo_net_median", "pass")}, flush=True)
(ROOT / ("reports/XASSET_3_TRAINING" + ("" if os.environ.get("ZN_DEF", "16") == "16" else "_" + os.environ["ZN_DEF"]) + ".json")).write_text(json.dumps(dict(book_a=base, B1=b1, C1=c1), indent=1, default=str)); print("done")
