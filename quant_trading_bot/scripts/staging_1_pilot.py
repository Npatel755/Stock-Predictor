"""staging_1 (research/staging_1/PROTOCOL.md): funded trailing-floor staging policy over frozen legs, training 2010-23 only."""
import json, os, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import mass_1m_search as m1
NY = "America/New_York"; END = pd.Timestamp("2024-01-01", tz=NY)
# --- SKEW state (sizing_3 definition)
sk = pd.read_csv(ROOT / "data/external/SKEW_History.csv"); sk["DATE"] = pd.to_datetime(sk.DATE); sk = sk.set_index("DATE").SKEW.sort_index(); sk = sk[sk.index < "2024-01-01"]
below = ((sk - sk.rolling(20).mean()) < 0)
def skew_below(ts):
    d = pd.Timestamp(ts).tz_convert(NY).tz_localize(None).normalize(); i = below.index.searchsorted(d, side="left") - 1
    return bool(below.iloc[i]) if i >= 0 else False
# --- L1 overnight v2 (book_1 construction: worst = min(night low, 09:30-09:45 low))
src3 = (ROOT / "scripts/overnight_3_pilot.py").read_text().split("out = {")[0]; n3 = {"__file__": str(ROOT / "scripts/overnight_3_pilot.py")}; exec(src3, n3)
mn, ms = n3["nights"]("MNQ"), n3["nights"]("MES"); mg, msd = ms.gap.reindex(mn.index), ms.sd20.reindex(mn.index)
mask = ((mn.gap <= -0.5 * mn.sd20) & (mg <= -0.5 * msd)).fillna(False); p_on = n3["pnl"](mn, "MNQ", ex="x0945"); p_on = p_on[mask & p_on.notna()]
b = m1.load_bars("MNQ", 1, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "low"]]; et = b.timestamp_utc.dt.tz_convert(NY)
b["date"] = et.dt.date; b["sod"] = et.dt.hour * 60 + et.dt.minute; low_open = b[(b.sod >= 570) & (b.sod < 585)].groupby("date").low.min()
dates = np.array(sorted(set(mn.index) | set(low_open.index)))
def next_day(d):
    i = dates.searchsorted(d, side="right"); return dates[i] if i < len(dates) else None
trades = []  # dict(leg, t_in, t_out, worst, net)
for nk, p in p_on.items():
    ex_day = next_day(nk); e = float(mn.at[nk, "e1805"]); lo = min(float(mn.at[nk, "low_night"]), float(low_open.get(ex_day, np.inf)))
    trades.append(dict(leg="L1", t_in=pd.Timestamp(f"{nk} 18:05", tz=NY), t_out=pd.Timestamp(f"{ex_day} 09:45", tz=NY), worst=(lo - e) * 2.0 - 3.0, net=float(p)))
# --- L2 All-Weather 1c (always one contract, as deployed)
os.environ["SIZING_BUDGET"] = "1e9"
srcs = (ROOT / "scripts/sizing_1_pilot.py").read_text().split("\nfor key in (")[0]; ns1 = {"__file__": str(ROOT / "scripts/sizing_1_pilot.py")}; exec(srcs, ns1)
for t in ns1["run_candidate"]("ag_all_weather_v2", True):
    trades.append(dict(leg="L2", t_in=pd.Timestamp(t["entry_ts"]).tz_convert(NY), t_out=pd.Timestamp(t["exit_ts"]).tz_convert(NY), worst=-float(t["stop_risk"]), net=float(t["net"])))
# --- L3 D+ v2 ($150 budget: dplus pilot calls run_sleeve directly -> default budget, matches the reported +17,576)
srcd = (ROOT / "scripts/dplus_1_pilot.py").read_text().split("\nout = {}")[0]; nd = {"__file__": str(ROOT / "scripts/dplus_1_pilot.py")}; exec(srcd, nd)
import quant_futures.ensemble_paper as ep
sls = ep.CANDIDATES["ag_arch_d_plus_v2"]["sleeves"]
for t in nd["route"](sum((nd["run_sl"](sl, i) for i, sl in enumerate(sls)), [])):
    trades.append(dict(leg="L3", t_in=pd.Timestamp(t["entry_ts"]).tz_convert(NY), t_out=pd.Timestamp(t["exit_ts"]).tz_convert(NY), worst=-float(t["stop_risk"]), net=float(t["net"])))
trades = [t for t in trades if t["t_out"] < END]; trades.sort(key=lambda t: t["t_in"])
for i, t in enumerate(trades): t["id"] = i; t["day"] = t["t_in"].date(); t["skew"] = skew_below(t["t_in"])
print({l: (sum(1 for t in trades if t["leg"] == l), round(sum(t["net"] for t in trades if t["leg"] == l), 2)) for l in ("L1", "L2", "L3")}, flush=True)
# --- policy engine
FLOOR, LOCK_AT, LOCK_FLOOR = 2000.0, 2100.0, 100.0
BOOK = {"L1": 1, "L2": 1}; SKEWBOOK = "skew"
def config(policy, locked, cushion):
    pre = policy["pre"]
    if not policy.get("staged"): return pre
    if not locked or cushion < 500: return pre
    if cushion < 1500: return BOOK
    if cushion < 3000: return SKEWBOOK
    return "skew+L3"
def mult(cfg, t):
    if cfg == SKEWBOOK: return (2 if t["skew"] else 1) if t["leg"] in ("L1", "L2") else 0
    if cfg == "skew+L3": return ((2 if t["skew"] else 1) if t["leg"] in ("L1", "L2") else 1)
    return cfg.get(t["leg"], 0)
