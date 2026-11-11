"""payout_5 (Claude, 2026-11-10): what does D+ do at TODAY's price level? TRAINING 2010-23 trades only, re-expressed in 2026 dollars.

PRE-DECLARED (before results):
  Finding that motivates it: on the live feed (2026-10-30..11-10, NQ ~27,980, ES ~7,584) the engine's $150-per-contract stop-risk budget
  blocks the Crabel and 60m-trend sleeves on 100% of RTH bars (median stop risk $384 / $492 per micro); only the MES 30m sleeve fits (52%).
  The budget is fixed in dollars, so it tightened as NQ's price rose (2.9% of price in 2012, 0.26% today). The deployed v4 / D+ ledgers can
  therefore trade almost only the MES sleeve today.
  Question: if the training R-distribution repeats at today's price level, what payout rate does a 1-micro, no-dollar-budget D+ give, and is
  the static $2,000 floor survivable when one micro's stop is ~$380?
  Method: run ag_arch_d_plus_v2 sleeves with no stop-risk budget (always 1 contract, research post-hoc routing, historical VIX filter) on
  2010-23. Re-express each trade at today's price: raw move (engine fills minus 2 ticks adverse per side) x (today's price / entry price),
  minus today's 2 ticks adverse per side and $1 commission. Check first that today's stop as % of price sits inside the training range.
  Cells: N1 all three sleeves at 1 micro | MES1 MES sleeve only at 1 micro (what the budget lets through today) | N1 + account stop $600 |
  N1 + account stop $400. Account: static -$2,000 floor, $1,000 DLL (realised), payout = 5 days >= $150 with a $1,000 cushion (W1).
  Report by era; no parameter is tuned on these results.
"""
import copy, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P = (ROOT / "scripts/dplus_7e_pilot.py").read_text(encoding="utf-8").split("\nout = {}")[0].split("\ntr = route(")[0]
ns = {"__file__": str(ROOT / "scripts/dplus_7e_pilot.py")}
exec(P, ns)
ep, OVR = ns["ep"], ns["OVR"]; d7 = ns["ns"]; bars_for = d7["bars_for"]; START = d7["ns"]["START"]
OVR.clear()


def _cboe(n):
    d = pd.read_csv(ROOT / f"data/external/{n}_History.csv"); d.index = pd.to_datetime(d.DATE, format="%m/%d/%Y"); return d.CLOSE.astype(float)
_j = pd.concat([_cboe("VIX").rename("vix"), _cboe("VIX3M").rename("vix3m")], axis=1).dropna().sort_index()
ep._VIX_CACHE["series"] = (_j.vix > _j.vix3m)

TODAY = {"MNQ": 27981.5, "MES": 7584.0}          # live feed close, 2026-11-10
LIVE_STOP_PCT = {"AG_CRABEL15_D_1c": 2.0 * 95.4 / 27981.5, "AG_TRD60_D_1c": 1.25 * 195.7 / 27981.5, "AG_MES_TRD30_D_1c": 1.25 * 22.8 / 7584.0}
MULT = {"MNQ": 2.0, "MES": 5.0}; ADV = 0.5; FEE = 1.0

spec = copy.deepcopy(ep.CANDIDATES["ag_arch_d_plus_v2"])
spec["sleeves"] = [dict(sl, risk_per_trade=1e9, max_open_risk=1e9) for sl in spec["sleeves"]]   # no dollar budget: always 1 contract
bars, atrs = {}, {}
for sl in spec["sleeves"]:
    b, mins, atr = bars_for(sl); bars.setdefault(ep.bars_key(sl), b); atrs[sl["name"]] = (atr, mins, float(sl["stop_atr"]), sl["instrument"])
runs = ep.run_routed(spec, bars, START)
NY = "America/New_York"
rows = []
for name, r in runs.items():
    atr, mins, k, inst = atrs[name]
    for t in r["trades"]:
        e, x, s = float(t["entry_price"]), float(t["exit_price"]), int(t["side"])
        dec = pd.Timestamp(t["entry_ts"]) - pd.Timedelta(minutes=mins); a = float(atr.get(dec, np.nan))
        raw = s * (x - e) + 2 * ADV                       # move before the engine's adverse fills
        today = (raw * TODAY[inst] / e - 2 * ADV) * MULT[inst] - FEE
        rows.append(dict(sleeve=name, inst=inst, tin=pd.Timestamp(t["entry_ts"]).tz_convert(NY), tout=pd.Timestamp(t["exit_ts"]).tz_convert(NY),
                         net_then=float(t["net"]), net_today=today, stop_pct=k * a / e, year=pd.Timestamp(t["entry_ts"]).year))
