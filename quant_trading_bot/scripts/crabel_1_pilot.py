"""crabel_1 (research/crabel_1/PROTOCOL.md): Crabel on MES + backwardation attribution per sleeve. Training 2010-2023 only."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
srcc = (ROOT / "scripts/replicate_antigravity_arch_c.py").read_text().split("B15 = m1.load_bars")[0]; ns = {"__file__": str(ROOT / "scripts/replicate_antigravity_arch_c.py")}; exec(srcc, ns)
ep, m1, START, crabel_signal, trend_signal = ns["ep"], ns["m1"], ns["START"], ns["crabel_signal"], ns["trend_signal"]
rng = np.random.default_rng(113)
def cboe(n):
    d = pd.read_csv(ROOT / f"data/external/{n}_History.csv"); d["date"] = pd.to_datetime(d.DATE, format="%m/%d/%Y").dt.date; return d.set_index("date").CLOSE.astype(float)
RATIO = (cboe("VIX") / cboe("VIX3M")).dropna(); rdates = np.array(sorted(RATIO.index))
def prior_backw(d):
    i = rdates.searchsorted(d); return bool(RATIO[rdates[i - 1]] > 1.0) if i > 0 else False
def yearly(tr):
    t = pd.DataFrame(tr); t["year"] = pd.to_datetime(t.entry_ts).dt.year; return t.groupby("year").net.sum()
def summarize(tr, label):
    if not tr: return {"net": 0, "trades": 0}
    yr = yearly(tr); t = pd.DataFrame(tr); t["day"] = pd.to_datetime(t.entry_ts).dt.tz_convert("America/New_York").dt.date; t["backw"] = t.day.map(prior_backw)
    g = t.groupby("backw").net.agg(["sum", "mean", "count"])
    return dict(net=round(float(t.net.sum()), 2), trades=int(len(t)), pos_years=int((yr > 0).sum()), max_year_share=round(float(yr.max() / t.net.sum()), 3) if t.net.sum() > 0 else None,
                backw={str(k): dict(total=round(float(v["sum"]), 2), per_trade=round(float(v["mean"]), 2), n=int(v["count"])) for k, v in g.iterrows()}, by_year={int(y): round(float(v), 2) for y, v in yr.items()})
out = {}
# Q1: Crabel on MES
B15_MES = m1.load_bars("MES", 15, "2009-11-01", "2024-01-01", "train").reset_index(drop=True)
cfg = dict(name="CRABEL_MES", instrument="MES", family="trend", lookback=8, threshold=0.0, stop_atr=2.0, target_r=4.0, hold_bars=12, trailing_atr=0.0, max_contracts=1,
           session_start=600, session_end=945, signal="crabel", entry_start=585, entry_end=585, max_gap_minutes=20)
r = ep.run_sleeve(cfg, B15_MES, START); tr = r["trades"]; q1 = summarize(tr, "crabel_mes")
# placebo: same number of long/short signals per year on random days, same exits
sig, atr = crabel_signal(cfg, B15_MES); et = B15_MES.timestamp_utc.dt.tz_convert("America/New_York"); sod = (et.dt.hour * 60 + et.dt.minute).to_numpy(); yrs = et.dt.year.to_numpy()
idx585 = np.flatnonzero(sod == 585); plc = []
for _ in range(20):
    s2 = np.zeros(len(sig), np.int8)
    for y in np.unique(yrs):
        pool = idx585[yrs[idx585] == y]; real = sig[pool]; n_long, n_short = int((real == 1).sum()), int((real == -1).sum())
        pick = rng.choice(pool, size=min(len(pool), n_long + n_short), replace=False); s2[pick[:n_long]] = 1; s2[pick[n_long:]] = -1
    ep.custom_signal = lambda c, b, s2=s2, atr=atr: (s2, atr)
    plc.append(float(sum(x["net"] for x in ep.run_sleeve(cfg, B15_MES, START)["trades"])))
ep.custom_signal = ns["dispatch"]
q1.update(placebo_beat=int(sum(q1["net"] > p for p in plc)), placebo_mean=round(float(np.mean(plc)), 2))
q1["pass"] = bool(q1["net"] > 0 and q1["pos_years"] >= 10 and (q1["max_year_share"] or 1) <= 0.4 and q1["placebo_beat"] >= 19); out["Q1_crabel_mes"] = q1; print("Q1", {k: v for k, v in q1.items() if k != "by_year"}, flush=True)
# Q2: attribution per sleeve on MNQ
B15, B30, B60 = (m1.load_bars("MNQ", m, "2009-11-01", "2024-01-01", "train").reset_index(drop=True) for m in (15, 30, 60))
import importlib; _orig_custom = importlib.reload(ep).custom_signal
ep.custom_signal = lambda c, b: crabel_signal(c, b) if c.get("signal") == "crabel" else (trend_signal(c, b) if c.get("signal") == "trend" else _orig_custom(c, b))
S1 = dict(name="S1_crabel", instrument="MNQ", family="trend", lookback=8, threshold=0.0, stop_atr=2.0, target_r=4.0, hold_bars=12, trailing_atr=0.0, max_contracts=1, session_start=600, session_end=945, signal="crabel", entry_start=585, entry_end=585, max_gap_minutes=20)
S2 = dict(name="S2_trend30", instrument="MNQ", family="trend", lookback=16, threshold=0.75, stop_atr=1.5, target_r=3.5, hold_bars=8, trailing_atr=0.0, max_contracts=1, session_start=585, session_end=720, signal="trend", entry_start=555, entry_end=690, max_gap_minutes=60)
S3 = dict(name="S3_trend60", instrument="MNQ", family="trend", lookback=12, threshold=0.75, stop_atr=1.25, target_r=4.0, hold_bars=8, trailing_atr=0.0, max_contracts=1, session_start=600, session_end=720, signal="trend", entry_start=540, entry_end=660, max_gap_minutes=90)
sleeves = {"archc_crabel": (S1, B15), "archc_trend30_lb16": (S2, B30), "archc_trend60_lb12": (S3, B60),
           "quad_morn30_lb16": (ep._sleeve("AG_MORN30_1c", ep._AG_MORN30, 1), B30), "quad_trend60": (ep._sleeve("AG_TRD60Q_1c", ep._AG_TRD60Q, 1), B60),
           "quad_pm30_lb8": (ep._sleeve("AG_TRD30PM_1c", ep._AG_TRD30PM, 1), B30), "allweather_brk30": (ep._sleeve("AG_BRK30_1c", ep._AG_BRK30, 1), B30)}
out["Q2_attribution"] = {}
for name, (c, b) in sleeves.items():
    try:
        s = summarize(ep.run_sleeve(c, b, START)["trades"], name); out["Q2_attribution"][name] = s; print(name, {k: v for k, v in s.items() if k != "by_year"}, flush=True)
    except Exception as e:
        out["Q2_attribution"][name] = {"error": str(e)}; print(name, "error", e, flush=True)
json.dump(out, open(ROOT / "reports/CRABEL_1_TRAINING.json", "w"), indent=1, default=str); print("DONE")
