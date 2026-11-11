"""Research script to explore the theoretical frontier of Pass Rate vs Ruin Rate
on Topstep $50K Static Combine (90 calendar days, -$2,000 static floor, 1-min MAE).
TRAINING 2010-23 only, today's price level, integer contracts.
Ablated Book: CRABEL15_D, TRD60_D, MES_TRD30_D, and overnight_dip_v2.
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
base = p17.base_intra
ov = P10["ov"]
mnq, mes = P10["m1"], P10["mes1"]

BARS = {}
for k, b in (("MNQ", mnq), ("MES", mes)):
    BARS[k] = (
        pd.to_datetime(b.timestamp_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy(),
        b.open.to_numpy(float),
        b.high.to_numpy(float),
        b.low.to_numpy(float),
    )

def mae_pct(inst, tin, tout, side, entry):
    ts, O, H, L = BARS[inst]
    i0, i1 = int(np.searchsorted(ts, tin.value)), int(np.searchsorted(ts, tout.value))
    if i1 <= i0:
        return 0.0
    worst = L[i0:i1].min() if side > 0 else H[i0:i1].max()
    return min(0.0, side * (worst - entry) / entry)

# Overnight leg with MAE
ts, O, H, L = BARS["MNQ"]
ov_rows = []
for t in ov:
    e_raw = float(t["entry_price"]) - pl.ADV
    x_raw = float(t["exit_price"]) + pl.ADV
    tin, tout = pd.Timestamp(t["entry_ts"]), pd.Timestamp(t["exit_ts"])
    stop = e_raw * (1 - 0.0055)
    i0, i1 = int(np.searchsorted(ts, tin.value)), int(np.searchsorted(ts, tout.value))
    hit = np.nonzero(L[i0:i1] <= stop)[0]
    if len(hit):
        j = i0 + int(hit[0])
        x_raw = min(stop, O[j]) if j > i0 else stop
        lowest = x_raw
    else:
        lowest = L[i0:i1].min() if i1 > i0 else e_raw
    pm = (((x_raw - e_raw) / e_raw) * pl.TODAY["MNQ"] - 2 * pl.ADV) * pl.MULT["MNQ"] - pl.FEE
    mae = (min(0.0, (lowest - e_raw) / e_raw) * pl.TODAY["MNQ"] - pl.ADV) * pl.MULT["MNQ"]
    ov_rows.append(
        dict(
            tin=tin.tz_convert(pl.NY),
            tout=tout.tz_convert(pl.NY),
            per_micro=pm,
            mae_per_micro=min(mae, pm),
            n_contracts=1.0,
            night=True,
        )
    )
nights = pd.DataFrame(ov_rows)
NIGHT_RISK = abs(float(p17.stop_loss_level))

# Ablated intraday trades (no TRD30PM)
base_no_pm = base[~base.sleeve.str.contains("TRD30PM")].copy()
intra_df = pl.route(base_no_pm[base_no_pm.risk_today <= 300.0]).copy()
intra_df["per_micro"] = intra_df.net_today / intra_df.n_contracts
intra_df["mae_per_micro"] = [
    (mae_pct(r.inst, r.tin, r.tout, r.side, r.entry) * pl.TODAY[r.inst] - pl.ADV) * pl.MULT[r.inst]
    for r in intra_df.itertuples()
]

def build_trades(k):
    a = intra_df.assign(
        q=np.minimum(k * intra_df.n_contracts, np.floor(900.0 / intra_df.risk_today)),
        night=False,
    )
    parts = [a[["tin", "tout", "per_micro", "mae_per_micro", "q", "night", "n_contracts"]]]
    qn = min(k, int(900.0 // NIGHT_RISK))
    if qn >= 1:
        parts.append(nights.assign(q=float(qn))[["tin", "tout", "per_micro", "mae_per_micro", "q", "night", "n_contracts"]])
    t = pd.concat(parts, ignore_index=True)
    t = t[t.q >= 1].copy()
    t["net"] = t.per_micro * t.q
    t["mae"] = t.mae_per_micro * t.q
    t["day"] = t.tout.dt.date
    return t.sort_values("tin").reset_index(drop=True)

# Precompute trades for k in 1..6
BY = {}
for k in (1, 2, 3, 4, 5, 6):
    t = build_trades(k)
    BY[k] = {d: g for d, g in t.groupby("day")}

TDAYS = sorted(set().union(*[set(v) for v in BY.values()]))
TIX = pd.to_datetime(pd.Series(TDAYS).astype(str)).to_numpy()

SESS = sorted(set(pd.to_datetime(mnq.timestamp_utc, utc=True).dt.tz_convert(pl.NY).dt.date))
SESS = [d for d in SESS if pd.Timestamp(d).dayofweek < 5 and pd.Timestamp("2010-06-07").date() <= d <= pd.Timestamp("2023-09-29").date()]

def evaluate_policy(rule_func, max_days=90):
    out = []
    for s in SESS:
        end = (pd.Timestamp(s) + pd.Timedelta(days=max_days)).date()
        a = int(np.searchsorted(TIX, np.datetime64(pd.Timestamp(s))))
        bal = 0.0
        best = 0.0
        res = "timeout"
        when = None
        for d in TDAYS[a:]:
            if d >= end:
                break
            k = rule_func(bal)
            stop = min(400.0 * k, 700.0)
            day = 0.0
            g = BY[k].get(d)
            if g is not None:
                for r in g.itertuples():
                    if day <= -stop or day <= -1000.0:
                        break
                    if bal + day + r.mae <= -2000.0:
                        res = "fail"
                        break
                    if day + r.mae <= -1000.0:
                        day = -1000.0
                        break
                    day += r.net
            if res == "fail":
                break
            bal += max(day, -1000.0)
            best = max(best, day)
            if bal <= -2000.0:
                res = "fail"
                break
            if bal >= max(4000.0, best / 0.55):
                res = "pass"
                when = d
                break
        out.append((s, res, None if when is None else int(np.busday_count(s, when)) + 1))
    r = pd.DataFrame(out, columns=["start", "res", "sess"])
    h1 = (r.start < pd.Timestamp("2017-01-01").date()).to_numpy()
    def sh(m):
        return {o: round(100 * float((r.res[m] == o).mean()), 1) for o in ("pass", "fail", "timeout")}
    return dict(
        all=sh(np.ones(len(r), bool)),
        half1=sh(h1),
        half2=sh(~h1),
        starts=len(r),
        median_sess=float(r.sess.dropna().median()) if r.sess.notna().any() else None,
        p25_sess=float(r.sess.dropna().quantile(0.25)) if r.sess.notna().any() else None,
    )

print("Precomputing complete. Testing policies...")

policies = {}

# Fixed baselines
for k in (1, 2, 3, 4, 5):
    policies[f"Fixed k={k}"] = (lambda k_val: lambda b: k_val)(k)

# Defensive floor variants (starting at k=3 or k=4)
policies["Defensive: k3, k1 <= -500"] = lambda b: 1 if b <= -500 else 3
policies["Defensive: k3, k1 <= -800"] = lambda b: 1 if b <= -800 else 3
policies["Defensive: k3, k1 <= -1000"] = lambda b: 1 if b <= -1000 else 3
policies["Defensive: k3, k2 <= -500, k1 <= -1000"] = lambda b: 1 if b <= -1000 else (2 if b <= -500 else 3)
policies["Defensive: k2, k1 <= -500"] = lambda b: 1 if b <= -500 else 2

# Asymmetric Cushion Accelerators (Defensive floor + Aggressive ceiling)
policies["Asymmetric A: k1 <= -500, k3 base, k4 >= +1500"] = lambda b: 1 if b <= -500 else (4 if b >= 1500 else 3)
policies["Asymmetric B: k1 <= -500, k3 base, k5 >= +1500"] = lambda b: 1 if b <= -500 else (5 if b >= 1500 else 3)
policies["Asymmetric C: k1 <= -800, k3 base, k4 >= +1500"] = lambda b: 1 if b <= -800 else (4 if b >= 1500 else 3)
policies["Asymmetric D: k1 <= -800, k3 base, k5 >= +1500"] = lambda b: 1 if b <= -800 else (5 if b >= 1500 else 3)
policies["Asymmetric E: k1 <= -500, k2 <= 0, k3 base, k5 >= +1500"] = lambda b: 1 if b <= -500 else (2 if b <= 0 else (5 if b >= 1500 else 3))
policies["Asymmetric F: k1 <= -500, k3 base, k5 >= +2000"] = lambda b: 1 if b <= -500 else (5 if b >= 2000 else 3)
policies["Asymmetric G: k1 <= -500, k3 base, k6 >= +2000"] = lambda b: 1 if b <= -500 else (6 if b >= 2000 else 3)
policies["Asymmetric H (High Floor): k2 <= -300, k1 <= -700, k3 base, k5 >= +1500"] = lambda b: 1 if b <= -700 else (2 if b <= -300 else (5 if b >= 1500 else 3))
policies["Asymmetric I (Fortress): k1 <= 0, k2 <= 1000, k4 >= 1000, k6 >= 2500"] = lambda b: 1 if b <= 0 else (2 if b <= 1000 else (6 if b >= 2500 else 4))

results = {}
for name, func in policies.items():
    res = evaluate_policy(func, max_days=90)
    results[name] = res
    print(f"\n{name}")
    print(f"  All: Pass {res['all']['pass']}% | Fail {res['all']['fail']}% | Timeout {res['all']['timeout']}% | Median {res['median_sess']}d")
    print(f"  Half1: Pass {res['half1']['pass']}% | Fail {res['half1']['fail']}% | Timeout {res['half1']['timeout']}%")
    print(f"  Half2: Pass {res['half2']['pass']}% | Fail {res['half2']['fail']}% | Timeout {res['half2']['timeout']}%")

# Also test if Topstep 120 days or 180 days were allowed, what happens
print("\n" + "="*70)
print("TESTING LONGER HORIZONS (e.g. if account has more time or resets allowed)")
print("="*70)
for days in (90, 120, 150, 180):
    res = evaluate_policy(policies["Asymmetric E: k1 <= -500, k2 <= 0, k3 base, k5 >= +1500"], max_days=days)
    print(f"Asymmetric E at {days} calendar days: Pass {res['all']['pass']}% | Fail {res['all']['fail']}% | Timeout {res['all']['timeout']}% | Median {res['median_sess']}d")

out_file = pl.ROOT / "reports/RESEARCH_MAXIMIZE_EVAL_PASS_RATE.json"
out_file.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
print(f"\nSaved results to {out_file}")
