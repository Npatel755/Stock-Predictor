"""Research Supercharged Two-Stage Strategy (Training 2010-2023):
Combines:
1. Two-Stage Cushion: First payout taken at +$4,000 ($1,000 out) -> Fast payback in ~47 days.
2. Supercharged Ladder (1x <$2.5k, 2x $2.5k-$4.5k, 3x $4.5k-$6.5k, 4x >=$6.5k).
3. Post-payout supercharged cushion K swept across $6,500, $7,000, $7,500, $8,000.
4. Audits: S0, S3 stress, S4 vol surge, H1/H2 halves, conservative ruin, worst valley.
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
ov = P10["ov"]
m1 = P10["m1"]

NIGHT_RISK = abs(float(stop_loss_level))
HALVES = (("2010-07-01", "2016-06-01"), ("2016-07-01", "2022-01-01"))

# 1. Ablated book (no TRD30PM)
base_no_pm = base_intra[~base_intra.sleeve.str.contains("TRD30PM")].copy()

# 2. Derive 09:15 ET overnight exit
ts = pd.to_datetime(m1.timestamp_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy()
O, H, L, C = m1.open.to_numpy(float), m1.high.to_numpy(float), m1.low.to_numpy(float), m1.close.to_numpy(float)

ov_rows = []
for t in ov:
    e_raw = float(t["entry_price"]) - pl.ADV
    tin = pd.Timestamp(t["entry_ts"])
    exit_dt = pd.Timestamp(t["exit_ts"]).tz_convert(pl.NY).replace(hour=9, minute=15).tz_convert("UTC")
    stop = e_raw * (1 - 0.0055)
    i0, i1 = int(np.searchsorted(ts, tin.value)), int(np.searchsorted(ts, exit_dt.value))
    if i1 <= i0:
        continue
    hit = np.nonzero(L[i0:i1] <= stop)[0]
    if len(hit):
        j = i0 + int(hit[0])
        x_raw = min(stop, O[j]) if j > i0 else stop
        lowest = x_raw
    else:
        lowest = L[i0:i1].min() if i1 > i0 else e_raw
        x_raw = C[i1 - 1] + pl.ADV
    pm = (((x_raw - e_raw) / e_raw) * pl.TODAY["MNQ"] - 2 * pl.ADV) * pl.MULT["MNQ"] - pl.FEE
    mae = (min(0.0, (lowest - e_raw) / e_raw) * pl.TODAY["MNQ"] - pl.ADV) * pl.MULT["MNQ"]
    ov_rows.append(
        dict(
            tin=tin.tz_convert(pl.NY),
            tout=exit_dt.tz_convert(pl.NY),
            net_today=pm,
            per_micro=pm,
            mae_per_micro=min(mae, pm),
            n_contracts=1.0,
            night=True,
        )
    )

nights_0915 = pd.DataFrame(ov_rows)

def build_data(nights_df):
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

        # Overnight stress
        n = nights_df.copy()
        if kind in ("S1", "S3"):
            n["net_today"] -= 1.0 * pl.MULT["MNQ"]
        if kind in ("S2", "S3"):
            n["net_today"] -= 0.25 * max(float(n.net_today.mean()), 0.0)
        if kind == "S4":
            stopped = n.net_today <= stop_loss_level
            n.loc[~stopped, "net_today"] *= 1.5

        for m in (1, 2, 3, 4, 5):
            r = pl.route(e).copy()
            q = np.maximum(1.0, np.minimum(float(m) * r.n_contracts, np.floor(900.0 / r.risk_today)))
            net_scaled = r.net_today * (q / r.n_contracts)
            i = pd.DataFrame({"tin": r.tin, "tout": r.tout, "net_today": net_scaled})

            qn = min(m, int(900.0 // (NIGHT_RISK * (1.5 if kind == "S4" else 1))))
            nm = n.assign(net_today=n.net_today * qn) if qn >= 1 else n.iloc[0:0]
            stop = 400.0 if m == 1 else min(400.0 * m, 700.0)
            rk = (r.risk_today * q).groupby(r.tout.dt.date).max() if len(r) else pd.Series(dtype=float)

            SER[(kind, m, False)] = fast_day_series(i, stop).to_dict()
            SER[(kind, m, True)] = fast_day_series(pd.concat([i, nm], ignore_index=True), stop).to_dict()
            if len(nm):
                rn = pd.Series(
                    qn * NIGHT_RISK * (1.5 if kind == "S4" else 1),
                    index=pd.Index(n.tout.dt.date),
                ).groupby(level=0).max()
                rk = pd.concat([rk, rn]).groupby(level=0).max()
            RISK[(kind, m)] = rk.to_dict()
    return SER, RISK

print("Building simulation lookup tables...")
SER_OPT, RISK_OPT = build_data(nights_0915)

def simulate_twostage(SER, RISK, kind, K_first, W_first, K_steady, ladder_spec, start_from="2010-07-01", start_to="2022-01-01"):
    keys = [k for k in SER if k[0] == kind]
    days = sorted(set().union(*[set(SER[k]) for k in keys]))
    ix = pd.to_datetime(pd.Series(days).astype(str)).to_numpy()
    rows = []

    for s0 in pd.date_range(start_from, start_to, freq="MS"):
        a = int(np.searchsorted(ix, np.datetime64(s0)))
        b = int(np.searchsorted(ix, np.datetime64(s0 + pd.DateOffset(months=24))))
        cut = np.datetime64(s0 + pd.DateOffset(months=12))
        bal = 0.0
        payout_count = 0
        since = 0.0
        p1 = p2 = 0
        usd = 0.0
        closed = False
        cons = False
        lowest_bal = 0.0
        days_to_p1 = np.nan

        trading_days_elapsed = 0
        for x, t in zip(days[a:b], ix[a:b]):
            trading_days_elapsed += 1
            m = 1
            for thresh, mult in ladder_spec:
                if bal >= thresh:
                    m = mult

            floor = 0.0 if payout_count > 0 else -2000.0
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

            # Payout logic
            if payout_count == 0:
                # Stage 1: Early payback
                if bal >= K_first:
                    w = W_first
                    bal -= w
                    usd += w
                    payout_count += 1
                    since = 0.0
                    days_to_p1 = trading_days_elapsed
                    if t < cut:
                        p1 += 1
                    else:
                        p2 += 1
            else:
                # Stage 2: Steady supercharged cushion
                if since > 0 and bal - K_steady >= 250.0:
                    w = min(1500.0, bal - K_steady)
                    bal -= w
                    usd += w
                    payout_count += 1
                    since = 0.0
                    if t < cut:
                        p1 += 1
                    else:
                        p2 += 1

        rows.append((p1, p2, usd, closed, cons, lowest_bal, days_to_p1))

    r = pd.DataFrame(rows, columns=["p1", "p2", "usd", "closed", "cons", "lowest_bal", "days_to_p1"])
    return dict(
        withdrawn_24m=round(float(r.usd.mean()), 0),
        payouts_y1=round(float(r.p1.mean()), 2),
        payouts_y2=round(float(r.p2.mean()), 2),
        payouts_y1_p10=float(r.p1.quantile(0.1)),
        closed_24m=round(float(r.closed.mean()), 3),
        closed_24m_conservative=round(float(r.cons.mean()), 3),
        worst_drawdown_valley=round(float(r.lowest_bal.min()), 0),
        median_days_to_p1=round(float(r.days_to_p1.dropna().median()), 1) if len(r.days_to_p1.dropna()) else np.nan,
    )

ladder_supercharged = [(0, 1), (2500, 2), (4500, 3), (6500, 4)]
ladder_3x_tier = [(0, 1), (2500, 2), (4500, 3)]
ladder_conservative_4x = [(0, 1), (3000, 2), (5000, 3), (7000, 4)]

specs = [
    # Baseline comparison (single stage 2x)
    ("Baseline 2x (K=$5.5k Single Stage)", 5500.0, 1500.0, 5500.0, [(0, 1), (3500, 2)]),
    # Supercharged Single Stage K=$7.5k
    ("Single-Stage Supercharged 4x (K=$7.5k)", 7500.0, 1500.0, 7500.0, ladder_supercharged),
    ("Single-Stage Supercharged 4x (K=$8.0k)", 8000.0, 1500.0, 8000.0, ladder_supercharged),
    # Two-Stage Supercharged
    ("Two-Stage Supercharged 4x (P1 @ $4.0k -$1k | K=$7.0k)", 4000.0, 1000.0, 7000.0, ladder_supercharged),
    ("Two-Stage Supercharged 4x (P1 @ $4.0k -$1k | K=$7.5k)", 4000.0, 1000.0, 7500.0, ladder_supercharged),
    ("Two-Stage Supercharged 4x (P1 @ $4.0k -$1k | K=$8.0k)", 4000.0, 1000.0, 8000.0, ladder_supercharged),
    # Two-Stage 3x Tier (More conservative, no 4x)
    ("Two-Stage 3x Tier (P1 @ $4.0k -$1k | K=$6.5k)", 4000.0, 1000.0, 6500.0, ladder_3x_tier),
    ("Two-Stage 3x Tier (P1 @ $4.0k -$1k | K=$7.0k)", 4000.0, 1000.0, 7000.0, ladder_3x_tier),
    # Two-Stage Conservative 4x
    ("Two-Stage Conservative 4x (P1 @ $4.0k -$1k | K=$7.5k)", 4000.0, 1000.0, 7500.0, ladder_conservative_4x),
    ("Two-Stage Conservative 4x (P1 @ $4.0k -$1k | K=$8.0k)", 4000.0, 1000.0, 8000.0, ladder_conservative_4x),
]

print("\n--- RUNNING SUPERCHARGED TWO-STAGE COMPARISON ---")
out_results = {}
for name, k_first, w_first, k_steady, lad in specs:
    s0 = simulate_twostage(SER_OPT, RISK_OPT, "S0", k_first, w_first, k_steady, lad)
    s3 = simulate_twostage(SER_OPT, RISK_OPT, "S3", k_first, w_first, k_steady, lad)
    s4 = simulate_twostage(SER_OPT, RISK_OPT, "S4", k_first, w_first, k_steady, lad)
    h1 = simulate_twostage(SER_OPT, RISK_OPT, "S0", k_first, w_first, k_steady, lad, start_from=HALVES[0][0], start_to=HALVES[0][1])
    h2 = simulate_twostage(SER_OPT, RISK_OPT, "S0", k_first, w_first, k_steady, lad, start_from=HALVES[1][0], start_to=HALVES[1][1])

    eligible = bool(s0["closed_24m"] <= 0.02 and s3["closed_24m"] <= 0.08 and s4["closed_24m"] <= 0.15)
    out_results[name] = dict(S0=s0, S3=s3, S4=s4, half1=h1, half2=h2, eligible=eligible)

    print(f"\n{name}:")
    print(f"  S0: 24m Cash ${s0['withdrawn_24m']:,.0f} | Ruin: {s0['closed_24m']*100:.1f}% (Cons: {s0['closed_24m_conservative']*100:.1f}%) | Days to P1: {s0['median_days_to_p1']} d | Worst Valley: ${s0['worst_drawdown_valley']:,.0f}")
    print(f"  S3: 24m Cash ${s3['withdrawn_24m']:,.0f} | Ruin: {s3['closed_24m']*100:.1f}%")
    print(f"  S4: 24m Cash ${s4['withdrawn_24m']:,.0f} | Ruin: {s4['closed_24m']*100:.1f}%")
    print(f"  Halves: H1 ${h1['withdrawn_24m']:,.0f} | H2 ${h2['withdrawn_24m']:,.0f} | Eligible: {eligible}")

out_path = pl.ROOT / "reports/RESEARCH_SUPERCHARGED_TWOSTAGE_TRAINING.json"
out_path.write_text(json.dumps(out_results, indent=2, default=str), encoding="utf-8")
print(f"\nSaved report to {out_path}")
