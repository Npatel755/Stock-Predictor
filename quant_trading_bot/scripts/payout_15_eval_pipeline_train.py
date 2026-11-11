"""payout_15 (Claude, 2026-11-10): evaluation leg of the payout pipeline at today's prices. TRAINING 2010-23 only.

PRE-DECLARED (before results): run the payout setups through a Topstep 50K static evaluation from each of 151 monthly starts: pass when
cumulative P&L >= +$4,000 with the best day < 50% of the profit at that moment, fail at <= -$2,000 (static) or a day <= -$1,000, else open
after 12 months. Setups: V = v5.2; R = v5.2 + overnight (0.55% stop) on once balance >= $500. Report pass / fail / open, median and p75
trading days to pass, and the implied time to the first payout (pass time + median days to the first 5 qualifying days in the funded account).
"""
import json
import numpy as np, pandas as pd
import payout_lib as pl

src = (pl.ROOT / "scripts/payout_13_stress_train.py").read_text(encoding="utf-8").split("\nout = {}")[0]
ns = {"__name__": "p13"}; exec(src, ns)
base_intra, nights = ns["base_intra"], ns["nights"]
intra = pl.route(base_intra[base_intra.risk_today <= 300.0])[["tin", "tout", "net_today"]]
n = nights(0.0055)[["tin", "tout", "net_today"]]
io = pl.day_series(intra, stop=400.0).to_dict(); wn = pl.day_series(pd.concat([intra, n], ignore_index=True), stop=400.0).to_dict()
days = sorted(set(io) | set(wn)); idx = pd.to_datetime(pd.Series(days).astype(str)).to_numpy(); eff = {x: wn.get(x, 0.0) - io.get(x, 0.0) for x in days}
# calendar of real sessions for "trading days" (all weekdays with RTH data in the training bars)
sessions = pd.bdate_range("2010-06-01", "2023-12-29")


def evaluation(with_night):
    res = []
    for s0 in pd.date_range("2010-07-01", "2023-01-01", freq="MS"):
        i0 = int(np.searchsorted(idx, np.datetime64(s0))); i1 = int(np.searchsorted(idx, np.datetime64(s0 + pd.DateOffset(months=12))))
        cum = 0.0; best = 0.0; outcome = "open"; end = None; first_funded = None
        for x in days[i0:i1]:
            p = io.get(x, 0.0) + (eff[x] if (with_night and cum >= 500.0) else 0.0)
            if p <= -1000: outcome, end = "fail_dll", x; break
            cum += p; best = max(best, p)
            if cum <= -2000: outcome, end = "fail_floor", x; break
            if cum >= 4000 and best < 0.5 * cum: outcome, end = "pass", x; break
        tdays = int(((sessions >= s0) & (sessions <= pd.Timestamp(str(end)))).sum()) if outcome == "pass" else None
        # funded phase: sessions from the pass to the 5th qualifying day (same setup, fresh account, no withdrawal yet)
        if outcome == "pass":
            j0 = days.index(end) + 1; good = 0; bal = 0.0
            for x in days[j0:]:
                p = io.get(x, 0.0) + (eff[x] if (with_night and bal >= 500.0) else 0.0); bal += p; good += p >= 150
                if good >= 5: first_funded = int(((sessions > pd.Timestamp(str(end))) & (sessions <= pd.Timestamp(str(x)))).sum()); break
        res.append((outcome, tdays, first_funded))
    r = pd.DataFrame(res, columns=["outcome", "days_to_pass", "days_pass_to_first_payout"])
    p = r[r.outcome == "pass"]
    tot = (p.days_to_pass + p.days_pass_to_first_payout).dropna()
    return dict(starts=len(r), pass_rate=round(float((r.outcome == "pass").mean()), 3), fail_floor=round(float((r.outcome == "fail_floor").mean()), 3),
                fail_dll=round(float((r.outcome == "fail_dll").mean()), 3), open_after_12m=round(float((r.outcome == "open").mean()), 3),
                median_trading_days_to_pass=float(p.days_to_pass.median()) if len(p) else None, p75_trading_days_to_pass=float(p.days_to_pass.quantile(.75)) if len(p) else None,
                median_trading_days_pass_to_first_payout=float(p.days_pass_to_first_payout.median()) if len(p) else None,
                median_trading_days_start_to_first_payout=float(tot.median()) if len(tot) else None)


out = {"V v5.2": evaluation(False), "R v5.2 + staged overnight": evaluation(True)}
for k, v in out.items(): print(k, v, flush=True)
(pl.ROOT / "reports/PAYOUT_15_EVAL_PIPELINE_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
