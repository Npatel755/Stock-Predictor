"""bookx_1 (Claude fork C, 2026-11-11): how the EXISTING eval_8 book is assembled vs the $50K Static Combine pass rate. TRAINING 2010-23 only.

PRE-DECLARED (written before any result). Incumbent = eval_8 SLEEVES + DEF + ENDGAME via scripts/eval_harness.py (54.5% / 65.6%, must
reproduce). Daily Sharpe = mean / sd of the k3 day P&L (incumbent day simulation) over every training session 2010-06-07..2023-09-29.
Sleeve groups (as eval_11): CRABEL_CONT (Crabel with base 2 micros), CRABEL_FADE (base 1), TRD60, MES_TRD30, BRK_E, MES_MOM, NIGHT.

F1 FAILURE ANATOMY (descriptive only, no adoption): for every failed start under the incumbent: fail type (MAE-only touch = the day's
   close stays above -$2,000 but the intraday worst point touches it; close-through otherwise), DLL day (day flattened at -$1,000), k on
   the fail day, the sleeve of the trade at which the day's worst point occurred, calendar days to fail, distinct fail days (overlapping
   starts share days), and each sleeve's P&L inside failed vs passed attempts (per trade taken).
F2 LEAVE-ONE-SLEEVE-OUT (7 cells): drop one group BEFORE routing (freed slots re-filled by the router); NIGHT = build without the overnight leg.
F3 ROUTING (2 cells): trades the one-position router drops (risk <= $300 eligible) added back as a concurrent stream sized like the book
   (k x base, capped floor($900 / risk)), overlap-aware (eval_13 rule: open trades counted at their MAE):
   NOROUTE = every dropped trade; TWOSLOT = the dropped trades re-routed one-position among themselves (a second slot).
F4 NOISE-AREA DIRECTION FILTER (2 cells) on book trades (before routing; overnight leg exempt): MNQ noise-area state (eval_12 definition,
   14 full sessions, band around max/min(open, prior close)) at the 1-minute bar that CLOSES at the trade's entry time: above UB -> +1,
   below LB -> -1, inside -> 0. FA: skip trades against a non-zero state. FB: FA and also skip when the state is 0. Trades with no state
   (outside RTH, non-full session, first 14 sessions) are kept. GATE before any pass-rate claim: the cell's daily Sharpe must beat >= 190
   of 200 random masks that skip the same number of trades from the same state-eligible set (seed 7), each re-routed.
F5 CRABEL CONTINUATION BASE (2 cells): base 2 -> 1 (CC1) or 3 (CC3) micros, P&L scaled per micro.
PROTOCOL per family (F2, F3, F4 if gated, F5): pick the best cell on 2010-16 starts and report it on 2017-23; pick on 2017-23 and report on
2010-16. ADOPT only if BOTH out-of-fold halves >= incumbent's same half + 1.0 point (>= 55.5 and >= 66.6).
"""
import json, sys
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts"))
from eval_harness import Harness, H1_END

OUTP = ROOT / "reports/BOOKX_1_BOOK_INTERNALS_TRAINING.json"
out = {}


def save():
    OUTP.write_text(json.dumps(out, indent=1, default=str))


H = Harness(); pl = H.pl
GROUPS = ("TRD60", "MES_TRD30", "BRK_E", "MES_MOM")


def group(name, n):
    if "CRABEL" in name: return "CRABEL_CONT" if n >= 2 else "CRABEL_FADE"
    if name == "NIGHT": return "NIGHT"
    for g in GROUPS:
        if g in name: return g
    raise ValueError(name)


PRE = H.PRE.copy(); PRE["g"] = [group(s, n) for s, n in zip(PRE.sleeve, PRE.n_contracts)]
print("PRE columns", list(PRE.columns), flush=True); print("groups", PRE.g.value_counts().to_dict(), flush=True)
assert "side" in PRE.columns and "dec" in PRE.columns


