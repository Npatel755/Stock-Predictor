"""eval_32 (Claude, 2026-11-11): measure the TRUE joint drawdown of overlapping trades from 1-minute bars, then price the incumbent book with
it. TRAINING 2010-23 only. Decides INC vs STRICT routing (eval_30 / eval_31). Nothing tuned.

eval_31: INC passes 49.7 / 59.4 if an open trade's full MAE is charged at the next entry (v2) and 53.3 / 64.1 if it is ignored (v2_OPT);
STRICT (no overlaps) is 54.4 / 61.1 under every rule. The truth for INC lies between. For every overlapping pair (j entered while i was
open; 384 pairs, 99.5% same side) compute on 1-minute bars, per micro and with the harness's MAE convention (adverse bar extreme,
one 0.5-pt adverse tick, today's prices):
  exact = min over minutes t in j's life of [ i's marked value at t (its realised P&L once it has exited) + j's marked value at t ]
  v2 charge = mae_i + mae_j          v2_OPT charge = mae_j
f = (exact - mae_j) / mae_i = the share of i's MAE that is really concurrent with j's worst point (clipped to [0, 1]).
PRE-DECLARED use: INC re-priced with v2_F, i.e. v2 with every open trade's MAE multiplied by the median f (and, as a bound, the 75th
percentile f). Decision rule written now: switch the evaluation plan to STRICT if STRICT >= INC(v2_F at the median f) + 1.0 in BOTH halves;
keep INC if INC(v2_F) >= STRICT in both halves; otherwise call it a tie and prefer STRICT only as a paper challenger.
"""
import os, json
os.environ["TRAIN_MINI_UNTIL"] = "2019-05-06"
import numpy as np, pandas as pd
from pathlib import Path
import eval_harness as eh

ROOT = Path(__file__).resolve().parents[1]; NY = "America/New_York"
H = eh.Harness(); pl = H.pl
BAR = {}
for inst, key in (("MNQ", "m1"), ("MES", "mes1")):
    b = H.E9["P10"][key]; ts = pd.to_datetime(b.timestamp_utc, utc=True); assert ts.max() < pd.Timestamp("2024-01-01", tz="UTC")
    BAR[inst] = (ts.dt.as_unit("ns").astype("int64").to_numpy(), b.high.to_numpy(float), b.low.to_numpy(float), b.close.to_numpy(float))


def path(r, t0, t1):
    """per-micro marked value of trade r on minutes [t0, t1) (ns), adverse extreme of each bar, harness MAE convention"""
    ts, Hh, L, C = BAR[r.inst]; i0, i1 = np.searchsorted(ts, t0), np.searchsorted(ts, t1)
    adv = L[i0:i1] if r.side > 0 else Hh[i0:i1]
    return ts[i0:i1], (r.side * (adv - r.entry) / r.entry * pl.TODAY[r.inst] - pl.ADV) * pl.MULT[r.inst]


R = pl.route(H.PRE[H.PRE.risk_today <= 300.0]).copy().sort_values("tin", kind="stable").reset_index(drop=True)
R["per_micro"] = R.net_today / R.n_contracts; R["day"] = R.tin.dt.date
rows = []
for d, g in R.groupby("day"):
    g = g.reset_index(drop=True)
    for j in range(1, len(g)):
        for i in range(j):
            ri, rj = g.loc[i], g.loc[j]
            if not ri.tout > rj.tin: continue
            tj, vj = path(rj, rj.tin.value, max(rj.tout.value, rj.tin.value + 60_000_000_000))
            if len(tj) == 0: continue
            ti, vi = path(ri, rj.tin.value, ri.tout.value)
            vi_at = np.where(tj < ri.tout.value, np.interp(tj, ti, vi) if len(ti) else ri.per_micro, ri.per_micro)
            exact = float(min(0.0, np.min(vi_at + vj)))
            mi, mj = min(float(ri.mae_per_micro), float(ri.per_micro)), min(float(rj.mae_per_micro), float(rj.per_micro))
            f = np.clip((exact - mj) / mi, 0.0, 1.0) if mi < -1e-9 else 0.0
            rows.append(dict(day=str(d), same_side=bool(ri.side == rj.side), exact=exact, v2=mi + mj, opt=mj, f=float(f)))
P = pd.DataFrame(rows)
fmed, f75 = float(P.f.median()), float(P.f.quantile(0.75))
out = dict(pairs=len(P), f_median=round(fmed, 3), f_p75=round(f75, 3), f_mean=round(float(P.f.mean()), 3),
           mean_exact=round(float(P.exact.mean()), 1), mean_v2=round(float(P.v2.mean()), 1), mean_opt=round(float(P.opt.mean()), 1))
print("pairs", out, flush=True)


def make_sim(fac):
    def sim(x, k, nsize="F1"):
        a, b, per, mae, n, risk, nz = x
        mae = np.minimum(mae, per); cap = np.floor(900.0 / risk); q = np.minimum(k * n, cap)
        stop = 400.0 if np.all(q <= n) else 700.0; acc = []; w = 0.0; dll = False
        for j in range(len(per)):
            if q[j] < 1: continue
            done = [i for i in acc if b[i] < a[j] or (b[i] == a[j] and a[i] < a[j])]
            realised = sum(per[i] * q[i] for i in done); opn = fac * sum(min(0.0, mae[i] * q[i]) for i in acc if i not in done)
            if realised <= -stop or realised <= -1000.0: break
            worst = realised + mae[j] * q[j] + opn; w = min(w, worst)
            if worst <= -1000.0: dll = True; break
            acc.append(j)
        p = -1000.0 if dll else max(sum(per[i] * q[i] for i in acc), -1000.0)
        return p, min(w, p)
    return sim


def rate(book, sim):
    f = book[H.COLS].assign(noise=False).sort_values(["tin", "tout", "per_micro"], kind="stable").reset_index(drop=True)
    PD = H._per_day(f); td = sorted(PD); tix = pd.to_datetime(pd.Series(td).astype(str)).to_numpy()
    DAY = {k: {dd: sim(PD[dd], float(k)) for dd in td} for k in (1, 2, 3, 5)}
    return dict(h1=H._evaluate(DAY, H.A, td, tix, H.DEF_END), h2=H._evaluate(DAY, H.B, td, tix, H.DEF_END))


out["INC_v2_F_median"] = rate(H.BOOK, make_sim(fmed)); out["INC_v2_F_p75"] = rate(H.BOOK, make_sim(f75))
out["STRICT"] = dict(h1=54.4, h2=61.1)
for k in ("INC_v2_F_median", "INC_v2_F_p75"): print(k, out[k], flush=True)
I = out["INC_v2_F_median"]
if 54.4 >= I["h1"]["pass_"] + 1.0 and 61.1 >= I["h2"]["pass_"] + 1.0: verdict = "SWITCH to STRICT"
elif I["h1"]["pass_"] >= 54.4 and I["h2"]["pass_"] >= 61.1: verdict = "KEEP INC"
else: verdict = "TIE - STRICT as paper challenger only"
out["verdict"] = verdict; print("verdict", verdict, flush=True)
(ROOT / "reports/EVAL_32_EXACT_OVERLAP_PATH_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
