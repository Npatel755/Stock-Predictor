"""quad_2 (research/quad_2/PROTOCOL.md): backwardation stand-aside for the Quad's morning sleeves. Training 2010-2023 only."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import mass_1m_search as m1
from quant_futures import ensemble_paper as ep
rng = np.random.default_rng(131); START = "2010-01-01T00:00:00Z"
def cboe(n):
    d = pd.read_csv(ROOT / f"data/external/{n}_History.csv"); d["date"] = pd.to_datetime(d.DATE, format="%m/%d/%Y").dt.date; return d.set_index("date").CLOSE.astype(float)
RATIO = (cboe("VIX") / cboe("VIX3M")).dropna(); rdates = np.array(sorted(RATIO.index))
def backw_mask(bars):
    days = bars.timestamp_utc.dt.tz_convert("America/New_York").dt.date.to_numpy(); pos = rdates.searchsorted(days) - 1
    vals = (RATIO.reindex(rdates).to_numpy() > 1.0); return np.where(pos >= 0, vals[np.clip(pos, 0, len(vals) - 1)], False)
B30 = m1.load_bars("MNQ", 30, "2009-11-01", "2024-01-01", "train").reset_index(drop=True); B60 = m1.load_bars("MNQ", 60, "2009-11-01", "2024-01-01", "train").reset_index(drop=True)
E30 = m1.load_bars("MES", 30, "2009-11-01", "2024-01-01", "train").reset_index(drop=True)
SL = [("AG_MORN30_1c", ep._sleeve("AG_MORN30_1c", ep._AG_MORN30, 1), B30, 30, True), ("AG_TRD60Q_1c", ep._sleeve("AG_TRD60Q_1c", ep._AG_TRD60Q, 1), B60, 60, True),
      ("AG_TRD30PM_1c", ep._sleeve("AG_TRD30PM_1c", ep._AG_TRD30PM, 1), B30, 30, False), ("AG_MES_TRD30_1c", ep._sleeve("AG_MES_TRD30_1c", ep._AG_MES_TRD30, 1), E30, 30, False)]
def run(filtered):
    allt = []
    for prio, (name, cfg, b, mins, morning) in enumerate(SL):
        r = ep.run_sleeve(cfg, b, START, backw_mask(b) if (filtered and morning) else None)
        for t in r["trades"]:
            t["sleeve"] = name; t["prio"] = prio; t["dec"] = pd.Timestamp(t["entry_ts"]) - pd.Timedelta(minutes=mins); t["day"] = t["dec"].tz_convert("America/New_York").date(); t["exit_day"] = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
        allt += r["trades"]
    allt.sort(key=lambda x: (x["dec"], x["prio"])); acc = []
    for x in allt:
        if any(pd.Timestamp(a["entry_ts"]) <= x["dec"] < pd.Timestamp(a["exit_ts"]) for a in acc[-5:]): continue
        acc.append(x)
    return acc
def summary(tr):
    t = pd.DataFrame(tr); daily = t.groupby("exit_day").net.sum().sort_index(); yr = t.groupby(pd.to_datetime(t.entry_ts).dt.year).net.sum(); eq = daily.cumsum()
    return dict(net=round(float(t.net.sum()), 2), trades=int(len(t)), per_trade=round(float(t.net.mean()), 2), pos_years=int((yr > 0).sum()), pre2020=round(float(yr[yr.index < 2020].sum()), 2),
                max_year_share=round(float(yr.max() / t.net.sum()), 3) if t.net.sum() > 0 else None, closed_dd=round(float((eq.cummax() - eq).max()), 2), by_sleeve={k: round(float(v), 2) for k, v in t.groupby("sleeve").net.sum().items()}, by_year={int(y): round(float(v), 2) for y, v in yr.items()})
ch_tr = run(False); ch = summary(ch_tr); v_tr = run(True); v = summary(v_tr)
days_all = sorted(set(x["day"] for x in ch_tr)); net_by_day = pd.Series([x["net"] for x in ch_tr], index=[x["day"] for x in ch_tr]).groupby(level=0).sum()
kept = set(x["day"] for x in v_tr); removed = [d for d in days_all if d not in kept]; removed_net = float(net_by_day.reindex(removed).fillna(0).sum())
plc = [float(net_by_day.loc[rng.choice(days_all, size=len(removed), replace=False)].sum()) for _ in range(20)] if removed else [0.0]
v.update(removed_days=len(removed), removed_net=round(removed_net, 2), removed_p5=round(float(np.percentile(plc, 5)), 2))
v["pass"] = bool(v["net"] > ch["net"] and v["closed_dd"] <= ch["closed_dd"] and v["pos_years"] >= ch["pos_years"] and removed_net < np.percentile(plc, 5))
out = {"champion": ch, "V1_morning_skip_backwardation": v}
for k, r in out.items(): print(k, {a: b for a, b in r.items() if a != "by_year"}, flush=True)
json.dump(out, open(ROOT / "reports/QUAD_2_TRAINING.json", "w"), indent=1, default=str); print("DONE")
