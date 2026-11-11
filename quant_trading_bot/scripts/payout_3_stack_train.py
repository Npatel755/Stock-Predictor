"""payout_3 (Claude, 2026-11-09): does stacking the overnight reopen-dip on D+ v4 add payout days? TRAINING 2010-23 only.

PRE-DECLARED (before results): one Topstep 50K static account running D+ v4 (exact runner trades, reports/PARITY_DPLUS_V4.md) plus
overnight_dip_v2 (runner's own run_overnight, 1-min MNQ/MES) at k in {0 (v4 alone), 1, 2} micros. A night (18:05 -> 09:45 ET) counts on its
exit date (same Topstep session as that day's v4 trades; v4's first entries are at 10:00, so no overlap). Account-level -$600 stop is not
extended to the night leg (reported). Metrics: $150+ days per year, median winning day, payouts per year (5 days >= $150, withdraw the cycle
profit, static -$2,000 floor, account restarts after a breach), days with realised P&L <= -$1,000, nights whose marked open loss reaches
-$1,000 (DLL risk), worst day, net by era. Gate for recommending the stack: more payouts per year than v4 alone with zero DLL days.
"""
import json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P = (ROOT / "scripts/dplus_7e_pilot.py").read_text(encoding="utf-8").split("\nout = {}")[0]
ns = {"__file__": str(ROOT / "scripts/dplus_7e_pilot.py")}
exec(P, ns)
ep, tr, gs, NY, OVR = ns["ep"], ns["tr"], ns["gs"], ns["NY"], ns["OVR"]
d7 = ns["ns"]; bars_for = d7["bars_for"]; START = d7["ns"]["START"]
OVR.clear()

# ---- v4 day P&L (identical to the runner per PARITY_DPLUS_V4)
rows = []
for t in tr:
    tin = pd.Timestamp(t["entry_ts"]).tz_convert(NY); tout = pd.Timestamp(t["exit_ts"]).tz_convert(NY)
    cont = "CRABEL" in t["sleeve"] and int(t["side"]) * gs.get(tin.date(), 0) >= 0
    rows.append(dict(tin=tin, tout=tout, net=float(t["net"]) * (4 / 3 if cont else 1), day=tout.date(), eday=tin.date()))
rows.sort(key=lambda r: r["tin"])
kept = []
for r in rows:
    if sum(x["net"] for x in kept if x["day"] == r["eday"] and x["tout"] <= r["tin"]) <= -600.0:
        continue
    kept.append(r)
v4_day = pd.Series([r["net"] for r in kept], index=[r["day"] for r in kept]).groupby(level=0).sum()

# ---- overnight_dip_v2 through the runner (1-min MNQ + MES)
spec = ep.CANDIDATES["overnight_dip_v2"]
b1 = {"MNQ@1": bars_for(dict(instrument="MNQ", bar_minutes=1))[0], "MES@1": bars_for(dict(instrument="MES", bar_minutes=1))[0]}
run = ep.run_routed(spec, b1, START)
ov = list(run.values())[0]
curve = ov["curve"].copy(); curve["ts"] = pd.to_datetime(curve["ts"], utc=True)
nights = []
for t in ov["trades"]:
    e, x = pd.Timestamp(t["entry_ts"]), pd.Timestamp(t["exit_ts"])
    w = curve[(curve.ts >= e) & (curve.ts <= x)]
    base_cash = float(curve[curve.ts < e].cash.iloc[-1]) if (curve.ts < e).any() else ep.INITIAL_BALANCE
    nights.append(dict(exit_day=x.tz_convert(NY).date(), net=float(t["net"]), mae=float(min(w.worst.min() - base_cash, 0.0)) if len(w) else 0.0))
nd = pd.DataFrame(nights)
assert pd.to_datetime(pd.Series(nd.exit_day).astype(str)).max() < pd.Timestamp("2024-01-01")
ov_day = nd.groupby("exit_day").net.sum(); ov_mae = nd.groupby("exit_day").mae.min()


def account(day):
    bal = 0.0; good = 0; payouts = []; blow = 0
    for p in day.to_numpy():
        bal += p
        if bal <= -2000.0: blow += 1; bal = 0.0; good = 0; continue
        good += p >= 150
        if good >= 5: payouts.append(max(bal, 0.0)); bal = min(bal, 0.0); good = 0
    yrs = 14.0
    return round(len(payouts) / yrs, 2), round(float(np.median(payouts)), 0) if payouts else 0, round(blow / yrs, 2)


out = dict(overnight_runner=dict(nights=len(nd), net=round(float(nd.net.sum()), 2), worst_night=round(float(nd.net.min()), 2),
                                 worst_marked=round(float(nd.mae.min()), 2), expected="Devin: +11,797 / 490 nights"))
for k in (0, 1, 2):
    day = v4_day.add(ov_day * k, fill_value=0.0).sort_index()
    day = day.reindex(sorted(day.index))
    wd = day[day > 0]; yrs = pd.DatetimeIndex(pd.to_datetime(pd.Series(day.index).astype(str)))
    d150 = pd.Series((day >= 150).to_numpy(), index=yrs.year).groupby(level=0).sum()
    ppy, med_pay, blow = account(day)
    early = yrs.year < 2020
    out[f"v4 + overnight x{k}"] = dict(
        net=round(float(day.sum()), 2), net_2010_19=round(float(day[early].sum()), 0), net_2020_23=round(float(day[~early].sum()), 0),
        days150_per_year=round(float(d150.mean()), 1), median_win_day=round(float(np.median(wd)), 2), worst_day=round(float(day.min()), 2),
        days_le_minus_1000=int((day <= -1000).sum()), nights_marked_le_minus_1000=int((ov_mae * k <= -1000).sum()) if k else 0,
        payouts_per_year=ppy, median_payout=med_pay, blowups_per_year=blow)
print(json.dumps(out, indent=1, default=str))
(ROOT / "reports/PAYOUT_3_STACK_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
