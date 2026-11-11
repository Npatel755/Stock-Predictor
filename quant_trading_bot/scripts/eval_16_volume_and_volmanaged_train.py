"""eval_16 (Claude, 2026-11-11): two never-used inputs for the eval_8 book - relative volume and volatility-managed sizing. TRAINING only.

PRE-DECLARED (written before any result). Harness book / simulator / starts / incumbent (DEF_END, 54.5 / 65.6, daily Sharpe 0.1506).
FAMILY R - relative-volume filter (source idea: Zarattini & Aziz 2023 ORB "stocks in play": breakouts work on high relative-volume days).
  RVOL(d, m) = MNQ cumulative RTH volume from 09:30 to the decision minute m / mean of the same quantity over the previous 14 full sessions.
  Skip a book trade (before routing, so freed slots refill) whose decision falls in RTH and RVOL < theta, theta in {0.8, 1.0}.
  Gate R1: daily Sharpe (k3, as save_daily) must beat >= 190 of 200 random skip masks of the same size among eligible trades (seed 16).
  Gate R2: 2-fold pass rate - pick theta on 2010-16 starts, report on 2017-23 and vice versa; adopt only if both >= 55.5 / 66.6.
FAMILY V - volatility-managed size (Moreira & Muir 2017; Barroso & Santa-Clara 2015 for momentum). sigma_t = st.dev. of the last L MNQ RTH
  close-to-close returns before day t (known at the prior close), L in {20, 60}; s_t = sigma* / sigma_t, sigma* = median sigma_t over the
  FIT fold's sessions; k = clip(round(k_DEF x s_t), 1, 5) where k_DEF is the incumbent's ladder k. 2-fold: fit sigma* and pick L on fold A,
  run on fold B, and vice versa; adopt only if both out-of-fold halves >= 55.5 / 66.6.
Prior evidence (lessons, EDGE_ATTRIBUTION_VOL): 2010-19 high-vol sessions lost and 2020-23 profit is an era effect, so V may flip between
halves; it is tested because volatility-managed SIZING (not a skip filter) is a different, published mechanism.
"""
import json
import numpy as np, pandas as pd
from pathlib import Path
import eval_harness as eh

ROOT = Path(__file__).resolve().parents[1]; NY = "America/New_York"
H = eh.Harness(); DEF = H.DEF_END; out = {}
m1 = H.E9["P10"]["m1"]
t = pd.to_datetime(m1.timestamp_utc, utc=True).dt.tz_convert(NY); mi = (t.dt.hour * 60 + t.dt.minute - 570).to_numpy()
r = pd.DataFrame(dict(d=t.dt.date.to_numpy(), m=mi, v=m1.volume.to_numpy(float), c=m1.close.to_numpy(float)))[lambda x: (x.m >= 0) & (x.m < 390)]
cnt = r.groupby("d").size(); full = cnt[cnt >= 385].index
V = r[r.d.isin(full)].pivot_table(index="d", columns="m", values="v", aggfunc="sum").reindex(columns=range(390)).fillna(0.0).cumsum(axis=1)
C = r[r.d.isin(full)].groupby("d").c.last()
days = list(V.index); Vm = V.to_numpy(); RV = {}
for i in range(14, len(days)):
    base = Vm[i - 14:i].mean(axis=0); RV[days[i]] = np.where(base > 0, Vm[i] / np.maximum(base, 1e-9), np.nan)


def rvol_at(ts):
    d = ts.date(); m = ts.hour * 60 + ts.minute - 570
    if d not in RV or not (0 <= m < 390): return np.nan
    return float(RV[d][max(m - 1, 0)])          # last COMPLETED minute before the decision


PRE = H.PRE.copy(); PRE["rv"] = [rvol_at(x) for x in PRE.dec]
elig = PRE.rv.notna().to_numpy(); out["R_coverage"] = dict(trades=len(PRE), eligible=int(elig.sum()))


def daily_sr(book):
    PD = H._per_day(book[H.COLS].assign(noise=False))
    k3 = pd.Series({d: H.sim_day(PD[d], 3.0)[0] for d in PD}).reindex(H.SESS, fill_value=0.0)
    h1 = np.array([d < eh.H1_END for d in H.SESS])
    return eh._sr(k3), eh._sr(k3[h1]), eh._sr(k3[~h1])


