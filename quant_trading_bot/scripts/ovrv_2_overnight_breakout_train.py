"""ovrv_2 (Claude fork B, 2026-11-11): overnight-session breakout / noise-band streams on MNQ and MES. TRAINING 2010-23 only.

Not repeats: the reopen-dip hold is the book's overnight leg; overnight_8 rejected Asia-return -> 03:00-open holds (timing of a
directional premium); gap_1 rejected Globex-range breaks at the RTH open. Untested: two-sided momentum INSIDE the overnight session around
the European open, where the book has no intraday trades (it can only overlap the overnight-dip leg).

PRE-DECLARED (written before any result).
Data: full-Globex 1-minute bars of NQ->MNQ and ES->MES (mass_1m_search 'train'). Session date = the RTH day that follows (bars from 18:00 ET
  belong to the next date). Minute index m from 18:00 ET (03:00 = 540, 09:25 = 925), window m in [0, 930). Kept sessions: Mon-Fri session
  date, first bar at m <= 5, >= 800 of 930 minutes present, one contract; missing minutes forward-filled (h = l = o = previous close, v = 0).
  Bar m closes at m + 1. Decision at the close of bar m -> fill at the open of bar m + 1. Everything flat at the close of bar 924 (09:25 ET),
  before the RTH open, so these trades never overlap the book's RTH trades.
Costs: payout_lib per micro plus ONE EXTRA TICK PER SIDE for thin overnight books:
  per micro = ((side x (exit - entry) / entry x TODAY - 2 x 0.5 - 2 x 0.25) x MULT - $1). MAE on 1-minute highs/lows, same costs.
  risk_today = stop distance % x TODAY x MULT + 1 + 0.75 x MULT (engine formula; distance floor 0.05%).
CELLS (12):
  ORB_{inst}_{L}_{stop} (8): European-open range = bars [540, 540 + L), L in {15, 30} min. First 1-minute close above the range high ->
    long, below the low -> short (one trade per session, entries until bar 923). Resting stop at the opposite side (OPP) or the range
    midpoint (MID), walked on 1-minute bars, gap-through fills at the bar open. Exit at the 09:25 close. inst in {MNQ, MES}.
  BAND18_{inst} (2): eval_12 noise-area logic anchored at the 18:00 Globex open O: sigma(m) = mean over the previous 14 kept sessions of
    |close(m) / O - 1|; UB / LB = O x (1 +/- sigma); VWAP from 18:00; checks at the closes of 03:00, 03:30, ..., 09:00; trailing stop =
    closer of band / VWAP on the stop side, checked only at the 30-minute marks (published P mode); exit at the 09:25 close.
  BAND03_{inst} (2): the same anchored at the 03:00 open (moves measured from bar 540, VWAP from 03:00), checks 03:30 .. 09:00.
REPORTED per cell: n, net, mean, PF, years positive per half; random-side placebo (same entries/exits, 200 draws, seed 202);
  eval_harness.screen() on the daily series ($ per micro, session date).
GATE: screen_pass. Passers -> Harness().pass_rate(extra=ledger, nsize="F1") 2-fold (pick on 2010-16 starts, report on 2017-23 and vice
  versa); ADOPT only if both out-of-fold halves >= 55.5 / 66.6.
"""
import json, sys
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import mass_1m_search as m1
import payout_lib as pl
import eval_harness as eh

NY = "America/New_York"; H1_END = pd.Timestamp("2017-01-01").date(); START = pd.Timestamp("2010-06-07").date()
W = 930; EXIT = 924; LOOK = 14; XT = 0.25


