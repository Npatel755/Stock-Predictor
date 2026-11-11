"""payout_9 (Claude, 2026-11-10): gap-continuation sizing inside v5 at today's prices. TRAINING 2010-23 only.

PRE-DECLARED (before results): dplus_4/5 found Crabel drives that agree with the opening gap earn ~2x per trade (13/14 years) vs fades.
Cells (1 micro base, $300 per-micro budget, research routing, $400 account stop, $1k buffer): v5 | v5 + Crabel continuation at 2 micros |
v5+TRD30PM | v5+TRD30PM + Crabel continuation at 2 micros | same two with account stop $600 (2-micro trades can lose ~$600).
Gate: payouts per 12 months up vs the same book without gap sizing, 12-month breach <= 2%, 0 days <= -$1,000.
"""
import json
import numpy as np, pandas as pd
import payout_lib as pl

ep, bars_for, START, gs = pl.engine()
S = {"CRABEL": (dict(ep._AG_CRABEL15_D, name="AG_CRABEL15_D_1c"), True), "TRD60": (dict(ep._AG_TRD60_D, name="AG_TRD60_D_1c"), True),
     "MES30": (dict(ep._AG_MES_TRD30_D, name="AG_MES_TRD30_D_1c"), False), "TRD30PM": (dict(ep._AG_TRD30PM, name="AG_TRD30PM_1c"), False)}
T = {k: pl.price_normalize(pl.sleeve_trades(ep, bars_for, START, sl, i, flt)) for i, (k, (sl, flt)) in enumerate(S.items())}
c = T["CRABEL"]; cont = np.array([int(r.side) * gs.get(r.tin.date(), 0) >= 0 for r in c.itertuples()])
print(f"Crabel trades {len(c)}, continuation {cont.sum()}, net_today cont/fade per trade {c.net_today[cont].mean():.1f} / {c.net_today[~cont].mean():.1f}", flush=True)


def book(keys, gap2, stop):
    parts = []
    for k in keys:
        d = T[k].copy()
        if k == "CRABEL" and gap2:
            d.loc[cont, "net_today"] = d.loc[cont, "net_today"] * 2.0
        parts.append(d)
    df = pd.concat(parts, ignore_index=True)
    return pl.day_series(pl.route(df[df.risk_today <= 300.0]), stop=stop)


out = {}
for name, keys, gap2, stop in (("v5", ["CRABEL", "TRD60", "MES30"], False, 400.0), ("v5 + gap 2-micro Crabel", ["CRABEL", "TRD60", "MES30"], True, 400.0),
                               ("v5 + gap 2-micro Crabel, stop $600", ["CRABEL", "TRD60", "MES30"], True, 600.0),
                               ("v5+TRD30PM", ["CRABEL", "TRD60", "MES30", "TRD30PM"], False, 400.0),
                               ("v5+TRD30PM + gap 2-micro Crabel", ["CRABEL", "TRD60", "MES30", "TRD30PM"], True, 400.0),
                               ("v5+TRD30PM + gap 2-micro Crabel, stop $600", ["CRABEL", "TRD60", "MES30", "TRD30PM"], True, 600.0)):
    out[name] = pl.summ(book(keys, gap2, stop)); print(pl.fmt(name, out[name]), flush=True)
for a, b in (("v5 + gap 2-micro Crabel", "v5"), ("v5 + gap 2-micro Crabel, stop $600", "v5"), ("v5+TRD30PM + gap 2-micro Crabel", "v5+TRD30PM"),
             ("v5+TRD30PM + gap 2-micro Crabel, stop $600", "v5+TRD30PM")):
    out[a]["gate"] = bool(out[a]["payouts_12m_median"] >= out[b]["payouts_12m_median"] and out[a]["payouts_per_year"] > out[b]["payouts_per_year"]
                          and out[a]["p_breach_12m"] <= 0.02 and out[a]["dll_days"] == 0)
print("gates:", {k: v.get("gate") for k, v in out.items() if "gate" in v})
(pl.ROOT / "reports/PAYOUT_9_GAPSIZE_V5_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
