"""anomaly_1 (research/anomaly_1/PROTOCOL.md): A intraday momentum, B pre-FOMC drift, C ER filter on a fixed 15m momentum rule. Training 2010-23 only."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from numba import njit
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts"))
import mass_1m_search as m1
COMM, SLIP = 0.61, 1.0
SPEC = {"MNQ": dict(tick=0.25, pv=0.5, spread=1.75), "MES": dict(tick=0.25, pv=1.25, spread=1.0)}
rng = np.random.default_rng(20261109); out = {"A": [], "B": [], "C": []}

def load(prod, res=1):
    b = m1.load_bars(prod, res, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]].copy()
    et = b.timestamp_utc.dt.tz_convert("America/New_York"); b["sod"] = et.dt.hour * 60 + et.dt.minute; b["date"] = et.dt.date; b["year"] = et.dt.year
    return b[(b.sod >= 570) & (b.sod < 960)].reset_index(drop=True)
def rt_cost(prod):  # $ per round trip excl. direction: spread + 2 slips + commissions
    s = SPEC[prod]; return (s["spread"] + 2 * SLIP) * s["pv"] + 2 * COMM
def gate(net, yearly, trades, pl, min_trades):
    yearly = {int(k): float(v) for k, v in dict(yearly).items()}
    pos = sum(v > 0 for v in yearly.values()); share = max(yearly.values()) / net if net > 0 else None
    return dict(net=round(net, 2), trades=int(trades), pos_years=int(pos), max_year_share=round(share, 2) if share else None, placebo_pct=float(np.mean(np.array(pl) < net)) if len(pl) else None,
                placebo_mean=round(float(np.mean(pl)), 2) if len(pl) else None, yearly={int(k): round(float(v), 2) for k, v in yearly.items()},
                passes=bool(net > 0 and pos >= 10 and (share or 1) <= 0.4 and (len(pl) == 0 or np.mean(np.array(pl) < net) >= 0.95) and trades >= min_trades))

# ---------- A: intraday momentum ----------
def day_table(b):
    g = b.groupby("date"); px = lambda sod, col: g.apply(lambda d: d.loc[d.sod == sod, col].iloc[0] if (d.sod == sod).any() else np.nan)
    t = pd.DataFrame(dict(o930=px(570, "open"), c959=px(599, "close"), o1330=px(810, "open"), c1359=px(839, "close"), o1500=px(900, "open"), o1530=px(930, "open"), c1554=px(954, "close")))
    t["year"] = pd.to_datetime(t.index).year; t["r1"] = t.c959 / t.o930 - 1; t["r12"] = t.c1359 / t.o1330 - 1; t["z1"] = t.r1 / t.r1.rolling(20).std().shift(1); return t
for prod in ("MNQ", "MES"):
    b = load(prod); t = day_table(b); s = SPEC[prod]
    for entry in ("o1500", "o1530"):
        for th in (0.0, 0.5, 1.0):
            for both in (False, True):
                dirn = np.sign(t.r1).where(t.z1.abs() >= th, 0.0)
                if both: dirn = dirn.where(np.sign(t.r12) == np.sign(t.r1), 0.0)
                m = (dirn != 0) & t[entry].notna() & t.c1554.notna()
                pnl = dirn[m] * (t.c1554[m] - t[entry][m]) / s["tick"] * s["pv"] - rt_cost(prod)
                yearly = pnl.groupby(t.year[m]).sum(); gross = ((t.c1554[m] - t[entry][m]) / s["tick"] * s["pv"])
                pl = [float((rng.choice([-1, 1], size=int(m.sum())) * gross - rt_cost(prod)).sum()) for _ in range(20)]
                rec = dict(product=prod, entry=entry, z_th=th, both=both, **gate(float(pnl.sum()), yearly, int(m.sum()), pl, 100)); out["A"].append(rec)
                print("A", prod, entry, th, both, rec["net"], rec["trades"], rec["pos_years"], rec["placebo_pct"], rec["passes"], flush=True)

# ---------- B: pre-FOMC drift ----------
cal = pd.read_csv(ROOT / "research/news/official_calendar_2010_2026.csv"); fomc = sorted(set(pd.to_datetime(cal[cal.family == "FOMC"].date_et).dt.date)); fomc = [d for d in fomc if d.year <= 2023]
for prod in ("MNQ", "MES"):
    b = load(prod); t = day_table(b); s = SPEC[prod]; days = list(t.index); pos_of = {d: i for i, d in enumerate(days)}
    g = b.groupby("date"); t["c1355"] = g.apply(lambda d: d.loc[d.sod == 835, "close"].iloc[0] if (d.sod == 835).any() else np.nan); t["o1000"] = g.apply(lambda d: d.loc[d.sod == 600, "open"].iloc[0] if (d.sod == 600).any() else np.nan)
    windows = {"day0_0930_1355": ("o930", "c1355", 0), "day0_1000_1355": ("o1000", "c1355", 0), "daym1_0930_1555": ("o930", "c1554", -1)}
    for wname, (a, c, off) in windows.items():
        ret = ((t[c] - t[a]) / s["tick"] * s["pv"]).rename("g")  # long gross $
        ev = [days[pos_of[d] + off] for d in fomc if d in pos_of and 0 <= pos_of[d] + off < len(days)]
        evn = ret.loc[ev].dropna() - rt_cost(prod); ctrl = ret.drop(index=[d for d in ev if d in ret.index]).dropna() - rt_cost(prod)
        yearly = evn.groupby(pd.to_datetime(evn.index).year).sum(); tstat = float(evn.mean() / (evn.std(ddof=1) / np.sqrt(len(evn))))
        pl = []
        for _ in range(200):
            pick = []
            for y in range(2010, 2024):
                yd = [d for d in days if d.year == y]; pick += list(rng.choice(yd, size=min(8, len(yd)), replace=False))
            pl.append(float((ret.loc[pick].dropna() - rt_cost(prod)).sum()))
        rec = dict(product=prod, window=wname, events=int(len(evn)), mean_event_net=round(float(evn.mean()), 2), t=round(tstat, 2), control_mean_net=round(float(ctrl.mean()), 2), **gate(float(evn.sum()), yearly, len(evn), pl, 0))
        rec["passes"] = bool(rec["passes"] and abs(tstat) > 3 and evn.mean() > 0); out["B"].append(rec)
        print("B", prod, wname, rec["events"], rec["mean_event_net"], "t", rec["t"], "ctrl", rec["control_mean_net"], rec["pos_years"], rec["placebo_pct"], rec["passes"], flush=True)

# ---------- C: ER filter on fixed 15m momentum rule (MNQ) ----------
@njit(cache=True)
def sim15(o, h, l, c, atr, sig, day, sod, hold, stop_mult, tgt_r, s0, s1, flat, cost):
    n = len(o); pnl = np.zeros(n); pos = 0; ep = 0.0; st = 0.0; tg = 0.0; ei = 0; eday = -1; ntr = 0
    for i in range(n):
        if pos != 0:
            ex = False; px = 0.0
            if day[i] != eday: ex = True; px = o[i]
            elif pos > 0 and l[i] <= st: ex = True; px = st
            elif pos < 0 and h[i] >= st: ex = True; px = st
            elif pos > 0 and h[i] >= tg: ex = True; px = tg
            elif pos < 0 and l[i] <= tg: ex = True; px = tg
            elif i - ei >= hold or sod[i] + 15 >= flat: ex = True; px = c[i]
            if ex: pnl[i] += pos * (px - ep) / 0.25 * 0.5 - cost; pos = 0; ntr += 1
        if pos == 0 and sig[i] != 0 and sod[i] >= s0 and sod[i] < s1 and i + 1 < n and day[i + 1] == day[i] and atr[i] > 0:
            pos = sig[i]; ep = o[i + 1]; r = stop_mult * atr[i]; st = ep - r if pos > 0 else ep + r; tg = ep + tgt_r * r if pos > 0 else ep - tgt_r * r; ei = i + 1; eday = day[i]
    return pnl, ntr
b = load("MNQ", 15); b["day"] = pd.factorize(b.date)[0]; g = b.groupby("day", sort=False)
mom = (b.close / g.close.shift(24) - 1); er = (b.close - g.close.shift(24)).abs() / b.close.diff().abs().groupby(b.day).transform(lambda s: s.rolling(24).sum())
tr = np.maximum(b.high - b.low, np.maximum((b.high - g.close.shift(1)).abs(), (b.low - g.close.shift(1)).abs())); atr = tr.rolling(14, min_periods=14).mean().to_numpy()
# note: lb24 at 15m spans ~a session; rolling across session boundary is intentional for the all-day rule
mom = (b.close / b.close.shift(24) - 1).to_numpy(); er = ((b.close - b.close.shift(24)).abs() / b.close.diff().abs().rolling(24).sum()).to_numpy()
o, h_, l_, c_ = [b[k].to_numpy(float) for k in ("open", "high", "low", "close")]; day = b.day.to_numpy(np.int64); sod = b.sod.to_numpy(np.int64); year = b.year.to_numpy()
valid = (sod >= 585) & (sod < 930); base = np.where(valid, np.sign(np.nan_to_num(mom)), 0).astype(np.int8); cost = rt_cost("MNQ")
def runC(sig):
    pnl, ntr = sim15(o, h_, l_, c_, np.nan_to_num(atr), sig, day, sod, 24, 2.0, 3.0, 585, 930, 955, cost); return float(pnl.sum()), ntr, pd.Series(pnl).groupby(year).sum()
for th in (None, 0.3, 0.5, 0.7):
    mask = valid if th is None else (valid & (np.nan_to_num(er) > th)); sig = np.where(mask, base, 0).astype(np.int8)
    net, ntr, yearly = runC(sig); pl = []
    if th is not None:
        for _ in range(20):
            ps = np.zeros_like(sig)
            for y in range(2010, 2024):
                idx = np.flatnonzero(valid & (year == y)); n = int((mask & (year == y)).sum()); pick = rng.choice(idx, size=min(n, len(idx)), replace=False); ps[pick] = base[pick]
            pl.append(runC(ps)[0])
    rec = dict(er_th=th, **gate(net, yearly, ntr, pl, 100)); out["C"].append(rec)
    print("C", th, rec["net"], rec["trades"], rec["pos_years"], rec["placebo_pct"], rec["placebo_mean"], rec["passes"], flush=True)
json.dump(out, open(ROOT / "reports/ANOMALY_1_TRAINING.json", "w"), indent=1, default=float); print("DONE", flush=True)