def panel(inst):
    b = m1.load_bars(inst, 1, "2009-11-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close", "volume", "contract"]]
    assert b.timestamp_utc.max() < pd.Timestamp("2024-01-01", tz="UTC")
    t = b.timestamp_utc.dt.tz_convert(NY); hr = t.dt.hour.to_numpy(); mn = t.dt.minute.to_numpy()
    mi = np.where(hr >= 18, (hr - 18) * 60 + mn, (hr + 6) * 60 + mn)
    sd = (t.dt.normalize() + pd.to_timedelta((hr >= 18).astype(int), unit="D")).dt.date.to_numpy()
    keep = mi < W; b = b[keep].copy(); b["m"] = mi[keep]; b["sd"] = sd[keep]; b["t0"] = (t[keep] - pd.to_timedelta(mi[keep], unit="m"))
    out = []
    for d, g in b.groupby("sd", sort=True):
        if pd.Timestamp(d).dayofweek >= 5 or len(g) < 800 or g.m.iloc[0] > 5 or g.contract.nunique() != 1: continue
        g = g.drop_duplicates("m").set_index("m").reindex(range(W))
        c = g.close.ffill().bfill().to_numpy(float)
        o = np.where(np.isnan(g.open.to_numpy(float)), c, g.open.to_numpy(float))
        h = np.where(np.isnan(g.high.to_numpy(float)), c, g.high.to_numpy(float)); l = np.where(np.isnan(g.low.to_numpy(float)), c, g.low.to_numpy(float))
        v = g.volume.fillna(0).to_numpy(float)
        out.append(dict(d=d, o=o, h=h, l=l, c=c, v=v, t0=g.t0.dropna().iloc[0]))
    return out


def mk(inst, x, side, ein, e, px, j_exit, kind, stop_pct, why):
    T, M = pl.TODAY[inst], pl.MULT[inst]
    hi = j_exit if kind == "open" else j_exit + 1
    seg_l = np.append(x["l"][ein:hi], px); seg_h = np.append(x["h"][ein:hi], px)
    worst = (seg_l.min() - e) / e if side > 0 else (e - seg_h.max()) / e
    pm = ((side * (px - e) / e * T - 2 * pl.ADV - 2 * XT) * M - pl.FEE)
    mae = min(pm, (min(0.0, worst) * T - pl.ADV - XT) * M)
    return dict(inst=inst, side=side, entry=e, exit=px, per_micro=pm, mae_per_micro=mae, why=why,
                tin=x["t0"] + pd.Timedelta(minutes=ein), tout=x["t0"] + pd.Timedelta(minutes=hi),
                risk_today=max(stop_pct, 0.0005) * T * M + 1.0 + 0.75 * M)


def orb(days, inst, L, stop_kind):
    rows = []
    for x in days:
        if x["d"] < START: continue
        HR = x["h"][540:540 + L].max(); LR = x["l"][540:540 + L].min(); mid = (HR + LR) / 2
        for j in range(540 + L, EXIT):
            side = 1 if x["c"][j] > HR else (-1 if x["c"][j] < LR else 0)
            if not side: continue
            ein = j + 1; e = x["o"][ein]; stop = (LR if side > 0 else HR) if stop_kind == "OPP" else mid; done = None
            for k in range(ein, EXIT + 1):
                if side > 0 and x["l"][k] <= stop: done = (k, min(stop, x["o"][k])); break
                if side < 0 and x["h"][k] >= stop: done = (k, max(stop, x["o"][k])); break
            sp = abs(e - stop) / e
            rows.append(mk(inst, x, side, ein, e, done[1], done[0], "open", sp, "stop") if done else
                        mk(inst, x, side, ein, e, x["c"][EXIT], EXIT, "close", sp, "eod"))
            break
    return pd.DataFrame(rows)


def band(days, inst, anchor):
    a0 = 0 if anchor == 18 else 540; checks = [a0 + 539 - a0 + 30 * k for k in range(13)] if anchor == 18 else [569 + 30 * k for k in range(12)]
    mv = np.array([np.abs(x["c"][a0:] / x["o"][a0] - 1.0) for x in days])   # move from the anchor at each minute (index m - a0)
    rows = []
    for i in range(LOOK, len(days)):
        x = days[i]
        if x["d"] < START: continue
        O = x["o"][a0]; sig = mv[i - LOOK:i].mean(axis=0)
        typ = (x["h"] + x["l"] + x["c"]) / 3.0; vv = x["v"].copy(); vv[:a0] = 0.0
        cv = np.cumsum(vv); vw = np.where(cv > 0, np.cumsum(typ * vv) / np.maximum(cv, 1e-9), x["c"])
        pos = 0; ein = None; e = None; sp = None
        for m in checks:
            p = x["c"][m]; s_ = sig[m - a0]; UB, LB = O * (1 + s_), O * (1 - s_)
            if pos:
                st = (max(UB, vw[m]) if vw[m] < p else UB) if pos > 0 else (min(LB, vw[m]) if vw[m] > p else LB)
                if (pos > 0 and p <= st) or (pos < 0 and p >= st):
                    rows.append(mk(inst, x, pos, ein, e, x["o"][m + 1], m + 1, "open", sp, "check")); pos = 0
            if not pos and m + 1 < EXIT:
                side = 1 if p > UB else (-1 if p < LB else 0)
                if side:
                    pos = side; ein = m + 1; e = x["o"][ein]
                    st = (max(UB, vw[m]) if vw[m] < p else UB) if pos > 0 else (min(LB, vw[m]) if vw[m] > p else LB); sp = abs(e - st) / e
        if pos: rows.append(mk(inst, x, pos, ein, e, x["c"][EXIT], EXIT, "close", sp, "eod"))
    return pd.DataFrame(rows)


