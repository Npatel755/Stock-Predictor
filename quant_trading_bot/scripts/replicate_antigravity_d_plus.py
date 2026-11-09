"""Fixed-engine (paper-runner) replication of Antigravity 'Grand Champion Architecture D+' (ag_arch_d_plus) and 'Book D+' (book_d_plus) exactly as
registered in ensemble_paper.py (da1733a): Crabel 15m (min_range 15, tail 0.2) > MNQ 30m trend > MNQ 60m trend > MES 30m trend, strict 1c router,
morning sleeves stand aside after a VIX>VIX3M close; overnight_dip_v2 skipping nights after a backwardation close. Training 2010-23 only; 2024-26 not loaded.
Marks: book_1 convention (overnight leg at every 1m low, intraday stops assumed hit)."""
import json, sys, os
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
src = (ROOT / "scripts/book_1_pilot.py").read_text().split("\nfor t in aw:")[0]
ns = {"__file__": str(ROOT / "scripts/book_1_pilot.py")}; exec(src, ns)
ep, ns1, ev_on, mn, p_on = ns["ep"] if "ep" in ns else ns["ns1"]["ep"], ns["ns1"], list(ns["ev"]), ns["mn"], ns["p_on"]
bars_for, backw_mask, daily, START = ns1["bars_for"], ns1["backw_mask"], ns1["daily"], ns1["START"]
aw = ns["aw"]

def run_book_intraday(key):
    spec = ep.CANDIDATES[key]; allt = []
    for prio, sl in enumerate(spec["sleeves"]):
        b, mins, atr = bars_for(sl); MULT = ns1["MULT"]
        blocked = backw_mask(b) if (spec.get("day_filter") == "no_backwardation" and not sl.get("day_filter_exempt")) else None
        r = ep.run_sleeve(sl, b, START, blocked)
        for t in r["trades"]:
            t["prio"] = prio; t["sleeve"] = sl["name"]; t["exit_day"] = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date(); t["dec"] = pd.Timestamp(t["entry_ts"]) - pd.Timedelta(minutes=mins)
            a = float(atr.get(t["dec"], np.nan)); t["stop_risk"] = round(float(sl["stop_atr"]) * a * MULT[sl["instrument"]] + 1.0 + 3 * 0.25 * MULT[sl["instrument"]], 2)
        allt += r["trades"]; print(key, sl["name"], len(r["trades"]), round(sum(t["net"] for t in r["trades"]), 2), flush=True)
    allt.sort(key=lambda x: (x["dec"], x["prio"])); acc = []
    for x in allt:
        if any(pd.Timestamp(a["entry_ts"]) <= x["dec"] < pd.Timestamp(a["exit_ts"]) for a in acc[-6:]): continue
        acc.append(x)
    return acc
def stats(acc):
    d = daily(acc); d.index = pd.to_datetime(d.index); yr = d.groupby(d.index.year).sum(); eq = d.cumsum(); n = len(acc)
    return dict(net=round(float(d.sum()), 2), trades=n, per=round(float(d.sum() / max(n, 1)), 2), closed_dd=round(float((eq.cummax() - eq).max()), 2),
                pos_years=int((yr > 0).sum()), years=len(yr), max_year_share=round(float(yr.max() / d.sum()), 3) if d.sum() > 0 else None,
                pre2020=round(float(yr[yr.index < 2020].sum()), 2), post2020=round(float(yr[yr.index >= 2020].sum()), 2),
                by_sleeve={s: round(float(sum(t["net"] for t in acc if t["sleeve"] == s)), 2) for s in sorted({t["sleeve"] for t in acc})})