def book_from(pre, nights=True):
    b = H.build_book(pre.drop(columns=["g"], errors="ignore"), nights=nights)
    b["g"] = [group(s, n) for s, n in zip(b.sleeve, b.n_contracts)]
    return b


def per_day(frame):
    df = frame.copy(); df["day"] = df.tout.dt.date; df = df.sort_values("tin")
    df["a"] = df.tin.map(lambda x: x.value); df["b"] = df.tout.map(lambda x: x.value)
    if "g" not in df: df["g"] = "X"
    return {k: (g.a.to_numpy(), g.b.to_numpy(), g.per_micro.to_numpy(float), g.mae_per_micro.to_numpy(float), g.n_contracts.to_numpy(float),
                g.risk_today.to_numpy(float), g.noise.to_numpy(bool), g.g.to_numpy()) for k, g in df.groupby("day")}


def sim_x(x, k):
    """eval_harness.sim_day with concurrent extras sized like the book (min(k x base, cap)); identical when there are no extras."""
    a, b, per, mae, n, risk, nz, _ = x
    q = np.minimum(k * n, np.floor(900.0 / risk)); bk = ~nz; stop = 400.0 if np.all(q[bk] <= n[bk]) else 700.0
    acc = []; w = 0.0; dll = False
    for j in range(len(per)):
        if q[j] < 1: continue
        if not nz[j]:
            realised = sum(per[i] * q[i] for i in acc if not nz[i]) + sum(per[i] * q[i] for i in acc if nz[i] and b[i] <= a[j])
            opn = sum(min(0.0, mae[i] * q[i]) for i in acc if nz[i] and b[i] > a[j])
        else:
            realised = sum(per[i] * q[i] for i in acc if b[i] <= a[j])
            opn = sum(min(0.0, mae[i] * q[i]) for i in acc if b[i] > a[j])
        if realised <= -stop or realised <= -1000.0: break
        worst = realised + mae[j] * q[j] + opn
        w = min(w, worst)
        if worst <= -1000.0: dll = True; break
        acc.append(j)
    return (-1000.0 if dll else max(sum(per[i] * q[i] for i in acc), -1000.0)), w


def frame_of(book, extra=None):
    f = book[H.COLS + ["g"]].assign(noise=False)
    if extra is not None and len(extra): f = pd.concat([f, extra[H.COLS + ["g"]].assign(noise=True)], ignore_index=True)
    return f


def daily_sr(frame):
    PD = per_day(frame); s = pd.Series({d: sim_x(PD[d], 3.0)[0] for d in PD}).reindex(H.SESS, fill_value=0.0)
    h1 = np.array([d < H1_END for d in s.index])
    f = lambda x: round(float(x.mean() / x.std()), 4)
    return dict(all=f(s), h1=f(s[h1]), h2=f(s[~h1]), mean=round(float(s.mean()), 1), sd=round(float(s.std()), 0))


def pass_rate(frame):
    PD = per_day(frame); td = sorted(PD); tix = pd.to_datetime(pd.Series(td).astype(str)).to_numpy()
    DAY = {k: {dd: sim_x(PD[dd], float(k)) for dd in td} for k in (1, 2, 3, 5)}
    return dict(h1=H._evaluate(DAY, H.A, td, tix, H.DEF_END), h2=H._evaluate(DAY, H.B, td, tix, H.DEF_END))


def two_fold(cells, inc):
    pA = max(cells, key=lambda k: cells[k]["pass"]["h1"]["pass_"]); pB = max(cells, key=lambda k: cells[k]["pass"]["h2"]["pass_"])
    onB, onA = cells[pA]["pass"]["h2"], cells[pB]["pass"]["h1"]
    return dict(picked_on_A=pA, picked_on_B=pB, oof_h1=onA["pass_"], oof_h2=onB["pass_"],
                oof_all=round((onA["pass_"] * onA["n"] + onB["pass_"] * onB["n"]) / (onA["n"] + onB["n"]), 1),
                adopt=bool(onA["pass_"] >= inc["h1"]["pass_"] + 1.0 and onB["pass_"] >= inc["h2"]["pass_"] + 1.0))


