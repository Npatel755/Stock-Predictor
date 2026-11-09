"""archc_3: MES-confirmation ('breadth') gate on Architecture C sleeves; fixed engine; training 2010-23 only."""
import json, os, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
os.environ["SIZING_BUDGET"] = "150"
src = (ROOT / "scripts/sizing_1_pilot.py").read_text().split("\nfor key in (")[0]
ns = {"__file__": str(ROOT / "scripts/sizing_1_pilot.py")}; exec(src, ns)
ep, bars_for, daily = ns["ep"], ns["bars_for"], ns["daily"]
rng = np.random.default_rng(20261109); START = ns["START"]
spec = ep.CANDIDATES["ag_arch_c"]

def raw_signal(sl, inst):
    b, mins, _ = bars_for(dict(sl, instrument=inst))
    raw, _atr = ep.custom_signal(dict(sl, instrument=inst), b)
    return pd.Series(np.asarray(raw, dtype=np.int8), index=pd.DatetimeIndex(b.timestamp_utc)), b

def run(variant):
    allt = []
    for prio, sl in enumerate(spec["sleeves"]):
        r_mnq, b = raw_signal(sl, "MNQ"); blocked = None
        if variant and not (variant == "B2" and sl["signal"] == "crabel_open_drive"):
            r_mes, _ = raw_signal(sl, "MES"); m = r_mes.reindex(r_mnq.index).fillna(0).to_numpy().astype(int); q = r_mnq.to_numpy().astype(int)
            blocked = ((q != 0) & (m != q)) if variant in ("B1", "B2") else ((q != 0) & (m == -q))
        r = ep.run_sleeve(sl, b, START, blocked)
        for t in r["trades"]:
            t["prio"] = prio; t["dec"] = pd.Timestamp(t["entry_ts"]) - pd.Timedelta(minutes=int(sl["bar_minutes"]))
            t["exit_day"] = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
        allt += r["trades"]
    allt.sort(key=lambda x: (x["dec"], x["prio"])); acc = []
    for x in allt:
        if any(pd.Timestamp(a["entry_ts"]) <= x["dec"] < pd.Timestamp(a["exit_ts"]) for a in acc[-5:]): continue
        acc.append(x)
    return acc

def stats(acc):
    d = daily(acc); d.index = pd.to_datetime(d.index); yr = d.groupby(d.index.year).sum(); eq = d.cumsum()
    return dict(net=round(float(d.sum()), 2), trades=len(acc), per=round(float(d.sum() / max(len(acc), 1)), 2), closed_dd=round(float((eq.cummax() - eq).max()), 2),
                pos_years=int((yr > 0).sum()), max_year_share=round(float(yr.max() / d.sum()), 3) if d.sum() > 0 else None, pre2020=round(float(yr[yr.index < 2020].sum()), 2))

key = lambda t: (t["sleeve"], t["entry_ts"], t["exit_ts"])
base = run(None); bs = stats(base); print("BASE", bs, flush=True); out = {"base": bs}
bnet = np.array([t["net"] for t in base])
for v in ("B1", "B2", "B3"):
    acc = run(v); st = stats(acc); keep = {key(t) for t in acc}
    removed = [t for t in base if key(t) not in keep]; added = [t for t in acc if key(t) not in {key(t) for t in base}]
    rem = float(sum(t["net"] for t in removed)); k = len(removed)
    rand = np.array([bnet[rng.choice(len(bnet), size=k, replace=False)].sum() for _ in range(200)]) if k else np.array([0.0])
    st.update(removed=k, removed_net=round(rem, 2), random_removals_worse=int((rand < rem).sum()), added=len(added), added_net=round(float(sum(t["net"] for t in added)), 2))
    st["pass"] = bool(st["net"] > bs["net"] and st["closed_dd"] <= bs["closed_dd"] and st["pos_years"] >= bs["pos_years"] and st["pre2020"] > bs["pre2020"] and rem < 0 and st["random_removals_worse"] <= 10)
    out[v] = st; print(v, st, flush=True)
Path(ROOT / "reports/ARCHC_3_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
