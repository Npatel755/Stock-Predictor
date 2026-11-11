"""Cap-Aware Scaling Research:
Instead of dropping trades when m * risk > $900 (which crippled 3x in payout_24),
cap each trade's size dynamically: q = min(m * n_contracts, floor(900.0 / risk_today)).
This ensures NO profitable trade is ever skipped, while strictly respecting the $900 risk cap and -$1,000 DLL.
Evaluated on the Ablated Book (CRABEL15, TRD60, MES30, overnight_dip_v2) across all 139 24-month windows (2010-2023).
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
stop_loss_level = p17.stop_loss_level
fast_day_series = p17.fast_day_series
sc17 = p17.scenario
N0 = p17.N0

NIGHT_RISK = abs(float(stop_loss_level))
HALVES = (("2010-07-01", "2016-06-01"), ("2016-07-01", "2022-01-01"))

# Ablated book without TRD30PM
base_no_pm = base_intra[~base_intra.sleeve.str.contains("TRD30PM")].copy()

def build_cap_aware_data(mode="cap_aware"):
    """mode in ('hard_drop', 'cap_aware')"""
    SER = {}
    RISK = {}
    for kind in ("S0", "S3", "S4"):
        d = base_no_pm.copy()
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

        for m in (1, 2, 3, 4):
            if mode == "hard_drop":
                em = e[e.risk_today * e.n_contracts * m <= (900.0 if m > 1 else 1e9)].copy()
                r = pl.route(em)
                i = r[["tin", "tout", "net_today"]].assign(net_today=lambda x: x.net_today * m)
                night_ok = (m == 1 or NIGHT_RISK * (1.5 if kind == "S4" else 1) * m <= 900.0)
                nm = n.assign(net_today=n.net_today * m) if night_ok else n.iloc[0:0]
                stop = 400.0 if m == 1 else 700.0
                rk = (r.risk_today * r.n_contracts * m).groupby(r.tout.dt.date).max() if len(r) else pd.Series(dtype=float)
            else: # cap_aware
                # Route first at base eligible trades, then scale each trade's size dynamically
                r = pl.route(e).copy()
                # Dynamically calculate contracts q per trade
                q = np.maximum(1.0, np.minimum(float(m) * r.n_contracts, np.floor(900.0 / r.risk_today)))
                # net_today scaled proportionally to q / n_contracts
                net_scaled = r.net_today * (q / r.n_contracts)
                i = pd.DataFrame({"tin": r.tin, "tout": r.tout, "net_today": net_scaled})
                
                # Overnight scaling
                qn = min(m, int(900.0 // (NIGHT_RISK * (1.5 if kind == "S4" else 1))))
                nm = n.assign(net_today=n.net_today * qn) if qn >= 1 else n.iloc[0:0]
                stop = 400.0 if m == 1 else min(400.0 * m, 700.0)
                rk = (r.risk_today * q).groupby(r.tout.dt.date).max() if len(r) else pd.Series(dtype=float)

            SER[(kind, m, False)] = fast_day_series(i, stop).to_dict()
            SER[(kind, m, True)] = fast_day_series(pd.concat([i, nm], ignore_index=True), stop).to_dict()
            if len(nm):
                rn = pd.Series(
                    (qn if mode == 'cap_aware' else m) * NIGHT_RISK * (1.5 if kind == "S4" else 1),
                    index=pd.Index(n.tout.dt.date),
                ).groupby(level=0).max()
                rk = pd.concat([rk, rn]).groupby(level=0).max()
            RISK[(kind, m)] = rk.to_dict()
    return SER, RISK

def simulate_payouts(SER, RISK, kind, K, ladder_spec, start_from="2010-07-01", start_to="2022-01-01"):
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
            # Ladder spec: list of (threshold, multiplier) e.g. [(0, 1), (3500, 2), (8000, 3)]
            m = 1
            for thresh, mult in ladder_spec:
                if bal >= thresh:
                    m = mult

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

print("Building data for Hard-Drop mode vs Cap-Aware mode...")
SER_HD, RISK_HD = build_cap_aware_data(mode="hard_drop")
SER_CA, RISK_CA = build_cap_aware_data(mode="cap_aware")

experiments = [
    # Baseline from previous run
    ("1. Upgraded Baseline: Hard-Drop (1x <$3.5k, 2x >=$3.5k | K=$5.5k)", SER_HD, RISK_HD, 5500.0, [(0, 1), (3500, 2)]),
    
    # Cap-Aware 2x
    ("2. Cap-Aware 2x (1x <$3.5k, 2x >=$3.5k | K=$5.5k)", SER_CA, RISK_CA, 5500.0, [(0, 1), (3500, 2)]),
    
    # Cap-Aware 3x on House Money (1x <$3.5k, 2x $3.5k-$7.5k, 3x >=$7.5k | K=$5.5k)
    ("3. Cap-Aware 3x Tier (1x <$3.5k, 2x $3.5k-$7.5k, 3x >=$7.5k | K=$5.5k)", SER_CA, RISK_CA, 5500.0, [(0, 1), (3500, 2), (7500, 3)]),
    
    # Cap-Aware 3x Tier with K=$6.0k
    ("4. Cap-Aware 3x Tier (1x <$3.5k, 2x $3.5k-$8.0k, 3x >=$8.0k | K=$6.0k)", SER_CA, RISK_CA, 6000.0, [(0, 1), (3500, 2), (8000, 3)]),
    
    # Cap-Aware 3x Tier with K=$6.5k
    ("5. Cap-Aware 3x Tier (1x <$3.5k, 2x $3.5k-$8.0k, 3x >=$8.0k | K=$6.5k)", SER_CA, RISK_CA, 6500.0, [(0, 1), (3500, 2), (8000, 3)]),
    
    # Cap-Aware 4x on Ultra-Buffer (1x <$3.5k, 2x $3.5k-$7.5k, 3x $7.5k-$11k, 4x >=$11k | K=$6.0k)
    ("6. Cap-Aware 4x Ultra-Buffer (1x/2x/3x/4x | K=$6.0k)", SER_CA, RISK_CA, 6000.0, [(0, 1), (3500, 2), (7500, 3), (11000, 4)]),
]

results = {}
for label, ser, rsk, K_val, ladder in experiments:
    s0 = simulate_payouts(ser, rsk, "S0", K_val, ladder)
    s3 = simulate_payouts(ser, rsk, "S3", K_val, ladder)
    s4 = simulate_payouts(ser, rsk, "S4", K_val, ladder)
    h1 = simulate_payouts(ser, rsk, "S0", K_val, ladder, start_from=HALVES[0][0], start_to=HALVES[0][1])
    h2 = simulate_payouts(ser, rsk, "S0", K_val, ladder, start_from=HALVES[1][0], start_to=HALVES[1][1])

    eligible = bool(s0["closed_24m"] <= 0.03 and s3["closed_24m"] <= 0.08 and s4["closed_24m"] <= 0.15
                    and s0["payouts_y1"] >= 7.5 and s0["payouts_y2"] >= 8.0)

    res = dict(S0=s0, S3=s3, S4=s4, half1=h1, half2=h2, eligible=eligible)
    results[label] = res

    print(f"\n{label}")
    print(f"  S0: 24m Withdrawn ${s0['withdrawn_24m']:,.0f} | Y1 Pays: {s0['payouts_y1']} | Y2 Pays: {s0['payouts_y2']} | Ruin/Closed: {s0['closed_24m']*100:.1f}% (Cons: {s0['closed_24m_conservative']*100:.1f}%) | Worst Valley: ${s0['worst_drawdown_valley']:,.0f}")
    print(f"  S3 (Stress): 24m Withdrawn ${s3['withdrawn_24m']:,.0f} | Ruin/Closed: {s3['closed_24m']*100:.1f}%")
    print(f"  S4 (1.5x Vol): 24m Withdrawn ${s4['withdrawn_24m']:,.0f} | Ruin/Closed: {s4['closed_24m']*100:.1f}%")
    print(f"  Halves: H1 ${h1['withdrawn_24m']:,.0f} | H2 ${h2['withdrawn_24m']:,.0f} | Eligible: {eligible}")

out_path = pl.ROOT / "reports/RESEARCH_CAP_AWARE_SCALING_TRAINING.json"
out_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
print(f"\nSaved report to {out_path}")
