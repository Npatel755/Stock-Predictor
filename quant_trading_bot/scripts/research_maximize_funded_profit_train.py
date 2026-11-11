"""Research script to find the strategy architecture and sizing ladder that achieves
the HIGHEST PROFIT within the Topstep $50K Static drawdown limits (-$2,000 static floor, -$1,000 DLL).
TRAINING 2010-23 only, today's price level, path-correct accounting.
Tests:
  1. Base Book v5.2 vs Ablated Book (NO TRD30PM)
  2. Cushion ladders K in {$4k, $6k, $8k, $10k}
  3. Max sizing multipliers M_MAX in {1, 2, 3, 4, 5}
  4. Advanced cushion scaling (higher size only on large house-money buffers)
  5. Stress tests S0 (nominal), S3 (costs + haircut), S4 (1.5x vol)
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

def build_scenario_data(base_df, use_night=True):
    SER = {}
    RISK = {}
    for kind in ("S0", "S3", "S4"):
        d = base_df.copy()
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

        for m in (1, 2, 3, 4, 5):
            em = e[e.risk_today * e.n_contracts * m <= (900.0 if m > 1 else 1e9)]
            r = pl.route(em)
            i = r[["tin", "tout", "net_today"]].assign(net_today=lambda x: x.net_today * m)
            night_ok = use_night and (m == 1 or NIGHT_RISK * (1.5 if kind == "S4" else 1) * m <= 900.0)
            nm = n.assign(net_today=n.net_today * m) if night_ok else n.iloc[0:0]
            stop = 400.0 if m == 1 else min(400.0 * m, 700.0)
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

def simulate_funded(SER, RISK, kind, K, M_MAX, ladder_type="standard", start_from="2010-07-01", start_to="2022-01-01"):
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
            # Sizing policy
            if ladder_type == "standard":
                m = min(M_MAX, 4 if bal >= 8000 else 3 if bal >= 6000 else 2 if bal >= 4000 else 1)
            elif ladder_type == "steep":
                # Steeper sizing on larger cushions (up to M_MAX)
                m = min(M_MAX, 5 if bal >= 12000 else 4 if bal >= 8000 else 3 if bal >= 5000 else 2 if bal >= 3000 else 1)
            elif ladder_type == "cautious_start":
                # 1x until $4k, then 2x until $8k, then 3x
                m = min(M_MAX, 3 if bal >= 8000 else 2 if bal >= 4000 else 1)
            else:
                m = min(M_MAX, 1)

            floor = 0.0 if paid else -2000.0
            if not cons and bal - RISK[(kind, m)].get(x, 0.0) <= floor:
                cons = True
            p = max(SER[(kind, m, bal >= 500.0)].get(x, 0.0), -1000.0)
            bal += p
            since += p
            lowest_bal = min(lowest_bal, bal)

            if bal <= floor:
                closed = True
                cons = True
                break

            # Daily payout check (profits above cushion K, min $250, max $1,500/day)
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

print("Building baseline book scenario data (v5.2 with TRD30PM)...")
SER_BASE, RISK_BASE = build_scenario_data(base_intra)

print("Building ablated book scenario data (v5.2 WITHOUT TRD30PM)...")
base_no_pm = base_intra[~base_intra.sleeve.str.contains("TRD30PM")].copy()
SER_ABL, RISK_ABL = build_scenario_data(base_no_pm)

print("\nRunning comparative ladder experiments across K and M_MAX...")

results = {}

configs = [
    # Baseline comparison (K=6000, M=2)
    ("Baseline v5.2 | keep $6k | max 2x", SER_BASE, RISK_BASE, 6000.0, 2, "standard"),
    ("Ablated Book | keep $6k | max 2x", SER_ABL, RISK_ABL, 6000.0, 2, "standard"),
    
    # Testing higher cushions and sizing limits on Ablated Book
    ("Ablated Book | keep $6k | max 3x", SER_ABL, RISK_ABL, 6000.0, 3, "standard"),
    ("Ablated Book | keep $8k | max 2x", SER_ABL, RISK_ABL, 8000.0, 2, "standard"),
    ("Ablated Book | keep $8k | max 3x", SER_ABL, RISK_ABL, 8000.0, 3, "standard"),
    ("Ablated Book | keep $8k | max 4x", SER_ABL, RISK_ABL, 8000.0, 4, "standard"),
    ("Ablated Book | keep $10k | max 3x", SER_ABL, RISK_ABL, 10000.0, 3, "standard"),
    ("Ablated Book | keep $10k | max 4x", SER_ABL, RISK_ABL, 10000.0, 4, "standard"),
    ("Ablated Book | keep $10k | max 5x", SER_ABL, RISK_ABL, 10000.0, 5, "steep"),
    ("Ablated Book | keep $8k | max 4x (Steep Ladder)", SER_ABL, RISK_ABL, 8000.0, 4, "steep"),
]

for label, ser, rsk, K, M, lad in configs:
    s0 = simulate_funded(ser, rsk, "S0", K, M, ladder_type=lad)
    s3 = simulate_funded(ser, rsk, "S3", K, M, ladder_type=lad)
    s4 = simulate_funded(ser, rsk, "S4", K, M, ladder_type=lad)
    h1 = simulate_funded(ser, rsk, "S0", K, M, ladder_type=lad, start_from=HALVES[0][0], start_to=HALVES[0][1])
    h2 = simulate_funded(ser, rsk, "S0", K, M, ladder_type=lad, start_from=HALVES[1][0], start_to=HALVES[1][1])
    
    # Eligibility criteria: 24m closure <= 3% S0, <= 8% S3, <= 15% S4; payouts >= 8 y1, >= 8 y2
    eligible = bool(s0["closed_24m"] <= 0.03 and s3["closed_24m"] <= 0.08 and s4["closed_24m"] <= 0.15
                    and s0["payouts_y1"] >= 7.5 and s0["payouts_y2"] >= 8.0)
    
    res = dict(S0=s0, S3=s3, S4=s4, half1=h1, half2=h2, eligible=eligible)
    results[label] = res
    
    print(f"\n{label}")
    print(f"  S0: 24m Withdrawn ${s0['withdrawn_24m']:,.0f} | Y1 Pays: {s0['payouts_y1']} | Y2 Pays: {s0['payouts_y2']} | Ruin/Closed: {s0['closed_24m']*100:.1f}% (Cons: {s0['closed_24m_conservative']*100:.1f}%) | Worst Valley: ${s0['worst_drawdown_valley']:,.0f}")
    print(f"  S3 (Stress): 24m Withdrawn ${s3['withdrawn_24m']:,.0f} | Ruin/Closed: {s3['closed_24m']*100:.1f}%")
    print(f"  S4 (1.5x Vol): 24m Withdrawn ${s4['withdrawn_24m']:,.0f} | Ruin/Closed: {s4['closed_24m']*100:.1f}%")
    print(f"  Halves: H1 ${h1['withdrawn_24m']:,.0f} | H2 ${h2['withdrawn_24m']:,.0f} | Eligible: {eligible}")

out_path = pl.ROOT / "reports/RESEARCH_MAXIMIZE_FUNDED_PROFIT_TRAINING.json"
out_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
print(f"\nSaved report to {out_path}")
