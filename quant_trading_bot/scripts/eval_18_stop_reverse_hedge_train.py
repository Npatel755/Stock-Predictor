"""eval_18 (Claude, 2026-11-11): stop-and-reverse after the book's own stop-outs as a HEDGE stream for the evaluation. TRAINING only.

Idea (new perspective): bookx_1 found the book's fails are slow bleeds on choppy, false-breakout stretches. A stream that is active ONLY
after a book trade is stopped out, and trades the other way, should profit when a breakout fails and reverses and is idle on clean trend
days - so its correlation with the book should be negative. For a hedge the screen matters, not standalone profit: a stream raises the
combined daily Sharpe whenever its own Sharpe > rho x 0.151, which a negatively correlated stream can meet even near break-even.
Not tested before (lessons: no stop-and-reverse; training_session_research had only an unconditional 5-minute failed-breakout rule).

PRE-DECLARED (before any result). Source trades = the harness book's ROUTED intraday trades (pl.route of PRE, risk <= $300), MNQ and MES.
  Stop-out = side x (exit - entry) / entry <= -0.8 x stop_pct (exit at or through the stop).  At most one reversal per instrument per day
  (the first stop-out).  Reversal entry = open of the 1-minute bar AFTER the first bar that trades through the stopped fill (causal;
  the engine exit stamp can be the start of the stop bar), only if before 15:30
  ET; side = opposite of the stopped trade.  R = the stopped trade's stop distance in price (stop_pct x its entry).  Stop = entry -/+ R.
  Cells: X1 exit at the 15:59 bar close (stop active) | X2 +1R target or stop or 15:59 | X3 +2R target or stop or 15:59.
  1-minute path, stop checked before target within a bar (adverse first); stop fills at min(stop, bar open) for longs (max for shorts);
  targets fill at the target price. Costs and price normalisation exactly as payout_lib (2 x 0.5 pt adverse, $1 fee, today's prices).
GATE 1: eval_harness.screen(daily per micro) -> screen_pass (lift >= +0.007 and > 0 in both halves).
GATE 2 (gate-1 passers only): Harness.pass_rate(extra=ledger) with nsize F1 and K; 2-fold pick across all passer x nsize cells; adopt only
  if both out-of-fold halves >= 55.5 / 66.6.
"""
import json
import numpy as np, pandas as pd
from pathlib import Path
import eval_harness as eh

ROOT = Path(__file__).resolve().parents[1]; NY = "America/New_York"
H = eh.Harness(); pl = H.pl
R0 = pl.route(H.PRE[H.PRE.risk_today <= 300.0]).copy()
R0 = R0[R0.inst.isin(["MNQ", "MES"])]
R0["ret"] = R0.side * (R0.exit - R0.entry) / R0.entry
stops = R0[R0.ret <= -0.8 * R0.stop_pct].sort_values("tout")
stops = stops.groupby([stops.inst, stops.tout.dt.date], sort=False).head(1)
print("routed intraday trades", len(R0), "stop-outs used", len(stops), flush=True)

BAR = {}
for inst, key in (("MNQ", "m1"), ("MES", "mes1")):
    b = H.E9["P10"][key]; ts = pd.to_datetime(b.timestamp_utc, utc=True)
    assert ts.max() < pd.Timestamp("2024-01-01", tz="UTC")
    loc = ts.dt.tz_convert(NY)
    BAR[inst] = (ts.dt.as_unit("ns").astype("int64").to_numpy(), b.open.to_numpy(float), b.high.to_numpy(float), b.low.to_numpy(float),
                 b.close.to_numpy(float), loc, (loc.dt.hour * 60 + loc.dt.minute).to_numpy(), loc.dt.date.to_numpy())


