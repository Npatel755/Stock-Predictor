"""Resolve the inside-the-minute ordering of the Crabel 16/28/120 trades (free-roll sprint + Vol-Adaptive Fortress) with Databento
1-second bars. TRAINING 2010-23 ONLY. Run after fetch_1s_crabel_train.py --download --scope amb.

PRE-DECLARED (before the 1-second data was seen):
- The 221 days where any 1-minute bar held both the stop and the entry/target are re-simulated on 1-second bars with exactly the same
  rules as audit_vol_adaptive_fortress_train.sim(pess=True) (the 15-minute range still comes from the 1-minute bars). A conflict left
  inside one second is resolved stop-first and counted. All other days keep the 1-minute result: with no conflicting bar their
  order is known, so the pessimistic and the true path agree there.
- Data check: the 1-second bars must reproduce the 1-minute highs/lows of the same minutes (report the match share).
- Report, beside the published (optimistic) and the worst case: 1-micro P&L per trade and profit factor, the Fortress ladder pass /
  fail / still-open shares over ALL windows at 100 and 252 sessions (prior-day VIX), with and without the 1-micro floor, and the
  free-roll sprint at its published 6 micros: net, worst day, days >= $150 per year.
- Verdict rule: the edge is called real only if the resolved 1-micro average per trade is > $0 AND the resolved profit factor >= 1.10.
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import audit_vol_adaptive_fortress_train as au

SEC = ROOT / "data/market/onesec_nq"


def one_sec_day(d):
    s = pd.read_parquet(SEC / f"{d}.parquet")
    ts = pd.to_datetime(s["ts_event"], utc=True).dt.tz_convert("America/New_York")
    s = s.assign(sod=(ts.dt.hour * 60 + ts.dt.minute).astype(int)).sort_values("ts_event")
    return s[(s.sod >= 585) & (s.sod <= 955)]


def main():
    dates, gap, G = au.load_train()
    by_date = {str(d)[:10]: d for d in dates}
    est = json.loads((SEC / "_spend_ledger.json").read_text())
    amb_days = sorted(est["days"])
    assert all(x < "2024-01-01" for x in amb_days)
    G1s, match, total = {}, 0, 0
    for x in amb_days:
        d = by_date[x]; g = G[d]; s = one_sec_day(x)
        m = g["sod"] < 585
        G1s[d] = dict(sod=np.concatenate([g["sod"][m], s.sod.to_numpy()]), open=np.concatenate([g["open"][m], s.open.to_numpy()]),
                      high=np.concatenate([g["high"][m], s.high.to_numpy()]), low=np.concatenate([g["low"][m], s.low.to_numpy()]),
                      close=np.concatenate([g["close"][m], s.close.to_numpy()]))
        agg = s.groupby("sod").agg(h=("high", "max"), l=("low", "min"))
        one = pd.DataFrame({"sod": g["sod"], "h": g["high"], "l": g["low"]}).set_index("sod").loc[lambda f: (f.index >= 585) & (f.index <= 955)]
        j = one.join(agg, rsuffix="_s", how="inner"); total += len(one)
        match += int(((j.h - j.h_s).abs() < 1e-9).mul((j.l - j.l_s).abs() < 1e-9).sum())
    out = {"data_check": dict(minutes=total, minutes_matching_1s_high_low=match, share=round(match / max(1, total), 4), days=len(amb_days))}
    print(out["data_check"], flush=True)
    res = {}
    for tag, vixf in (("same_day_vix", au.same_day_vix), ("prior_day_vix", au.prior_day_vix)):
        pub, _, _ = au.sim(dates, gap, G, vixf, pess=False)
        worst, _, _ = au.sim(dates, gap, G, vixf, pess=True)
        sec, amb_left, n_sec = au.sim([by_date[x] for x in amb_days], gap, G1s, vixf, pess=True)
        resolved = dict(worst); resolved.update(sec)
        res[tag] = dict(published=pub, worst_case=worst, resolved_1s=resolved, left_ambiguous_inside_one_second=f"{amb_left}/{n_sec}")
    for tag, r in res.items():
        vixf = au.same_day_vix if tag == "same_day_vix" else au.prior_day_vix
        o = out[tag] = {"left_ambiguous_inside_one_second": r.pop("left_ambiguous_inside_one_second")}
        for name, daily in r.items():
            n1 = np.array([v["net_1c"] for v in daily.values() if v["traded"]])
            six = pd.Series({k[:10]: v["net_1c"] * 6 for k, v in daily.items() if v["traded"]}); six.index = pd.to_datetime(six.index)
            o[name] = dict(trades=int(len(n1)), avg_per_trade_1c=round(float(n1.mean()), 2), pf_1c=round(float(n1[n1 > 0].sum() / -n1[n1 < 0].sum()), 3),
                           net_1c=round(float(n1.sum()), 0),
                           freeroll_6c=dict(net=round(float(six.sum()), 0), worst_day=round(float(six.min()), 0),
                                            days_ge_150_per_year=round(float((six >= 150).sum() / (len(dates) / 252)), 1)),
                           fortress_100=au.evaluate(dates, daily, vixf, 100), fortress_252=au.evaluate(dates, daily, vixf, 252),
                           fortress_100_no_floor=au.evaluate(dates, daily, vixf, 100, def_thr=-1e9))
            print(tag, name, {k: v for k, v in o[name].items() if k in ("trades", "avg_per_trade_1c", "pf_1c", "net_1c")},
                  "| F100", o[name]["fortress_100"]["pass_pct_of_all"], "| F252", o[name]["fortress_252"]["pass_pct_of_all"], o[name]["fortress_252"]["fail_pct"], flush=True)
    out["by_year_1c_prior_vix"] = {k: au.by_year(res["prior_day_vix"][k]) for k in ("published", "resolved_1s")}
    r = out["prior_day_vix"]["resolved_1s"]
    out["verdict_edge_real"] = bool(r["avg_per_trade_1c"] > 0 and r["pf_1c"] >= 1.10)
    print("verdict_edge_real:", out["verdict_edge_real"])
    (ROOT / "reports/RESOLVE_CRABEL_1S_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
