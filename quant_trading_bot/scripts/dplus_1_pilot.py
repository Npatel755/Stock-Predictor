"""dplus_1 (research/dplus_1/PROTOCOL.md): ablation, marked DD, Crabel min_range plateau and prospective choice for ag_arch_d_plus. Training 2010-23 only."""
import json, sys, os
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
os.environ["SIZING_BUDGET"] = "1e9"
srcs = (ROOT / "scripts/sizing_1_pilot.py").read_text().split("\nfor key in (")[0]; ns1 = {"__file__": str(ROOT / "scripts/sizing_1_pilot.py")}; exec(srcs, ns1)
ep, bars_for, backw_mask, daily, START, MULT = ns1["ep"], ns1["bars_for"], ns1["backw_mask"], ns1["daily"], ns1["START"], ns1["MULT"]
spec = ep.CANDIDATES["ag_arch_d_plus"]
def run_sl(sl, prio, blocked_ok=True):
    b, mins, atr = bars_for(sl)
    blocked = backw_mask(b) if (blocked_ok and spec.get("day_filter") == "no_backwardation" and not sl.get("day_filter_exempt")) else None
    r = ep.run_sleeve(sl, b, START, blocked)
    for t in r["trades"]:
        t["prio"] = prio; t["sleeve"] = sl["name"]; t["exit_day"] = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
        t["dec"] = pd.Timestamp(t["entry_ts"]) - pd.Timedelta(minutes=mins); a = float(atr.get(t["dec"], np.nan))
        t["stop_risk"] = round(float(sl["stop_atr"]) * a * MULT[sl["instrument"]] + 1.0 + 3 * 0.25 * MULT[sl["instrument"]], 2)
    return r["trades"]
def route(allt):
    allt = sorted(allt, key=lambda x: (x["dec"], x["prio"])); acc = []
    for x in allt:
        if any(pd.Timestamp(a["entry_ts"]) <= x["dec"] < pd.Timestamp(a["exit_ts"]) for a in acc[-6:]): continue
        acc.append(x)
    return acc
def stats(acc):
    if not acc: return dict(net=0, trades=0)
    d = daily(acc); d.index = pd.to_datetime(d.index); yr = d.groupby(d.index.year).sum(); eq = d.cumsum()
    return dict(net=round(float(d.sum()), 2), trades=len(acc), per=round(float(d.sum() / len(acc)), 2), closed_dd=round(float((eq.cummax() - eq).max()), 2),
                pos_years=int((yr > 0).sum()), years=len(yr), by_year={int(k): round(float(v), 2) for k, v in yr.items()})
def marked(acc):
    ev = []
    for t in acc:
        ev.append((pd.Timestamp(t["entry_ts"]), "worst", -float(t["stop_risk"]), 0.0)); ev.append((pd.Timestamp(t["exit_ts"]), "close", 0.0, float(t["net"])))
    ev.sort(key=lambda x: x[0]); closed = hwm = worst = 0.0; when = None; br = {2000: 0, 2500: 0}; inb = {f: False for f in br}
    for ts, kind, unreal, real in ev:
        if kind == "worst": eq = closed + unreal
        else: closed += real; eq = closed; hwm = max(hwm, eq)
        tdd = hwm - eq
        if tdd > worst: worst, when = tdd, str(ts)
        for f in br:
            if tdd >= f and not inb[f]: br[f] += 1; inb[f] = True
            if tdd < f * 0.5: inb[f] = False
    return dict(marked_dd=round(worst, 2), when=when, touches=br)
out = {}
by_sleeve = {sl["name"]: run_sl(sl, i) for i, sl in enumerate(spec["sleeves"])}
full = route(sum(by_sleeve.values(), [])); out["full"] = stats(full); out["full_marked"] = marked(full); print("full", out["full"], out["full_marked"], flush=True)
out["ablation"] = {}
for name in by_sleeve:
    acc = route(sum((v for k, v in by_sleeve.items() if k != name), [])); s = stats(acc); s.pop("by_year"); s.update(marked(acc)); out["ablation"]["drop_" + name] = s; print("drop", name, s, flush=True)
# Crabel min_range plateau (standalone sleeve, same backwardation block as deployed)
cr = dict(spec["sleeves"][0]); plateau = {}; yr_tab = {}
for mr in (0, 5, 10, 15, 20, 25):
    sl = dict(cr); sl["min_range"] = float(mr); tr = run_sl(sl, 0); s = stats(tr); yr_tab[mr] = s.pop("by_year"); plateau[mr] = s; print("min_range", mr, s, flush=True)
out["plateau"] = plateau
ref = plateau[15]["net"]; out["plateau_gate"] = dict(n10=round(plateau[10]["net"] / ref, 3), n20=round(plateau[20]["net"] / ref, 3), passes=bool(plateau[10]["net"] >= 0.7 * ref and plateau[20]["net"] >= 0.7 * ref))
# expanding-window prospective choice: score = net / closed_dd on years < Y
Y = pd.DataFrame(yr_tab).fillna(0.0); Y.index = Y.index.astype(int); pros = 0.0; fixed = 0.0; picks = {}
for y in range(2013, 2024):
    past = Y.loc[Y.index < y]; best = None
    for mr in Y.columns:
        eq = past[mr].cumsum(); dd = float((eq.cummax() - eq).max()) or 1.0; sc = float(past[mr].sum()) / dd
        if best is None or sc > best[1]: best = (mr, sc)
    picks[y] = int(best[0]); pros += float(Y.at[y, best[0]]) if y in Y.index else 0.0; fixed += float(Y.at[y, 15]) if y in Y.index else 0.0
out["prospective"] = dict(picks=picks, prospective_total=round(pros, 2), fixed15_total=round(fixed, 2), ratio=round(pros / fixed, 3) if fixed else None, passes=bool(fixed > 0 and pros >= 0.6 * fixed))
print("prospective", out["prospective"], flush=True)
json.dump(out, open(ROOT / "reports/DPLUS_1_TRAINING.json", "w"), indent=1, default=str); print("DONE")
