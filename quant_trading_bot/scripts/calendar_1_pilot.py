"""calendar_1: intraday-only calendar anomalies on MNQ/MES, training 2010-2023 (research/calendar_1/PROTOCOL.md). Day sets come from dates only."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts"))
src = open(ROOT / "scripts/anomaly_1_pilot.py").read()
ns = {"__file__": str(ROOT / "scripts/anomaly_1_pilot.py")}; exec(src.split("# ---------- A:")[0], ns); load, SPEC, rt_cost, gate = ns["load"], ns["SPEC"], ns["rt_cost"], ns["gate"]
exec("import numpy as np\nfrom numba import njit\n" + src.split("# ---------- C: ER filter on fixed 15m momentum rule (MNQ) ----------")[1].split("b = load(")[0].replace("cache=True", "cache=False"), ns); sim15 = ns["sim15"]
rng = np.random.default_rng(20261111); out = {"T1": [], "T1b": [], "T2": []}

def daysets(trading_days):
    td = pd.DatetimeIndex(sorted(pd.to_datetime(pd.Series(list(trading_days)))))
    s = pd.Series(td, index=td); nxt = s.shift(-1); prv = s.shift(1)
    month_end = td.month != nxt.dt.month.fillna(-1).astype(int).values
    first_n = pd.Series(td.month != prv.dt.month.fillna(-1).astype(int).values, index=td)
    pos_in_month = first_n.groupby(td.to_period("M")).cumsum()  # ones at first day; use rank within month instead
    rank = pd.Series(np.arange(len(td)), index=td).groupby(td.to_period("M")).rank(method="first")
    tom = month_end | (rank <= 3).values
    opex = (td.weekday == 4) & (td.day >= 15) & (td.day <= 21)
    qend = month_end & np.isin(td.month, [3, 6, 9, 12])
    gap = (nxt - s).dt.days.fillna(1).values; pre_hol = ((gap >= 2) & (td.weekday != 4)) | ((gap >= 4) & (td.weekday == 4))
    D = dict(tom=tom, non_tom=~tom, opex=opex, month_end=month_end, quarter_end=qend, pre_holiday=pre_hol, mon=td.weekday == 0, tue=td.weekday == 1, wed=td.weekday == 2, thu=td.weekday == 3, fri=td.weekday == 4, all=np.ones(len(td), bool))
    return {k: pd.Series(np.asarray(v, bool), index=td.date) for k, v in D.items()}

def run_dayset(prod, t, gross, sets, names, label, n_pl=200):
    for st in names:
        m = sets[st].reindex(t.index).fillna(False).to_numpy(); yrs = t.year.values
        for side in (1, -1):
            pnl = side * gross[m] - rt_cost(prod); yearly = pnl.groupby(yrs[m]).sum(); pl = []
            for _ in range(n_pl):  # random day sets with the same count per year, same direction
                pm = np.zeros(len(t), bool)
                for y in np.unique(yrs):
                    idx = np.flatnonzero(yrs == y); n = int((m & (yrs == y)).sum()); pm[rng.choice(idx, size=n, replace=False)] = True
                pl.append(float((side * gross[pm] - rt_cost(prod)).sum()))
            rec = dict(product=prod, dayset=st, side=side, days=int(m.sum()), **gate(float(pnl.sum()), yearly, int(m.sum()), pl, 100)); out[label].append(rec)
            print(label, prod, st, side, rec["days"], rec["net"], rec["pos_years"], rec["placebo_pct"], rec["placebo_mean"], rec["passes"], flush=True)

for prod in ("MNQ", "MES"):
    b = load(prod, 1); s = SPEC[prod]; g = b.groupby("date")
    px = lambda sod, col: g.apply(lambda d: d.loc[d.sod == sod, col].iloc[0] if (d.sod == sod).any() else np.nan)
    t = pd.DataFrame(dict(o945=px(585, "open"), o1500=px(900, "open"), c1554=px(954, "close"))).dropna(); t["year"] = pd.to_datetime(t.index).year
    sets = daysets(t.index)
    run_dayset(prod, t, (t.c1554 - t.o945) / s["tick"] * s["pv"], sets, ["tom", "non_tom", "opex", "pre_holiday", "mon", "tue", "wed", "thu", "fri"], "T1")
    run_dayset(prod, t, (t.c1554 - t.o1500) / s["tick"] * s["pv"], sets, ["month_end", "quarter_end", "opex", "tom", "all"], "T1b")

# T2 day-set filters on the fixed 15m MNQ momentum rule
b = load("MNQ", 15); b["day"] = pd.factorize(b.date)[0]; g = b.groupby("day", sort=False)
tr = np.maximum(b.high - b.low, np.maximum((b.high - g.close.shift(1)).abs(), (b.low - g.close.shift(1)).abs())); atr = np.nan_to_num(tr.rolling(14, min_periods=14).mean().to_numpy())
mom = (b.close / b.close.shift(24) - 1).to_numpy(); o, h_, l_, c_ = [b[k].to_numpy(float) for k in ("open", "high", "low", "close")]
day = b.day.to_numpy(np.int64); sod = b.sod.to_numpy(np.int64); year = b.year.to_numpy(); dates = b.date.to_numpy()
valid = (sod >= 585) & (sod < 930); base = np.where(valid, np.sign(np.nan_to_num(mom)), 0).astype(np.int8); cost = rt_cost("MNQ")
def runC(sig):
    pnl, ntr = sim15(o, h_, l_, c_, atr, sig, day, sod, 24, 2.0, 3.0, 585, 930, 955, cost); return float(pnl.sum()), ntr, pd.Series(pnl).groupby(year).sum()
all_days = pd.Series(dates).drop_duplicates(); day_year = pd.Series(pd.to_datetime(all_days).dt.year.values, index=all_days.values); sets = daysets(all_days)
FILTERS = dict(tom=sets["tom"], opex=sets["opex"], mon=sets["mon"], fri=sets["fri"], ex_opex=~sets["opex"], ex_tom=~sets["tom"])
for st, sm in FILTERS.items():
    on_days = set(sm[sm].index); mask = valid & np.isin(dates, list(on_days)); net, ntr, yearly = runC(np.where(mask, base, 0).astype(np.int8)); pl = []
    for _ in range(20):
        pick = []
        for y, grp in day_year.groupby(day_year):
            n = len(on_days & set(grp.index)); pick += list(rng.choice(grp.index.to_numpy(), size=min(n, len(grp)), replace=False))
        pm = valid & np.isin(dates, pick); pl.append(runC(np.where(pm, base, 0).astype(np.int8))[0])
    rec = dict(filter=st, days=len(on_days & set(all_days)), **gate(net, yearly, ntr, pl, 100)); out["T2"].append(rec)
    print("T2", st, rec["days"], rec["net"], rec["trades"], rec["pos_years"], rec["placebo_pct"], rec["placebo_mean"], rec["passes"], flush=True)
json.dump(out, open(ROOT / "reports/CALENDAR_1_TRAINING.json", "w"), indent=1, default=float); print("DONE")