def stats(t):
    w = t.per_micro[t.per_micro > 0].sum(); l = -t.per_micro[t.per_micro < 0].sum(); yrs = t.groupby(t.tout.dt.year).per_micro.sum()
    return dict(n=len(t), net=round(float(t.per_micro.sum()), 0), mean=round(float(t.per_micro.mean()), 2),
                pf=round(float(w / l), 3) if l > 0 else None, years_pos=f"{int((yrs > 0).sum())}/{len(yrs)}")


def placebo(t, inst, n=200, seed=202):
    rng = np.random.default_rng(seed); e, x = t.entry.to_numpy(), t.exit.to_numpy(); act = t.per_micro.sum(); beat = 0
    T, M = pl.TODAY[inst], pl.MULT[inst]
    for _ in range(n):
        s = rng.choice([-1, 1], size=len(t)); beat += int(act > ((s * (x - e) / e * T - 2 * pl.ADV - 2 * XT) * M - pl.FEE).sum())
    return beat


out = {"cells": {}}; LED = {}
for inst in ("MNQ", "MES"):
    days = panel(inst); print(inst, "kept sessions", len(days), days[0]["d"], days[-1]["d"], flush=True)
    cells = [(f"ORB_{inst}_{L}_{sk}", lambda L=L, sk=sk: orb(days, inst, L, sk)) for L in (15, 30) for sk in ("OPP", "MID")] + \
            [(f"BAND{a}_{inst}", lambda a=a: band(days, inst, a)) for a in (18, 3)]
    for name, f in cells:
        t = f(); t = t[t.tout.dt.date >= START].reset_index(drop=True)
        assert t.tout.max() < pd.Timestamp("2024-01-01", tz=NY)
        h1 = t.tout.dt.date < H1_END; daily = t.per_micro.groupby(t.tout.dt.date).sum()
        c = dict(h1=stats(t[h1]), h2=stats(t[~h1]), all=stats(t), placebo_beaten=placebo(t, inst), exits=t.why.value_counts().to_dict(),
                 med_risk=round(float(t.risk_today.median()), 0), screen=eh.screen(daily, name))
        out["cells"][name] = c; LED[name] = t; sc = c["screen"]
        print(name, c["h1"], c["h2"], "placebo", c["placebo_beaten"], "| screen sr", sc["sr"], "rho", sc["rho"], "lift", sc["lift"],
              {h: sc["halves"][h]["lift_at_best_w"] for h in ("h1", "h2")}, "PASS" if sc["screen_pass"] else "fail", flush=True)
    del days

passers = [k for k, c in out["cells"].items() if c["screen"]["screen_pass"]]; out["screen_passers"] = passers
if passers:
    Hn = eh.Harness(); inc = Hn.pass_rate(); out["incumbent"] = inc; print("incumbent", inc, flush=True)
    pr = {}
    for k in passers:
        L_ = LED[k][["tin", "tout", "per_micro", "mae_per_micro", "risk_today"]].assign(n_contracts=1.0)
        pr[k] = Hn.pass_rate(extra=L_, nsize="F1"); print("pass_rate", k, pr[k], flush=True)
    out["pass_rate"] = pr
    pA = max(pr, key=lambda k: pr[k]["h1"]["pass_"]); pB = max(pr, key=lambda k: pr[k]["h2"]["pass_"])
    out["result"] = dict(picked_on_A=pA, oof_h2=pr[pA]["h2"], picked_on_B=pB, oof_h1=pr[pB]["h1"],
                         adopt=bool(pr[pB]["h1"]["pass_"] >= inc["h1"]["pass_"] + 1.0 and pr[pA]["h2"]["pass_"] >= inc["h2"]["pass_"] + 1.0))
    print("result", out["result"], flush=True)
else:
    print("no cell passed the screen", flush=True)
(ROOT / "reports/OVRV_2_OVERNIGHT_BREAKOUT_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
