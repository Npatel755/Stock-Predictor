"""eval_3 (Claude, 2026-11-10): does WHEN you start the evaluation predict passing? TRAINING 2010-23 only.

PRE-DECLARED (before results). Attempt = eval_1 selection (payout book at k = 3, overnight on, $4,000 target, static -$2,000 floor checked on
each trade's 1-minute MAE, DLL $1,000, 55% consistency, 90 calendar days); one attempt per session start 2010-06..2023-09 (eval_1's starts).
Start-day features, all known at the prior session close: VIX close | VIX / VIX3M | NQ close vs its 50-session average | NQ 20-session
realised volatility | the book's own 1x P&L over the prior 20 sessions. Each feature is cut into thirds using the 2010-06..2016-12 starts only;
filter = "start only when the feature is in third b". 15 filters.
SELECTION on 2010-06..2016-12: the highest pass share among filters keeping >= 25% of those starts.
CONFIRMATION on 2017-01..2023-09 (same cut points), all required: pass share >= the unfiltered 2017-23 pass share + 5 points; keeps >= 15% of
starts; beats >= 190 of 200 block placebos (random 21-session blocks of 2017-23 starts totalling the same count; seed 20261110), because
neighbouring starts share most of their 90 days.
"""
import json
import numpy as np, pandas as pd
import payout_lib as pl

src = (pl.ROOT / "scripts/eval_1_scaled_payout_book_train.py").read_text(encoding="utf-8").split("\nout = {}\n")[0]
E1 = {"__name__": "e1"}; exec(src, E1)
trades, SESS, mnq, p17 = E1["trades"], E1["SESS"], E1["mnq"], E1["p17"]
SEED = 20261110; H1_END = pd.Timestamp("2017-01-01").date()

t = trades(3, True); BY = {d: g for d, g in t.groupby("day")}; TD = sorted(BY); TIX = pd.to_datetime(pd.Series(TD).astype(str)).to_numpy()


def outcome(s):
    end = (pd.Timestamp(s) + pd.Timedelta(days=90)).date(); a = int(np.searchsorted(TIX, np.datetime64(pd.Timestamp(s)))); bal = 0.0; best = 0.0
    for d in TD[a:]:
        if d >= end: return "timeout"
        day = 0.0
        for r in BY[d].itertuples():
            if day <= -700.0 or day <= -1000.0: break
            if bal + day + r.mae <= -2000.0: return "fail"
            if day + r.mae <= -1000.0: day = -1000.0; break
            day += r.net
        bal += max(day, -1000.0); best = max(best, day)
        if bal <= -2000.0: return "fail"
        if bal >= max(4000.0, best / 0.55): return "pass"
    return "timeout"


res = pd.DataFrame({"start": SESS, "out": [outcome(s) for s in SESS]}); res["passed"] = res.out == "pass"

# ---- point-in-time features (value known at the close before the start)
def cboe(n):
    d = pd.read_csv(pl.ROOT / f"data/external/{n}_History.csv"); return pd.Series(d.CLOSE.astype(float).to_numpy(), index=pd.to_datetime(d.DATE, format="%m/%d/%Y").dt.date).groupby(level=0).last()
vix, vix3m = cboe("VIX"), cboe("VIX3M"); ratio = (vix / vix3m).dropna()
et = pd.to_datetime(mnq.timestamp_utc, utc=True).dt.tz_convert(pl.NY)
sod = (et.dt.hour * 60 + et.dt.minute)
rth = pd.DataFrame({"date": et.dt.date, "close": mnq.close.astype(float), "k": mnq.contract})[(sod >= 570) & (sod <= 959)]
daily = rth.groupby("date").agg(close=("close", "last"), k=("k", "last"))
ret = daily.close.pct_change().where(daily.k == daily.k.shift(1), 0.0).fillna(0.0)
idx = (1 + ret).cumprod()
trend = idx / idx.rolling(50).mean() - 1; rv = ret.rolling(20).std() * np.sqrt(252)
book = pd.Series(p17.fast_day_series(pd.concat([p17.scenario("S0", p17.N0)[0], p17.N0[["tin", "tout", "net_today"]]], ignore_index=True)).to_dict())
book.index = pd.to_datetime(pd.Series(book.index).astype(str)).dt.date
sess_all = sorted(daily.index); bk = pd.Series(0.0, index=sess_all).add(book.reindex(sess_all).fillna(0.0), fill_value=0.0)
mom20 = bk.rolling(20).sum()


