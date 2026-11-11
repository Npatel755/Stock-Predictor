"""eval_20 (Claude, 2026-11-11): the eval_8 plan's pass / fail / timeout by START YEAR, 2010-23 training. Descriptive realism check."""
import json
import numpy as np, pandas as pd
from pathlib import Path
import eval_harness as eh

ROOT = Path(__file__).resolve().parents[1]
H = eh.Harness(); DEF = H.DEF_END
PD = H._per_day(H.BOOK[H.COLS].assign(noise=False)); TD = sorted(PD); TIX = pd.to_datetime(pd.Series(TD).astype(str)).to_numpy()
DAY = {k: {d: H.sim_day(PD[d], float(k)) for d in TD} for k in (1, 2, 3, 5)}


def attempt(start):
    end = (pd.Timestamp(start) + pd.Timedelta(days=90)).date(); i = int(np.searchsorted(TIX, np.datetime64(pd.Timestamp(start))))
    bal = 0.0; best = 0.0
    for d in TD[i:]:
        if d >= end: return "timeout", bal
        k = DEF(bal, (d - start).days, max(4000.0, best / 0.55), 0); p, w = DAY[k][d]
        if bal + min(w, p) <= -2000.0: return "fail", bal + min(w, p)
        bal += p; best = max(best, p)
        if bal >= max(4000.0, best / 0.55): return "pass", bal
    return "timeout", bal


r = pd.DataFrame([(s, *attempt(s)) for s in H.SESS], columns=["s", "o", "bal"]); r["y"] = [s.year for s in r.s]
tab = r.groupby("y").o.value_counts(normalize=True).unstack(fill_value=0).mul(100).round(1)
print(tab.to_string(), flush=True)
t = r[r.o == "timeout"]; print("timeouts", len(t), "final balance quartiles", t.bal.quantile([0.25, 0.5, 0.75]).round(0).to_dict(),
                              "share ending >= +$2,000", round(100 * float((t.bal >= 2000).mean()), 1), flush=True)
(ROOT / "reports/EVAL_20_BY_YEAR_TRAINING.json").write_text(json.dumps(dict(by_year=tab.to_dict(orient="index"),
    timeout_balance_quartiles=t.bal.quantile([0.25, 0.5, 0.75]).round(0).to_dict()), indent=1, default=str))


def attempt2(start):
    end = (pd.Timestamp(start) + pd.Timedelta(days=90)).date(); i = int(np.searchsorted(TIX, np.datetime64(pd.Timestamp(start))))
    bal = 0.0; best = 0.0
    for d in TD[i:]:
        if d >= end: return "timeout", bal, max(4000.0, best / 0.55)
        k = DEF(bal, (d - start).days, max(4000.0, best / 0.55), 0); p, w = DAY[k][d]
        if bal + min(w, p) <= -2000.0: return "fail", bal, max(4000.0, best / 0.55)
        bal += p; best = max(best, p)
        if bal >= max(4000.0, best / 0.55): return "pass", bal, max(4000.0, best / 0.55)
    return "timeout", bal, max(4000.0, best / 0.55)


q = pd.DataFrame([(s, *attempt2(s)) for s in H.SESS], columns=["s", "o", "bal", "tgt"]); tt = q[q.o == "timeout"]
print("timeouts ending >= $3,000:", round(100 * float((tt.bal >= 3000).mean()), 1), "% | >= $4,000 but target raised by the 55% rule:",
      round(100 * float((tt.bal >= 4000).mean()), 1), "% of timeouts =", round(100 * float(((q.o == "timeout") & (q.bal >= 4000)).mean()), 1),
      "% of all starts | passes whose target was raised:", round(100 * float(((q.o == "pass") & (q.tgt > 4000)).mean()), 1), "% of starts", flush=True)
