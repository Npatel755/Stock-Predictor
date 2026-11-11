"""payout_11 (Claude, 2026-11-10): v5.2 + stopped overnight leg, overnight leg enabled only above a buffer. TRAINING 2010-23 only.

PRE-DECLARED (after payout_10 failed its 2% breach gate at 2.6%, before running this): the overnight leg (stop 0.40% or 0.55%) trades a night
only if the account balance at the end of the previous session is >= S; intraday v5.2 always trades. Buffer for withdrawals C = $1,000.
S in {$500, $1,000}. Gate (same as payout_10): payouts/yr > 5.5 (v5.2) and 12-month breach <= 2% over 151 monthly starts, 0 days <= -$1,000.
Caveat recorded in advance: the overnight family failed its one-shot 2024-25 validation (Devin, overnight_2); a pass here is paper-only.
"""
import json, importlib.util, sys
import numpy as np, pandas as pd
import payout_lib as pl

spec = importlib.util.spec_from_file_location("p10", str(pl.ROOT / "scripts/payout_10_overnight_stop_train.py"))
src = (pl.ROOT / "scripts/payout_10_overnight_stop_train.py").read_text(encoding="utf-8").split("\nout = {}")[0]
ns = {"__name__": "p10"}; exec(src, ns)
intraday, nights = ns["intraday"], ns["nights"]


def run_window(intra_day, night_day, S, C, i0, i1, days):
    bal = 0.0; good = 0; pays = 0; breach = False
    for d in days[i0:i1]:
        p = intra_day.get(d, 0.0) + (night_day.get(d, 0.0) if bal >= S else 0.0)
        bal += max(p, -1000.0)
        if bal <= -2000.0: breach = True; break
        good += p >= 150
        if good >= 5 and bal - C > 0: pays += 1; bal = C; good = 0
    return pays, breach


out = {}
for s in (0.004, 0.0055):
    nd = nights(s)
    # account stop: a losing night counts toward the $400 intraday stop; compute intraday day P&L with the night's realised loss known first
    for S in (500.0, 1000.0):
        # build day P&L with and without the night (account stop applied in both)
        both = pd.concat([intraday[["tin", "tout", "net_today"]], nd[["tin", "tout", "net_today"]]], ignore_index=True)
        with_night = pl.day_series(both, stop=400.0); intra_only = pl.day_series(intraday[["tin", "tout", "net_today"]], stop=400.0)
        days = sorted(set(with_night.index) | set(intra_only.index)); idx = pd.to_datetime(pd.Series(days).astype(str)).to_numpy()
        wn, io = with_night.to_dict(), intra_only.to_dict()
        night_effect = {d: wn.get(d, 0.0) - io.get(d, 0.0) for d in days}
        full_pays, _ = run_window(io, night_effect, S, 1000.0, 0, len(days), days)
        res = []
        for s0 in pd.date_range("2010-07-01", "2023-01-01", freq="MS"):
            i0 = int(np.searchsorted(idx, np.datetime64(s0))); i1 = int(np.searchsorted(idx, np.datetime64(s0 + pd.DateOffset(months=12))))
            res.append(run_window(io, night_effect, S, 1000.0, i0, i1, days))
        r = pd.DataFrame(res, columns=["pays", "breach"])
        name = f"v5.2 + overnight stop {100*s:.2f}%, night only when balance >= ${int(S)}"
        out[name] = dict(payouts_per_year_14y=round(full_pays / 14, 2), payouts_12m_mean=round(float(r.pays.mean()), 2),
                         payouts_12m_p10_p90=[float(r.pays.quantile(.1)), float(r.pays.quantile(.9))], p_breach_12m=round(float(r.breach.mean()), 3),
                         worst_day=round(float(min(min(io.values()), min(wn.values()))), 0))
        out[name]["gate"] = bool(out[name]["payouts_per_year_14y"] > 5.5 and out[name]["p_breach_12m"] <= 0.02 and out[name]["worst_day"] > -1000)
        print(name, out[name], flush=True)
(pl.ROOT / "reports/PAYOUT_11_OVERNIGHT_STAGED_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
