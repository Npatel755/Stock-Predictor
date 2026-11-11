"""xmkt_zn (Claude fork A, 2026-11-11): 10-Year Note (ZN) intraday streams as a NEW evaluation sleeve. TRAINING 2010-23 only.

DATA: data/market/crossasset_train/ZN_c_0_ohlcv1h_2010_2023.parquet (Databento ZN.c.0, 1-hour bars, ts_event = bar START, UTC). Unadjusted
calendar-roll continuous: a session is used only if every bar it needs has one instrument_id; the prior close PC is replaced by the
open when the contract changed; TSMOM returns skip roll days.
TOPSTEP: ZN is a permitted Combine product (help.topstep.com "When and What Products Can I Trade?", read 2026-11-11); flat by 3:10 PM CT
(16:10 ET); reopen 5:00 PM CT (18:00 ET). No micro ZN is listed, so 1 unit = 1 ZN ($1,000 per point, tick 1/64 = $15.625).
COSTS (per contract): 1.5 ticks adverse per side ($23.44) + $2.62 commission per side (Topstep fee page) -> $52.12 round trip.
MAE per contract from the held bars' highs/lows (the entry bar's full range counts: conservative). Stops on hourly bars fill at the stop
or the bar open if gapped through (never better). risk_today = stop distance x $1,000 + $52.12.
ET hour h = the bar starting at h:00 ET. Day session bars 8..14 (08:00-15:00 ET), bar 15 = 15:00-16:00.
CELLS (10, pre-declared, fixed before any result):
  NOISE_15 / NOISE_16  Zarattini-style band on hourly bars: O = 08:00 open, sigma(h) = 14-session mean |close(h)/O - 1|, UB/LB around
                        max/min(O, PC); checks at the closes of bars 8..13; long > UB / short < LB at the next open; trailing stop = the closer
                        of band / VWAP (from 08:00, typical price x volume) on the stop side, checked at hourly closes; flat at 15:00 / 16:00.
  ORB_1 / ORB_2         range = bar 8 (08:00-09:00, holds the 08:30 releases) / bars 8-9; first close beyond it (until the 14:00 close) -> enter
                        next open, stop = other side of the range, one trade per day, flat at 15:00.
  TSMOM_20_D / TSMOM_60_D / TSMOM_20_ON / TSMOM_60_ON   direction = sign of the sum of daily (15:00-to-15:00 ET) returns over the last N
                        sessions (roll days skipped); D = hold 08:00 open -> 15:00 close; ON = 18:00 ET reopen -> 15:00 close next day;
                        stop = 1.0 x ATR20 (mean 08:00-15:00 range of the last 20 sessions), checked every bar.
  IM_1 / IM_2           intraday momentum: sign of PC -> 09:00 close (IM_1) or PC -> 14:00 close (IM_2) return; trade bar 14 (14:00-15:00)
                        in that direction; stop 0.5 x ATR20.
GATES: standalone net, PF per half (2010-16 / 2017-23), years positive and a 200-draw random-side placebo (seed 7) are REPORTED.
  SCREEN = eval_harness.screen on the daily $ per contract series (screen_pass: lift >= +0.007 and > 0 in both halves at the best weight).
  Only screen passers run Harness().pass_rate(extra=ledger, nsize F1 / F2): pick on 2010-16 starts, report on 2017-23, and vice versa;
  ADOPT only if both out-of-fold halves >= 55.5 / 66.6.
"""
import json, sys
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts"))
import eval_harness as eh

NY = "America/New_York"; PT = 1000.0; TICK = 1.0 / 64; ADV = 1.5 * TICK; COM = 2.62; RT = 2 * (ADV * PT + COM)
H1_END = pd.Timestamp("2017-01-01").date()

z = pd.read_parquet(ROOT / "data/market/crossasset_train/ZN_c_0_ohlcv1h_2010_2023.parquet")
assert z.index.max() < pd.Timestamp("2024-01-01", tz="UTC")
et = z.index.tz_convert(NY); z = z.assign(d=et.date, h=et.hour, ts=et)
BAR = {(d, h): r for d, h, r in zip(z.d, z.h, z[["open", "high", "low", "close", "volume", "instrument_id", "ts"]].itertuples(index=False))}
DATES = sorted(d for d in set(z.d) if pd.Timestamp(d).dayofweek < 5)


def day_bars(d, hours):
    rows = [BAR.get((d, h)) for h in hours]
    if any(r is None for r in rows) or len({r.instrument_id for r in rows}) != 1: return None
    return rows


SESS = []   # (date, bars 8..15, previous good date's 15:00 close if same contract else None)
prev = None
for d in DATES:
    b = day_bars(d, range(8, 16))
    if b is None: continue
    pc = prev[1][6].close if (prev is not None and prev[1][6].instrument_id == b[0].instrument_id and (d - prev[0]).days <= 4) else None
    SESS.append((d, b, pc)); prev = (d, b)
