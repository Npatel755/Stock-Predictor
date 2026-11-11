"""Research script to optimize and improve the Ablated Payout Book
on the Topstep $50K Static funded account (-$2,000 static floor, -$1,000 DLL).
TRAINING 2010-23 only, today's price level, path-correct accounting.

Candidate Improvements Tested:
  1. Risk-Balanced Sizing: Size MES to match NQ dollar risk (MES base 2 micros instead of 1).
  2. Refined Payout Cushion K in {$4,500, $5,000, $5,500, $6,000}.
  3. Staged Sizing Curve: 1x below $3,500, 2x above $3,500.
  4. Overnight Staging: Staged at $0, $250, $500, $750.
  5. Account Stop: $400/1x, $700/2x vs $450/1x, $750/2x.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import sys

scripts_dir = Path(__file__).resolve().parent
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

import payout_lib as pl
import payout_17_bond_filter_train as p17

P10 = p17.ns["ns"]
base_intra = p17.base_intra
nights_func = p17.nights
stop_loss_level = p17.stop_loss_level
fast_day_series = p17.fast_day_series
sc17 = p17.scenario
N0 = p17.N0

NIGHT_RISK = abs(float(stop_loss_level))
HALVES = (("2010-07-01", "2016-06-01"), ("2016-07-01", "2022-01-01"))

# Base ablated intraday trades (without TRD30PM)
base_no_pm = base_intra[~base_intra.sleeve.str.contains("TRD30PM")].copy()

def prepare_book(mes_multiplier=1.0, crabel_continuation_mult=2.0):
    d = base_no_pm.copy()
    # If mes_multiplier > 1.0, scale MES base contracts
    is_mes = d.sleeve.str.contains("MES")
    d.loc[is_mes, "n_contracts"] *= mes_multiplier
    d.loc[is_mes, "net_today"] *= mes_multiplier
    d.loc[is_mes, "risk_today"] *= mes_multiplier
    return d

def build_series_dict(df, acct_stop_1x=400.0, acct_stop_2x=700.0):
    SER = {}
    RISK = {}
    for kind in ("S0", "S3", "S4"):
        d = df.copy()
        if kind in ("S1", "S3"):
            d["net_today"] -= 1.0 * d.inst.map(pl.MULT) * d.n_contracts
        if kind in ("S2", "S3"):
            avg = d.groupby("sleeve").net_today.transform("mean")
            d["net_today"] -= 0.25 * avg.clip(lower=0)
        if kind == "S4":
            d["risk_today"] *= 1.5
            d["net_today"] *= 1.5
        e = d[d.risk_today <= 300.0]
        _, n = sc17(kind, N0)

        for m in (1, 2):
            em = e[e.risk_today * e.n_contracts * m <= (900.0 if m > 1 else 1e9)]
            r = pl.route(em)
            i = r[["tin", "tout", "net_today"]].assign(net_today=lambda x: x.net_today * m)
            night_ok = m == 1 or NIGHT_RISK * (1.5 if kind == "S4" else 1) * m <= 900.0
            nm = n.assign(net_today=n.net_today * m) if night_ok else n.iloc[0:0]
            stop = acct_stop_1x if m == 1 else acct_stop_2x
            SER[(kind, m, False)] = fast_day_series(i, stop).to_dict()
            SER[(kind, m, True)] = fast_day_series(pd.concat([i, nm], ignore_index=True), stop).to_dict()
            rk = (r.risk_today * r.n_contracts * m).groupby(r.tout.dt.date).max()
            if night_ok:
                rn = pd.Series(
                    NIGHT_RISK * (1.5 if kind == "S4" else 1) * m,
                    index=pd.Index(n.tout.dt.date),
                ).groupby(level=0).max()
                rk = pd.concat([rk, rn]).groupby(level=0).max()
            RISK[(kind, m)] = rk.to_dict()
    return SER, RISK

def simulate_engine(SER, RISK, kind, K=6000.0, scale_up_bal=4000.0, overnight_min_bal=500.0,
                    start_from="2010-07-01", start_to="2022-01-01"):
    keys = [k for k in SER if k[0] == kind]
    days = sorted(set().union(*[set(SER[k]) for k in keys]))
    ix = pd.to_datetime(pd.Series(days).astype(str)).to_numpy()
    rows = []

    for s0 in pd.date_range(start_from, start_to, freq="MS"):
        a = int(np.searchsorted(ix, np.datetime64(s0)))
        b = int(np.searchsorted(ix, np.datetime64(s0 + pd.DateOffset(months=24))))
        cut = np.datetime64(s0 + pd.DateOffset(months=12))
        bal = 0.0
        paid = False
        since = 0.0
        p1 = p2 = 0
        usd = 0.0
        closed = False
        cons = False
        lowest_bal = 0.0

        for x, t in zip(days[a:b], ix[a:b]):
            m = 2 if bal >= scale_up_bal else 1
            floor = 0.0 if paid else -2000.0
            if not cons and bal - RISK[(kind, m)].get(x, 0.0) <= floor:
                cons = True
            
            p = max(SER[(kind, m, bal >= overnight_min_bal)].get(x, 0.0), -1000.0)
            bal += p
            since += p
            lowest_bal = min(lowest_bal, bal)

            if bal <= floor:
                closed = True
                cons = True
                break

            # Daily payouts of profit above cushion K
            if (since > 0 or not paid) and bal - K >= 250.0:
                w = min(1500.0, bal - K)
                bal -= w
                usd += w
                paid = True
                since = 0.0
                if t < cut:
                    p1 += 1
                else:
                    p2 += 1

        rows.append((p1, p2, usd, closed, cons, lowest_bal))

    r = pd.DataFrame(rows, columns=["p1", "p2", "usd", "closed", "cons", "lowest_bal"])
    return dict(
        withdrawn_24m=round(float(r.usd.mean()), 0),
        payouts_y1=round(float(r.p1.mean()), 2),
        payouts_y2=round(float(r.p2.mean()), 2),
        payouts_y1_p10=float(r.p1.quantile(0.1)),
        closed_24m=round(float(r.closed.mean()), 3),
        closed_24m_conservative=round(float(r.cons.mean()), 3),
        worst_drawdown_valley=round(float(r.lowest_bal.min()), 0),
    )

print("Running strategic improvement grid on 14-year training data...")

experiments = [
    # Reference
    ("0. Reference: Ablated Core (MES 1c, K=$6k, Scale @ $4k, O/N @ $500)", 1.0, 6000.0, 4000.0, 500.0, 400.0, 700.0),
    
    # Variation 1: Cushion Optimization (K in $4.5k, $5k, $5.5k)
    ("1A. Lower Cushion: K=$5,000 (Scale @ $3.5k)", 1.0, 5000.0, 3500.0, 500.0, 400.0, 700.0),
    ("1B. Lower Cushion: K=$5,500 (Scale @ $3.5k)", 1.0, 5500.0, 3500.0, 500.0, 400.0, 700.0),
    ("1C. Lower Cushion: K=$5,000 (Scale @ $4.0k)", 1.0, 5000.0, 4000.0, 500.0, 400.0, 700.0),
    
    # Variation 2: Risk-Balanced Sizing (MES at 2 micros base because stop is only $95)
    ("2A. Risk-Balanced MES 2c (K=$6k, Scale @ $4k)", 2.0, 6000.0, 4000.0, 500.0, 400.0, 700.0),
    ("2B. Risk-Balanced MES 2c + K=$5k (Scale @ $3.5k)", 2.0, 5000.0, 3500.0, 500.0, 400.0, 700.0),
    ("2C. Risk-Balanced MES 2c + K=$5.5k (Scale @ $3.5k)", 2.0, 5500.0, 3500.0, 500.0, 400.0, 700.0),
    
    # Variation 3: Overnight Activation Optimization ($0 vs $250 vs $500)
    ("3A. Overnight Activated @ $250 Balance (K=$5.5k, MES 2c)", 2.0, 5500.0, 3500.0, 250.0, 400.0, 700.0),
    ("3B. Overnight Activated @ $0 Balance (K=$5.5k, MES 2c)", 2.0, 5500.0, 3500.0, 0.0, 400.0, 700.0),
    
    # Variation 4: Circuit Breaker Tuning ($450 / $750 stops)
    ("4A. Slightly Wider Account Stops ($450/$750, MES 2c, K=$5.5k)", 2.0, 5500.0, 3500.0, 250.0, 450.0, 750.0),
]

SER_CACHE = {}
results = {}

for label, mes_mult, K_val, scale_bal, on_bal, st1, st2 in experiments:
    cache_key = (mes_mult, st1, st2)
    if cache_key not in SER_CACHE:
        df_p = prepare_book(mes_multiplier=mes_mult)
        SER_CACHE[cache_key] = build_series_dict(df_p, acct_stop_1x=st1, acct_stop_2x=st2)
    ser, rsk = SER_CACHE[cache_key]

    s0 = simulate_engine(ser, rsk, "S0", K=K_val, scale_up_bal=scale_bal, overnight_min_bal=on_bal)
    s3 = simulate_engine(ser, rsk, "S3", K=K_val, scale_up_bal=scale_bal, overnight_min_bal=on_bal)
    s4 = simulate_engine(ser, rsk, "S4", K=K_val, scale_up_bal=scale_bal, overnight_min_bal=on_bal)
    h1 = simulate_engine(ser, rsk, "S0", K=K_val, scale_up_bal=scale_bal, overnight_min_bal=on_bal, start_from=HALVES[0][0], start_to=HALVES[0][1])
    h2 = simulate_engine(ser, rsk, "S0", K=K_val, scale_up_bal=scale_bal, overnight_min_bal=on_bal, start_from=HALVES[1][0], start_to=HALVES[1][1])

    eligible = bool(s0["closed_24m"] <= 0.03 and s3["closed_24m"] <= 0.08 and s4["closed_24m"] <= 0.15
                    and s0["payouts_y1"] >= 7.5 and s0["payouts_y2"] >= 8.0)

    res = dict(S0=s0, S3=s3, S4=s4, half1=h1, half2=h2, eligible=eligible)
    results[label] = res

    print(f"\n{label}")
    print(f"  S0: 24m Withdrawn ${s0['withdrawn_24m']:,.0f} | Y1 Pays: {s0['payouts_y1']} | Y2 Pays: {s0['payouts_y2']} | Ruin/Closed: {s0['closed_24m']*100:.1f}% (Cons: {s0['closed_24m_conservative']*100:.1f}%) | Worst Valley: ${s0['worst_drawdown_valley']:,.0f}")
    print(f"  S3 (Stress): 24m Withdrawn ${s3['withdrawn_24m']:,.0f} | Ruin/Closed: {s3['closed_24m']*100:.1f}%")
    print(f"  S4 (1.5x Vol): 24m Withdrawn ${s4['withdrawn_24m']:,.0f} | Ruin/Closed: {s4['closed_24m']*100:.1f}%")
    print(f"  Halves: H1 ${h1['withdrawn_24m']:,.0f} | H2 ${h2['withdrawn_24m']:,.0f} | Eligible: {eligible}")

out_path = pl.ROOT / "reports/RESEARCH_IMPROVE_FUNDED_STRATEGY_TRAINING.json"
out_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
print(f"\nSaved optimization report to {out_path}")
