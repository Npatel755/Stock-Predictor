"""eval_24 (Claude, 2026-11-11): WHEN to buy the Combine - a market-regime gate on the purchase date. TRAINING 2010-23 only.

Why (written before results): eval_20 shows the eval_8 plan's pass rate swings 9-96% by start year, and eval_16 shows the book earns in
volatile markets. eval_15 showed a FAILED ATTEMPT does not predict the next one (the book's own state has little persistence), but market
volatility is strongly persistent at month scales. Nick chooses the purchase day; if a regime observable at purchase predicts the next
90 days, buying only when it is favourable raises the per-attempt rate at the cost of waiting. Not tested before (lessons: only trade-level
gates, e.g. the 200-SMA direction gate, which was noise - hence the placebo below).

PRE-DECLARED (before any result). Plan = eval_8 (DEF_END) on the harness book; starts = H.A (2010-06..2016) and H.B (2017..2023-09);
per-start outcome identical to the incumbent (asserted 54.5 / 65.6). Features use MNQ 1-minute bars up to the RTH close (16:00 ET) of the
session BEFORE the start. Daily return = log(RTH close / RTH open) + overnight gap log(RTH open / prior RTH close), the gap set to 0 for
sessions from 9 days before to the 3rd Friday of Mar / Jun / Sep / Dec (the c.0 series is not back-adjusted; this removes roll jumps).
  VOLHI   V20 (st.dev. of the last 20 daily returns) > median of V20 over the prior 250 sessions (>= 120 needed, else closed)
  VOLLO   V20 < that median
  VOLUP   V20 > V60
  ER_HI   ER60 = |sum of last 60 returns| / sum of |returns| > its prior-250 median
  CORR    cumulative-return index < 0.95 x its max over the prior 250 sessions (in a >= 5% pullback)
  BOOK60  the book's k1 P&L over the prior 60 sessions > 0 (reports/EVAL_BOOK_DAILY_TRAINING.csv)
  BOOK120 the same over 120 sessions > 0
Eligible: gate open on >= 25% of start sessions in BOTH halves. PRIMARY = per-attempt pass rate among starts with the gate open.
2-fold: pick the eligible gate with the best 2010-16 rate, report its 2017-23 rate, and vice versa. ADOPT only if (a) both out-of-fold
halves >= 55.5 / 66.6 (ungated + 1.0) AND (b) placebo: the picked gate's lift over ungated ranks >= 90th percentile of 500 circular shifts
of its own open/closed series (offset 120..n-120 sessions, same coverage and run lengths) in EACH half (seed 24).
Secondary (information): two sequential attempts where every purchase waits for an open gate; P(pass within 180 days of the decision day)
vs ungated; mean wait in sessions. Also reported: rank correlation of each raw feature with the start's outcome per half (descriptive).
"""
import json
import numpy as np, pandas as pd
from pathlib import Path
import eval_harness as eh

ROOT = Path(__file__).resolve().parents[1]; NY = "America/New_York"
H = eh.Harness(); DEF = H.DEF_END
PD = H._per_day(H.BOOK[H.COLS].assign(noise=False)); TD = sorted(PD); TIX = pd.to_datetime(pd.Series(TD).astype(str)).to_numpy()
DAY = {k: {d: H.sim_day(PD[d], float(k)) for d in TD} for k in (1, 2, 3, 5)}
LAST = TD[-1]; SESS = list(H.SESS); SIX = np.array(SESS, dtype=object)


def run(start):
    end = (pd.Timestamp(start) + pd.Timedelta(days=90)).date(); i = int(np.searchsorted(TIX, np.datetime64(pd.Timestamp(start))))
    bal = 0.0; best = 0.0
    for d in TD[i:]:
        if d >= end: return "timeout", end
        k = DEF(bal, (d - start).days, max(4000.0, best / 0.55), 0); p, w = DAY[k][d]
        if bal + min(w, p) <= -2000.0: return "fail", d
        bal += p; best = max(best, p)
        if bal >= max(4000.0, best / 0.55): return "pass", d
    return "timeout", end


CACHE = {}
def plain(s):
    if s not in CACHE: CACHE[s] = run(s)
    return CACHE[s]