BOOK = book_from(PRE); F0 = frame_of(BOOK)
inc = pass_rate(F0); print("incumbent", inc, flush=True)
assert inc["h1"]["pass_"] == 54.5 and inc["h2"]["pass_"] == 65.6, "does not reproduce the incumbent"
out["incumbent"] = dict(pass_=inc, daily_sr=daily_sr(F0)); print("incumbent SR", out["incumbent"]["daily_sr"], flush=True); save()

# ---------------- F1 failure anatomy
PD0 = per_day(F0); TD0 = sorted(PD0); TIX0 = pd.to_datetime(pd.Series(TD0).astype(str)).to_numpy()


def sim_attr(x, k):
    a, b, per, mae, n, risk, nz, g = x
    q = np.minimum(k * n, np.floor(900.0 / risk)); stop = 400.0 if np.all(q <= n) else 700.0
    day = 0.0; w = 0.0; wj = None; dll = False; contrib = {}
    for j in range(len(per)):
        if q[j] < 1: continue
        if day <= -stop or day <= -1000.0: break
        cand = day + mae[j] * q[j]
        if cand < w: w = cand; wj = j
        if cand <= -1000.0:
            contrib[g[j]] = contrib.get(g[j], 0.0) + (-1000.0 - day); day = -1000.0; dll = True; break
        day += per[j] * q[j]; contrib[g[j]] = contrib.get(g[j], 0.0) + per[j] * q[j]
    return max(day, -1000.0), w, (g[wj] if wj is not None else None), dll, contrib


ATTR = {k: {dd: sim_attr(PD0[dd], float(k)) for dd in TD0} for k in (1, 2, 3, 5)}
recs = []
for s in H.SESS:
    end = (pd.Timestamp(s) + pd.Timedelta(days=90)).date(); i = int(np.searchsorted(TIX0, np.datetime64(pd.Timestamp(s))))
    bal = 0.0; best = 0.0; o = "timeout"; c_att = {}; info = None
    for dd in TD0[i:]:
        if dd >= end: break
        k = H.DEF_END(bal, (dd - s).days, max(4000.0, best / 0.55), 0); p, w, wg, dll, contrib = ATTR[k][dd]
        if bal + min(w, p) <= -2000.0:
            o = "fail"; info = dict(day=dd, k=k, mae_only=bool(bal + p > -2000.0), dll=dll, worst_sleeve=wg, bal_before=bal, day_pnl=p,
                                   day_worst=w, cal_days=(dd - s).days, day_contrib=contrib)
            for kk, v in contrib.items(): c_att[kk] = c_att.get(kk, 0.0) + v
            break
        for kk, v in contrib.items(): c_att[kk] = c_att.get(kk, 0.0) + v
        bal += p; best = max(best, p)
        if bal >= max(4000.0, best / 0.55): o = "pass"; break
    recs.append(dict(s=s, o=o, att=c_att, info=info))
R = pd.DataFrame(recs); h1m = R.s < H1_END
chk = dict(h1=round(100 * float((R.o[h1m] == "pass").mean()), 1), h2=round(100 * float((R.o[~h1m] == "pass").mean()), 1))
assert chk["h1"] == 54.5 and chk["h2"] == 65.6, f"anatomy loop does not reproduce {chk}"
F = R[R.o == "fail"]; I = pd.DataFrame(list(F["info"]))
anat = dict(n_fail=len(F), mae_only_share=round(float(I.mae_only.mean()), 3), dll_day_share=round(float(I.dll.mean()), 3),
            k_on_fail_day={int(k): int(v) for k, v in I.k.value_counts().sort_index().items()}, worst_sleeve_on_fail_day=I.worst_sleeve.value_counts().to_dict(),
            cal_days_to_fail=dict(p25=float(I.cal_days.quantile(0.25)), median=float(I.cal_days.median()), p75=float(I.cal_days.quantile(0.75))),
            bal_before_fail_day=dict(p25=float(I.bal_before.quantile(0.25)), median=float(I.bal_before.median()), p75=float(I.bal_before.quantile(0.75))),
            fail_day_pnl=dict(median=float(I.day_pnl.median()), share_le_minus700=round(float((I.day_pnl <= -700).mean()), 3)),
            distinct_fail_days=int(I.day.nunique()),
            top_fail_days={str(k): int(v) for k, v in I.day.value_counts().head(12).items()},
            fail_years={int(k): int(v) for k, v in pd.Series([d.year for d in I.day]).value_counts().sort_index().items()})
