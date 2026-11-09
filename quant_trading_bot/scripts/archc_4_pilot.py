"""archc_4: NQ-only drive (MES does NOT confirm) gate; derived from archc_3; fixed engine; training 2010-23 only. Was: archc_3: MES-confirmation ('breadth') gate on Architecture C sleeves; fixed engine; training 2010-23 only."""
import json, os, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
os.environ["SIZING_BUDGET"] = "150"
src = (ROOT / "scripts/sizing_1_pilot.py").read_text().split("\nfor key in (")[0]
ns = {"__file__": str(ROOT / "scripts/sizing_1_pilot.py")}; exec(src, ns)
ep, bars_for, daily = ns["ep"], ns["bars_for"], ns["daily"]
rng = np.random.default_rng(20261109); START = ns["START"]
SPECS = {"C": ep.CANDIDATES["ag_arch_c"], "AW": ep.CANDIDATES["ag_all_weather_v2_1c"]}
spec = SPECS["C"]

def raw_signal(sl, inst):
    b, mins, _ = bars_for(dict(sl, instrument=inst))
    if sl.get("signal"): raw, _atr = ep.custom_signal(dict(sl, instrument=inst), b)
    else:
        eng = ep.engine(); feats = eng["features"](b, int(sl["lookback"])); raw = eng["signal_for"](sl, feats)
    return pd.Series(np.asarray(raw, dtype=np.int8), index=pd.DatetimeIndex(b.timestamp_utc)), b

def run(variant):
    allt = []
    for prio, sl in enumerate(spec["sleeves"]):
        r_mnq, b = raw_signal(sl, "MNQ"); blocked = None
        if variant and not (variant == "R2" and sl.get("signal") == "crabel_open_drive"):
            r_mes, _ = raw_signal(sl, "MES"); m = r_mes.reindex(r_mnq.index).fillna(0).to_numpy().astype(int); q = r_mnq.to_numpy().astype(int)
            blocked = (q != 0) & (m == q)
        if spec.get("day_filter") == "no_backwardation":
            bw = ns["backw_mask"](b); blocked = bw if blocked is None else (blocked | bw)
        r = ep.run_sleeve(sl, b, START, blocked)
        for t in r["trades"]:
            t["prio"] = prio; t["dec"] = pd.Timestamp(t["entry_ts"]) - pd.Timedelta(minutes=int(sl["bar_minutes"]))
            t["exit_day"] = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
        allt += r["trades"]
    allt.sort(key=lambda x: (x["dec"], x["prio"])); acc = []
    if spec.get("router") != "strict_1c": return allt
    for x in allt:
        if any(pd.Timestamp(a["entry_ts"]) <= x["dec"] < pd.Timestamp(a["exit_ts"]) for a in acc[-5:]): continue
        acc.append(x)
    return acc

def stats(acc):
    d = daily(acc); d.index = pd.to_datetime(d.index); yr = d.groupby(d.index.year).sum(); eq = d.cumsum()
    return dict(net=round(float(d.sum()), 2), trades=len(acc), per=round(float(d.sum() / max(len(acc), 1)), 2), closed_dd=round(float((eq.cummax() - eq).max()), 2),
                pos_years=int((yr > 0).sum()), max_year_share=round(float(yr.max() / d.sum()), 3) if d.sum() > 0 else None, pre2020=round(float(yr[yr.index < 2020].sum()), 2))

key = lambda t: (t["sleeve"], t["entry_ts"], t["exit_ts"])
out = {}
for fam, variants in (("C", ("R1", "R2")), ("AW", ("R1",))):
    spec = SPECS[fam]; ns["UNCAP"]["on"] = (fam == "AW"); ns["BUDGET"] = 1e9 if fam == "AW" else 150.0
    base = run(None); bs = stats(base); print(fam, "BASE", bs, flush=True); out[f"{fam}_base"] = bs
    bnet = np.array([t["net"] for t in base])
    for v in variants:
        acc = run(v); st = stats(acc); k = len(acc)
        rand = np.array([bnet[rng.choice(len(bnet), size=min(k, len(bnet)), replace=False)].sum() for _ in range(200)])
        st.update(beats_subsets=int((st["net"] > rand).sum()), subset_median=round(float(np.median(rand)), 2))
        st["pass"] = bool(st["per"] > bs["per"] and st["closed_dd"] <= bs["closed_dd"] and st["pos_years"] >= bs["pos_years"] and (st["max_year_share"] or 1) <= 0.4
                          and st["pre2020"] > 0.5 * bs["pre2020"] and st["beats_subsets"] >= 190)
        out[f"{fam}_{v}"] = st; print(fam, v, st, flush=True)
Path(ROOT / "reports/ARCHC_4_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
