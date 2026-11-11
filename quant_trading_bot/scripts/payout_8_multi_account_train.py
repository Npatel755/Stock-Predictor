"""payout_8 (Claude, 2026-11-10): reaching 12 payouts/yr with several funded accounts. TRAINING 2010-23 only, today's price level.

PRE-DECLARED (before results): candidate one-account books (1 micro, $300 budget, $400 account stop, $1k buffer, research routing):
  A = v5 (Crabel, 60m trend, MES 30m)          B = v5 + TRD30PM
  C = TRD30_D + BRK30 + TRD30PM (the non-D+ sleeves)      D = TRD30_D + BRK30 + MES 30m      E = TRD30PM + MES 30m + 60m trend
Each book must pass alone: 12-month breach <= 2% over 151 monthly starts. Then every 2- and 3-account combination of passing books:
total payouts per 12-month start (mean, p10), P(any account breaches), P(2+ breach), mean pairwise correlation of monthly P&L.
Target: total >= 12 payouts per 12 months on average with P(any breach) <= 5%.
"""
import itertools, json
import numpy as np, pandas as pd
import payout_lib as pl

ep, bars_for, START, _ = pl.engine()
S = {"CRABEL": (dict(ep._AG_CRABEL15_D, name="AG_CRABEL15_D_1c"), True), "TRD60": (dict(ep._AG_TRD60_D, name="AG_TRD60_D_1c"), True),
     "MES30": (dict(ep._AG_MES_TRD30_D, name="AG_MES_TRD30_D_1c"), False), "TRD30_D": (dict(ep._AG_TRD30_D, name="AG_TRD30_D_1c"), True),
     "BRK30": (dict(ep._AG_BRK30, name="AG_BRK30_1c"), True), "TRD30PM": (dict(ep._AG_TRD30PM, name="AG_TRD30PM_1c"), False)}
T = {k: pl.price_normalize(pl.sleeve_trades(ep, bars_for, START, sl, i, flt)) for i, (k, (sl, flt)) in enumerate(S.items())}
BOOKS = {"A v5": ["CRABEL", "TRD60", "MES30"], "B v5+TRD30PM": ["CRABEL", "TRD60", "MES30", "TRD30PM"],
         "C TRD30_D+BRK30+TRD30PM": ["TRD30_D", "BRK30", "TRD30PM"], "D TRD30_D+BRK30+MES30": ["TRD30_D", "BRK30", "MES30"],
         "E TRD30PM+MES30+TRD60": ["TRD30PM", "MES30", "TRD60"]}
DAY = {}
for k, keys in BOOKS.items():
    df = pd.concat([T[s] for s in keys], ignore_index=True)
    DAY[k] = pl.day_series(pl.route(df[df.risk_today <= 300.0]), stop=400.0)
days = sorted(set().union(*[set(s.index) for s in DAY.values()]))
idx = pd.to_datetime(pd.Series(days).astype(str)).to_numpy()
A = {k: v.reindex(days, fill_value=0.0).to_numpy() for k, v in DAY.items()}
STARTS = pd.date_range("2010-07-01", "2023-01-01", freq="MS")


def window(arr, i0, i1, cushion=1000.0):
    bal = 0.0; good = 0; pays = 0; breach = False
    for p in arr[i0:i1]:
        bal += max(p, -1000.0)
        if bal <= -2000.0: breach = True; break
        good += p >= 150
        if good >= 5 and bal - cushion > 0: pays += 1; bal = cushion; good = 0
    return pays, breach


W = {}
for k in BOOKS:
    W[k] = []
    for s0 in STARTS:
        i0 = int(np.searchsorted(idx, np.datetime64(s0))); i1 = int(np.searchsorted(idx, np.datetime64(s0 + pd.DateOffset(months=12))))
        W[k].append(window(A[k], i0, i1))
out = {"books": {}}
for k in BOOKS:
    p = np.array([w[0] for w in W[k]]); b = np.array([w[1] for w in W[k]])
    out["books"][k] = dict(payouts_12m_mean=round(float(p.mean()), 2), payouts_12m_p10=float(np.quantile(p, .1)), p_breach_12m=round(float(b.mean()), 3),
                           passes=bool(b.mean() <= 0.02), **{kk: v for kk, v in pl.summ(DAY[k]).items() if kk in ("days150_per_year", "net_per_year", "worst_day", "max_drawdown")})
    print(k, out["books"][k], flush=True)
monthly = pd.DataFrame({k: pd.Series(A[k], index=idx).groupby(pd.Series(idx).dt.to_period("M").to_numpy()).sum() for k in BOOKS})
out["monthly_corr"] = monthly.corr().round(2).to_dict()
passing = [k for k in BOOKS if out["books"][k]["passes"]]
out["portfolios"] = {}
for n in (2, 3):
    for combo in itertools.combinations(passing, n):
        tot = np.sum([[w[0] for w in W[k]] for k in combo], axis=0); br = np.array([[w[1] for w in W[k]] for k in combo])
        corr = np.mean([monthly[a].corr(monthly[b]) for a, b in itertools.combinations(combo, 2)])
        r = dict(total_payouts_12m_mean=round(float(tot.mean()), 2), total_payouts_12m_p10=float(np.quantile(tot, .1)),
                 p_any_breach_12m=round(float(br.any(axis=0).mean()), 3), p_2plus_breach_12m=round(float((br.sum(axis=0) >= 2).mean()), 3),
                 mean_monthly_corr=round(float(corr), 2))
        r["meets_target"] = bool(r["total_payouts_12m_mean"] >= 12 and r["p_any_breach_12m"] <= 0.05)
        out["portfolios"][" + ".join(combo)] = r
        print(f"{n} accounts: {' + '.join(combo):60s} {r}", flush=True)
(pl.ROOT / "reports/PAYOUT_8_MULTI_ACCOUNT_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