PASS = {s: plain(s)[0] == "pass" for s in list(H.A) + list(H.B)}
a0 = round(100 * np.mean([PASS[s] for s in H.A]), 1); b0 = round(100 * np.mean([PASS[s] for s in H.B]), 1)
print("ungated", a0, b0, flush=True); assert (a0, b0) == (54.5, 65.6)

# ---------------- features (known at the prior session's RTH close)
m1 = H.E9["P10"]["m1"]; t = pd.to_datetime(m1.timestamp_utc, utc=True)
assert t.max() < pd.Timestamp("2024-01-01", tz="UTC")
t = t.dt.tz_convert(NY); mi = (t.dt.hour * 60 + t.dt.minute - 570).to_numpy()
r = pd.DataFrame(dict(d=t.dt.date.to_numpy(), m=mi, o=m1.open.to_numpy(float), c=m1.close.to_numpy(float)))[lambda x: (x.m >= 0) & (x.m < 390)]
g = r.groupby("d"); cnt = g.size(); D = pd.DataFrame(dict(o=g.o.first(), c=g.c.last()))[cnt >= 300]
D.index = pd.Index(D.index)


def third_friday(y, m):
    d = pd.Timestamp(y, m, 1); return (d + pd.Timedelta(days=(4 - d.weekday()) % 7 + 14)).date()


ROLL = set()
for y in range(2009, 2025):
    for m in (3, 6, 9, 12):
        f = third_friday(y, m)
        for k in range(0, 10): ROLL.add(f - pd.Timedelta(days=k).to_pytimedelta())
gap = np.log(D.o / D.c.shift(1)); gap[[d in ROLL for d in D.index]] = 0.0; gap = gap.fillna(0.0)
ret = np.log(D.c / D.o) + gap
print("largest |gap| kept", gap.abs().sort_values().tail(5).round(4).to_dict(), flush=True)
V20 = ret.rolling(20).std(); V60 = ret.rolling(60).std()
ER60 = ret.rolling(60).sum().abs() / ret.abs().rolling(60).sum()
IDX = ret.cumsum()
med = lambda x: x.rolling(250, min_periods=120).median()
F = pd.DataFrame(dict(VOLHI=V20 > med(V20), VOLLO=V20 < med(V20), VOLUP=V20 > V60, ER_HI=ER60 > med(ER60),
                      CORR=IDX < np.log(0.95) + IDX.rolling(250, min_periods=120).max()))
F[(med(V20).isna())] = False
bd = pd.read_csv(eh.DAILY, parse_dates=["day"]); bd["day"] = bd.day.dt.date; k1 = bd.set_index("day").k1
F = F.join(pd.DataFrame(dict(BOOK60=k1.rolling(60).sum() > 0, BOOK120=k1.rolling(120).sum() > 0)), how="outer").fillna(False).astype(bool)
RAW = pd.DataFrame(dict(V20=V20, V20_V60=V20 / V60, ER60=ER60, PULLBACK=IDX - IDX.rolling(250, min_periods=120).max())).join(
    pd.DataFrame(dict(BOOK60=k1.rolling(60).sum(), BOOK120=k1.rolling(120).sum())), how="outer")
FIX = np.array(sorted(F.index), dtype=object); F = F.loc[list(FIX)]; RAW = RAW.reindex(list(FIX))


def prior(s):
    j = int(np.searchsorted(FIX, s, side="left")) - 1; return FIX[j] if j >= 0 else None


GATES = list(F.columns)
G = {}
for half, starts in (("h1", list(H.A)), ("h2", list(H.B))):
    pv = [prior(s) for s in starts]
    G[half] = dict(starts=starts, y=np.array([PASS[s] for s in starts]),
                   gate={c: np.array([bool(F.at[p, c]) if p is not None else False for p in pv]) for c in GATES},
                   raw={c: np.array([RAW.at[p, c] if p is not None else np.nan for p in pv], dtype=float) for c in RAW.columns})

