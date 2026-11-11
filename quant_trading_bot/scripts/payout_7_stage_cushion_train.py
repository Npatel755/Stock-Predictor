"""payout_7 (Claude, 2026-11-10): staging + cushion - run the safe book until a buffer is built, add sleeves above it. TRAINING 2010-23 only.

PRE-DECLARED (before results): books at today's prices (1 micro, $300 budget, $400 account stop): SAFE = v5; FULL = v5 + TRD30PM or
v5 + TRD30_D + BRK30 + TRD30PM. Each day the account trades FULL if the balance at the start of the day is >= S, else SAFE. A payout =
5 days >= $150 since the last payout, withdrawing only the balance above the buffer C (C = S). Static -$2,000 floor from the start balance.
Grid: S = C in {1000, 1500, 2000, 2500} x FULL in {v5+TRD30PM, v5+all3}; plus "no staging" (FULL always) at the same cushions for reference.
Metrics: payouts/yr, payouts per 12-month start (p10-p90), 12-month breach odds over 151 monthly starts, median payout.
Gate: a cell is adopted if 12-month breach <= 2% and payouts/yr > 5.07 (v5 + TRD30PM at C = $1,000, payout_6).
"""
import json
import numpy as np, pandas as pd
import payout_lib as pl

ep, bars_for, START, _ = pl.engine()
S = {"CRABEL": (dict(ep._AG_CRABEL15_D, name="AG_CRABEL15_D_1c"), True), "TRD60": (dict(ep._AG_TRD60_D, name="AG_TRD60_D_1c"), True),
     "MES30": (dict(ep._AG_MES_TRD30_D, name="AG_MES_TRD30_D_1c"), False), "TRD30_D": (dict(ep._AG_TRD30_D, name="AG_TRD30_D_1c"), True),
     "BRK30": (dict(ep._AG_BRK30, name="AG_BRK30_1c"), True), "TRD30PM": (dict(ep._AG_TRD30PM, name="AG_TRD30PM_1c"), False)}
T = {k: pl.price_normalize(pl.sleeve_trades(ep, bars_for, START, sl, i, flt)) for i, (k, (sl, flt)) in enumerate(S.items())}


def book(keys):
    df = pd.concat([T[k] for k in keys], ignore_index=True)
    return pl.day_series(pl.route(df[df.risk_today <= 300.0]), stop=400.0)


BASE = ["CRABEL", "TRD60", "MES30"]
D = {"SAFE": book(BASE), "v5+TRD30PM": book(BASE + ["TRD30PM"]), "v5+all3": book(BASE + ["TRD30_D", "BRK30", "TRD30PM"])}
days = sorted(set().union(*[set(s.index) for s in D.values()]))
A = {k: pd.Series(v, index=v.index).reindex(days, fill_value=0.0) for k, v in D.items()}
idx = pd.to_datetime(pd.Series(days).astype(str)).to_numpy()


def run(full, stage, cushion, i0=0, i1=None):
    """Sequential account from day index i0 to i1. Returns payouts, breach flag, payout amounts."""
    bal = 0.0; good = 0; pays = []; breach = False
    safe, fullv = A["SAFE"].to_numpy(), A[full].to_numpy()
    for i in range(i0, len(days) if i1 is None else i1):
        p = fullv[i] if (stage is None or bal >= stage) else safe[i]
        bal += max(p, -1000.0)
        if bal <= -2000.0:
            breach = True; break
        good += p >= 150
        if good >= 5 and bal - cushion > 0:
            pays.append(bal - cushion); bal = cushion; good = 0
    return pays, breach


def evaluate(full, stage, cushion):
    pays, _ = run(full, stage, cushion)
    res12 = []
    for s0 in pd.date_range("2010-07-01", "2023-01-01", freq="MS"):
        i0 = int(np.searchsorted(idx, np.datetime64(s0))); i1 = int(np.searchsorted(idx, np.datetime64(s0 + pd.DateOffset(months=12))))
        p, b = run(full, stage, cushion, i0, i1); res12.append((len(p), b))
    r = pd.DataFrame(res12, columns=["pays", "breach"])
    return dict(payouts_per_year_14y_path=round(len(pays) / 14, 2), median_payout=round(float(np.median(pays)), 0) if pays else 0,
                payouts_12m_median=float(r.pays.median()), payouts_12m_mean=round(float(r.pays.mean()), 2),
                payouts_12m_p10_p90=[float(r.pays.quantile(.1)), float(r.pays.quantile(.9))], p_breach_12m=round(float(r.breach.mean()), 3))


out = {}
for full in ("v5+TRD30PM", "v5+all3"):
    for C in (1000.0, 1500.0, 2000.0, 2500.0):
        for stage in (None, C):
            name = f"{full} | {'staged at' if stage else 'always full,'} buffer ${int(C)}"
            out[name] = r = evaluate(full, stage, C)
            out[name]["gate"] = bool(r["p_breach_12m"] <= 0.02 and r["payouts_per_year_14y_path"] > 5.07)
            print(f"{name:46s} pay/yr {r['payouts_per_year_14y_path']:>5} | per 12m mean {r['payouts_12m_mean']:>5} med {r['payouts_12m_median']} "
                  f"{r['payouts_12m_p10_p90']} | breach {r['p_breach_12m']:>5} | med payout {r['median_payout']:>6} | gate {r['gate']}", flush=True)
out["SAFE reference"] = evaluate("SAFE", None, 1000.0)
print("SAFE (v5) buffer $1000:", out["SAFE reference"])
(pl.ROOT / "reports/PAYOUT_7_STAGE_CUSHION_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
