"""Ablation study of AG_TRD30PM on Topstep $50K Static Combine evaluation.
TRAINING 2010-23 only, today's price level, path-correct 1-minute MAE floor checking.
Compares:
  Baseline: v5.2 + overnight_dip_v2 (CRABEL, TRD60, MES30, TRD30PM)
  Ablated:  v5.2 without TRD30PM + overnight_dip_v2 (CRABEL, TRD60, MES30)
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import sys

# Ensure scripts dir is on sys.path
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

# Overnight leg re-derivation with MAE (identical to eval_1)
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

SESS = sorted(set(pd.to_datetime(mnq.timestamp_utc, utc=True).dt.tz_convert(pl.NY).dt.date))
SESS = [d for d in SESS if pd.Timestamp(d).dayofweek < 5 and pd.Timestamp("2010-06-07").date() <= d <= pd.Timestamp("2023-09-29").date()]

def run_evaluation(intra_df, tag=""):
    print(f"\n=======================================================")
    print(f"EVALUATING BOOK: {tag}")
    print(f"Total raw intraday trades: {len(intra_df)}")
    wins = (intra_df.net_today > 0).sum()
    gross_win = intra_df.loc[intra_df.net_today > 0, "net_today"].sum()
    gross_loss = abs(intra_df.loc[intra_df.net_today < 0, "net_today"].sum())
    pf = gross_win / gross_loss if gross_loss > 0 else np.nan
    wr = 100 * wins / len(intra_df) if len(intra_df) else 0
    tot_pnl = intra_df.net_today.sum()
    print(f"Intraday Net PnL (1x): ${tot_pnl:,.2f} | Win Rate: {wr:.1f}% | PF: {pf:.3f}")
    print(f"=======================================================")

    intra_df = intra_df.copy()
    intra_df["per_micro"] = intra_df.net_today / intra_df.n_contracts
    intra_df["mae_per_micro"] = [
        (mae_pct(r.inst, r.tin, r.tout, r.side, r.entry) * pl.TODAY[r.inst] - pl.ADV) * pl.MULT[r.inst]
        for r in intra_df.itertuples()
    ]

    def build_trades(k, night_on):
        a = intra_df.assign(
            q=np.minimum(k * intra_df.n_contracts, np.floor(900.0 / intra_df.risk_today)),
            night=False,
        )
        parts = [a[["tin", "tout", "per_micro", "mae_per_micro", "q", "night", "n_contracts"]]]
        if night_on:
            qn = min(k, int(900.0 // NIGHT_RISK))
            if qn >= 1:
                parts.append(nights.assign(q=float(qn))[["tin", "tout", "per_micro", "mae_per_micro", "q", "night", "n_contracts"]])
        t = pd.concat(parts, ignore_index=True)
        t = t[t.q >= 1].copy()
        t["net"] = t.per_micro * t.q
        t["mae"] = t.mae_per_micro * t.q
        t["day"] = t.tout.dt.date
        return t.sort_values("tin").reset_index(drop=True)

    def evaluate_variant(k, night_on):
        t = build_trades(k, night_on)
        stop = min(400.0 * k, 700.0)
        by_day = {d: g for d, g in t.groupby("day")}
        tdays = sorted(by_day)
        tix = pd.to_datetime(pd.Series(tdays).astype(str)).to_numpy()
        out = []
        for s in SESS:
            end = (pd.Timestamp(s) + pd.Timedelta(days=90)).date()
            a = int(np.searchsorted(tix, np.datetime64(pd.Timestamp(s))))
            bal = 0.0
            best = 0.0
            res = "timeout"
            when = None
            for d in tdays[a:]:
                if d >= end:
                    break
                day = 0.0
                for r in by_day[d].itertuples():
                    if day <= -stop or day <= -1000.0:
                        break
                    if bal + day + r.mae <= -2000.0:
                        res = "fail"
                        break
                    if day + r.mae <= -1000.0:
                        day = -1000.0
                        break  # DLL flattens trade
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

        def sh(m):
            return {o: round(100 * float((r.res[m] == o).mean()), 1) for o in ("pass", "fail", "timeout")}

        h1 = r.start < pd.Timestamp("2017-01-01").date()
        return dict(
            all=sh(np.ones(len(r), bool)),
            half1=sh(h1.to_numpy()),
            half2=sh((~h1).to_numpy()),
            starts=len(r),
            median_sessions_to_pass=float(r.sess.dropna().median()) if r.sess.notna().any() else None,
            p25_sessions_to_pass=float(r.sess.dropna().quantile(0.25)) if r.sess.notna().any() else None,
        )

    results = {}
    for k in (2, 3, 4):
        for night_on in (True, False):
            name = f"k{k} | overnight {'on' if night_on else 'off'}"
            c = results[name] = evaluate_variant(k, night_on)
            print(
                f"{name:20s} pass/fail/timeout {c['all']} | half1 {c['half1']['pass']} half2 {c['half2']['pass']} | median {c['median_sessions_to_pass']} p25 {c['p25_sessions_to_pass']}",
                flush=True,
            )

    return {
        "raw_stats": dict(trades=len(intra_df), net_pnl=tot_pnl, win_rate=wr, profit_factor=pf),
        "results": results,
    }

# 1. Baseline: v5.2 routed trades (all 4 sleeves: CRABEL, TRD60, MES30, TRD30PM)
intra_baseline = pl.route(base[base.risk_today <= 300.0]).copy()
baseline_eval = run_evaluation(intra_baseline, tag="BASELINE v5.2 (with TRD30PM)")

# 2. Ablated: v5.2 without TRD30PM
base_no_pm = base[~base.sleeve.str.contains("TRD30PM")].copy()
intra_ablated = pl.route(base_no_pm[base_no_pm.risk_today <= 300.0]).copy()
ablated_eval = run_evaluation(intra_ablated, tag="ABLATED v5.2 (WITHOUT TRD30PM)")

# Compare side-by-side
print("\n" + "=" * 65)
print("SIDE-BY-SIDE COMPARISON: BASELINE vs ABLATED (WITHOUT TRD30PM)")
print("=" * 65)
for k_str in ["k2 | overnight on", "k3 | overnight on", "k4 | overnight on"]:
    b = baseline_eval["results"][k_str]
    a = ablated_eval["results"][k_str]
    print(f"\n--- {k_str} ---")
    print(f"  Baseline: Pass {b['all']['pass']}% | Fail {b['all']['fail']}% | Timeout {b['all']['timeout']}% | Median {b['median_sessions_to_pass']}d (Half1: {b['half1']['pass']}%, Half2: {b['half2']['pass']}%)")
    print(f"  Ablated:  Pass {a['all']['pass']}% | Fail {a['all']['fail']}% | Timeout {a['all']['timeout']}% | Median {a['median_sessions_to_pass']}d (Half1: {a['half1']['pass']}%, Half2: {a['half2']['pass']}%)")

final_payload = {
    "baseline_v52": baseline_eval,
    "ablated_no_trd30pm": ablated_eval,
}

out_path = pl.ROOT / "reports/ABLATE_TRD30PM_TRAINING.json"
out_path.write_text(json.dumps(final_payload, indent=2, default=str), encoding="utf-8")
print(f"\nSaved full report to {out_path}")
