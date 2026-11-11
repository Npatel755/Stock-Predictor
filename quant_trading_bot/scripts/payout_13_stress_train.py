"""payout_13 (Claude, 2026-11-10): stress test of the recommended payout setup. TRAINING 2010-23 only, today's price level.

PRE-DECLARED (before results): setups R = v5.2 + overnight dip (0.55% stop, night only when balance >= $500) and V = v5.2 alone; 50K static
floor -$2,000, DLL $1,000, $400 account stop, $1,000 buffer, 151 monthly 12-month starts.
Stresses: S1 costs +2 ticks per side on every contract (= +1.0 pt round trip per contract); S2 edge haircut: each trade loses 25% of its sleeve's
average net per trade (variance unchanged); S3 = S1 + S2; S4 volatility x1.5: stop risk x1.5 (more trades exceed the $300 budget), every
intraday trade's net x1.5, overnight non-stopped nights x1.5 and stopped nights keep their stop-out loss.
Report payouts per 12 months (mean, p10) and breach; a setup is called robust if it keeps >= 4 payouts per 12 months and <= 5% breach in S3.
"""
import json
import numpy as np, pandas as pd
import payout_lib as pl

src = (pl.ROOT / "scripts/payout_10_overnight_stop_train.py").read_text(encoding="utf-8").split("\nout = {}")[0]
ns = {"__name__": "p10"}; exec(src, ns)
T, nights, cont = ns["T"], ns["nights"], ns["cont"]
base_intra = pd.concat(list(T.values()), ignore_index=True)       # Crabel continuation already at 2 micros (payout_10 setup)
base_intra["n_contracts"] = 1.0
crab_idx = base_intra.index[base_intra.sleeve.str.contains("CRABEL")]
base_intra.loc[crab_idx[cont], "n_contracts"] = 2.0
nd0 = nights(0.0055); stop_loss_level = float(nd0.net_today.min())


def stressed(kind):
    d = base_intra.copy(); n = nights(0.0055).copy()
    if kind in ("S1", "S3"):
        d["net_today"] -= 1.0 * d.inst.map(pl.MULT) * d.n_contracts; n["net_today"] -= 1.0 * pl.MULT["MNQ"]
    if kind in ("S2", "S3"):
        avg = d.groupby("sleeve").net_today.transform("mean"); d["net_today"] -= 0.25 * avg.clip(lower=0)
        n["net_today"] -= 0.25 * max(float(n.net_today.mean()), 0.0)
    if kind == "S4":
        d["risk_today"] = d.risk_today * 1.5; d["net_today"] = d.net_today * 1.5
        stopped = n.net_today <= stop_loss_level + 1e-6
        n.loc[~stopped, "net_today"] = n.loc[~stopped, "net_today"] * 1.5
    intra = pl.route(d[d.risk_today <= 300.0])[["tin", "tout", "net_today"]]
    return intra, n[["tin", "tout", "net_today"]]


def evaluate(intra, n, with_night, S=500.0, C=1000.0):
    io = pl.day_series(intra, stop=400.0).to_dict()
    wn = pl.day_series(pd.concat([intra, n], ignore_index=True), stop=400.0).to_dict() if with_night else io
    days = sorted(set(io) | set(wn)); idx = pd.to_datetime(pd.Series(days).astype(str)).to_numpy()
    eff = {d: wn.get(d, 0.0) - io.get(d, 0.0) for d in days}; res = []
    for s0 in pd.date_range("2010-07-01", "2023-01-01", freq="MS"):
        i0 = int(np.searchsorted(idx, np.datetime64(s0))); i1 = int(np.searchsorted(idx, np.datetime64(s0 + pd.DateOffset(months=12))))
        bal = 0.0; good = 0; pays = 0; breach = False
        for d in days[i0:i1]:
            p = io.get(d, 0.0) + (eff[d] if bal >= S else 0.0)
            bal += max(p, -1000.0)
            if bal <= -2000.0: breach = True; break
            good += p >= 150
            if good >= 5 and bal - C > 0: pays += 1; bal = C; good = 0
        res.append((pays, breach))
    r = pd.DataFrame(res, columns=["pays", "breach"])
    return dict(payouts_12m_mean=round(float(r.pays.mean()), 2), payouts_12m_p10=float(r.pays.quantile(.1)), p_breach_12m=round(float(r.breach.mean()), 3))


out = {}
for kind in ("S0 base", "S1 costs +2 ticks/side", "S2 edge -25%", "S3 costs + edge", "S4 volatility x1.5"):
    intra, n = stressed(kind.split()[0])
    for name, wnight in (("R v5.2 + staged overnight", True), ("V v5.2 alone", False)):
        out[f"{kind} | {name}"] = r = evaluate(intra, n, wnight)
        print(f"{kind:24s} | {name:28s} {r}", flush=True)
for name in ("R v5.2 + staged overnight", "V v5.2 alone"):
    r = out[f"S3 costs + edge | {name}"]; out[f"robust | {name}"] = bool(r["payouts_12m_mean"] >= 4 and r["p_breach_12m"] <= 0.05)
print({k: v for k, v in out.items() if k.startswith("robust")})
(pl.ROOT / "reports/PAYOUT_13_STRESS_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