def run(policy, tr, variant="A", horizon_end=None, restart=False):
    """events in time order; returns dict(breached, when, closed, lock_at, months_to_lock, n_breach)."""
    ev = []
    for t in tr: ev.append((t["t_in"], 0, t)); ev.append((t["t_out"], 1, t))
    ev.sort(key=lambda x: (x[0], x[1]))
    closed = 0.0; hwm = 0.0; locked = False; floor = -FLOOR; open_ = {}; breached = None; n_breach = 0; lock_ts = None
    for ts, kind, t in ev:
        if horizon_end is not None and ts >= horizon_end: break
        if kind == 0:
            floor_now = floor; cushion = closed - floor_now
            m = mult(config(policy, locked, cushion), t)
            if m: open_[t["id"]] = m
            if variant == "A" and open_:
                eq = closed + sum(trades[i]["worst"] * q for i, q in open_.items())
                if eq <= floor:
                    n_breach += 1; breached = breached or str(ts)
                    if not restart: break
                    closed = 0.0; hwm = 0.0; locked = False; floor = -FLOOR; open_ = {}
        else:
            m = open_.pop(t["id"], 0)
            if not m: continue
            closed += t["net"] * m; hwm = max(hwm, closed)
            if not locked and hwm >= LOCK_AT: locked = True; floor = LOCK_FLOOR; lock_ts = lock_ts or ts
            if not locked: floor = hwm - FLOOR
            if closed <= floor:
                n_breach += 1; breached = breached or str(ts)
                if not restart: break
                closed = 0.0; hwm = 0.0; locked = False; floor = -FLOOR; open_ = {}
    return dict(breached=breached, closed=round(closed, 2), lock_ts=str(lock_ts) if lock_ts else None, n_breach=n_breach)
POL = {"S_A": dict(pre=BOOK), "S_1": dict(pre={"L1": 1}), "S_2": dict(pre={"L2": 1}), "S_3": dict(pre={"L3": 1}),
       "P_L1": dict(pre={"L1": 1}, staged=True), "P_L2": dict(pre={"L2": 1}, staged=True), "P_L3": dict(pre={"L3": 1}, staged=True), "P_BookA": dict(pre=BOOK, staged=True)}
starts = pd.date_range("2010-01-01", "2023-01-01", freq="MS", tz=NY)
out = {}
for name, pol in POL.items():
    res = {}
    for variant in ("A", "B"):
        rows = []
        for s0 in starts:
            e0 = s0 + pd.DateOffset(months=12); tr = [t for t in trades if s0 <= t["t_in"] < e0]
            r = run(pol, tr, variant, horizon_end=e0); rows.append(dict(start=str(s0.date()), **r))
        df = pd.DataFrame(rows); surv = df.breached.isna()
        mtl = pd.to_datetime(df.lock_ts.dropna(), utc=True); months_to_lock = ((mtl.dt.tz_convert(NY).dt.tz_localize(None) - pd.to_datetime(df.loc[df.lock_ts.notna(), "start"])).dt.days / 30.4)
        res[variant] = dict(n_starts=len(df), survival=round(float(surv.mean()), 3), median_net_12m=round(float(df.closed[surv].median()), 2) if surv.any() else None,
                            p10_net_12m=round(float(df.closed[surv].quantile(0.1)), 2) if surv.any() else None, locked_share=round(float(df.lock_ts.notna().mean()), 3),
                            median_months_to_lock=round(float(months_to_lock.median()), 1) if len(months_to_lock) else None,
                            breach_starts=[r["start"] for r in rows if r["breached"]][:30])
        full = run(pol, trades, variant, restart=True); res[variant]["full_path_2010_23"] = dict(closed=full["closed"], n_breach=full["n_breach"], first_breach=full["breached"])
    out[name] = res; print(name, {v: {k: res[v][k] for k in ("survival", "median_net_12m", "p10_net_12m", "locked_share", "median_months_to_lock")} for v in res}, res["A"]["full_path_2010_23"], flush=True)
# --- block bootstrap (20 trade-day blocks, 1y = 252 days, 2000 paths), variant A and B
rng = np.random.default_rng(7); days = sorted(set(t["day"] for t in trades)); by_day = {}
for t in trades: by_day.setdefault(t["day"], []).append(t)
def synth_path():
    seq = []; n = 0
    while n < 252:
        i = rng.integers(0, len(days) - 20); seq.extend(days[i:i + 20]); n += 20
    base = pd.Timestamp("2030-01-04", tz=NY); outt = []; k = 0
    for d in seq[:252]:
        off = base + pd.Timedelta(days=k); k += 1
        for t in by_day.get(d, []):
            dur = t["t_out"] - t["t_in"]; tin = off + (t["t_in"] - pd.Timestamp(t["t_in"].date(), tz=NY))
            outt.append(dict(t, t_in=tin, t_out=tin + dur))
    return outt
boot = {n: {"A": 0, "B": 0} for n in POL}; NB = 2000
for p in range(NB):
    sp = synth_path()
    for n, pol in POL.items():
        for v in ("A", "B"):
            if run(pol, sp, v)["breached"]: boot[n][v] += 1
for n in POL: out[n]["bootstrap_breach_1y"] = {v: round(boot[n][v] / NB, 3) for v in ("A", "B")}
print({n: out[n]["bootstrap_breach_1y"] for n in POL}, flush=True)
json.dump(out, open(ROOT / "reports/STAGING_1_TRAINING.json", "w"), indent=1, default=str); print("DONE")
