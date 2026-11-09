"""extstate_2: CBOE SKEW prior-close states vs overnight dip nights, all nights, and All-Weather 1c trades; training 2010-23 only."""
import json, os, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
rng = np.random.default_rng(20261109)
sk = pd.read_csv(ROOT / "data/external/SKEW_History.csv"); sk["DATE"] = pd.to_datetime(sk.DATE); sk = sk.set_index("DATE").SKEW.sort_index()
sk = sk[sk.index < "2024-01-01"]
F = pd.DataFrame(dict(
    F1=pd.cut(sk.rolling(252, min_periods=200).rank(pct=True), [0, 1/3, 2/3, 1.0001], labels=["low", "mid", "high"]),
    F2=np.where(sk.diff(5) > 0, "up", "down"),
    F3=pd.qcut((sk - sk.rolling(20).mean()), 3, labels=["below", "mid", "above"])))
F.index = sk.index

def state_before(dates):
    """feature row from the last CBOE close strictly before each date (date = ET session date of the decision)."""
    d = pd.to_datetime(pd.Series(list(dates))).dt.tz_localize(None).dt.normalize()
    pos = np.searchsorted(F.index.to_numpy(), d.to_numpy(), side="left") - 1
    ok = pos >= 0
    out = F.iloc[np.clip(pos, 0, len(F) - 1)].reset_index(drop=True); out[~ok] = np.nan
    out.index = list(dates); return out

def removal_test(pnl, mask, n_sets=200):
    """net of removed set vs same-count random removals; returns (removed_net, #random removals that are *better* (more negative) than it)."""
    k = int(mask.sum()); rem = float(pnl[mask].sum()); arr = pnl.to_numpy()
    rand = np.array([arr[rng.choice(len(arr), size=k, replace=False)].sum() for _ in range(n_sets)]) if k else np.array([0.0])
    return rem, int((rand < rem).sum())

def gate_overnight(q):
    yr = q.groupby(q.index.map(lambda d: pd.Timestamp(d).year)).sum(); eq = q.cumsum(); dd = float((eq.cummax() - eq).max())
    return dict(net=round(float(q.sum()), 2), n=int(len(q)), pos_years=int((yr > 0).sum()), max_year_share=round(float(yr.max() / q.sum()), 3) if q.sum() > 0 else None, dd=round(dd, 2))

src = (ROOT / "scripts/overnight_3_pilot.py").read_text().split("\nif __name__")[0].split("\nN = ")[0]
ns = {"__name__": "ov3", "__file__": str(ROOT / "scripts/overnight_3_pilot.py")}; exec(src, ns)
mn, me = ns["nights"]("MNQ"), ns["nights"]("MES")
assert pd.Timestamp(max(mn.index)) < pd.Timestamp("2024-01-01")
p_all = ns["pnl"](mn, "MNQ", ex="x0945"); p_all = p_all[p_all.notna()]
mg, msd = me.gap.reindex(mn.index), me.sd20.reindex(mn.index)
dip = ((mn.gap <= -0.5 * mn.sd20) & (mg <= -0.5 * msd)).fillna(False).reindex(p_all.index).fillna(False)
p_dip = p_all[dip]
out = {"T1_dip_nights": {}, "T2_all_nights": {}, "T3_allweather": {}}
S_dip, S_all = state_before(p_dip.index), state_before(p_all.index)
print("dip nights", len(p_dip), "net", round(p_dip.sum(), 2), "| all nights", len(p_all), flush=True)
for f in ("F1", "F2", "F3"):
    for st in pd.unique(F[f].dropna().astype(str)):
        m1 = (S_dip[f].astype(str) == st).to_numpy()
        rem, better = removal_test(p_dip, m1); keep = gate_overnight(p_dip[~m1])
        out["T1_dip_nights"][f"{f}={st}"] = dict(n=int(m1.sum()), per=round(float(p_dip[m1].mean()), 2) if m1.sum() else None, removed_net=round(rem, 2), random_removals_worse=better, remaining=keep)
        m2 = (S_all[f].astype(str) == st).to_numpy(); q = p_all[m2]
        g = gate_overnight(q); cnt = pd.Series(m2).groupby(np.array([pd.Timestamp(d).year for d in p_all.index])).sum()
        yrs = np.array([pd.Timestamp(d).year for d in p_all.index]); pl = []
        for _ in range(200):
            pick = np.zeros(len(p_all), bool)
            for y, k in cnt.items():
                pool = np.where(yrs == y)[0]
                if k > 0: pick[rng.choice(pool, size=min(int(k), len(pool)), replace=False)] = True
            pl.append(float(p_all.to_numpy()[pick].sum()))
        g["beats"] = int((g["net"] > np.array(pl)).sum()); g["per"] = round(float(q.mean()), 2); out["T2_all_nights"][f"{f}={st}"] = g
        print(f, st, "T1", out["T1_dip_nights"][f"{f}={st}"], "| T2", g, flush=True)
os.environ["SIZING_BUDGET"] = "1e9"
srcs = (ROOT / "scripts/sizing_1_pilot.py").read_text().split("\nfor key in (")[0]
ns1 = {"__file__": str(ROOT / "scripts/sizing_1_pilot.py")}; exec(srcs, ns1)
aw = ns1["run_candidate"]("ag_all_weather_v2", True)
tr = pd.DataFrame(aw); tr["day"] = pd.to_datetime(tr.exit_day).dt.date
assert pd.to_datetime(tr.exit_day).max() < pd.Timestamp("2024-01-01")
tp = tr.groupby("day").net.sum(); S_aw = state_before([pd.Timestamp(d) for d in tp.index])
base_eq = tp.cumsum(); base = dict(net=round(float(tp.sum()), 2), dd=round(float((base_eq.cummax() - base_eq).max()), 2), pos_years=int((tp.groupby(pd.to_datetime(tp.index).year).sum() > 0).sum()))
print("AW 1c base", base, flush=True); out["T3_allweather"]["base"] = base
for f in ("F1", "F2", "F3"):
    for st in pd.unique(F[f].dropna().astype(str)):
        m = (S_aw[f].astype(str) == st).to_numpy(); rem, better = removal_test(tp, m)
        keep = tp[~m]; eq = keep.cumsum()
        out["T3_allweather"][f"{f}={st}"] = dict(days=int(m.sum()), removed_net=round(rem, 2), random_removals_worse=better, remaining=dict(net=round(float(keep.sum()), 2), dd=round(float((eq.cummax() - eq).max()), 2), pos_years=int((keep.groupby(pd.to_datetime(keep.index).year).sum() > 0).sum())))
        print(f, st, "T3", out["T3_allweather"][f"{f}={st}"], flush=True)
Path(ROOT / "reports/EXTSTATE_2_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
