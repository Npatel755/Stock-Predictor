"""ONE-SHOT holdout check of the eval_1 selection (k = 3, overnight on), frozen on training (reports/EVAL_1_SCALED_PAYOUT_BOOK_TRAINING.json).
Secondary evidence: 2024-26 was already read on 2026-11-10 for this book (holdout_payout24.py). Same rules as eval_1 (target $4,000,
static -$2,000 on unrealised P&L via each trade's 1-minute MAE, DLL $1,000 flatten, 55% consistency, 90 calendar days, size min(3 x base,
floor($900 / risk per micro)), overnight min(3, floor($900 / risk)), account stop $700). Starts: every session with 90 days of data after it.
Reported as is; nothing is changed after this run.
"""
import json
import numpy as np, pandas as pd
import payout_lib as pl
import holdout_payout24 as hp
from payout_17_bond_filter_train import stop_loss_level

K = 3; NIGHT_RISK = abs(float(stop_loss_level)); STOP = min(400.0 * K, 700.0)


def run(name):
    base, nights, last_bar, bars_for = hp.build(name)
    B = {}
    for inst in ("MNQ", "MES"):
        b = bars_for(dict(instrument=inst, bar_minutes=1))[0]
        B[inst] = (pd.to_datetime(b.timestamp_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy(), b.high.to_numpy(float), b.low.to_numpy(float))
    def mae(inst, tin, tout, side, entry):
        ts, H, L = B[inst]; i0, i1 = int(np.searchsorted(ts, tin.value)), int(np.searchsorted(ts, tout.value))
        if i1 <= i0: return 0.0
        w = L[i0:i1].min() if side > 0 else H[i0:i1].max(); return min(0.0, side * (w - entry) / entry)
    intra = pl.route(base[base.risk_today <= 300.0]).copy()
    intra["per_micro"] = intra.net_today / intra.n_contracts
    intra["mae_per_micro"] = [(mae(r.inst, r.tin, r.tout, r.side, r.entry) * pl.TODAY[r.inst] - pl.ADV) * pl.MULT[r.inst] for r in intra.itertuples()]
    a = intra.assign(q=np.minimum(K * intra.n_contracts, np.floor(900.0 / intra.risk_today)))
    qn = min(K, int(900.0 // NIGHT_RISK))
    n = nights.assign(per_micro=nights.net_today, q=float(qn))
    t = pd.concat([a[["tin", "tout", "per_micro", "mae_per_micro", "q"]], n[["tin", "tout", "per_micro", "mae_per_micro", "q"]]], ignore_index=True)
    t = t[t.q >= 1].assign(net=lambda x: x.per_micro * x.q, mae=lambda x: x.mae_per_micro * x.q, day=lambda x: x.tout.dt.date).sort_values("tin")
    by_day = {d: g for d, g in t.groupby("day")}; tdays = sorted(by_day); tix = pd.to_datetime(pd.Series(tdays).astype(str)).to_numpy()
    mn = bars_for(dict(instrument="MNQ", bar_minutes=1))[0]
    sess = sorted(d for d in set(pd.to_datetime(mn.timestamp_utc, utc=True).dt.tz_convert(pl.NY).dt.date)
                  if pd.Timestamp(d).dayofweek < 5 and d >= pd.Timestamp(hp.SPLITS[name]["lo"]).date())
    last = pd.Timestamp(last_bar).tz_convert(pl.NY).date(); out = []
    for s in sess:
        end = (pd.Timestamp(s) + pd.Timedelta(days=90)).date()
        if end > last: break
        i = int(np.searchsorted(tix, np.datetime64(pd.Timestamp(s)))); bal = 0.0; best = 0.0; res = "timeout"; when = None
        for d in tdays[i:]:
            if d >= end: break
            day = 0.0
            for r in by_day[d].itertuples():
                if day <= -STOP or day <= -1000.0: break
                if bal + day + r.mae <= -2000.0: res = "fail"; break
                if day + r.mae <= -1000.0: day = -1000.0; break
                day += r.net
            if res == "fail": break
            bal += max(day, -1000.0); best = max(best, day)
            if bal <= -2000.0: res = "fail"; break
            if bal >= max(4000.0, best / 0.55): res = "pass"; when = d; break
        out.append((s, res, None if when is None else int(np.busday_count(s, when)) + 1))
    r = pd.DataFrame(out, columns=["start", "res", "sess"])
    by_q = r.assign(q=pd.to_datetime(r.start).dt.to_period("Q").astype(str)).groupby("q").res.apply(lambda x: f"{100 * (x == 'pass').mean():.0f}% pass of {len(x)}").to_dict()
    return dict(starts=len(r), **{o: round(100 * float((r.res == o).mean()), 1) for o in ("pass", "fail", "timeout")},
                median_sessions_to_pass=float(r.sess.dropna().median()) if r.sess.notna().any() else None, by_start_quarter=by_q)


out = {name: run(name) for name in ("validation", "test")}
for k, v in out.items(): print(k, v, flush=True)
(pl.ROOT / "reports/HOLDOUT_EVAL1_RESULTS.json").write_text(json.dumps(out, indent=1, default=str))