df = pd.DataFrame(rows).sort_values("tin")
assert df.tout.max() < pd.Timestamp("2024-01-01", tz=NY)

# ---- check: today's stop % inside the training range?
chk = {}
for name, g in df.groupby("sleeve"):
    q = g.stop_pct.quantile([0.1, 0.5, 0.9]).to_numpy()
    chk[name] = dict(train_stop_pct_p10_p50_p90=[round(100 * v, 3) for v in q], today_stop_pct=round(100 * LIVE_STOP_PCT[name], 3),
                     today_percentile_in_training=round(float((g.stop_pct <= LIVE_STOP_PCT[name]).mean()), 2),
                     by_era_median_pct={str(k): round(100 * float(v), 3) for k, v in g.groupby(pd.cut(g.year, [2009, 2015, 2019, 2023])).stop_pct.median().items()})


def day_series(sub, stop=None):
    sub = sub.sort_values("tin"); kept = []
    for _, r in sub.iterrows():
        if stop is not None and sum(q["net_today"] for q in kept if q["tout"].date() == r["tin"].date() and q["tout"] <= r["tin"]) <= -stop:
            continue
        kept.append(r)
    k = pd.DataFrame(kept)
    return k.groupby(k.tout.dt.date).net_today.sum().sort_index()


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


def summ(day):
    yrs = pd.DatetimeIndex(pd.to_datetime(pd.Series(day.index).astype(str))).year
    q = pd.Series((day >= 150).to_numpy(), index=yrs).groupby(level=0).sum().reindex(range(2010, 2024), fill_value=0)
    yr_net = pd.Series(day.to_numpy(), index=yrs).groupby(level=0).sum().reindex(range(2010, 2024), fill_value=0)
    out = dict(net_today_dollars=round(float(day.sum()), 0), net_per_year=round(float(day.sum()) / 14, 0), days150_per_year=round(float(q.mean()), 1),
               days150_2010_19=round(float(q[q.index < 2020].mean()), 1), days150_2020_23=round(float(q[q.index >= 2020].mean()), 1),
               pos_years=f"{int((yr_net > 0).sum())}/14", worst_day=round(float(day.min()), 0),
               max_drawdown=round(float((day.cumsum().cummax() - day.cumsum()).max()), 0))
    out.update(account(day))
    return out


cells = {"N1 all sleeves 1 micro": (df, None), "N1 + account stop $600": (df, 600.0), "N1 + account stop $400": (df, 400.0),
         "MES1 MES sleeve only (what the budget allows today)": (df[df.inst == "MES"], None)}
res = {"stop_pct_check": chk, "trades": int(len(df)), "net_then_1c": round(float(df.net_then.sum()), 2)}
for name, (sub, stop) in cells.items():
    res[name] = summ(day_series(sub, stop))

# ---- ADDENDUM (declared after the first table, before running it): today's volatility and multi-start breach odds
# R-rescale: each trade's move in stop units (R) times TODAY's stop in points (live median), i.e. today's elevated volatility persists.
stop_pts_today = {k: v * TODAY["MES" if "MES" in k else "MNQ"] for k, v in LIVE_STOP_PCT.items()}
df_r = df.copy()
for i, r in df_r.iterrows():
    pass
raw_r = []
for _, r in df.iterrows():
    stop_then_pts = r["stop_pct"] * (TODAY[r["inst"]] / TODAY[r["inst"]])  # placeholder to keep units explicit below
    raw_r.append(r)
df_r["R_mult"] = [(float(np.nan) if not np.isfinite(r.stop_pct) or r.stop_pct <= 0 else
                   ((r.net_today + FEE) / MULT[r.inst] + 2 * ADV) / (r.stop_pct * TODAY[r.inst])) for r in df.itertuples()]
df_r = df_r[np.isfinite(df_r.R_mult)].copy()
df_r["net_today"] = [(row.R_mult * stop_pts_today[row.sleeve] - 2 * ADV) * MULT[row.inst] - FEE for row in df_r.itertuples()]


