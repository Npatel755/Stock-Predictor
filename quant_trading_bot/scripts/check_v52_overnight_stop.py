"""Runner checks for ag_arch_d_plus_v2_price_aware_v52 and overnight_dip_v2_stop055 (Claude, 2026-11-10). TRAINING 2010-23 only.
(1) v5.2 runner replay vs research route at historical prices; (2) stopped overnight vs the payout_10 stop rule; (3) overnight_dip_v2 unchanged;
(4) live path: bars truncated mid-trade for both."""
import json
import numpy as np, pandas as pd
import payout_lib as pl

ep, bars_for, START, gs = pl.engine()
out = {}
# (1) v5.2 at historical prices
spec = ep.CANDIDATES["ag_arch_d_plus_v2_price_aware_v52"]; bars = {}
for sl in spec["sleeves"]: bars.setdefault(ep.bars_key(sl), bars_for(sl)[0])
runs = ep.run_routed(spec, bars, START); rt = [t for r in runs.values() for t in r["trades"]]
S = {"CRABEL": (dict(ep._AG_CRABEL15_D, name="AG_CRABEL15_D_1c"), True), "TRD60": (dict(ep._AG_TRD60_D, name="AG_TRD60_D_1c"), True),
     "MES30": (dict(ep._AG_MES_TRD30_D, name="AG_MES_TRD30_D_1c"), False), "TRD30PM": (dict(ep._AG_TRD30PM, name="AG_TRD30PM_1c"), False)}
T = pd.concat([pl.sleeve_trades(ep, bars_for, START, sl, i, flt) for i, (k, (sl, flt)) in enumerate(S.items())], ignore_index=True)
T["risk_then"] = T.stop_pct * T.entry * T.inst.map(pl.MULT) + 1.0 + 0.75 * T.inst.map(pl.MULT)
R = pl.route(T[T.risk_then <= 300.0]).copy()
cont = np.array([("CRABEL" in r.sleeve) and int(r.side) * gs.get(r.tin.date(), 0) >= 0 for r in R.itertuples()])
R["net_then"] = R.net_then * np.where(cont, 2.0, 1.0)
rd = pl.day_series(R, stop=400.0, col="net_then")
qd = pd.Series([float(t["net"]) for t in rt], index=[pd.Timestamp(t["exit_ts"]).tz_convert(pl.NY).date() for t in rt]).groupby(level=0).sum()
both = rd.index.union(qd.index); diff = (rd.reindex(both, fill_value=0) - qd.reindex(both, fill_value=0)).abs()
out["v52"] = dict(runner_trades=len(rt), runner_net=round(sum(float(t["net"]) for t in rt), 2), research_net=round(float(rd.sum()), 2),
                  days_differing=int((diff > 0.02).sum()), max_day_diff=round(float(diff.max()), 2), locks={n: r.get("lock") for n, r in runs.items() if r.get("lock")})
print("v52:", out["v52"], flush=True)
# (2)+(3) overnight
m1 = bars_for(dict(instrument="MNQ", bar_minutes=1))[0]; mes1 = bars_for(dict(instrument="MES", bar_minutes=1))[0]; ob = {"MNQ@1": m1, "MES@1": mes1}
base = list(ep.run_routed(ep.CANDIDATES["overnight_dip_v2"], ob, START).values())[0]["trades"]
stp = list(ep.run_routed(ep.CANDIDATES["overnight_dip_v2_stop055"], ob, START).values())[0]["trades"]
out["overnight_dip_v2_regression"] = dict(nights=len(base), net=round(sum(float(t["net"]) for t in base), 2), expected="518 / +11,145.31")
ts = pd.to_datetime(m1.timestamp_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy(); O, L = m1.open.to_numpy(float), m1.low.to_numpy(float)
mism = 0; n_stop_research = 0
for tb, tsx in zip(base, stp):
    e_raw = float(tb["entry_price"]) - 0.5; stop = None
    i0, i1 = int(np.searchsorted(ts, pd.Timestamp(tb["entry_ts"]).value)), int(np.searchsorted(ts, pd.Timestamp(tb["exit_ts"]).value))
    hit = np.nonzero(L[i0:i1] <= e_raw * (1 - 0.0055))[0]
    research_stopped = bool(len(hit)); n_stop_research += research_stopped
    mism += research_stopped != (tsx["reason"] == "stop")
out["overnight_stop055"] = dict(nights=len(stp), same_entries=bool([t["entry_ts"] for t in stp] == [t["entry_ts"] for t in base]),
                                runner_stop_exits=sum(t["reason"] == "stop" for t in stp), research_stop_exits=n_stop_research, stop_decision_mismatches=mism,
                                net=round(sum(float(t["net"]) for t in stp), 2), worst_night=round(min(float(t["net"]) for t in stp), 2))
print("overnight:", out["overnight_dip_v2_regression"], out["overnight_stop055"], flush=True)
# (4) live path
key = lambda t: (t["sleeve"], t["entry_ts"], t["exit_ts"], t["net"])
pick = next(t for t in reversed(sorted(rt, key=lambda t: t["entry_ts"])) if pd.Timestamp(t["exit_ts"]) - pd.Timestamp(t["entry_ts"]) >= pd.Timedelta(minutes=45))
cut = pd.Timestamp(pick["entry_ts"]) + pd.Timedelta(minutes=15)
part = ep.run_routed(spec, {k: v[v.timestamp_utc <= cut].reset_index(drop=True) for k, v in bars.items()}, START)
pt = [t for r in part.values() for t in r["trades"]]; closed = [t for t in rt if pd.Timestamp(t["exit_ts"]) <= cut - pd.Timedelta(minutes=60)]
out["v52_live_path"] = dict(cut=str(cut), open={n: r["position"]["quantity"] for n, r in part.items() if r["position"].get("quantity")},
                            prefix_ok=bool({key(t) for t in closed} <= {key(t) for t in pt}))
ns_ = next(t for t in reversed(stp) if t["reason"] != "stop"); cut2 = pd.Timestamp(ns_["entry_ts"]) + pd.Timedelta(hours=3)
p2 = list(ep.run_routed(ep.CANDIDATES["overnight_dip_v2_stop055"], {k: v[v.timestamp_utc <= cut2].reset_index(drop=True) for k, v in ob.items()}, START).values())[0]
out["overnight_live_path"] = dict(cut=str(cut2), open_qty=p2["position"]["quantity"], open_since=p2.get("open_since"),
                                  prefix_ok=bool({key(t) for t in stp if pd.Timestamp(t["exit_ts"]) < cut2} <= {key(t) for t in p2["trades"]}))
print("live:", out["v52_live_path"], out["overnight_live_path"], flush=True)
(pl.ROOT / "reports/CHECK_V52_OVERNIGHT_STOP.json").write_text(json.dumps(out, indent=1, default=str))