fd = {}
for c in I.day_contrib:
    for kk, v in c.items(): fd[kk] = fd.get(kk, 0.0) + v
anat["fail_day_loss_by_sleeve"] = {k: round(v, 0) for k, v in sorted(fd.items(), key=lambda kv: kv[1])}
# per-sleeve P&L inside failed vs passed attempts, normalised by attempts
for o in ("fail", "pass", "timeout"):
    tot = {}
    for a_ in R[R.o == o].att:
        for kk, v in a_.items(): tot[kk] = tot.get(kk, 0.0) + v
    anat[f"sleeve_pnl_per_attempt_{o}"] = {k: round(v / max(1, (R.o == o).sum()), 1) for k, v in sorted(tot.items())}
# how the fail-day worst sleeve compares with that sleeve's share of trades taken at all
anat["sleeve_share_of_book_trades"] = BOOK.g.value_counts(normalize=True).round(3).to_dict()
out["F1_anatomy"] = anat; print("F1", json.dumps(anat, default=str)[:3000], flush=True); save()

# ---------------- F2 leave-one-sleeve-out
cells = {}
for gname in ("CRABEL_CONT", "CRABEL_FADE", "TRD60", "MES_TRD30", "BRK_E", "MES_MOM", "NIGHT"):
    bk = book_from(PRE, nights=False) if gname == "NIGHT" else book_from(PRE[PRE.g != gname])
    fr = frame_of(bk); cells[f"drop_{gname}"] = dict(daily_sr=daily_sr(fr))
    cells[f"drop_{gname}"]["pass"] = pass_rate(fr); print("F2", gname, cells[f"drop_{gname}"], flush=True)
out["F2_loso"] = dict(cells=cells, result=two_fold(cells, inc)); print("F2 result", out["F2_loso"]["result"], flush=True); save()

# ---------------- F3 routing
elig = PRE[PRE.risk_today <= 300.0]; routed = pl.route(elig.drop(columns=["g"])); dropped = elig.drop(index=routed.index).copy()
dropped["per_micro"] = dropped.net_today / dropped.n_contracts
slot2 = dropped.loc[pl.route(dropped.drop(columns=["g", "per_micro"])).index]
cells = {}
for nm, ex in (("NOROUTE", dropped), ("TWOSLOT", slot2)):
    fr = frame_of(BOOK, ex); cells[nm] = dict(extra_trades=len(ex), extra_net_per_micro_sum=round(float(ex.per_micro.sum()), 0),
                                             extra_by_group=ex.g.value_counts().to_dict(), daily_sr=daily_sr(fr))
    cells[nm]["pass"] = pass_rate(fr); print("F3", nm, cells[nm], flush=True)
out["F3_routing"] = dict(cells=cells, result=two_fold(cells, inc)); print("F3 result", out["F3_routing"]["result"], flush=True); save()

# ---------------- F5 Crabel continuation base
cells = {}
for nm, nb in (("CC1", 1.0), ("CC3", 3.0)):
    p2 = PRE.copy(); m = p2.g == "CRABEL_CONT"; p2.loc[m, "net_today"] = p2.loc[m, "net_today"] / p2.loc[m, "n_contracts"] * nb; p2.loc[m, "n_contracts"] = nb
    fr = frame_of(book_from(p2)); cells[nm] = dict(daily_sr=daily_sr(fr)); cells[nm]["pass"] = pass_rate(fr); print("F5", nm, cells[nm], flush=True)