def multistart(day, months=12, cushion=1000.0):
    s = pd.Series(day.to_numpy(), index=pd.to_datetime(pd.Series(day.index).astype(str)).to_numpy())
    starts = pd.date_range("2010-07-01", "2023-01-01", freq="MS"); out = []
    for s0 in starts:
        w = s[(s.index >= s0) & (s.index < s0 + pd.DateOffset(months=months))]
        bal = 0.0; good = 0; pays = 0; breach = False; dll = False
        for p in w.to_numpy():
            dll |= p <= -1000; bal += max(p, -1000.0)
            if bal <= -2000.0: breach = True; break
            good += p >= 150
            if good >= 5 and bal - cushion > 0: pays += 1; bal = cushion; good = 0
        out.append((breach, dll, pays))
    o = pd.DataFrame(out, columns=["breach", "dll", "pays"])
    return dict(starts=len(o), p_breach_12m=round(float(o.breach.mean()), 3), p_dll_day_12m=round(float(o.dll.mean()), 3),
                payouts_12m_median=float(o.pays.median()), payouts_12m_p10_p90=[float(o.pays.quantile(.1)), float(o.pays.quantile(.9))])


for name, sub_df, stop in (("PRICE-normalized, account stop $400", df, 400.0), ("TODAY-vol (R-rescaled), account stop $400", df_r, 400.0),
                           ("TODAY-vol (R-rescaled), account stop $600", df_r, 600.0), ("TODAY-vol (R-rescaled), MES only", df_r[df_r.inst == "MES"], None)):
    day = day_series(sub_df, stop)
    res[name] = dict(summ(day), **multistart(day))
# ---- ADDENDUM 2 (declared before running): re-set the per-micro stop-risk budget in TODAY's dollars, inside the price-normalized replay
# (which keeps training's ups and downs in % volatility). A trade is skipped when its today-dollar stop risk exceeds B. 1 micro, $400 stop.
df["risk_today"] = [r.stop_pct * TODAY[r.inst] * MULT[r.inst] + 1.0 + 3 * 0.25 * MULT[r.inst] for r in df.itertuples()]
for B in (200.0, 250.0, 300.0):
    sub = df[df.risk_today <= B]
    day = day_series(sub, 400.0)
    res[f"BUDGET ${int(B)}/micro today, price-normalized, stop $400"] = dict(summ(day), **multistart(day), trades=int(len(sub)),
        share_of_trades_kept=round(len(sub) / len(df), 3), kept_by_sleeve={k: int(v) for k, v in sub.groupby("sleeve").size().items()})
# ---- ADDENDUM 3 (declared before running): the DEPLOYED v4 at today's prices. Engine sizing = min(3, floor($450 / per-contract risk)),
# 0 -> skipped; gap-continuation Crabel x4/3; $600 account stop. Same price-normalized replay (training % volatility, today's price level).
crab_cont = {}
gsd = ns["gs"]
for r in df.itertuples():
    crab_cont[r.Index] = ("CRABEL" in r.sleeve)
df_v4 = df.copy()
qty = np.minimum(3, np.floor(450.0 / df_v4.risk_today)).astype(int)
side_gap = []
for r in df.itertuples():
    side_gap.append(False)
df_v4["qty_today"] = qty
df_v4 = df_v4[df_v4.qty_today >= 1].copy()
# continuation flag needs the trade side: re-derive from runs (same order as df rows built above)
side_map = {}
for name, rr in runs.items():
    for t in rr["trades"]:
        side_map[(name, pd.Timestamp(t["entry_ts"]).tz_convert(NY))] = int(t["side"])
cont = [("CRABEL" in r.sleeve) and side_map[(r.sleeve, r.tin)] * gsd.get(r.tin.date(), 0) >= 0 for r in df_v4.itertuples()]
df_v4["net_today"] = df_v4.net_today * df_v4.qty_today * np.where(cont, 4.0 / 3.0, 1.0)
day = day_series(df_v4, 600.0)
res["DEPLOYED v4 at today's prices (price-normalized)"] = dict(summ(day), **multistart(day), trades=int(len(df_v4)),
    qty_mix={int(k): int(v) for k, v in df_v4.qty_today.value_counts().items()}, kept_by_sleeve={k: int(v) for k, v in df_v4.groupby("sleeve").size().items()})
res["live_share_of_bars_within_budget_note"] = "live feed 2026-10-30..11-10: Crabel stop risk median $384, 60m trend $492, MES $147 per micro"
print(json.dumps(res, indent=1, default=str))
(ROOT / "reports/PAYOUT_5_PRICE_NORMALIZED_TRAINING.json").write_text(json.dumps(res, indent=1, default=str))
