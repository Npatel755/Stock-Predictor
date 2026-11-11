"""payout_10 (Claude, 2026-11-10): add the overnight reopen-dip (overnight_dip_v2) as a separate overnight leg with a % stop. TRAINING only.

PRE-DECLARED (before results): v5.2 = v5 + TRD30PM + 2 micros on gap-continuation Crabel (payout_9), intraday, research routing.
Overnight leg = the runner's own overnight_dip_v2 nights (18:05 -> 09:45 ET, MNQ, buy when MNQ and MES reopen <= -0.5 sd), 1 micro, with a
protective stop s below the raw entry, walked on 1-min MNQ bars (gap-through fills at the bar open). s in {none, 0.40%, 0.55%, 0.75%}
(~$225 / $308 / $420 per micro at NQ 27,981). Re-expressed at today's price; the night counts on its 09:45 exit day, so a losing night
counts toward the $400 account stop before the day's intraday entries. Gate: payouts/yr up vs v5.2, 12-month breach <= 2%, 0 days <= -$1,000.
"""
import json
import numpy as np, pandas as pd
import payout_lib as pl

ep, bars_for, START, gs = pl.engine()
S = {"CRABEL": (dict(ep._AG_CRABEL15_D, name="AG_CRABEL15_D_1c"), True), "TRD60": (dict(ep._AG_TRD60_D, name="AG_TRD60_D_1c"), True),
     "MES30": (dict(ep._AG_MES_TRD30_D, name="AG_MES_TRD30_D_1c"), False), "TRD30PM": (dict(ep._AG_TRD30PM, name="AG_TRD30PM_1c"), False)}
T = {k: pl.price_normalize(pl.sleeve_trades(ep, bars_for, START, sl, i, flt)) for i, (k, (sl, flt)) in enumerate(S.items())}
c = T["CRABEL"]; cont = np.array([int(r.side) * gs.get(r.tin.date(), 0) >= 0 for r in c.itertuples()]); c.loc[cont, "net_today"] *= 2.0
intraday = pl.route(pd.concat(list(T.values()), ignore_index=True).pipe(lambda d: d[d.risk_today <= 300.0]))

m1 = bars_for(dict(instrument="MNQ", bar_minutes=1))[0]; mes1 = bars_for(dict(instrument="MES", bar_minutes=1))[0]
ov = list(ep.run_routed(ep.CANDIDATES["overnight_dip_v2"], {"MNQ@1": m1, "MES@1": mes1}, START).values())[0]["trades"]
ts = pd.to_datetime(m1.timestamp_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy(); O, L = m1.open.to_numpy(float), m1.low.to_numpy(float)
print("1-min bar unit check:", m1.timestamp_utc.dtype, "first ns", ts[0], flush=True)
print(f"overnight nights {len(ov)}, net_then {sum(float(t['net']) for t in ov):,.0f}", flush=True)


def nights(s):
    rows = []
    for t in ov:
        e_raw = float(t["entry_price"]) - pl.ADV; x_raw = float(t["exit_price"]) + pl.ADV
        tin, tout = pd.Timestamp(t["entry_ts"]), pd.Timestamp(t["exit_ts"])
        if s is not None:
            stop = e_raw * (1 - s); i0, i1 = int(np.searchsorted(ts, tin.value)), int(np.searchsorted(ts, tout.value))
            hit = np.nonzero(L[i0:i1] <= stop)[0]
            if len(hit):
                j = i0 + int(hit[0]); x_raw = min(stop, O[j]) if j > i0 else stop
        pct = (x_raw - e_raw) / e_raw
        rows.append(dict(tin=tin.tz_convert(pl.NY), tout=tout.tz_convert(pl.NY), inst="MNQ",
                         net_today=(pct * pl.TODAY["MNQ"] - 2 * pl.ADV) * pl.MULT["MNQ"] - pl.FEE))
    return pd.DataFrame(rows)


out = {}
out["v5.2 (no overnight)"] = pl.summ(pl.day_series(intraday, stop=400.0)); print(pl.fmt("v5.2 (no overnight)", out["v5.2 (no overnight)"]), flush=True)
for s in (None, 0.004, 0.0055, 0.0075):
    nd = nights(s)
    name = f"v5.2 + overnight, stop {'none' if s is None else f'{100*s:.2f}%'}"
    both = pd.concat([intraday[["tin", "tout", "net_today"]], nd[["tin", "tout", "net_today"]]], ignore_index=True)
    out[name] = pl.summ(pl.day_series(both, stop=400.0))
    out[name]["overnight_alone_net_per_year"] = round(float(nd.net_today.sum()) / 14, 0)
    out[name]["overnight_worst_night"] = round(float(nd.net_today.min()), 0)
    out[name]["gate"] = bool(out[name]["payouts_per_year"] > out["v5.2 (no overnight)"]["payouts_per_year"] and out[name]["p_breach_12m"] <= 0.02 and out[name]["dll_days"] == 0)
    print(pl.fmt(name, out[name]), "| night alone/yr", out[name]["overnight_alone_net_per_year"], "worst night", out[name]["overnight_worst_night"], "| gate", out[name]["gate"], flush=True)
(pl.ROOT / "reports/PAYOUT_10_OVERNIGHT_STOP_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
