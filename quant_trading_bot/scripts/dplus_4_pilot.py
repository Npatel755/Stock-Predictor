"""dplus_4: Crabel gap-alignment audit on the fixed engine, training 2010-23 only (research/dplus_4/PROTOCOL.md)."""
import json
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts/dplus_1_pilot.py").read_text().split("\nout = {}")[0]; ns = {"__file__": str(ROOT / "scripts/dplus_1_pilot.py")}; exec(src, ns)
ep, run_sl, route, stats, marked, bars_for = ns["ep"], ns["run_sl"], ns["route"], ns["stats"], ns["marked"], ns["bars_for"]
sls = ep.CANDIDATES["ag_arch_d_plus_v2"]["sleeves"]; cr = [s for s in sls if "CRABEL" in s["name"]][0]
b, _, _ = bars_for(cr); print(list(b.columns)[:12], flush=True)
loc = b.timestamp_utc.dt.tz_convert("America/New_York"); m = loc.dt.hour * 60 + loc.dt.minute; day = loc.dt.date
rth = b[(m >= 570) & (m <= 960)]; rl = loc[rth.index]
first_open = rth.groupby(day[rth.index]).open.first(); last_close = rth.groupby(day[rth.index]).close.last()
gap = (first_open - last_close.shift(1)).dropna(); gap.index = pd.to_datetime(pd.Series(gap.index)).dt.date.to_numpy()
gapd = dict(zip(gap.index, gap.to_numpy()))
allt = sum((run_sl(sl, i) for i, sl in enumerate(sls)), []); base = route(allt)
print(sorted(base[0].keys()), flush=True)
dkey = next(k for k in ("direction", "side", "dir") if k in base[0])
def summ(tr):
    s = stats(tr); s.pop("by_year", None); return dict(s, **marked(tr))
def is_long(t):
    v = t[dkey]; return (v > 0) if isinstance(v, (int, float, np.integer, np.floating)) else str(v).lower() in ("long", "buy", "1")
for t in base:
    t["day"] = pd.Timestamp(t["entry_ts"]).tz_convert("America/New_York").date(); t["gap"] = gapd.get(t["day"], np.nan)
    t["crabel"] = t["sleeve"] == cr["name"]
    t["cont"] = bool(t["crabel"] and not np.isnan(t["gap"]) and ((is_long(t) and t["gap"] >= 0) or (not is_long(t) and t["gap"] <= 0)))
crab = [t for t in base if t["crabel"]]; cont = [t for t in crab if t["cont"]]; fade = [t for t in crab if not t["cont"]]
out = dict(base=summ(base), crabel_all=summ(crab), crabel_cont=summ(cont), crabel_fade=summ(fade), gap_nan=int(sum(np.isnan(t["gap"]) for t in crab)))
for k in ("crabel_all", "crabel_cont", "crabel_fade"): print(k, out[k], flush=True)
rng = np.random.default_rng(4); worse = 0; n = len(fade)
for _ in range(200):
    idx = set(rng.choice(len(crab), n, replace=False)); keep = [t for i, t in enumerate(crab) if i not in idx]
    worse += sum(t["net"] for t in keep) < out["crabel_cont"]["net"]
out["placebo_worse_of_200"] = int(worse)
v3 = [t for t in base if (not t["crabel"]) or t["cont"]]; mirror = [t for t in base if (not t["crabel"]) or (t["crabel"] and not t["cont"])]
out["dplus_v3"] = summ(v3); out["mirror_fades_only"] = summ(mirror)
out["by_year_cont"] = stats(cont)["by_year"]; out["by_year_fade"] = stats(fade)["by_year"]
g = dict(g1=out["crabel_fade"]["net"] <= 0 or out["crabel_fade"]["per"] < out["crabel_cont"]["per"] / 3, g2=worse >= 190, g3=out["crabel_cont"]["pos_years"] >= 11,
         g4=out["dplus_v3"]["marked_dd"] < out["base"]["marked_dd"] and out["dplus_v3"]["net"] >= 0.85 * out["base"]["net"],
         g5=out["mirror_fades_only"]["net"] < out["dplus_v3"]["net"] - 2000)
out["gates"] = {k: bool(v) for k, v in g.items()}; out["pass"] = all(g.values())
print("placebo", worse, "v3", out["dplus_v3"], "mirror", out["mirror_fades_only"], "gates", out["gates"], flush=True)
json.dump(out, open(ROOT / "reports/DPLUS_4_TRAINING.json", "w"), indent=1, default=str); print("DONE", flush=True)