def reversal(r, mode):
    """Causal entry: the engine's exit stamp may be the START of the bar in which the stop was hit, so walk 1-minute bars from that stamp
    to the first bar that actually trades through the stopped trade's exit fill (+/- the 0.5-pt engine slippage) and enter at the NEXT
    bar's open. No touch within 60 minutes -> skip."""
    ts, O, Hh, L, C, loc, MOD, DT = BAR[r.inst]; i0 = int(np.searchsorted(ts, r.tout.value))
    hit = None
    for j in range(i0, min(i0 + 60, len(ts) - 1)):
        if DT[j] != r.tout.date(): break
        if (r.side > 0 and L[j] <= r.exit + pl.ADV) or (r.side < 0 and Hh[j] >= r.exit - pl.ADV): hit = j; break
    if hit is None: return None
    i = hit + 1; t0 = loc.iloc[i]
    if DT[i] != r.tout.date() or MOD[i] >= 15 * 60 + 30: return None
    side = -int(r.side); e = O[i]; Rp = float(r.stop_pct) * float(r.entry)
    stop = e - side * Rp; tgt = None if mode == "X1" else e + side * Rp * (1.0 if mode == "X2" else 2.0)
    j = i; worst = e; x = None; why = "eod"
    while j < len(ts):
        if DT[j] != DT[i] or MOD[j] > 15 * 60 + 59: j -= 1; break
        if side > 0:
            worst = min(worst, L[j])
            if L[j] <= stop: x = min(stop, O[j]) if j > i else min(stop, e); why = "stop"; break
            if tgt is not None and Hh[j] >= tgt: x = tgt; why = "target"; break
        else:
            worst = max(worst, Hh[j])
            if Hh[j] >= stop: x = max(stop, O[j]) if j > i else max(stop, e); why = "stop"; break
            if tgt is not None and L[j] <= tgt: x = tgt; why = "target"; break
        if MOD[j] == 15 * 60 + 59: x = C[j]; break
        j += 1
    if x is None: x = C[min(j, len(ts) - 1)]
    T, M = pl.TODAY[r.inst], pl.MULT[r.inst]
    pm = ((side * (x - e) / e) * T - 2 * pl.ADV) * M - pl.FEE
    mae = min(pm, (min(0.0, side * (worst - e) / e) * T - pl.ADV) * M)
    tout = loc.iloc[min(j, len(ts) - 1)] + pd.Timedelta(minutes=1)
    return dict(inst=r.inst, side=side, entry=e, exit=x, tin=t0, tout=tout, per_micro=pm, mae_per_micro=mae, why=why,
                risk_today=Rp / e * T * M + 1.0 + 0.75 * M, n_contracts=1.0)


out = {"stopouts": len(stops), "cells": {}}; LED = {}
for mode in ("X1", "X2", "X3"):
    rows = [x for x in (reversal(r, mode) for r in stops.itertuples()) if x is not None]
    t = pd.DataFrame(rows); LED[mode] = t
    day = t.tout.dt.date; h1 = (day < eh.H1_END).to_numpy()
    def st(m):
        x = t.per_micro[m]; w = x[x > 0].sum(); l = -x[x < 0].sum()
        return dict(n=int(m.sum()), net=round(float(x.sum()), 0), pf=round(float(w / l), 3) if l > 0 else None)
    sc = eh.screen(t.per_micro.groupby(day).sum(), f"SAR_{mode}")
    out["cells"][mode] = dict(h1=st(h1), h2=st(~h1), exits=t.why.value_counts().to_dict(), screen=sc)
    print(mode, out["cells"][mode], flush=True)
    t.to_csv(ROOT / f"reports/EVAL_18_SAR_{mode}_TRADES_TRAINING.csv", index=False)

passers = [m for m, c in out["cells"].items() if c["screen"]["screen_pass"]]
out["gate1_pass"] = passers
if passers:
    P = {}
    for m in passers:
        for ns in ("F1", "K"):
            P[f"{m}_{ns}"] = H.pass_rate(extra=LED[m], nsize=ns); print(m, ns, P[f"{m}_{ns}"], flush=True)
    pA = max(P, key=lambda k: P[k]["h1"]["pass_"]); pB = max(P, key=lambda k: P[k]["h2"]["pass_"])
    oA, oB = P[pB]["h1"]["pass_"], P[pA]["h2"]["pass_"]
    out["gate2"] = dict(cells=P, pick_h1=pA, pick_h2=pB, oof_h1=oA, oof_h2=oB, adopt=bool(oA >= 55.5 and oB >= 66.6))
    print("gate2", out["gate2"], flush=True)
else:
    print("no cell passed the screen", flush=True)
(ROOT / "reports/EVAL_18_STOP_REVERSE_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