def prior(series, d):
    s = series[series.index < d]; return float(s.iloc[-1]) if len(s) else np.nan


FEAT = {"VIX": vix, "VIX/VIX3M": ratio, "NQ vs 50-day avg": trend, "NQ 20-day vol": rv, "book 20-session P&L": mom20}
for name, ser in FEAT.items():
    ser = ser.dropna(); keys = np.array(ser.index); vals = ser.to_numpy()
    pos = np.searchsorted(keys, np.array(res.start.tolist()), side="left") - 1
    res[name] = np.where(pos >= 0, vals[np.clip(pos, 0, len(vals) - 1)], np.nan)

h1 = res[res.start < H1_END]; h2 = res[res.start >= H1_END]
out = dict(base=dict(all=round(100 * res.passed.mean(), 1), h1=round(100 * h1.passed.mean(), 1), h2=round(100 * h2.passed.mean(), 1), starts=len(res)), filters={})
print("base pass %:", out["base"], flush=True)
cands = {}
for name in FEAT:
    q1, q2 = np.nanquantile(h1[name], [1 / 3, 2 / 3])
    for b, (lo, hi) in (("low", (-np.inf, q1)), ("mid", (q1, q2)), ("high", (q2, np.inf))):
        m1 = (h1[name] > lo) & (h1[name] <= hi); m2 = (h2[name] > lo) & (h2[name] <= hi)
        f = dict(cut=[None if not np.isfinite(lo) else round(float(lo), 4), None if not np.isfinite(hi) else round(float(hi), 4)],
                 h1_pass=round(100 * float(h1.passed[m1].mean()), 1), h1_keep=round(100 * float(m1.mean()), 1),
                 h2_pass=round(100 * float(h2.passed[m2].mean()), 1) if m2.any() else None, h2_keep=round(100 * float(m2.mean()), 1))
        out["filters"][f"{name} {b}"] = f; cands[f"{name} {b}"] = m2
        print(f"{name:20s} {b:4s} H1 pass {f['h1_pass']:5} (keeps {f['h1_keep']:4}%) | H2 pass {f['h2_pass']} (keeps {f['h2_keep']}%)", flush=True)
ok = {k: v for k, v in out["filters"].items() if v["h1_keep"] >= 25}
pick = max(ok, key=lambda k: ok[k]["h1_pass"])
f = out["filters"][pick]; m2 = cands[pick].to_numpy()
rng = np.random.default_rng(SEED); n_keep = int(m2.sum()); n = len(h2); pl_rates = []
for _ in range(200):
    sel = np.zeros(n, bool)
    while sel.sum() < n_keep:
        a = int(rng.integers(0, n)); sel[a:a + 21] = True
    pl_rates.append(float(h2.passed.to_numpy()[sel].mean()))
beaten = int((np.array(pl_rates) < h2.passed.to_numpy()[m2].mean()).sum())
gates = dict(gain=bool(f["h2_pass"] is not None and f["h2_pass"] >= out["base"]["h2"] + 5), keep=bool(f["h2_keep"] >= 15), placebo=beaten >= 190)
out["selected"] = dict(filter=pick, **f, block_placebo_beaten=f"{beaten}/200", gates=gates, adopt=all(gates.values()))
print("selected:", out["selected"])
(pl.ROOT / "reports/EVAL_3_START_TIMING_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
