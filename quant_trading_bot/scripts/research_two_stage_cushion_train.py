"""Two-Stage Payout Cushion Optimization:
Compares:
  1. Fixed K=$6,000 (Current Champion: waits until $6,250 before payout 1).
  2. Two-Stage A: First payout @ $3,500 (withdraw $1k, leaving $2.5k buffer above $0 floor), then K=$5,500.
  3. Two-Stage B: First payout @ $4,000 (withdraw $1k, leaving $3.0k buffer above $0 floor), then K=$6,000.
  4. Two-Stage C: First payout @ $4,000 (withdraw $1.5k, leaving $2.5k buffer above $0 floor), then K=$5,500.
Evaluates:
  - Median days / months to FIRST payout (derisking timeline).
  - 24-month total dollars withdrawn.
  - Year 1 & Year 2 payouts taken.
  - S0 nominal ruin, S3 stress ruin, S4 vol surge ruin, and worst drawdown valley.
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
ov = P10["ov"]
m1 = P10["m1"]

NIGHT_RISK = abs(float(stop_loss_level))
HALVES = (("2010-07-01", "2016-06-01"), ("2016-07-01", "2022-01-01"))

# Base ablated book (no TRD30PM)
base_no_pm = base_intra[~base_intra.sleeve.str.contains("TRD30PM")].copy()

# 09:15 ET overnight exit
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

def build_data():
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

        n = nights_0915.copy()
        if kind in ("S1", "S3"):
            n["net_today"] -= 1.0 * pl.MULT["MNQ"]
        if kind in ("S2", "S3"):
            n["net_today"] -= 0.25 * max(float(n.net_today.mean()), 0.0)
        if kind == "S4":
            stopped = n.net_today <= stop_loss_level
            n.loc[~stopped, "net_today"] *= 1.5

        for m in (1, 2, 3):
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

def simulate_two_stage(SER, RISK, kind, K_first, W_first, K_subsequent,
                       ladder_spec=[(0, 1), (3500, 2), (8000, 3)],
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
        first_payout_days = None

        curr_day_idx = 0
        for x, t in zip(days[a:b], ix[a:b]):
            curr_day_idx += 1
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

            # Payout trigger logic
            if not paid:
                # First payout check at K_first
                if bal >= K_first:
                    w = min(W_first, bal - (K_first - W_first))
                    bal -= w
                    usd += w
                    paid = True
                    since = 0.0
                    first_payout_days = curr_day_idx
                    if t < cut:
                        p1 += 1
                    else:
                        p2 += 1
            else:
                # Subsequent payouts check at K_subsequent
                if since > 0 and bal - K_subsequent >= 250.0:
                    w = min(1500.0, bal - K_subsequent)
                    bal -= w
                    usd += w
                    since = 0.0
                    if t < cut:
                        p1 += 1
                    else:
                        p2 += 1

        rows.append((p1, p2, usd, closed, cons, lowest_bal, first_payout_days))

    r = pd.DataFrame(rows, columns=["p1", "p2", "usd", "closed", "cons", "lowest_bal", "first_days"])
    return dict(
        withdrawn_24m=round(float(r.usd.mean()), 0),
        payouts_y1=round(float(r.p1.mean()), 2),
        payouts_y2=round(float(r.p2.mean()), 2),
        payouts_y1_p10=float(r.p1.quantile(0.1)),
        closed_24m=round(float(r.closed.mean()), 3),
        closed_24m_conservative=round(float(r.cons.mean()), 3),
        worst_drawdown_valley=round(float(r.lowest_bal.min()), 0),
        median_first_payout_days=float(r.first_days.dropna().median()) if r.first_days.notna().any() else None,
    )

print("Building scenario data...")
SER, RISK = build_data()

configs = [
    ("1. Fixed K=$6,000 (Champion Baseline)", 6000.0, 1500.0, 6000.0),
    ("2. Two-Stage A: Pay 1 @ $3.5k ($1k out), then K=$5.5k", 3500.0, 1000.0, 5500.0),
    ("3. Two-Stage B: Pay 1 @ $4.0k ($1k out), then K=$6.0k", 4000.0, 1000.0, 6000.0),
    ("4. Two-Stage C: Pay 1 @ $4.0k ($1.5k out), then K=$5.5k", 4000.0, 1500.0, 5500.0),
    ("5. Two-Stage D: Pay 1 @ $4.5k ($1.5k out), then K=$5.5k", 4500.0, 1500.0, 5500.0),
]

results = {}
for label, k1, w1, k2 in configs:
    s0 = simulate_two_stage(SER, RISK, "S0", k1, w1, k2)
    s3 = simulate_two_stage(SER, RISK, "S3", k1, w1, k2)
    s4 = simulate_two_stage(SER, RISK, "S4", k1, w1, k2)
    h1 = simulate_two_stage(SER, RISK, "S0", k1, w1, k2, start_from=HALVES[0][0], start_to=HALVES[0][1])
    h2 = simulate_two_stage(SER, RISK, "S0", k1, w1, k2, start_from=HALVES[1][0], start_to=HALVES[1][1])

    eligible = bool(s0["closed_24m"] <= 0.03 and s3["closed_24m"] <= 0.08 and s4["closed_24m"] <= 0.15
                    and s0["payouts_y1"] >= 7.5 and s0["payouts_y2"] >= 8.0)

    res = dict(S0=s0, S3=s3, S4=s4, half1=h1, half2=h2, eligible=eligible)
    results[label] = res

    print(f"\n{label}")
    print(f"  S0: 24m Withdrawn ${s0['withdrawn_24m']:,.0f} | Y1 Pays: {s0['payouts_y1']} | Y2 Pays: {s0['payouts_y2']} | Ruin/Closed: {s0['closed_24m']*100:.1f}% | Median Days to 1st Pay: {s0['median_first_payout_days']}d | Worst Valley: ${s0['worst_drawdown_valley']:,.0f}")
    print(f"  S3 (Stress): 24m Withdrawn ${s3['withdrawn_24m']:,.0f} | Ruin/Closed: {s3['closed_24m']*100:.1f}%")
    print(f"  S4 (1.5x Vol): 24m Withdrawn ${s4['withdrawn_24m']:,.0f} | Ruin/Closed: {s4['closed_24m']*100:.1f}%")
    print(f"  Halves: H1 ${h1['withdrawn_24m']:,.0f} | H2 ${h2['withdrawn_24m']:,.0f} | Eligible: {eligible}")

out_path = pl.ROOT / "reports/RESEARCH_TWO_STAGE_CUSHION_TRAINING.json"
out_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
print(f"\nSaved two-stage optimization report to {out_path}")
