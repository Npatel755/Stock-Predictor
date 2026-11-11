"""tsm_1 (Claude fork C, 2026-11-11): daily time-series momentum on gold / silver / crude / bitcoin micros, re-entered every evening, as an
UNCORRELATED stream for the $50K Static Combine. TRAINING 2010-23 only.

WHY: book-level levers are exhausted (bookx_1). With corr ~0 the combined daily Sharpe is ~sqrt(0.1506^2 + SR_new^2). Published effect:
time-series momentum across futures (Moskowitz, Ooi & Pedersen 2012; Hurst, Ooi & Pedersen 2017). Not tested here before (metals_btc_1
covered session drift and intraday 60-min trend only). Fork A covers ZN / FX.

TRADABILITY (web, 2026-11-11): Topstep help center / TopstepX FAQ list MGC (10 oz), SIL (1,000 oz), MCL (100 bbl), MBT (0.1 BTC) as
permitted micros. Tick values used: MGC 0.10 = $1, SIL 0.005 = $5, MCL 0.01 = $1, MBT $5 = $0.50.
DATA: data/market/crossasset_train GC.v.0 / SI.v.0 / BTC.v.0 hourly, CL.v.0 1-minute aggregated to hourly (Databento, bar-start stamps,
volume-rolled front month). Assert nothing at or after 2024-01-01.

PRE-DECLARED (written before any result).
  Trade: enter at the OPEN of the 18:00 ET hourly bar after a session's close, exit at the CLOSE of the next session's 15:00 ET bar (16:00 ET,
  inside Topstep's 16:10 ET flat rule; hourly data has no 15:55 print). One round trip per session. Skipped: entry more than 24 h before the
  exit bar (holidays), or any contract change (instrument_id change, or a CL hour mixing two ids) between entry and exit bars.
  Session close = close of the 15:00 ET bar. Daily return for the SIGNAL = sum of within-contract hourly log returns between consecutive
  session closes (returns across a contract change are set to 0 = ratio back-adjustment). Signal for the trade entering after session D's
  close = sign of the sum of the last L daily returns up to D (no later data). L in {20, 60, 120, 250} sessions.
  P&L at each market's LAST TRAINING CLOSE price level (end-2023; the % move re-expressed, like the book's today-price convention but without
  any 2024+ data): gross = side x (exit / entry - 1) x P* x multiplier x micros.
  Costs per micro round trip: 2 ticks per side (1 spread + 1 slippage) + 1 extra tick on the 18:00 entry = 5 ticks, + $1.50 commission.
  MAE per trade from the hourly lows / highs over the held bars (incl. costs, capped at the trade's net).
  sd60 = sd of the last 60 daily (log) returns x P* x multiplier ($ per micro per session), known at entry.
  Sizes: family F = 1 micro; family V = clip(round(T / sd60), 1, 3) micros, T = median over the 4 markets of their full-training 1-micro
  daily $ sd (one constant). Nominal risk_today = 2 x sd60 x micros.
  Start: GC / SI / CL trades from 2011-06-01 for every L (common start, 250 sessions of history); BTC from 2019-01-02 (data from 2017-12).
  PORTFOLIO = sum of the markets trading that session (equal weight). 8 portfolio cells (4 L x F / V).
  Per cell and per market: net per half (exit < / >= 2017-01-01), profit factor, years positive, gross, costs, cost share of gross.
  Placebo (portfolio cells): 200 random-sign draws per market-session trade (same costs), seed 11.
  SCREEN: eval_harness.screen on the PORTFOLIO daily series (by exit date). Only screen passers go to Harness().pass_rate(extra=ledger)
  as a concurrent stream, nsize in {F1, F2}; 2-fold (pick on 2010-16 starts, report on 2017-23 and vice versa); ADOPT only if both
  out-of-fold halves >= 55.5 / 66.6.
"""
import json, sys
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts"))
from eval_harness import screen, H1_END

NY = "America/New_York"; D = ROOT / "data/market/crossasset_train"
SPEC = {"GC": dict(mult=10.0, tick=0.10, tv=1.0, f="GC_v_0_ohlcv1h_2010_2023", start="2011-06-01"),
        "SI": dict(mult=1000.0, tick=0.005, tv=5.0, f="SI_v_0_ohlcv1h_2010_2023", start="2011-06-01"),
        "CL": dict(mult=100.0, tick=0.01, tv=1.0, f="CL_v_0_ohlcv1m_2010_2023", start="2011-06-01"),
        "BTC": dict(mult=0.1, tick=5.0, tv=0.5, f="BTC_v_0_ohlcv1h_2010_2023", start="2019-01-02")}
