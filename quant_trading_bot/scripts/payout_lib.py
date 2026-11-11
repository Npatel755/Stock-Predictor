"""Shared helpers for the payout_* studies (Claude, 2026-11-10). TRAINING 2010-23 only.

Price normalisation: a training trade's move is re-expressed at TODAY's price level (same % move), with today's per-contract costs:
  net_today = ((side*(exit-entry) + 2*ADV) * TODAY/entry - 2*ADV) * MULT - FEE     (engine fills carry 2 ticks adverse per side)
  risk_today = stop_pct * TODAY * MULT + 1.0 + 0.75*MULT                              (engine stop_risk formula, dplus_1)
Payout model: a payout = 5 trading days with net >= $150 since the last payout, withdrawing only above a cushion; static -$2,000 floor
(account restarts after a breach); $1,000 daily loss limit applied to realised day P&L.
"""
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TODAY = {"MNQ": 27981.5, "MES": 7584.0}          # live feed close 2026-11-10
MULT = {"MNQ": 2.0, "MES": 5.0}; ADV = 0.5; FEE = 1.0
NY = "America/New_York"


def engine():
    """Load the research engine exactly as dplus_7e does (training bars loader, cleared overrides, historical VIX for the day filter)."""
    P = (ROOT / "scripts/dplus_7e_pilot.py").read_text(encoding="utf-8").split("\nout = {}")[0].split("\ntr = route(")[0]
    ns = {"__file__": str(ROOT / "scripts/dplus_7e_pilot.py")}
    exec(P, ns)
    ep, OVR = ns["ep"], ns["OVR"]; OVR.clear()
    d = {n: pd.read_csv(ROOT / f"data/external/{n}_History.csv") for n in ("VIX", "VIX3M")}
    s = {n: pd.Series(v.CLOSE.astype(float).to_numpy(), index=pd.to_datetime(v.DATE, format="%m/%d/%Y")) for n, v in d.items()}
    j = pd.concat([s["VIX"].rename("vix"), s["VIX3M"].rename("vix3m")], axis=1).dropna().sort_index()
    ep._VIX_CACHE["series"] = (j.vix > j.vix3m)
    return ep, ns["ns"]["bars_for"], ns["ns"]["ns"]["START"], ns["gs"]


def sleeve_trades(ep, bars_for, START, sl, prio, day_filter=True):
    """Independent 1-contract run of one sleeve (no dollar budget), with the VIX stand-aside unless exempt. Returns a DataFrame."""
    sl = dict(sl, risk_per_trade=1e9, max_open_risk=1e9, max_contracts=1, hard_drawdown=1e9, funded_drawdown=1e9)
    b, mins, atr = bars_for(sl)
    spec = {"day_filter": "no_backwardation"} if day_filter else {}
    r = ep.run_sleeve(sl, b, START, ep.day_filter_mask(spec, b, sl) if day_filter else None)
    rows = []
    for t in r["trades"]:
        e = pd.Timestamp(t["entry_ts"]); dec = e - pd.Timedelta(minutes=mins); a = float(atr.get(dec, np.nan))
        rows.append(dict(sleeve=sl["name"], prio=prio, inst=sl["instrument"], side=int(t["side"]), entry=float(t["entry_price"]),
                         exit=float(t["exit_price"]), net_then=float(t["net"]), tin=e.tz_convert(NY), tout=pd.Timestamp(t["exit_ts"]).tz_convert(NY),
                         dec=dec.tz_convert(NY), stop_pct=float(sl["stop_atr"]) * a / float(t["entry_price"])))
    df = pd.DataFrame(rows)
    assert df.tout.max() < pd.Timestamp("2024-01-01", tz=NY)
    return df


def price_normalize(df):
    df = df.copy()
    m = df.inst.map(MULT); px = df.inst.map(TODAY)
    df["net_today"] = ((df.side * (df.exit - df.entry) + 2 * ADV) * px / df.entry - 2 * ADV) * m - FEE
    df["risk_today"] = df.stop_pct * px * m + 1.0 + 0.75 * m
    return df


