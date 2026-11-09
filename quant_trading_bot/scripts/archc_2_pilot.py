"""archc_2 (research/archc_2/PROTOCOL.md): stress-day exclusion for Architecture C + combination with overnight_dip_v2. Training 2010-2023 only."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
src1 = (ROOT / "scripts/archc_1_pilot.py").read_text().split("base = list(S.items())")[0]; ns = {"__file__": str(ROOT / "scripts/archc_1_pilot.py")}
src1 = src1.replace('_eng["execution_cfg"] = _cfg_micro; ep.engine = lambda: _eng', 'pass')  # engine default costs, like portfolio_1
exec(src1, ns)
run_variant, summary, S, VIX, RATIO, prev_day, CAL = ns["run_variant"], ns["summary"], ns["S"], ns["VIX"], ns["RATIO"], ns["prev_day"], ns["CAL"]
rng = np.random.default_rng(101); base = list(S.items())
acc0 = run_variant("champion", base); ch = summary(acc0); out = {"champion": ch}; print("champion", {k: v for k, v in ch.items() if k != "by_year"}, flush=True)
days_all = sorted(set(x["day"] for x in acc0)); net_by_day = pd.Series([x["net"] for x in acc0], index=[x["day"] for x in acc0]).groupby(level=0).sum()
filters = {"V1_skip_vix25": lambda d: not (VIX.get(d, 0) >= 25), "V2_skip_vix30": lambda d: not (VIX.get(d, 0) >= 30), "V3_skip_backwardation": lambda d: not (RATIO.get(d, 0) > 1.0),
           "V4_skip_vix25_or_backw": lambda d: not (VIX.get(d, 0) >= 25 or RATIO.get(d, 0) > 1.0)}
# --- overnight v2 daily P&L (for portfolio_2)
src3 = (ROOT / "scripts/overnight_3_pilot.py").read_text().split("out = {")[0]; ns3 = {"__file__": str(ROOT / "scripts/overnight_3_pilot.py")}; exec(src3, ns3)
mn, ms = ns3["nights"]("MNQ"), ns3["nights"]("MES"); mg, msd = ms.gap.reindex(mn.index), ms.sd20.reindex(mn.index)
mask = ((mn.gap <= -0.5 * mn.sd20) & (mg <= -0.5 * msd)).fillna(False); p_on = ns3["pnl"](mn, "MNQ", ex="x0945"); p_on = p_on[mask & p_on.notna()]
dates = np.array(sorted(set(mn.index)))
def next_day(d):
    i = dates.searchsorted(d, side="right"); return dates[i] if i < len(dates) else None
on_daily = pd.Series(p_on.values, index=[next_day(d) for d in p_on.index]).groupby(level=0).sum()
def combo(acc):
    d_arch = pd.Series([x["net"] for x in acc], index=[x["exit_day"] for x in acc]).groupby(level=0).sum()
    cal = sorted(set(on_daily.index) | set(d_arch.index)); tot = on_daily.reindex(cal).fillna(0) + d_arch.reindex(cal).fillna(0); eq = tot.cumsum()
    yrs = pd.Series([d.year for d in cal], index=cal); x = tot.to_numpy(); n = len(x); per_year = n / 14; paths = 3000; breaches = 0; nets = []
    for _ in range(paths):
        idx = []
        while len(idx) < int(per_year):
            st = rng.integers(n); ln = rng.geometric(1 / 10); idx.extend(((st + np.arange(ln)) % n).tolist())
        idx = np.array(idx[:int(per_year)]); e = np.cumsum(x[idx]); pk = np.maximum.accumulate(np.concatenate([[0], e]))[:-1]; breaches += int((pk - e).max() >= 2000); nets.append(float(e[-1]))
    return dict(net=round(float(tot.sum()), 2), closed_dd=round(float((eq.cummax() - eq).max()), 2), pos_years=int((tot.groupby(yrs).sum() > 0).sum()), p_dd2k_1y=round(breaches / paths, 3), net_p50=round(float(np.median(nets))),
                qualifies=bool(float((eq.cummax() - eq).max()) < 2000 and breaches / paths <= 0.10))
for x in acc0: x["exit_day"] = pd.Timestamp(x["exit_ts"]).tz_convert("America/New_York").date()
out["portfolio_champion"] = combo(acc0); print("portfolio champion", out["portfolio_champion"], flush=True)
for name, f in filters.items():
    acc = run_variant(name, base, dfilter=f)
    for x in acc: x["exit_day"] = pd.Timestamp(x["exit_ts"]).tz_convert("America/New_York").date()
    r = summary(acc); kept = set(x["day"] for x in acc); removed_days = [d for d in days_all if d not in kept]; removed_net = float(net_by_day.reindex(removed_days).fillna(0).sum())
    plc = [float(net_by_day.loc[rng.choice(days_all, size=len(removed_days), replace=False)].sum()) for _ in range(20)] if removed_days else [0.0]
    r.update(removed_days=len(removed_days), removed_net=round(removed_net, 2), removed_p5=round(float(np.percentile(plc, 5)), 2), removed_bad=bool(removed_net < np.percentile(plc, 5)))
    r["pass"] = bool(r["net"] >= 0.9 * ch["net"] and r["closed_dd"] <= 0.8 * ch["closed_dd"] and r["pos_years"] >= 11 and (r["max_year_share"] or 1) <= 0.4 and r["removed_bad"])
    r["portfolio"] = combo(acc); out[name] = r; print(name, {k: v for k, v in r.items() if k != "by_year"}, flush=True)
out["passers"] = [k for k, v in out.items() if isinstance(v, dict) and v.get("pass")]; print("PASSERS", out["passers"])
json.dump(out, open(ROOT / "reports/ARCHC_2_TRAINING.json", "w"), indent=1, default=str); print("DONE")
