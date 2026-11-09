"""archc_1 (research/archc_1/PROTOCOL.md): improvement variants of Architecture C, training 2010-2023 only. Reuses the replication's sleeves/router."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
src = (ROOT / "scripts/replicate_antigravity_arch_c.py").read_text().split("out = {}; all_tr = []")[0]
ns = {"__file__": str(ROOT / "scripts/replicate_antigravity_arch_c.py")}; exec(src, ns)
ep, S, summary, START, m1 = ns["ep"], ns["S"], ns["summary"], ns["START"], ns["m1"]
B15, B30, B60 = ns["B15"], ns["B30"], ns["B60"]
crabel_signal = ns["crabel_signal"]; trend_signal = ns["trend_signal"]
rng = np.random.default_rng(71)
_eng = ep.engine(); _orig_cfg = _eng["execution_cfg"]
def _cfg_micro(c, factor=1):
    d = _orig_cfg(c, factor); d.update(commission_per_side=0.61, spread_ticks=1.75, slippage_ticks=1); return d
_eng["execution_cfg"] = _cfg_micro; ep.engine = lambda: _eng  # stated micro costs for champion and every variant alike
def cboe(n):
    d = pd.read_csv(ROOT / f"data/external/{n}_History.csv"); d["date"] = pd.to_datetime(d.DATE, format="%m/%d/%Y").dt.date; return d.set_index("date").CLOSE.astype(float)
VIX = cboe("VIX"); RATIO = (VIX / cboe("VIX3M")).dropna()
# point-in-time 20-day realized vol of NQ (daily closes from 60m bars) vs trailing 1-yr median
et60 = B60.timestamp_utc.dt.tz_convert("America/New_York"); dclose = B60.groupby(et60.dt.date).close.last(); rv = np.log(dclose).diff().rolling(20).std() * np.sqrt(252)
RV_HIGH = (rv >= rv.rolling(252, min_periods=120).median()).shift(1)  # known before the day starts
def day_filter(kind):
    if kind == "D1": return lambda d: VIX.get(d, np.nan) >= 15
    if kind == "D2": return lambda d: RATIO.get(d, np.nan) >= 0.9
    if kind == "D3": return lambda d: bool(RV_HIGH.get(d, False))
    return None
def prev_day(d, cal):  # value known at the open = prior trading day's close
    i = cal.searchsorted(d); return cal[i - 1] if i > 0 else None
CAL = np.array(sorted(set(et60.dt.date)))
def run_variant(name, sleeves, crabel_tail=0.2, crabel_range_atr=None, crabel_long_only=False, dfilter=None, size_fn=None):
    all_tr = []
    for prio, (sname, (cfg, bars, mins)) in enumerate(sleeves):
        cfg = dict(cfg)
        if sname == "S1_crabel":
            cfg["tail"] = crabel_tail; cfg["range_atr"] = crabel_range_atr; cfg["long_only"] = crabel_long_only
        r = ep.run_sleeve(cfg, bars, START); tr = r["trades"]
        for x in tr: x["sleeve"] = sname; x["prio"] = prio; x["dec"] = pd.Timestamp(x["entry_ts"]) - pd.Timedelta(minutes=mins); x["day"] = x["dec"].tz_convert("America/New_York").date()
        all_tr += tr
    if dfilter is not None:
        all_tr = [x for x in all_tr if (pd_ := prev_day(x["day"], CAL)) is not None and dfilter(pd_)]
    all_tr.sort(key=lambda x: (x["dec"], x["prio"])); acc = []
    for x in all_tr:
        if any(pd.Timestamp(a["entry_ts"]) <= x["dec"] < pd.Timestamp(a["exit_ts"]) for a in acc[-5:]): continue
        acc.append(x)
    if size_fn is not None:
        for x in acc: x["net"] = x["net"] * size_fn(prev_day(x["day"], CAL))
    return acc
# patch crabel signal to honour tail / range filter / long-only
def crabel2(cfg, bars):
    sig, atr = crabel_signal(dict(cfg), bars)
    et = bars.timestamp_utc.dt.tz_convert("America/New_York"); sod = (et.dt.hour * 60 + et.dt.minute).to_numpy(); day = et.dt.date.to_numpy()
    tail = cfg.get("tail", 0.2)
    if tail != 0.2 or cfg.get("range_atr") or cfg.get("long_only"):
        o, h, l, c = (bars[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
        df = pd.DataFrame(dict(day=day, sod=sod, o=o, h=h, l=l, c=c, atr=atr)); r = df[df.sod.isin([570, 585])].groupby("day")
        o930 = df[df.sod == 570].groupby("day").o.first(); c1000 = df[df.sod == 585].groupby("day").c.first(); hi, lo = r.h.max(), r.l.min()
        rng_ = (hi - lo); op = (o930 - lo) / rng_.replace(0, np.nan); cp = (c1000 - lo) / rng_.replace(0, np.nan)
        bull = (op <= tail) & (cp >= 1 - tail); bear = (op >= 1 - tail) & (cp <= tail)
        if cfg.get("range_atr"): a585 = df[df.sod == 585].groupby("day").atr.first(); ok = rng_ >= cfg["range_atr"] * a585; bull &= ok; bear &= ok
        if cfg.get("long_only"): bear &= False
        sig_day = pd.Series(np.where(bull, 1, np.where(bear, -1, 0)), index=op.index); sig = np.where(sod == 585, pd.Series(day).map(sig_day).fillna(0).to_numpy(), 0).astype(np.int8)
    return sig, atr
ep.custom_signal = lambda cfg, bars: crabel2(cfg, bars) if cfg["signal"] == "crabel" else trend_signal(cfg, bars)
def with_exits(sleeves, hold_mult=None, target=None, trailing=None):
    out = []
    for sname, (cfg, bars, mins) in sleeves:
        c = dict(cfg)
        if hold_mult: c["hold_bars"] = int(round(c["hold_bars"] * hold_mult))
        if target: c["target_r"] = target
        if trailing: c["trailing_atr"] = trailing
        out.append((sname, (c, bars, mins)))
    return out
base = list(S.items()); CH = {}
def gate(r, placebo_ok=True): return bool(r["net"] > CH["net"] and r["pos_years"] >= 11 and (r["max_year_share"] or 1) <= 0.4 and r["closed_dd"] <= 1800 and r["pre2020"] > CH["pre2020"] and r["trades"] >= 500 and placebo_ok)
out = {}
def rec(name, acc, placebo=None):
    r = summary(acc); r["placebo"] = placebo; r["pass"] = gate(r, placebo is None or placebo["beat"] >= 19); out[name] = r
    print(name, {k: v for k, v in r.items() if k != "by_year"}, flush=True)
acc0 = run_variant("champion", base); r0 = summary(acc0); CH.update(net=r0["net"], max_dd=r0["closed_dd"], pre2020=r0["pre2020"]); rec("CH_champion", acc0); out["CH_champion"]["pass"] = False
rec("A1_drop_S1", run_variant("A1", [s for s in base if s[0] != "S1_crabel"]))
rec("A2_drop_S2", run_variant("A2", [s for s in base if s[0] != "S2_trend30"]))
rec("A3_drop_S3", run_variant("A3", [s for s in base if s[0] != "S3_trend60"]))
rec("A4_trend_first", run_variant("A4", [base[1], base[2], base[0]]))
rec("B1_tails_0.15", run_variant("B1", base, crabel_tail=0.15)); rec("B2_tails_0.25", run_variant("B2", base, crabel_tail=0.25))
rec("B3_range_ge_1atr", run_variant("B3", base, crabel_range_atr=1.0)); rec("B4_crabel_long_only", run_variant("B4", base, crabel_long_only=True))
b5 = [(n, (dict(c, stop_atr=1.5, hold_bars=20) if n == "S1_crabel" else c, b, m)) for n, (c, b, m) in base]; rec("B5_crabel_stop1.5_hold20", run_variant("B5", b5))
rec("C1_hold_x1.5", run_variant("C1", with_exits(base, hold_mult=1.5))); rec("C2_target_3R", run_variant("C2", with_exits(base, target=3.0))); rec("C3_trailing_2atr", run_variant("C3", with_exits(base, trailing=2.0)))
# state filters with same-count random-day placebos
days_all = sorted(set(x["day"] for x in acc0))
for kind in ("D1", "D2", "D3"):
    acc = run_variant(kind, base, dfilter=day_filter(kind)); kept = set(x["day"] for x in acc); t = sum(x["net"] for x in acc)
    by_year = pd.Series([x["day"].year for x in acc]).value_counts().to_dict(); plc = []
    for _ in range(20):
        pick = set()
        for y, k in by_year.items():
            pool = [d for d in days_all if d.year == y]; pick |= set(rng.choice(pool, size=min(k, len(pool)), replace=False))
        plc.append(sum(x["net"] for x in acc0 if x["day"] in pick))
    rec(f"{kind}_state", acc, dict(beat=int(sum(t > p for p in plc)), mean=round(float(np.mean(plc)), 2), days=len(kept)))
rec("E1_size2_vix25", run_variant("E1", base, size_fn=lambda d: 2 if (d is not None and VIX.get(d, 0) >= 25) else 1)); out["E1_size2_vix25"]["pass"] = out["E1_size2_vix25"]["pass"] and out["E1_size2_vix25"]["closed_dd"] <= 1800
out["passers"] = [k for k, v in out.items() if isinstance(v, dict) and v.get("pass")]; print("PASSERS", out["passers"], flush=True)
json.dump(out, open(ROOT / "reports/ARCHC_1_TRAINING.json", "w"), indent=1, default=str); print("DONE")
