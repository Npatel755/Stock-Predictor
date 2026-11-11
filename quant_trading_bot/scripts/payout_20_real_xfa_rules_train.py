"""payout_20 (Claude, 2026-11-10): the payout book under Topstep's actual Express Funded Account (XFA) rules. TRAINING 2010-23 only.

Rules (help.topstep.com payout policy, XFA parameters, MLL and DLL articles, read 2026-11-10):
- Balance starts at $0. Maximum Loss Limit (MLL) starts at -$2,000 and trails the end-of-day balance (MLL = min(0, peak EOD balance - 2,000)),
  locking at $0 once the balance reaches $2,000. After the first payout the MLL is $0 permanently. Here the MLL is checked on realised day P&L
  (Topstep checks unrealised P&L in real time, so this is optimistic by the open loss of a trade inside a day).
- DLL $1,000: the day's loss is capped at -$1,000 and trading pauses for the session (not a violation).
- Standard path: 5 days with net >= $150 since the last payout (the count restarts after a payout and the request day does not count),
  positive profit since the last payout (first payout exempt). Payout = min(50% of balance, $2,000 cap, balance - K) and must be >= $125.
- Consistency path: >= 3 days with at least one trade since the last payout (request day excluded), window net profit > 0 and the largest
  winning day <= 40% of the window's net profit. Payout = min(50% of balance, $3,000 cap, balance - K), >= $125.
- K = balance kept after a payout (withdrawal policy, the trader's choice): K in {$0 (always take 50%), $500, $1,000, $1,500}.
Book: base R (v5.2 + overnight dip staged at a $500 balance, $400 account stop), stresses S0 / S3 / S4 as payout_13. 151 monthly 12-month
starts, each a fresh XFA. Measurement only (no gate): payouts per 12 months (mean, p10), $ withdrawn, share of accounts closed within 12 months,
by path and K, with the old static -$2,000 / $1,000-buffer model as the reference row.
"""
import json
import numpy as np, pandas as pd
import payout_lib as pl
from payout_17_bond_filter_train import fast_day_series, scenario, N0

H1, H2 = ("2010-07-01", "2016-12-01"), ("2017-01-01", "2023-01-01")


def series(kind, extra=None):
    i, n = scenario(kind, N0)
    parts = [i] + ([extra[kind]] if extra else [])
    return {False: fast_day_series(pd.concat(parts, ignore_index=True)).to_dict(),
            True: fast_day_series(pd.concat(parts + [n], ignore_index=True)).to_dict()}


def run(ser, path, K, S_night=500.0, start_from="2010-07-01", start_to="2023-01-01", static=False):
    days = sorted(set(ser[False]) | set(ser[True])); idx = pd.to_datetime(pd.Series(days).astype(str)).to_numpy(); res = []
    for s0 in pd.date_range(start_from, start_to, freq="MS"):
        a = int(np.searchsorted(idx, np.datetime64(s0))); b = int(np.searchsorted(idx, np.datetime64(s0 + pd.DateOffset(months=12))))
        bal = 0.0; peak = 0.0; paid_once = False; pays = []; closed = False
        cnt = 0; win = []; since = 0.0; skip_next = False
        for x in days[a:b]:
            p = max((ser[True] if bal >= S_night else ser[False]).get(x, 0.0), -1000.0)
            bal += p; since += p
            mll = -2000.0 if static else (0.0 if paid_once else min(0.0, peak - 2000.0))
            if bal <= mll: closed = True; break
            peak = max(peak, bal)
            if skip_next: skip_next = False; continue
            win.append(p)
            if static:
                cnt += p >= 150
                if cnt >= 5 and bal - 1000.0 > 0: pays.append(bal - 1000.0); bal = 1000.0; cnt = 0
                continue
            if path == "standard":
                cnt += p >= 150
                ok = cnt >= 5 and (since > 0 or not paid_once); cap = 2000.0
            else:
                tot = sum(win); ok = len(win) >= 3 and tot > 0 and max(win) <= 0.4 * tot; cap = 3000.0
            if ok:
                w = min(0.5 * bal, cap, bal - K)
                if w >= 125.0:
                    pays.append(w); bal -= w; paid_once = True; cnt = 0; win = []; since = 0.0; skip_next = True
        res.append((len(pays), closed, float(sum(pays))))
    r = pd.DataFrame(res, columns=["pays", "closed", "paid"])
    return dict(payouts_12m_mean=round(float(r.pays.mean()), 2), payouts_12m_p10=float(r.pays.quantile(.1)),
                closed_12m=round(float(r.closed.mean()), 3), withdrawn_12m_mean=round(float(r.paid.mean()), 0))


if __name__ == "__main__":
    SER = {k: series(k) for k in ("S0", "S3", "S4")}
    out = {"old model (static -$2,000, keep $1,000)": {k: run(SER[k], None, None, static=True) for k in ("S0", "S3", "S4")}}
    print("old model", out["old model (static -$2,000, keep $1,000)"], flush=True)
    for path in ("standard", "consistency"):
        for K in (0.0, 500.0, 1000.0, 1500.0):
            name = f"{path} | keep ${int(K)}"
            c = out[name] = {k: run(SER[k], path, K) for k in ("S0", "S3", "S4")}
            c["H1"] = run(SER["S0"], path, K, start_from=H1[0], start_to=H1[1]); c["H2"] = run(SER["S0"], path, K, start_from=H2[0], start_to=H2[1])
            print(name, c, flush=True)
    (pl.ROOT / "reports/PAYOUT_20_REAL_XFA_RULES_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
