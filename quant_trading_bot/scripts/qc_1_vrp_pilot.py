"""qc_1 T2 (vrp_1, research/qc_1/PROTOCOL.md): variance risk premium (prior-close VIX^2 minus realized variance of ES 15m RTH returns over the prior 21 sessions) as a point-in-time day state. Training 2010-23 only. Built from extstate_1_pilot.py."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts"))
import importlib.util
spec = importlib.util.spec_from_file_location("a1", ROOT / "scripts/anomaly_1_pilot.py"); src = (ROOT / "scripts/anomaly_1_pilot.py").read_text()
ns = {"__file__": str(ROOT / "scripts/anomaly_1_pilot.py")}; exec(src.split("# ---------- A:")[0], ns); load, SPEC, rt_cost, gate = ns["load"], ns["SPEC"], ns["rt_cost"], ns["gate"]
exec("import numpy as np\nfrom numba import njit\n" + src.split("# ---------- C: ER filter on fixed 15m momentum rule (MNQ) ----------")[1].split("b = load(")[0].replace("cache=True", "cache=False"), ns); sim15 = ns["sim15"]
rng = np.random.default_rng(20261111); out = {"T1": [], "T2": []}

def cboe(name):
    d = pd.read_csv(ROOT / f"data/external/{name}_History.csv"); d["date"] = pd.to_datetime(d.DATE, format="%m/%d/%Y").dt.date; return d.set_index("date").CLOSE.astype(float)
vix, vix3m = cboe("VIX"), cboe("VIX3M")
es15 = load("MES", 15); es_daily = es15.groupby("date").close.last()
es15["ret"] = es15.groupby("date").close.pct_change()
rv_day = es15.groupby("date").ret.apply(lambda s: float((s.dropna() ** 2).sum()))   # daily realized variance from 15m RTH returns
daily = pd.DataFrame(dict(vix=vix)).join(rv_day.rename("rv"), how="outer").sort_index()
daily["iv"] = (daily.vix / 100) ** 2 / 252                                              # implied daily variance
daily["rv21"] = daily.rv.rolling(21, min_periods=15).mean()
daily["vrp"] = daily.iv - daily.rv21
daily["vrp_rank"] = daily.vrp.rolling(504, min_periods=250).rank(pct=True)
prior = daily.shift(1)  # prior row = prior close for the trading day
STATES = dict(vrp_hi=prior.vrp_rank > 2 / 3, vrp_lo=prior.vrp_rank < 1 / 3, vrp_neg=prior.vrp < 0, vrp_pos=prior.vrp > 0)
STATES = {k: v.fillna(False) for k, v in STATES.items()}
LONG = ["vrp_hi", "vrp_pos", "vrp_lo", "vrp_neg"]; SHORT = ["vrp_hi", "vrp_pos", "vrp_lo", "vrp_neg"]   # both sides: sign of the premium-to-direction link is not assumed

# T1 day direction
for prod in ("MNQ", "MES"):
    b = load(prod, 1); s = SPEC[prod]; g = b.groupby("date")
    px = lambda sod, col: g.apply(lambda d: d.loc[d.sod == sod, col].iloc[0] if (d.sod == sod).any() else np.nan)
    t = pd.DataFrame(dict(o945=px(585, "open"), c1554=px(954, "close"))).dropna(); t["year"] = pd.to_datetime(t.index).year
    gross = (t.c1554 - t.o945) / s["tick"] * s["pv"]
    for st, side in [(k, 1) for k in LONG] + [(k, -1) for k in SHORT]:
        m = STATES[st].reindex(t.index).fillna(False).to_numpy(); pnl = side * gross[m] - rt_cost(prod); yearly = pnl.groupby(t.year[m]).sum()
        pl = [float((rng.choice([-1, 1], size=int(m.sum())) * gross[m] - rt_cost(prod)).sum()) for _ in range(20)]
        rec = dict(product=prod, state=st, side=side, days=int(m.sum()), **gate(float(pnl.sum()), yearly, int(m.sum()), pl, 100)); out["T1"].append(rec)
        print("T1", prod, st, side, rec["net"], rec["trades"], rec["pos_years"], rec["placebo_pct"], rec["passes"], flush=True)

# T2 state filter on fixed 15m MNQ momentum rule
b = load("MNQ", 15); b["day"] = pd.factorize(b.date)[0]; g = b.groupby("day", sort=False)
tr = np.maximum(b.high - b.low, np.maximum((b.high - g.close.shift(1)).abs(), (b.low - g.close.shift(1)).abs())); atr = np.nan_to_num(tr.rolling(14, min_periods=14).mean().to_numpy())
mom = (b.close / b.close.shift(24) - 1).to_numpy(); o, h_, l_, c_ = [b[k].to_numpy(float) for k in ("open", "high", "low", "close")]
day = b.day.to_numpy(np.int64); sod = b.sod.to_numpy(np.int64); year = b.year.to_numpy(); dates = b.date.to_numpy()
valid = (sod >= 585) & (sod < 930); base = np.where(valid, np.sign(np.nan_to_num(mom)), 0).astype(np.int8); cost = rt_cost("MNQ")
def runC(sig):
    pnl, ntr = sim15(o, h_, l_, c_, atr, sig, day, sod, 24, 2.0, 3.0, 585, 930, 955, cost); return float(pnl.sum()), ntr, pd.Series(pnl).groupby(year).sum()
all_days = pd.Series(dates).drop_duplicates(); day_year = pd.Series(pd.to_datetime(all_days).dt.year.values, index=all_days.values)
for st, sm in STATES.items():
    on_days = set(sm[sm].index); mask = valid & np.isin(dates, list(on_days)); net, ntr, yearly = runC(np.where(mask, base, 0).astype(np.int8)); pl = []
    for _ in range(20):
        pick = []
        for y in range(2010, 2024):
            yd = all_days[day_year.values == y].to_numpy(); n = len([d for d in yd if d in on_days]); pick += list(rng.choice(yd, size=n, replace=False))
        pm = valid & np.isin(dates, pick); pl.append(runC(np.where(pm, base, 0).astype(np.int8))[0])
    rec = dict(state=st, days=len(on_days & set(all_days)), **gate(net, yearly, ntr, pl, 100)); out["T2"].append(rec)
    print("T2", st, rec["days"], rec["net"], rec["trades"], rec["pos_years"], rec["placebo_pct"], rec["placebo_mean"], rec["passes"], flush=True)
json.dump(out, open(ROOT / "reports/QC_1_VRP_TRAINING.json", "w"), indent=1, default=float); print("DONE", flush=True)