base_sr = daily_sr(H.BOOK); out["base_sr"] = base_sr; print("base daily SR", base_sr, flush=True)
rng = np.random.default_rng(16); R = {}
for th in (0.8, 1.0):
    skip = elig & (PRE.rv.to_numpy() < th); n = int(skip.sum())
    bk = H.build_book(PRE[~skip].drop(columns="rv")); sr = daily_sr(bk)
    idx = np.flatnonzero(elig); beat = 0
    for _ in range(200):
        m = np.zeros(len(PRE), bool); m[rng.choice(idx, n, replace=False)] = True
        beat += int(sr[0] > daily_sr(H.build_book(PRE[~m].drop(columns="rv")))[0])
    R[th] = dict(skipped=n, skipped_net_per_micro=round(float((PRE.net_today / PRE.n_contracts)[skip].sum()), 0), daily_sr=sr, placebo_beaten=beat,
                 gate1=beat >= 190)
    if R[th]["gate1"]: R[th]["pass"] = H.pass_rate(book=bk)
    print("R", th, R[th], flush=True)
out["R"] = R
ok = [th for th in R if R[th]["gate1"]]
if ok:
    pA = max(ok, key=lambda th: R[th]["pass"]["h1"]["pass_"]); pB = max(ok, key=lambda th: R[th]["pass"]["h2"]["pass_"])
    out["R_result"] = dict(pick_h1=pA, pick_h2=pB, oof_h1=R[pB]["pass"]["h1"]["pass_"], oof_h2=R[pA]["pass"]["h2"]["pass_"],
                           adopt=bool(R[pB]["pass"]["h1"]["pass_"] >= 55.5 and R[pA]["pass"]["h2"]["pass_"] >= 66.6))
    print("R result", out["R_result"], flush=True)

# ---------------- family V
ret = np.log(C).diff(); SIG = {L: ret.rolling(L).std().shift(1) for L in (20, 60)}     # shift: known at the prior close
PD = H._per_day(H.BOOK[H.COLS].assign(noise=False)); TD = sorted(PD); TIX = pd.to_datetime(pd.Series(TD).astype(str)).to_numpy()
DAY = {k: {d: H.sim_day(PD[d], float(k)) for d in TD} for k in (1, 2, 3, 4, 5)}


def run(starts, L, sstar):
    sig = SIG[L]; res = []
    for s in starts:
        end = (pd.Timestamp(s) + pd.Timedelta(days=90)).date(); i = int(np.searchsorted(TIX, np.datetime64(pd.Timestamp(s))))
        bal = 0.0; best = 0.0; o = "timeout"
        for d in TD[i:]:
            if d >= end: break
            k0 = DEF(bal, (d - s).days, max(4000.0, best / 0.55), 0); st = sig.get(d, np.nan)
            k = k0 if not np.isfinite(st) or st <= 0 else int(np.clip(round(k0 * sstar / st), 1, 5))
            p, w = DAY[k][d]
            if bal + min(w, p) <= -2000.0: o = "fail"; break
            bal += p; best = max(best, p)
            if bal >= max(4000.0, best / 0.55): o = "pass"; break
        res.append(o)
    x = pd.Series(res)
    return dict(pass_=round(100 * float((x == "pass").mean()), 1), fail=round(100 * float((x == "fail").mean()), 1), n=len(x))


Vres = {}
for L in (20, 60):
    sA = float(SIG[L][[d for d in SIG[L].index if d < eh.H1_END]].median()); sB = float(SIG[L][[d for d in SIG[L].index if d >= eh.H1_END]].median())
    Vres[L] = dict(sigma_A=sA, sigma_B=sB, inA_on_A=run(H.A, L, sA), fitA_on_B=run(H.B, L, sA), inB_on_B=run(H.B, L, sB), fitB_on_A=run(H.A, L, sB))
    print("V", L, Vres[L], flush=True)
pA = max(Vres, key=lambda L: Vres[L]["inA_on_A"]["pass_"]); pB = max(Vres, key=lambda L: Vres[L]["inB_on_B"]["pass_"])
oA, oB = Vres[pB]["fitB_on_A"]["pass_"], Vres[pA]["fitA_on_B"]["pass_"]
out["V"] = Vres; out["V_result"] = dict(pick_A=pA, pick_B=pB, oof_h1=oA, oof_h2=oB, adopt=bool(oA >= 55.5 and oB >= 66.6))
print("V result", out["V_result"], flush=True)
(ROOT / "reports/EVAL_16_VOLUME_VOLMANAGED_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