out = {"ungated": dict(h1=a0, h2=b0), "gates": {}, "descriptive_spearman": {}}
for c in GATES:
    row = {}
    for half in ("h1", "h2"):
        x = G[half]; m = x["gate"][c]
        row[half] = dict(coverage=round(100 * m.mean(), 1), n=int(m.sum()), pass_=round(100 * x["y"][m].mean(), 1) if m.any() else None,
                         closed_pass=round(100 * x["y"][~m].mean(), 1) if (~m).any() else None)
    row["eligible"] = bool(row["h1"]["coverage"] >= 25 and row["h2"]["coverage"] >= 25)
    out["gates"][c] = row; print(c, row, flush=True)
for c in RAW.columns:
    out["descriptive_spearman"][c] = {h: round(float(pd.Series(G[h]["raw"][c]).corr(pd.Series(G[h]["y"].astype(float)), method="spearman")), 3)
                                      for h in ("h1", "h2")}
print("spearman", out["descriptive_spearman"], flush=True)

ok = [c for c in GATES if out["gates"][c]["eligible"]]
pA = max(ok, key=lambda c: out["gates"][c]["h1"]["pass_"]); pB = max(ok, key=lambda c: out["gates"][c]["h2"]["pass_"])
oA, oB = out["gates"][pB]["h1"]["pass_"], out["gates"][pA]["h2"]["pass_"]
rng = np.random.default_rng(24)


def placebo(c, half):
    x = G[half]; m = x["gate"][c]; y = x["y"]; n = len(m); real = y[m].mean() - y.mean()
    sh = [y[np.roll(m, int(k))].mean() - y.mean() for k in rng.integers(120, n - 120, 500)]
    return dict(lift=round(100 * real, 1), rank=round(float(np.mean(np.array(sh) < real)), 3), p95=round(100 * float(np.percentile(sh, 95)), 1))


PL = {c: {h: placebo(c, h) for h in ("h1", "h2")} for c in sorted({pA, pB})}
ranks_ok = all(PL[c][h]["rank"] >= 0.90 for c in PL for h in ("h1", "h2"))
out["result"] = dict(pick_h1=pA, pick_h2=pB, oof_h1=oA, oof_h2=oB, placebo=PL,
                     adopt=bool(oA >= a0 + 1.0 and oB >= b0 + 1.0 and ranks_ok))
print("result", out["result"], flush=True)


# ---------------- secondary: two sequential attempts, each purchase waits for an open gate
def nxt(d):
    j = int(np.searchsorted(SIX, d, side="right")); return SESS[j] if j < len(SESS) else None


def open_from(d, c):
    """first session >= d whose gate (as of the prior close) is open"""
    j = int(np.searchsorted(SIX, d, side="left"))
    while j < len(SESS):
        s = SESS[j]; p = prior(s)
        if c is None or (p is not None and bool(F.at[p, c])): return s
        j += 1
    return None


def two(d0, c):
    s = open_from(d0, c); wait = None if s is None else SESS.index(s) - SESS.index(d0)
    for _ in range(2):
        if s is None or (pd.Timestamp(s) + pd.Timedelta(days=90)).date() > LAST: return False, wait
        o, e = plain(s)
        if o == "pass": return (e - d0).days <= 180, wait
        n = nxt(e); s = open_from(n, c) if n is not None else None
    return False, wait


dec = [d for d in SESS if (pd.Timestamp(d) + pd.Timedelta(days=270)).date() <= LAST and d >= H.A[0]]
hd = np.array([d < eh.H1_END for d in dec])
out["two_attempts_180d"] = {}
for c in [None] + sorted({pA, pB}):
    res = [two(d, c) for d in dec]; w = np.array([x[0] for x in res]); wt = np.array([np.nan if x[1] is None else x[1] for x in res], float)
    out["two_attempts_180d"][c or "UNGATED"] = dict(h1=round(100 * w[hd].mean(), 1), h2=round(100 * w[~hd].mean(), 1),
                                                    mean_wait_sessions=round(float(np.nanmean(wt)), 1))
    print("two attempts", c or "UNGATED", out["two_attempts_180d"][c or "UNGATED"], flush=True)
(ROOT / "reports/EVAL_24_PURCHASE_TIMING_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