# nightly backwardation state (prior CBOE close VIX > VIX3M) by trade date, from the same mask the runner uses
b1 = bars_for(dict(instrument="MNQ", bar_minutes=30))[0]; bm = backw_mask(b1)
bd = pd.Series(bm, index=b1.timestamp_utc.dt.tz_convert("America/New_York").dt.date.to_numpy()).groupby(level=0).any()
night_dates = [pd.Timestamp(nk).date() for nk in p_on.index]
nxt = [ns["next_day"](nk) for nk in p_on.index]
skip_night = np.array([bool(bd.get(nd, False)) for nd in nxt])  # the day after the night is the gated day: prior close = the night's day close
print("nights", len(night_dates), "skipped (backwardation)", int(skip_night.sum()), flush=True)

def book(intraday_trades, skip_mask):
    ev = []
    for (nk, p), sk in zip(p_on.items(), skip_mask):
        if sk: continue
        ex_day = ns["next_day"](nk); e = float(mn.at[nk, "e1805"]); lo = min(float(mn.at[nk, "low_night"]), float(ns["low_open"].get(ex_day, np.inf)))
        ev.append((pd.Timestamp(f"{nk} 18:05", tz="America/New_York"), "worst", (lo - e) * 2.0 - 3.0, 0.0)); ev.append((pd.Timestamp(f"{ex_day} 09:45", tz="America/New_York"), "close", 0.0, float(p)))
    for t in intraday_trades:
        ev.append((pd.Timestamp(t["entry_ts"]).tz_convert("America/New_York"), "worst", -float(t["stop_risk"]), 0.0)); ev.append((pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York"), "close", 0.0, float(t["net"])))
    ev.sort(key=lambda x: x[0]); closed = 0.0; hwm = 0.0; worst = 0.0; when = None; br = {2000: 0, 2500: 0}; inb = {f: False for f in br}; yrs = {}
    for ts, kind, unreal, real in ev:
        if kind == "worst": eq = closed + unreal
        else: closed += real; eq = closed; hwm = max(hwm, eq); yrs[ts.year] = yrs.get(ts.year, 0.0) + real
        tdd = hwm - eq
        if tdd > worst: worst, when = tdd, str(ts)
        for f in br:
            if tdd >= f and not inb[f]: br[f] += 1; inb[f] = True
            if tdd < f * 0.5: inb[f] = False
    y = pd.Series(yrs)
    return dict(closed_net=round(closed, 2), marked_dd=round(worst, 2), when=when, breaches=br, pos_years=int((y > 0).sum()), years=len(y), pre2020=round(float(y[y.index < 2020].sum()), 2))

out = {}
dplus = run_book_intraday("ag_arch_d_plus"); out["ag_arch_d_plus"] = stats(dplus); print("ag_arch_d_plus", out["ag_arch_d_plus"], flush=True)
out["overnight_leg"] = dict(all=round(float(p_on.sum()), 2), nights=len(p_on), vix_gated=round(float(p_on[~skip_night].sum()), 2), nights_kept=int((~skip_night).sum()),
                            skipped_pnl=round(float(p_on[skip_night].sum()), 2))
print("overnight", out["overnight_leg"], flush=True)
out["book_a_ref"] = book(aw, np.zeros(len(p_on), bool)); print("book_a_ref", out["book_a_ref"], flush=True)
out["book_d_plus"] = book(dplus, skip_night); print("book_d_plus", out["book_d_plus"], flush=True)
out["book_d_plus_ungated_night"] = book(dplus, np.zeros(len(p_on), bool)); print("book_d_plus_ungated_night", out["book_d_plus_ungated_night"], flush=True)
out["book_a_vix_night"] = book(aw, skip_night); print("book_a_vix_night", out["book_a_vix_night"], flush=True)
out["antigravity_claims"] = dict(ag_arch_d_plus=dict(net=20292.55, trades=1635, per=12.41, closed_dd=935.65), book_d_plus=dict(closed_net=29169.65, marked_dd=1241.33, pos_years=11),
                                 overnight_dip_v2_vix=dict(net=8877, nights=420, marked_dd=1241))
json.dump(out, open(ROOT / "reports/ANTIGRAVITY_D_PLUS_REPLICATION.json", "w"), indent=1, default=str); print("DONE")
