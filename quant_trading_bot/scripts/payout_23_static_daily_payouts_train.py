"""payout_23 (Claude, 2026-11-10): the payout book on Topstep Labs' $50K Static (Daily Payouts+) funded account. TRAINING 2010-23 only.

Account rules (help.topstep.com Topstep Labs article, topstep.com/labs, Payout Policy; read 2026-11-10; conflicts resolved conservatively):
- Balance from $0. MLL -$2,000 static until the first payout; any payout (daily or 5-winning-day) sets it to $0 permanently. Checked here on
  realised day P&L (Topstep checks unrealised P&L in real time: optimistic by a trade's open loss inside a day).
- DLL $1,000 mandatory: the day's loss is capped at -$1,000 (soft breach, trading paused for the session).
- Daily route: at most one payout per trading day, only profit above a $2,000 buffer, $250 to $1,500 per request, net profit since the last
  payout > 0 (first payout exempt). Any payout resets the 5-winning-day count.
- 5-winning-day route: 5 days >= $150 since the last payout (request day excluded), payout <= 50% of balance, <= $8,000, >= $125.
PRE-DECLARED (before results). Books: B0 base R (v5.2 + overnight dip staged at a $500 balance) | B1 v5.2 + overnight every night. All trades
are flat inside one Topstep session (intraday exits <= 16:00 ET; overnight 18:05 ET -> <= 09:49 ET, no Friday entries).
Withdrawal policies: daily, keep K = $2,000 | $3,000 | $4,000 (take min($1,500, balance - K) whenever >= $250) | monthly (first eligible day
of each calendar month), keep $2,000 | $3,000 | 5-winning-day route, keep $2,500 (reference). 12 cells; stresses S0 / S3 / S4 (payout_13).
ELIGIBLE: S0 closed <= 3%, S3 <= 8%, S4 <= 15% (12-month windows). "Reaches 8": eligible AND S0 payouts >= 8 per 12 months AND >= 8 in both
halves of the starts (2010-07..2016-12, 2017-01..2023-01). Among those, the most S0 dollars withdrawn.
"""
import json
import numpy as np, pandas as pd
import payout_lib as pl
from payout_17_bond_filter_train import fast_day_series, scenario, N0

H1, H2 = ("2010-07-01", "2016-12-01"), ("2017-01-01", "2023-01-01")


def run(ser, S_night, pol, start_from="2010-07-01", start_to="2023-01-01"):
    mode, K = pol
    days = sorted(set(ser[False]) | set(ser[True])); idx = pd.to_datetime(pd.Series(days).astype(str)).to_numpy(); res = []
    for s0 in pd.date_range(start_from, start_to, freq="MS"):
        a = int(np.searchsorted(idx, np.datetime64(s0))); b = int(np.searchsorted(idx, np.datetime64(s0 + pd.DateOffset(months=12))))
        bal = 0.0; paid = False; pays = []; closed = False; since = 0.0; cnt = 0; skip = False; months = set()
        for x in days[a:b]:
            p = max((ser[True] if bal >= S_night else ser[False]).get(x, 0.0), -1000.0); bal += p; since += p
            if bal <= (0.0 if paid else -2000.0): closed = True; break
            if skip: skip = False
            else: cnt += p >= 150
            w = 0.0
            if mode in ("daily", "monthly") and (since > 0 or not paid) and bal - K >= 250.0:
                if mode == "daily" or (x.year, x.month) not in months: w = min(1500.0, bal - K)
            elif mode == "5wd" and cnt >= 5 and (since > 0 or not paid):
                w = min(0.5 * bal, 8000.0, bal - K); w = w if w >= 125.0 else 0.0
            if w > 0:
                pays.append(w); bal -= w; paid = True; since = 0.0; cnt = 0; skip = True; months.add((x.year, x.month))
        res.append((len(pays), closed, float(sum(pays)), len(months)))
    r = pd.DataFrame(res, columns=["pays", "closed", "paid", "months"])
    return dict(payouts_12m_mean=round(float(r.pays.mean()), 2), payouts_12m_p10=float(r.pays.quantile(.1)), closed_12m=round(float(r.closed.mean()), 3),
                withdrawn_12m_mean=round(float(r.paid.mean()), 0), months_with_payout=round(float(r.months.mean()), 1))


SER = {}
for kind in ("S0", "S3", "S4"):
    i, n = scenario(kind, N0)
    SER[kind] = {False: fast_day_series(i).to_dict(), True: fast_day_series(pd.concat([i, n], ignore_index=True)).to_dict()}
BOOKS = {"B0 base R": 500.0, "B1 overnight every night": -1e12}
POL = {"daily keep $2,000": ("daily", 2000.0), "daily keep $3,000": ("daily", 3000.0), "daily keep $4,000": ("daily", 4000.0),
       "monthly keep $2,000": ("monthly", 2000.0), "monthly keep $3,000": ("monthly", 3000.0), "5WD keep $2,500": ("5wd", 2500.0)}
out = {}
for bn, S in BOOKS.items():
    for pn, pol in POL.items():
        c = {k: run(SER[k], S, pol) for k in ("S0", "S3", "S4")}
        c["H1"] = run(SER["S0"], S, pol, *H1); c["H2"] = run(SER["S0"], S, pol, *H2)
        c["eligible"] = bool(c["S0"]["closed_12m"] <= 0.03 and c["S3"]["closed_12m"] <= 0.08 and c["S4"]["closed_12m"] <= 0.15)
        c["reaches_8"] = bool(c["eligible"] and min(c["S0"]["payouts_12m_mean"], c["H1"]["payouts_12m_mean"], c["H2"]["payouts_12m_mean"]) >= 8)
        out[f"{bn} | {pn}"] = c
        print(f"{bn:26s} | {pn:20s} S0 pays {c['S0']['payouts_12m_mean']:6} p10 {c['S0']['payouts_12m_p10']:4} months {c['S0']['months_with_payout']:4} "
              f"$ {c['S0']['withdrawn_12m_mean']:>6} closed {c['S0']['closed_12m']:.3f} | S3 cl {c['S3']['closed_12m']:.3f} $ {c['S3']['withdrawn_12m_mean']:>6} "
              f"| S4 cl {c['S4']['closed_12m']:.3f} | H1 {c['H1']['payouts_12m_mean']} H2 {c['H2']['payouts_12m_mean']} | elig {c['eligible']} 8+ {c['reaches_8']}", flush=True)
ok = {k: v for k, v in out.items() if v["reaches_8"]}
out["selected"] = max(ok, key=lambda k: ok[k]["S0"]["withdrawn_12m_mean"]) if ok else None
print("selected:", out["selected"])
(pl.ROOT / "reports/PAYOUT_23_STATIC_DAILY_PAYOUTS_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
