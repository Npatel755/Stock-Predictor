"""eval_21 (Claude, 2026-11-11): SWAP the book's TRD60 sleeve for the noise-area MNQ sleeve (instead of adding it). TRAINING 2010-23.

Why (written before results): eval_12 added noise-area on top of the book and failed partly because its 10:01-16:00 holds blocked the
book's later decisions in the one-position router; eval_13 ran it concurrently and it added variance. Both are trend sleeves on MNQ
(noise daily Sharpe 0.065-0.075 per micro; TRD60 is the book's 60-minute trend sleeve; bookx_1: dropping TRD60 alone -> 46.5 / 63.4).
A swap keeps one MNQ trend slot and asks which trend rule fills it better.
PRE-DECLARED: PRE without TRD60 trades + noise trades (eval_13 ledgers, published parameters) at TRD60's router priority, 1-micro base,
decision time = entry time minus 1 minute, risk <= $300 filter as every sleeve. Cells: P, R. Report daily Sharpe (k3) and pass rate.
2-fold: pick P/R on 2010-16 starts, report 2017-23, and vice versa; ADOPT only if both out-of-fold halves >= 55.5 / 66.6.
"""
import json
import numpy as np, pandas as pd
from pathlib import Path
import eval_harness as eh

ROOT = Path(__file__).resolve().parents[1]
H = eh.Harness(); PRE = H.PRE
is60 = PRE.sleeve.str.contains("TRD60"); prio60 = int(PRE.loc[is60, "prio"].mode().iloc[0])
print("TRD60 trades", int(is60.sum()), "priority", prio60, flush=True)


def daily_sr(book):
    PD = H._per_day(book[H.COLS].assign(noise=False))
    k3 = pd.Series({d: H.sim_day(PD[d], 3.0)[0] for d in PD}).reindex(H.SESS, fill_value=0.0); h1 = np.array([d < eh.H1_END for d in H.SESS])
    return round(eh._sr(k3), 4), round(eh._sr(k3[h1]), 4), round(eh._sr(k3[~h1]), 4)


out = {"base": dict(sr=daily_sr(H.BOOK)), "cells": {}}
for m in ("P", "R"):
    t = pd.read_csv(ROOT / f"reports/EVAL_13_NOISE_MNQ_{m}_TRADES_TRAINING.csv")
    for c in ("tin", "tout"): t[c] = pd.to_datetime(t[c], utc=True).dt.tz_convert("America/New_York")
    t = t.assign(sleeve=f"NOISE_{m}", prio=prio60, n_contracts=1.0, net_today=t.per_micro, dec=t.tin - pd.Timedelta(minutes=1))
    pre = pd.concat([PRE[~is60], t.reindex(columns=PRE.columns)], ignore_index=True)
    bk = H.build_book(pre); c = dict(sr=daily_sr(bk), noise_trades_taken=int((bk.sleeve == f"NOISE_{m}").sum()), pass_=H.pass_rate(book=bk))
    out["cells"][m] = c; print(m, c, flush=True)
C = out["cells"]; pA = max(C, key=lambda k: C[k]["pass_"]["h1"]["pass_"]); pB = max(C, key=lambda k: C[k]["pass_"]["h2"]["pass_"])
oA, oB = C[pB]["pass_"]["h1"]["pass_"], C[pA]["pass_"]["h2"]["pass_"]
out["result"] = dict(pick_h1=pA, pick_h2=pB, oof_h1=oA, oof_h2=oB, adopt=bool(oA >= 55.5 and oB >= 66.6))
print("base SR", out["base"], "result", out["result"], flush=True)
(ROOT / "reports/EVAL_21_SWAP_TRD60_NOISE_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
