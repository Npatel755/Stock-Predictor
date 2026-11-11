"""payout_14 (Claude, 2026-11-10): which budget / account stop keeps the recommended setup safe if volatility stays 1.5x? TRAINING only.

PRE-DECLARED (after payout_13 showed 11.3% breach at vol x1.5, before running this): setup R = v5.2 + overnight (0.55% stop, on above a
$500 balance). Grid: per-micro budget B in {$300, $250, $200} x account stop A in {$400, $300}. Scenarios: S0 base and S4 vol x1.5 (as in
payout_13). Selection rule (worst-case first): among cells with S0 breach <= 2% AND S4 breach <= 5%, choose the most S0 payouts per 12 months.
"""
import json
import numpy as np, pandas as pd
import payout_lib as pl

src = (pl.ROOT / "scripts/payout_13_stress_train.py").read_text(encoding="utf-8").split("\nout = {}")[0]
ns = {"__name__": "p13"}; exec(src, ns)
base_intra, nights, stop_loss_level = ns["base_intra"], ns["nights"], ns["stop_loss_level"]
n0 = nights(0.0055)[["tin", "tout", "net_today"]]


def scenario(vol):
    d = base_intra.copy(); n = n0.copy()
    if vol != 1.0:
        d["risk_today"] *= vol; d["net_today"] *= vol
        stopped = n.net_today <= stop_loss_level + 1e-6; n.loc[~stopped, "net_today"] *= vol
    return d, n


def evaluate(d, n, B, A, S=500.0, C=1000.0):
    intra = pl.route(d[d.risk_today <= B])[["tin", "tout", "net_today"]]
    io = pl.day_series(intra, stop=A).to_dict(); wn = pl.day_series(pd.concat([intra, n], ignore_index=True), stop=A).to_dict()
    days = sorted(set(io) | set(wn)); idx = pd.to_datetime(pd.Series(days).astype(str)).to_numpy(); eff = {x: wn.get(x, 0.0) - io.get(x, 0.0) for x in days}
    res = []
    for s0 in pd.date_range("2010-07-01", "2023-01-01", freq="MS"):
        i0 = int(np.searchsorted(idx, np.datetime64(s0))); i1 = int(np.searchsorted(idx, np.datetime64(s0 + pd.DateOffset(months=12))))
        bal = 0.0; good = 0; pays = 0; breach = False
        for x in days[i0:i1]:
            p = io.get(x, 0.0) + (eff[x] if bal >= S else 0.0); bal += max(p, -1000.0)
            if bal <= -2000.0: breach = True; break
            good += p >= 150
            if good >= 5 and bal - C > 0: pays += 1; bal = C; good = 0
        res.append((pays, breach))
    r = pd.DataFrame(res, columns=["pays", "breach"])
    return dict(payouts_12m_mean=round(float(r.pays.mean()), 2), payouts_12m_p10=float(r.pays.quantile(.1)), p_breach_12m=round(float(r.breach.mean()), 3))


S0, S4 = scenario(1.0), scenario(1.5)
out = {}
for B in (300.0, 250.0, 200.0):
    for A in (400.0, 300.0):
        a, b = evaluate(*S0, B, A), evaluate(*S4, B, A)
        name = f"budget ${int(B)} / account stop ${int(A)}"
        out[name] = dict(S0=a, S4_vol_x1_5=b, eligible=bool(a["p_breach_12m"] <= 0.02 and b["p_breach_12m"] <= 0.05))
        print(f"{name:34s} S0 {a} | S4 {b} | eligible {out[name]['eligible']}", flush=True)
ok = {k: v for k, v in out.items() if v["eligible"]}
out["selected"] = max(ok, key=lambda k: ok[k]["S0"]["payouts_12m_mean"]) if ok else None
print("selected:", out["selected"])
(pl.ROOT / "reports/PAYOUT_14_HIGHVOL_GUARD_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