print("ZN sessions with bars 08-16 ET on one contract:", len(SESS), SESS[0][0], SESS[-1][0], flush=True)
RNG = np.array([max(r.high for r in b[:7]) - min(r.low for r in b[:7]) for _, b, _ in SESS])
ATR20 = pd.Series(RNG).rolling(20).mean().shift(1).to_numpy()          # past sessions only


def trade(rows, side, e, stop, held, x, why, tin, tout):
    lo = min([r.low for r in held] + [x]); hi = max([r.high for r in held] + [x])
    worst = (lo - e) if side > 0 else (e - hi)
    pnl = side * (x - e) * PT - RT
    rows.append(dict(tin=tin, tout=tout, side=side, entry=e, exit=x, per_micro=pnl, mae_per_micro=min(pnl, worst * PT - RT / 2),
                     risk_today=abs(e - stop) * PT + RT, why=why))


def walk(rows, side, e, stop, bars, tin):
    """Hold from the open of bars[0] to the close of bars[-1] with a resting stop; returns after recording the trade."""
    for j, r in enumerate(bars):
        if (side > 0 and r.low <= stop) or (side < 0 and r.high >= stop):
            x = min(stop, r.open) if side > 0 else max(stop, r.open)
            trade(rows, side, e, stop, bars[:j + 1], x, "stop", tin, r.ts + pd.Timedelta(minutes=30)); return
    trade(rows, side, e, stop, bars, bars[-1].close, "time", tin, bars[-1].ts + pd.Timedelta(hours=1))


def noise(last):
    rows = []; mv = []
    for i, (d, b, pc) in enumerate(SESS):
        O = b[0].open; mv.append([abs(b[k].close / O - 1) for k in range(7)])
        if i < 14: continue
        sig = np.mean(mv[i - 14:i], axis=0); PC = pc if pc is not None else O
        UB = max(O, PC) * (1 + sig); LB = min(O, PC) * (1 - sig)
        tp = np.array([(r.high + r.low + r.close) / 3 for r in b]); v = np.array([r.volume for r in b], float)
        vw = np.cumsum(tp * v) / np.maximum(np.cumsum(v), 1e-9)
        pos = 0; e = None; ein = None
        for k in range(0, 6):           # checks at the closes of bars 8..13 (index 0..5)
            p = b[k].close
            if pos:
                s = (max(UB[k], vw[k]) if vw[k] < p else UB[k]) if pos > 0 else (min(LB[k], vw[k]) if vw[k] > p else LB[k])
                if (pos > 0 and p <= s) or (pos < 0 and p >= s):
                    trade(rows, pos, e, stop0, b[ein:k + 1], b[k + 1].open, "check", b[ein].ts, b[k + 1].ts); pos = 0
            if not pos:
                side = 1 if p > UB[k] else (-1 if p < LB[k] else 0)
                if side:
                    pos = side; ein = k + 1; e = b[ein].open
                    stop0 = (max(UB[k], vw[k]) if vw[k] < p else UB[k]) if side > 0 else (min(LB[k], vw[k]) if vw[k] > p else LB[k])
        if pos:
            end = 6 if last == 15 else 7
            trade(rows, pos, e, stop0, b[ein:end + 1], b[end].close, "eod", b[ein].ts, b[end].ts + pd.Timedelta(hours=1))
    return rows


def orb(nbars):
    rows = []
    for d, b, pc in SESS:
        H = max(r.high for r in b[:nbars]); L = min(r.low for r in b[:nbars])
        for k in range(nbars - 1, 6):   # closes up to the 14:00 close (index 5); entry at the next open
            p = b[k].close
            side = 1 if p > H else (-1 if p < L else 0)
            if side and k + 1 <= 6:
                walk(rows, side, b[k + 1].open, L if side > 0 else H, b[k + 1:7], b[k + 1].ts); break
    return rows


def tsmom(N, hold):
    rows = []; ret = []
    for i, (d, b, pc) in enumerate(SESS):
        sig = np.nansum(ret[-N:]) if len(ret) >= N else None
        if sig is not None and sig != 0 and not np.isnan(ATR20[i]):
            side = 1 if sig > 0 else -1
            if hold == "D":
                e = b[0].open; walk(rows, side, e, e - side * ATR20[i], b[:7], b[0].ts)
            else:
                pd_ = SESS[i - 1][0] if i else None
                ob = [BAR.get((pd_, h)) for h in (18, 19, 20, 21, 22, 23)] + [BAR.get((d, h)) for h in range(0, 15)] if pd_ is not None else [None]
                if all(r is not None for r in ob) and len({r.instrument_id for r in ob}) == 1 and (d - pd_).days == 1:
                    e = ob[0].open; walk(rows, side, e, e - side * ATR20[i], ob, ob[0].ts)
        ret.append(np.nan if pc is None else (b[6].close / pc - 1))
    return rows