LS = (20, 60, 120, 250); COMM = 1.50; OUTP = ROOT / "reports/TSM_1_DAILY_TREND_TRAINING.json"


def hourly(m):
    d = pd.read_parquet(D / f"{SPEC[m]['f']}.parquet")
    assert d.index.max() < pd.Timestamp("2024-01-01", tz="UTC"), "post-2023 data present"
    if m == "CL":
        d = d.reset_index(); d["h"] = d.ts_event.dt.floor("h")
        g = d.groupby("h", sort=True)
        d = pd.DataFrame(dict(open=g.open.first(), high=g.high.max(), low=g.low.min(), close=g.close.last(),
                              instrument_id=g.instrument_id.last(), mixed=g.instrument_id.nunique() > 1))
    else:
        d = d[["open", "high", "low", "close", "instrument_id"]].copy(); d["mixed"] = False; d.index.name = "h"
    d = d.sort_index(); d["et"] = d.index.tz_convert(NY)
    same = (d.instrument_id == d.instrument_id.shift(1)) & ~d.mixed & ~d.mixed.shift(1, fill_value=False)
    d["lr"] = np.where(same, np.log(d.close / d.close.shift(1)), 0.0); d["lr"] = d.lr.fillna(0.0)
    return d.reset_index()


def trades(m):
    s = SPEC[m]; d = hourly(m); et = d.et; hr = et.dt.hour.to_numpy()
    cl_idx = np.nonzero(hr == 15)[0]                            # session closes (15:00 bar, closes 16:00 ET)
    cl_date = et.iloc[cl_idx].dt.date.to_numpy()
    _, first = np.unique(cl_date, return_index=True); cl_idx = cl_idx[first]; cl_date = cl_date[first]
    cum = d.lr.cumsum().to_numpy(); r = np.diff(cum[cl_idx], prepend=np.nan)  # daily return between consecutive closes
    Pstar = float(d.close.iloc[cl_idx[-1]]); ent18 = np.nonzero(hr == 18)[0]
    O, Hh, Lw, C, iid, mx = (d[c].to_numpy() for c in ("open", "high", "low", "close", "instrument_id", "mixed"))
    rows = []
    for j in range(1, len(cl_idx)):
        xi = cl_idx[j]; pi = cl_idx[j - 1]
        k = np.searchsorted(ent18, pi + 1);
        if k >= len(ent18): break
        ei = ent18[k]
        if ei >= xi or (d.h.iloc[xi] - d.h.iloc[ei]) > pd.Timedelta(hours=23): continue
        if len(np.unique(iid[ei:xi + 1])) != 1 or mx[ei:xi + 1].any(): continue
        hist = r[1:j]                                            # daily returns up to the previous close (session j-1)
        if len(hist) < 60: continue
        sd60 = float(np.std(hist[-60:], ddof=1)) * Pstar * s["mult"]
        rec = dict(m=m, tin=et.iloc[ei], tout=None, xdate=cl_date[j], entry=float(O[ei]), exit=float(C[xi]), lo=float(Lw[ei:xi + 1].min()), hi=float(Hh[ei:xi + 1].max()),
                   sd60=sd60, P=Pstar)
        for L in LS: rec[f"sig{L}"] = float(np.sign(hist[-L:].sum())) if len(hist) >= L else np.nan
        rows.append(rec)
    t = pd.DataFrame(rows)
    t["tin"] = pd.to_datetime(t.tin); t["tout"] = [pd.Timestamp(str(x) + " 16:00", tz=NY) for x in t.xdate]
    t = t[t.xdate >= pd.Timestamp(s["start"]).date()].reset_index(drop=True)
    t["cost"] = 5 * s["tv"] + COMM; t["pct"] = t.exit / t.entry - 1.0
    t["daily_sd_1"] = float(np.nanstd(r[1:], ddof=1)) * Pstar * s["mult"]
    return t


def cell_trades(T, L, fam, target):
    out = []
    for m, t in T.items():
        x = t[t[f"sig{L}"].notna() & (t[f"sig{L}"] != 0)].copy(); s = SPEC[m]
        x["side"] = x[f"sig{L}"]; x["q"] = 1.0 if fam == "F" else np.clip(np.round(target / x.sd60), 1, 3)
        x["gross"] = x.side * x.pct * x.P * s["mult"] * x.q; x["costs"] = x.cost * x.q; x["net"] = x.gross - x.costs
        worst = np.where(x.side > 0, x.lo / x.entry - 1.0, 1.0 - x.hi / x.entry)
        x["mae"] = np.minimum(x.net, worst * x.P * s["mult"] * x.q - x.costs); x["risk_today"] = 2.0 * x.sd60 * x.q
        out.append(x)
    return pd.concat(out, ignore_index=True)


