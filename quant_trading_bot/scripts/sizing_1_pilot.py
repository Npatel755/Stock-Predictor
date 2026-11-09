"""sizing_1 (research/sizing_1/PROTOCOL.md): $150 stop-risk budget (V0, as deployed) vs always-one-contract (V1) for the three filtered
intraday paper candidates. Training 2010-2023 only; engine defaults; no 2024-26 data loaded."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import mass_1m_search as m1
from quant_futures import ensemble_paper as ep
rng = np.random.default_rng(151); START = "2010-01-01T00:00:00Z"
def cboe(n):
    d = pd.read_csv(ROOT / f"data/external/{n}_History.csv"); d["date"] = pd.to_datetime(d.DATE, format="%m/%d/%Y").dt.date; return d.set_index("date").CLOSE.astype(float)
RATIO = (cboe("VIX") / cboe("VIX3M")).dropna(); rdates = np.array(sorted(RATIO.index)); rvals = (RATIO.reindex(rdates).to_numpy() > 1.0)
def backw_mask(bars):
    days = bars.timestamp_utc.dt.tz_convert("America/New_York").dt.date.to_numpy(); pos = rdates.searchsorted(days) - 1
    return np.where(pos >= 0, rvals[np.clip(pos, 0, len(rvals) - 1)], False)
eng = ep.engine(); _orig_cfg = eng["execution_cfg"]; UNCAP = {"on": False}
def _cfg(c):
    d = _orig_cfg(c)
    if UNCAP["on"]: d.update(risk_per_trade=1e9, max_open_risk=1e9)
    return d
eng["execution_cfg"] = _cfg
BARS = {}
def bars_for(sl):
    k = ep.bars_key(sl); mins = int(sl.get("bar_minutes", ep.BAR_MINUTES))
    if k not in BARS:
        b = m1.load_bars(sl["instrument"], mins, "2009-11-01", "2024-01-01", "train").reset_index(drop=True)
        assert b.timestamp_utc.max() < pd.Timestamp("2024-01-01", tz="UTC")
        c, h, l = b.close.astype(float), b.high.astype(float), b.low.astype(float); prev = c.shift(1)
        atr = pd.concat((h - l, (h - prev).abs(), (l - prev).abs()), axis=1).max(axis=1).rolling(14, min_periods=14).mean()
        BARS[k] = (b, mins, pd.Series(atr.to_numpy(), index=pd.DatetimeIndex(b.timestamp_utc)))
    return BARS[k]
MULT = {"MNQ": 2.0, "MES": 5.0}
def run_candidate(key, uncapped):
    spec = ep.CANDIDATES[key]; UNCAP["on"] = uncapped; allt = []
    for prio, sl in enumerate(spec["sleeves"]):
        b, mins, atr = bars_for(sl)
        blocked = backw_mask(b) if (spec.get("day_filter") == "no_backwardation" and not sl.get("day_filter_exempt")) else None
        r = ep.run_sleeve(sl, b, START, blocked)
        for t in r["trades"]:
            t["prio"] = prio; t["dec"] = pd.Timestamp(t["entry_ts"]) - pd.Timedelta(minutes=mins)
            t["day"] = t["dec"].tz_convert("America/New_York").date(); t["exit_day"] = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
            a = float(atr.get(t["dec"], np.nan)); t["stop_risk"] = round(float(sl["stop_atr"]) * a * MULT[sl["instrument"]] + 1.0 + 3 * 0.25 * MULT[sl["instrument"]], 2)
        allt += r["trades"]
    UNCAP["on"] = False
    allt.sort(key=lambda x: (x["dec"], x["prio"]))
    if spec.get("router") != "strict_1c": return allt
    acc = []
    for x in allt:
        if any(pd.Timestamp(a["entry_ts"]) <= x["dec"] < pd.Timestamp(a["exit_ts"]) for a in acc[-5:]): continue
        acc.append(x)
    return acc
def daily(tr): return pd.Series([x["net"] for x in tr], index=[x["exit_day"] for x in tr]).groupby(level=0).sum().sort_index()
def breach(d, paths=2000):
    x = d.to_numpy(); n = len(x); per_year = int(n / 14); br = 0
    for _ in range(paths):
        idx = []
        while len(idx) < per_year:
            st = rng.integers(n); ln = rng.geometric(1 / 20); idx.extend(((st + np.arange(ln)) % n).tolist())
        e = np.cumsum(x[np.array(idx[:per_year])]); pk = np.maximum.accumulate(np.concatenate([[0], e]))[:-1]; br += int((pk - e).max() >= 2000)
    return round(br / paths, 3)
def summary(tr):
    t = pd.DataFrame(tr); d = daily(tr); yr = t.groupby(pd.to_datetime(t.entry_ts, utc=True).dt.year).net.sum(); eq = d.cumsum()
    return dict(net=round(float(t.net.sum()), 2), trades=int(len(t)), per_trade=round(float(t.net.mean()), 2), pos_years=int((yr > 0).sum()),
                pre2020=round(float(yr[yr.index < 2020].sum()), 2), max_year_share=round(float(yr.max() / t.net.sum()), 3) if t.net.sum() > 0 else None,
                closed_dd=round(float((eq.cummax() - eq).max()), 2), p_dd2k_1y=breach(d), by_sleeve={k: round(float(v), 2) for k, v in t.groupby("sleeve").net.sum().items()},
                by_year={int(y): round(float(v), 2) for y, v in yr.items()})
out = {}
for key in ("ag_quad_v2", "ag_arch_c_v2", "ag_all_weather_v2"):
    t0 = run_candidate(key, False); t1 = run_candidate(key, True); s0, s1 = summary(t0), summary(t1)
    k0 = set((x["sleeve"], x["entry_ts"]) for x in t0); added = [x for x in t1 if (x["sleeve"], x["entry_ts"]) not in k0]; dropped = len(k0 - set((x["sleeve"], x["entry_ts"]) for x in t1))
    a = pd.DataFrame(added) if added else pd.DataFrame(columns=["net", "stop_risk"])
    nets1 = np.array([x["net"] for x in t1]); plc_tr = [float(rng.choice(nets1, size=len(added), replace=False).sum()) for _ in range(20)] if added else [0.0]
    d1 = daily(t1); add_days = sorted(set(x["exit_day"] for x in added)); plc_day = [float(d1.sample(len(add_days), random_state=int(rng.integers(1e9))).sum()) for _ in range(20)] if add_days else [0.0]
    eq1 = d1.cumsum(); ddser = eq1.cummax() - eq1; dd_days = set(ddser[ddser >= 0.5 * ddser.max()].index)
    t1df = pd.DataFrame(t1); t1df["bucket"] = pd.cut(t1df.stop_risk, [0, 150, 250, 400, 1e9], labels=["<150", "150-250", "250-400", ">400"])
    buckets = {str(k): dict(n=int(len(g)), per_trade=round(float(g.net.mean()), 2) if len(g) else None, win=round(float((g.net > 0).mean()), 3) if len(g) else None, net=round(float(g.net.sum()), 2)) for k, g in t1df.groupby("bucket", observed=False)}
    added_info = dict(n=len(added), net=round(float(a.net.sum()), 2), per_trade=round(float(a.net.mean()), 2) if len(a) else None, worst=round(float(a.net.min()), 2) if len(a) else None,
                      dropped_from_v0=dropped, placebo_trades_p50=round(float(np.median(plc_tr)), 2), placebo_trades_p5=round(float(np.percentile(plc_tr, 5)), 2),
                      placebo_days_p50=round(float(np.median(plc_day)), 2), share_dd_days_with_added=round(float(np.mean([d in dd_days for d in add_days])), 3) if add_days else None)
    s1["pass"] = bool(s1["net"] > s0["net"] and s1["closed_dd"] <= 2000 and s1["pos_years"] >= s0["pos_years"] and added_info["net"] > 0 and added_info["net"] >= added_info["placebo_trades_p50"])
    out[key] = dict(V0_budget150=s0, V1_one_contract=s1, added=added_info, stop_risk_buckets=buckets)
    print(key, "\n V0", {k: v for k, v in s0.items() if k != "by_year"}, "\n V1", {k: v for k, v in s1.items() if k != "by_year"}, "\n added", added_info, "\n buckets", buckets, flush=True)
json.dump(out, open(ROOT / "reports/SIZING_1_TRAINING.json", "w"), indent=1, default=str); print("DONE")
