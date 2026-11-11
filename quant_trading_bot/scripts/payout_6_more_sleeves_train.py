"""payout_6 (Claude, 2026-11-10): do more replicated intraday sleeves add payouts to v5 at today's prices? TRAINING 2010-23 only.

PRE-DECLARED (before results): base = v5 (D+ v2 sleeves, 1 micro, $300 per-micro budget at today's price, $400 account stop, $1k cushion).
Add-ons, each already replicated on the fixed engine: TRD30_D (D+ original MNQ 30m morning trend), BRK30 (All-Weather MNQ 30m breakout),
TRD30PM (Quad MNQ 30m afternoon trend, no VIX filter). Cells: v5 | v5+TRD30_D | v5+BRK30 | v5+TRD30PM | v5+all three.
Budget filter BEFORE routing (a skipped trade frees the account), research post-hoc 1-position routing, add-ons rank after the D+ sleeves.
Gate to adopt an add-on: payouts/yr up vs v5, 12-month breach <= 2%, no $1,000 days, and 2010-19 $150 days not lower than v5's.
"""
import json
import payout_lib as pl

ep, bars_for, START, _ = pl.engine()
S = {"CRABEL": (dict(ep._AG_CRABEL15_D, name="AG_CRABEL15_D_1c"), True), "TRD60": (dict(ep._AG_TRD60_D, name="AG_TRD60_D_1c"), True),
     "MES30": (dict(ep._AG_MES_TRD30_D, name="AG_MES_TRD30_D_1c"), False), "TRD30_D": (dict(ep._AG_TRD30_D, name="AG_TRD30_D_1c"), True),
     "BRK30": (dict(ep._AG_BRK30, name="AG_BRK30_1c"), True), "TRD30PM": (dict(ep._AG_TRD30PM, name="AG_TRD30PM_1c"), False)}
T = {k: pl.price_normalize(pl.sleeve_trades(ep, bars_for, START, sl, i, flt)) for i, (k, (sl, flt)) in enumerate(S.items())}
print({k: (len(v), round(float(v.net_then.sum()), 0), round(float(v.net_today.sum()), 0)) for k, v in T.items()}, flush=True)

import pandas as pd
BASE = ["CRABEL", "TRD60", "MES30"]
cells = {"v5": BASE, "v5 + TRD30_D": BASE + ["TRD30_D"], "v5 + BRK30": BASE + ["BRK30"], "v5 + TRD30PM": BASE + ["TRD30PM"],
         "v5 + all three": BASE + ["TRD30_D", "BRK30", "TRD30PM"]}
out = {"sleeve_trades_net_then_net_today": {k: [len(v), round(float(v.net_then.sum()), 0), round(float(v.net_today.sum()), 0)] for k, v in T.items()}}
for name, keys in cells.items():
    df = pd.concat([T[k] for k in keys], ignore_index=True)
    df = df[df.risk_today <= 300.0]
    day = pl.day_series(pl.route(df), stop=400.0)
    out[name] = pl.summ(day); print(pl.fmt(name, out[name]), flush=True)
v5 = out["v5"]
for name in cells:
    if name == "v5": continue
    r = out[name]
    r["gate"] = bool(r["payouts_per_year"] > v5["payouts_per_year"] and r["p_breach_12m"] <= 0.02 and r["dll_days"] == 0
                     and r["days150_2010_19"] >= v5["days150_2010_19"])
print("gates:", {k: out[k].get("gate") for k in cells if k != "v5"})
(pl.ROOT / "reports/PAYOUT_6_MORE_SLEEVES_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
