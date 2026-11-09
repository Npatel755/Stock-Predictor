"""Fixed-engine replication of Antigravity 'Grand Champion Architecture D' = Champion 1 (Crabel open-drive + NQ-leader z>=1.25 at 10:00, long/short,
stop 2 ATR, 4R, hold 12x15m) + afternoon MNQ 30m EWMA trend (lb8, th0.5, decisions 13:30-15:15 ET, stop 1.5, 4R, hold 8) under a strict 1c router
(morning priority). Spec from scripts/audit_champion1_all_splits.py + audit_champion1_enhanced_afternoon.py. Training 2010-23 only; 2024-26 not loaded."""
import json, os, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
os.environ["SIZING_BUDGET"] = "150"
src = (ROOT / "scripts/sizing_1_pilot.py").read_text().split("\nfor key in (")[0]
ns = {"__file__": str(ROOT / "scripts/sizing_1_pilot.py")}; exec(src, ns)
ep, bars_for, daily = ns["ep"], ns["bars_for"], ns["daily"]; START = ns["START"]

MES15, _, _ = bars_for(dict(instrument="MES", bar_minutes=15))
_orig = ep.custom_signal
def champ1_signal(cfg, bars):
    if cfg["signal"] != "champ1": return _orig(cfg, bars)
    atr = ep._atr14(bars)
    def dayfeat(b):
        et = b.timestamp_utc.dt.tz_convert("America/New_York"); sod = (et.dt.hour * 60 + et.dt.minute).to_numpy(); day = et.dt.date.to_numpy()
        df = pd.DataFrame(dict(day=day, sod=sod, o=b.open.to_numpy(float), h=b.high.to_numpy(float), l=b.low.to_numpy(float), c=b.close.to_numpy(float)))
        r = df[df.sod.isin([570, 585])].groupby("day")
        return dict(o930=df[df.sod == 570].groupby("day").o.first(), c1000=df[df.sod == 585].groupby("day").c.first(), hi=r.h.max(), lo=r.l.min()), sod, day
    fm, sod, day = dayfeat(bars); fe, _, _ = dayfeat(MES15)
    idx = fm["o930"].index.intersection(fm["c1000"].index).intersection(fe["o930"].index).intersection(fe["c1000"].index)
    d = pd.DataFrame(index=idx)
    d["spread"] = (fm["c1000"].loc[idx] / fm["o930"].loc[idx] - 1) - (fe["c1000"].loc[idx] / fe["o930"].loc[idx] - 1)
    d["z"] = d.spread / d.spread.rolling(20, min_periods=20).std().shift(1)
    rng_ = (fm["hi"].loc[idx] - fm["lo"].loc[idx]).replace(0, np.nan); op = (fm["o930"].loc[idx] - fm["lo"].loc[idx]) / rng_; cp = (fm["c1000"].loc[idx] - fm["lo"].loc[idx]) / rng_
    crab = pd.Series(np.where((op <= 0.2) & (cp >= 0.8), 1, np.where((op >= 0.8) & (cp <= 0.2), -1, 0)), index=idx)
    lead = pd.Series(np.where(d.z >= 1.25, 1, np.where(d.z <= -1.25, -1, 0)), index=idx)
    comb = np.where(crab != 0, np.where((lead != 0) & (lead != crab), 0, crab), lead)
    comb = pd.Series(comb, index=idx)
    which = cfg.get("which", "comb"); sig_day = {"comb": comb, "crabel": crab, "lead": lead}[which]
    sig = np.where(sod == 585, pd.Series(day).map(sig_day).fillna(0).to_numpy(), 0)
    return sig.astype(np.int8), np.nan_to_num(atr).astype(np.float32)
ep.custom_signal = champ1_signal

def morning(which):
    return dict(name=f"D_MORN_{which}", instrument="MNQ", family="trend", lookback=8, threshold=0.0, stop_atr=2.0, target_r=4.0, hold_bars=12, trailing_atr=0.0,
                session_start=600, session_end=945, bar_minutes=15, signal="champ1", which=which, entry_start=585, entry_end=585, max_gap_minutes=60, max_contracts=1)
AFT = dict(name="D_AFT30", instrument="MNQ", family="trend", lookback=8, threshold=0.5, stop_atr=1.5, target_r=4.0, hold_bars=8, trailing_atr=0.0,
           session_start=810, session_end=915, bar_minutes=30, signal="ewma_trend", entry_start=780, entry_end=885, max_gap_minutes=60, max_contracts=1)

def run(sleeves):
    allt = []
    for prio, sl in enumerate(sleeves):
        b, mins, _ = bars_for(sl); r = ep.run_sleeve(sl, b, START, None)
        for t in r["trades"]:
            t["prio"] = prio; t["dec"] = pd.Timestamp(t["entry_ts"]) - pd.Timedelta(minutes=mins); t["exit_day"] = pd.Timestamp(t["exit_ts"]).tz_convert("America/New_York").date()
        allt += r["trades"]
    allt.sort(key=lambda x: (x["dec"], x["prio"])); acc = []
    for x in allt:
        if any(pd.Timestamp(a["entry_ts"]) <= x["dec"] < pd.Timestamp(a["exit_ts"]) for a in acc[-5:]): continue
        acc.append(x)
    return acc
def stats(acc):
    d = daily(acc); d.index = pd.to_datetime(d.index); yr = d.groupby(d.index.year).sum(); eq = d.cumsum(); n = len(acc)
    return dict(net=round(float(d.sum()), 2), trades=n, per=round(float(d.sum() / max(n, 1)), 2), closed_dd=round(float((eq.cummax() - eq).max()), 2),
                pos_years=int((yr > 0).sum()), max_year_share=round(float(yr.max() / d.sum()), 3) if d.sum() > 0 else None,
                pre2020=round(float(yr[yr.index < 2020].sum()), 2), pre2020_trades=int(sum(1 for t in acc if pd.Timestamp(t["entry_ts"]).year < 2020)),
                longs=int(sum(1 for t in acc if t["side"] > 0)), long_net=round(float(sum(t["net"] for t in acc if t["side"] > 0)), 2), years={int(k): round(float(v), 2) for k, v in yr.items()})
out = {}
for name, sleeves in (("crabel_only", [morning("crabel")]), ("nqleader_only", [morning("lead")]), ("champion1_dual_morning", [morning("comb")]),
                      ("afternoon_only", [AFT]), ("architecture_d", [morning("comb"), AFT])):
    acc = run(sleeves); out[name] = stats(acc); print(name, {k: v for k, v in out[name].items() if k != "years"}, flush=True); print("   years", out[name]["years"], flush=True)
Path(ROOT / "reports/ANTIGRAVITY_ARCH_D_REPLICATION.json").write_text(json.dumps(out, indent=1, default=str))