def im(which):
    rows = []
    for i, (d, b, pc) in enumerate(SESS):
        if pc is None or np.isnan(ATR20[i]): continue
        r = (b[0].close if which == 1 else b[5].close) / pc - 1
        if r == 0: continue
        side = 1 if r > 0 else -1; e = b[6].open; walk(rows, side, e, e - side * 0.5 * ATR20[i], b[6:7], b[6].ts)
    return rows


def stats(t):
    w = t.per_micro[t.per_micro > 0].sum(); l = -t.per_micro[t.per_micro < 0].sum(); yrs = t.groupby(t.tout.dt.year).per_micro.sum()
    return dict(n=len(t), net=round(float(t.per_micro.sum())), pf=round(float(w / l), 3) if l > 0 else None, years_pos=f"{int((yrs > 0).sum())}/{len(yrs)}")


def placebo(t, n=200, seed=7):
    rng = np.random.default_rng(seed); e, x = t.entry.to_numpy(), t.exit.to_numpy(); act = t.per_micro.sum(); beat = 0
    for _ in range(n):
        s = rng.choice([-1, 1], size=len(t)); beat += int(act > (s * (x - e) * PT - RT).sum())
    return beat


CELLS = {"NOISE_15": lambda: noise(15), "NOISE_16": lambda: noise(16), "ORB_1": lambda: orb(1), "ORB_2": lambda: orb(2),
         "TSMOM_20_D": lambda: tsmom(20, "D"), "TSMOM_60_D": lambda: tsmom(60, "D"), "TSMOM_20_ON": lambda: tsmom(20, "ON"),
         "TSMOM_60_ON": lambda: tsmom(60, "ON"), "IM_1": lambda: im(1), "IM_2": lambda: im(2)}
out = {"costs_rt_per_contract": RT, "cells": {}}; LED = {}
for name, f in CELLS.items():
    t = pd.DataFrame(f()); t = t[t.tout.dt.date >= pd.Timestamp("2010-06-07").date()].reset_index(drop=True)
    assert t.tout.max() < pd.Timestamp("2024-01-01", tz=NY)
    h1 = t.tout.dt.date < H1_END
    daily = t.groupby(t.tout.dt.date).per_micro.sum()
    c = dict(h1=stats(t[h1]), h2=stats(t[~h1]), placebo_beaten=placebo(t), med_risk=round(float(t.risk_today.median())),
             exits=t.why.value_counts().to_dict(), screen=eh.screen(daily, f"ZN_{name}"))
    out["cells"][name] = c; LED[name] = t
    s = c["screen"]; print(f"{name:12s} n {len(t):5d} net {c['h1']['net']:>8} / {c['h2']['net']:>8} PF {c['h1']['pf']} / {c['h2']['pf']} "
                           f"yrs {c['h1']['years_pos']} {c['h2']['years_pos']} plc {c['placebo_beaten']} | sr {s['sr']} rho {s['rho']} w {s['best_w']} "
                           f"lift {s['lift']} h1 {s['halves']['h1']['lift_at_best_w']} h2 {s['halves']['h2']['lift_at_best_w']} pass {s['screen_pass']}", flush=True)
    t.to_csv(ROOT / f"reports/xmkt_zn_{name}_trades_training.csv", index=False)

passers = [k for k, c in out["cells"].items() if c["screen"]["screen_pass"]]; out["screen_passers"] = passers
if passers:
    H = eh.Harness(); inc = H.pass_rate(); out["incumbent"] = inc; print("incumbent", inc, flush=True)
    res = {}
    for k in passers:
        for ns in ("F1", "F2"):
            res[f"{k}|{ns}"] = H.pass_rate(extra=LED[k], nsize=ns); print(k, ns, res[f"{k}|{ns}"], flush=True)
    pA = max(res, key=lambda q: res[q]["h1"]["pass_"]); pB = max(res, key=lambda q: res[q]["h2"]["pass_"])
    out["pass_rate"] = res; out["result"] = dict(picked_on_A=pA, oof_h2=res[pA]["h2"], picked_on_B=pB, oof_h1=res[pB]["h1"],
                                                 adopt=bool(res[pB]["h1"]["pass_"] >= 55.5 and res[pA]["h2"]["pass_"] >= 66.6))
    print("result", out["result"], flush=True)
(ROOT / "reports/xmkt_zn_training.json").write_text(json.dumps(out, indent=1, default=str))