def stats(x):
    w = x.net[x.net > 0].sum(); l = -x.net[x.net < 0].sum(); yrs = x.groupby(pd.to_datetime(x.xdate.astype(str)).dt.year).net.sum()
    h1 = x.xdate < H1_END; g = float(x.gross.sum())
    return dict(n=len(x), net=round(float(x.net.sum()), 0), net_h1=round(float(x.net[h1].sum()), 0), net_h2=round(float(x.net[~h1].sum()), 0),
                pf=round(float(w / l), 3) if l > 0 else None, years_pos=f"{int((yrs > 0).sum())}/{len(yrs)}", gross=round(g, 0),
                costs=round(float(x.costs.sum()), 0), cost_share_of_gross=round(float(x.costs.sum()) / g, 2) if g > 0 else "gross<=0")


T = {m: trades(m) for m in SPEC}
for m, t in T.items(): print(m, "trades", len(t), t.xdate.min(), t.xdate.max(), "P*", round(t.P.iloc[0], 2), "1-micro daily sd $", round(t.daily_sd_1.iloc[0], 1), flush=True)
TARGET = float(np.median([t.daily_sd_1.iloc[0] for t in T.values()])); print("V target $ sd", round(TARGET, 1), flush=True)
out = dict(target_sd=TARGET, markets={m: dict(P_star=float(t.P.iloc[0]), daily_sd_1micro=float(t.daily_sd_1.iloc[0]), sessions=len(t)) for m, t in T.items()}, cells={})
rng = np.random.default_rng(11); LED = {}
for fam in ("F", "V"):
    for L in LS:
        x = cell_trades(T, L, fam, TARGET); nm = f"{fam}_L{L}"; LED[nm] = x
        c = dict(portfolio=stats(x), per_market={m: stats(x[x.m == m]) for m in SPEC})
        g, cs = x.gross.to_numpy(), x.costs.to_numpy(); act = float(x.net.sum())
        c["placebo_beaten"] = int(sum(act > float((rng.choice([-1.0, 1.0], size=len(x)) * np.abs(g) * np.sign(g) - cs).sum()) for _ in range(200)))
        daily = x.groupby("xdate").net.sum(); c["screen"] = screen(daily, nm)
        out["cells"][nm] = c
        print(nm, json.dumps(dict(portfolio=c["portfolio"], placebo=c["placebo_beaten"], screen={k: c["screen"][k] for k in ("sr", "rho", "lift", "best_w", "screen_pass")},
                                  halves=c["screen"]["halves"], per_market={m: (v["net_h1"], v["net_h2"], v["pf"]) for m, v in c["per_market"].items()}), default=str), flush=True)
        OUTP.write_text(json.dumps(out, indent=1, default=str))

passers = [k for k, c in out["cells"].items() if c["screen"]["screen_pass"]]; out["screen_passers"] = passers
if not passers:
    out["result"] = "no portfolio cell passed the daily-Sharpe screen; no pass-rate run"; print(out["result"], flush=True)
else:
    from eval_harness import Harness
    H = Harness(); inc = H.pass_rate(); print("incumbent", inc, flush=True)
    assert inc["h1"]["pass_"] == 54.5 and inc["h2"]["pass_"] == 65.6
    cand = {}
    for nm in passers:
        x = LED[nm]; ex = pd.DataFrame(dict(tin=x.tin, tout=x.tout, per_micro=x.net, mae_per_micro=x.mae, risk_today=x.risk_today, n_contracts=1.0))
        for ns in ("F1", "F2"):
            cand[f"{nm}_{ns}"] = H.pass_rate(extra=ex, nsize=ns); print("pass", nm, ns, cand[f"{nm}_{ns}"], flush=True)
    pA = max(cand, key=lambda k: cand[k]["h1"]["pass_"]); pB = max(cand, key=lambda k: cand[k]["h2"]["pass_"])
    onB, onA = cand[pA]["h2"], cand[pB]["h1"]
    out["pass_rate"] = dict(incumbent=inc, cells=cand, picked_on_A=pA, picked_on_B=pB, oof_h1=onA["pass_"], oof_h2=onB["pass_"],
                            adopt=bool(onA["pass_"] >= inc["h1"]["pass_"] + 1.0 and onB["pass_"] >= inc["h2"]["pass_"] + 1.0))
    print("result", {k: v for k, v in out["pass_rate"].items() if k != "cells"}, flush=True)
OUTP.write_text(json.dumps(out, indent=1, default=str))
for nm, x in LED.items():
    if nm in passers: x.to_csv(ROOT / f"reports/TSM_1_{nm}_TRADES_TRAINING.csv", index=False)
print("done", flush=True)