out["F5_crabel_base"] = dict(cells=cells, result=two_fold(cells, inc)); print("F5 result", out["F5_crabel_base"]["result"], flush=True); save()

# ---------------- F4 noise-area direction filter
s12 = (ROOT / "scripts/eval_12_noise_area_train.py").read_text(encoding="utf-8").split('\nout = {"cells": {}}')[0]
N12 = {"__name__": "bookx_n", "__file__": str(ROOT / "scripts/eval_12_noise_area_train.py")}; exec(s12, N12)
days = N12["rth_panel"]("MNQ"); LOOK = N12["LOOK"]
mv = np.array([np.abs(x["c"] / x["o"][0] - 1.0) for x in days]); ST = {}
for i in range(LOOK, len(days)):
    x = days[i]; prev = days[i - 1]; O = x["o"][0]
    PC = prev["c"][-1] if (prev["con"] == x["con"] and (x["d"] - prev["d"]).days <= 4) else O
    sig = mv[i - LOOK:i].mean(axis=0); ST[x["d"]] = (x["t0"], max(O, PC) * (1 + sig), min(O, PC) * (1 - sig), x["c"])
del days, mv


def state(tin):
    v = ST.get(tin.date())
    if v is None: return np.nan
    t0, UB, LB, c = v; m = int(round((tin - t0).total_seconds() / 60.0)) - 1
    if m < 0 or m > 389: return np.nan
    return 1.0 if c[m] > UB[m] else (-1.0 if c[m] < LB[m] else 0.0)


PRE["nstate"] = [state(t) for t in PRE.tin]
cov = PRE[PRE.risk_today <= 300.0].nstate
out["F4_coverage"] = dict(eligible=int(cov.notna().sum()), no_state=int(cov.isna().sum()), state_counts=cov.value_counts().to_dict())
print("F4 coverage", out["F4_coverage"], flush=True)
ELIG = PRE.index[(PRE.risk_today <= 300.0) & PRE.nstate.notna()]
skipA = PRE.index[(PRE.risk_today <= 300.0) & (((PRE.nstate == 1.0) & (PRE.side < 0)) | ((PRE.nstate == -1.0) & (PRE.side > 0)))]
skipB = skipA.union(PRE.index[(PRE.risk_today <= 300.0) & (PRE.nstate == 0.0)])
rng = np.random.default_rng(7); cells = {}; gated = {}
for nm, sk in (("FA", skipA), ("FB", skipB)):
    fr = frame_of(book_from(PRE.drop(index=sk).drop(columns=["nstate"]))); sr = daily_sr(fr)
    plc = []
    for _ in range(200):
        r_ = rng.choice(ELIG.to_numpy(), size=len(sk), replace=False)
        plc.append(daily_sr(frame_of(book_from(PRE.drop(index=r_).drop(columns=["nstate"]))))["all"])
    beat = int(sum(sr["all"] > p for p in plc))
    cells[nm] = dict(skipped=len(sk), skipped_by_group=PRE.loc[sk].g.value_counts().to_dict(), daily_sr=sr, placebo_beaten=beat,
                     placebo_sr=dict(p50=float(np.median(plc)), p95=float(np.quantile(plc, 0.95))), gate=bool(beat >= 190))
    if cells[nm]["gate"]: cells[nm]["pass"] = pass_rate(fr); gated[nm] = cells[nm]
    print("F4", nm, cells[nm], flush=True); out["F4_noise_filter"] = dict(cells=cells); save()
out["F4_noise_filter"]["result"] = two_fold(gated, inc) if gated else "no cell passed the placebo gate; no pass-rate claim"
print("F4 result", out["F4_noise_filter"]["result"], flush=True); save()
print("done", flush=True)