def route(df):
    """Research post-hoc 1-position routing (dplus_1 route()): sorted by decision then priority; skip a trade whose decision falls inside
    [entry, exit) of one of the last six accepted trades."""
    acc = []; keep = []
    for r in df.sort_values(["dec", "prio"]).itertuples():
        if any(a_in <= r.dec < a_out for a_in, a_out in acc[-6:]):
            continue
        acc.append((r.tin, r.tout)); keep.append(r.Index)
    return df.loc[keep]


def day_series(df, stop=None, col="net_today"):
    kept = []
    for r in df.sort_values("tin").itertuples():
        if stop is not None and sum(getattr(q, col) for q in kept if q.tout.date() == r.tin.date() and q.tout <= r.tin) <= -stop:
            continue
        kept.append(r)
    k = pd.DataFrame(kept)
    return k.groupby(k.tout.dt.date)[col].sum().sort_index()


def account(day, cushion=1000.0):
    bal = 0.0; good = 0; pays = []; blow = 0; dll = 0
    for p in day.to_numpy():
        if p <= -1000: dll += 1
        bal += max(p, -1000.0)
        if bal <= -2000.0: blow += 1; bal = 0.0; good = 0; continue
        good += p >= 150
        if good >= 5:
            w = bal - cushion
            if w > 0: pays.append(w); bal -= w; good = 0
    return dict(payouts_per_year=round(len(pays) / 14, 2), median_payout=round(float(np.median(pays)), 0) if pays else 0,
                blowups_per_year=round(blow / 14, 2), dll_days=dll)


def multistart(day, months=12, cushion=1000.0):
    s = pd.Series(day.to_numpy(), index=pd.to_datetime(pd.Series(day.index).astype(str)).to_numpy())
    out = []
    for s0 in pd.date_range("2010-07-01", "2023-01-01", freq="MS"):
        w = s[(s.index >= s0) & (s.index < s0 + pd.DateOffset(months=months))]
        bal = 0.0; good = 0; pays = 0; breach = False; dll = False
        for p in w.to_numpy():
            dll |= p <= -1000; bal += max(p, -1000.0)
            if bal <= -2000.0: breach = True; break
            good += p >= 150
            if good >= 5 and bal - cushion > 0: pays += 1; bal = cushion; good = 0
        out.append((breach, dll, pays))
    o = pd.DataFrame(out, columns=["breach", "dll", "pays"])
    return dict(p_breach_12m=round(float(o.breach.mean()), 3), p_dll_day_12m=round(float(o.dll.mean()), 3),
                payouts_12m_median=float(o.pays.median()), payouts_12m_p10_p90=[float(o.pays.quantile(.1)), float(o.pays.quantile(.9))])


def summ(day, cushion=1000.0):
    yrs = pd.DatetimeIndex(pd.to_datetime(pd.Series(day.index).astype(str))).year
    q = pd.Series((day >= 150).to_numpy(), index=yrs).groupby(level=0).sum().reindex(range(2010, 2024), fill_value=0)
    yr_net = pd.Series(day.to_numpy(), index=yrs).groupby(level=0).sum().reindex(range(2010, 2024), fill_value=0)
    out = dict(days150_per_year=round(float(q.mean()), 1), days150_2010_19=round(float(q[q.index < 2020].mean()), 1),
               days150_2020_23=round(float(q[q.index >= 2020].mean()), 1), net_per_year=round(float(day.sum()) / 14, 0),
               pos_years=f"{int((yr_net > 0).sum())}/14", worst_day=round(float(day.min()), 0),
               max_drawdown=round(float((day.cumsum().cummax() - day.cumsum()).max()), 0))
    out.update(account(day, cushion)); out.update(multistart(day, cushion=cushion))
    return out


def fmt(name, r):
    return (f"{name:44s} $150d/yr {r['days150_per_year']:>5} ({r['days150_2010_19']}/{r['days150_2020_23']}) | pay/yr {r['payouts_per_year']:>5} "
            f"med {r['median_payout']:>6} | 12m breach {r['p_breach_12m']:>5} dll {r['p_dll_day_12m']:>5} | pays/12m {r['payouts_12m_median']} "
            f"{r['payouts_12m_p10_p90']} | net/yr {r['net_per_year']:>7} | worst {r['worst_day']:>6} | maxDD {r['max_drawdown']:>6} | yrs+ {r['pos_years']}")
