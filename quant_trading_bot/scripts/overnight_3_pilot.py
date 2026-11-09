"""overnight_3 (research/overnight_3/PROTOCOL.md): reopen-dip hold improvement round, training 2010-2023 only. 1-min bars."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts"))
import mass_1m_search as m1
SPEC = dict(MNQ=dict(tick=0.25, tv=0.5, spread=1.75), MES=dict(tick=0.25, tv=1.25, spread=1.0)); COMM, SLIP = 0.61, 1
rng = np.random.default_rng(53)

def nights(prod):
    b = m1.load_bars(prod, 1, "2010-01-01", "2024-01-01", "train")[["timestamp_utc", "open", "high", "low", "close"]]
    et = pd.to_datetime(b.timestamp_utc, utc=True).dt.tz_convert("America/New_York"); b["sod"] = (et.dt.hour * 60 + et.dt.minute).to_numpy(); b["date"] = et.dt.date.to_numpy()
    dates = sorted(set(b.date)); prev = {d: p for p, d in zip(dates[:-1], dates[1:])}
    nk = np.where(b.sod >= 1080, b.date, np.where(b.sod <= 600, pd.Series(b.date).map(prev).to_numpy(), None)); b["nk"] = nk
    day = b.groupby("date"); g = b[b.nk.notna()].groupby("nk")
    def at(sod, col, grp=g): s = b[b.sod == sod]; return s.groupby("nk" if grp is g else "date")[col].first()
    n = pd.DataFrame(dict(rth_open=at(570, "open", day), rth_close=b[(b.sod >= 955) & (b.sod < 960)].groupby("date").close.last(), c1659=b[(b.sod >= 1015) & (b.sod < 1020)].groupby("date").close.last(),
                          day_low=b[(b.sod >= 570) & (b.sod < 960)].groupby("date").low.min(), o1800=at(1080, "open", day), dow=pd.Series({d: pd.Timestamp(d).dayofweek for d in dates})))
    ent = pd.DataFrame(dict(e1805=at(1085, "open"), e1830=at(1110, "open"), e2000=at(1200, "open"), e0300=at(180, "open"), x0830=at(510, "open"), x0930=at(570, "open"), x0935=b[b.sod == 575].groupby("nk").close.last(),
                            x0945=at(585, "open"), x1000=at(600, "open")))
    pre = b[(b.nk.notna()) & ((b.sod >= 1086) | (b.sod < 570))].groupby("nk"); ent["low_night"] = pre.low.min()
    n["ref_close"] = n.rth_close.ffill()  # last RTH close known at 18:00 (same date, or Friday for Sunday nights)
    n = n.join(ent, how="inner").dropna(subset=["e1805", "x0930", "ref_close"]); n["year"] = [pd.Timestamp(d).year for d in n.index]
    n["gap"] = n.o1800 / n.ref_close - 1; n["sd20"] = n.gap.rolling(20, min_periods=15).std().shift(1)
    n["drift"] = n.c1659 / n.rth_close - 1; n["jump"] = n.o1800 / n.c1659 - 1
    n["sd20_drift"] = n.drift.rolling(20, min_periods=15).std().shift(1); n["sd20_jump"] = n.jump.rolling(20, min_periods=15).std().shift(1)
    cc = n.rth_close.ffill().pct_change(); n["sd20_cc"] = cc.rolling(20, min_periods=15).std().shift(1)
    n["rth_ret"] = n.rth_close / n.rth_open - 1
    # gap fill: first bar after 18:05 with high >= ref_close before 09:30 -> exit at ref_close
    hi_first = {}
    sub = b[(b.nk.notna()) & ((b.sod >= 1086) | (b.sod < 570))]
    for k, grp in sub.groupby("nk"):
        if k in n.index:
            lvl = n.at[k, "ref_close"]; m = grp.high.to_numpy() >= lvl
            hi_first[k] = lvl if m.any() else np.nan
    n["x_fill"] = pd.Series(hi_first).reindex(n.index).fillna(n.x0930)
    return n

def pnl(n, prod, ent="e1805", ex="x0930", size=None):
    s = SPEC[prod]; cost = (s["spread"] + 2 * SLIP) * s["tv"] + 2 * COMM; sz = size if size is not None else 1
    return ((n[ex] - n[ent]) / s["tick"] * s["tv"] - cost) * sz

def evaluate(n, p, mask, champion=None, n_plc=200, pnl_full=None):
    p = p[mask & p.notna()]; yrs = n.year.loc[p.index]; yr = p.groupby(yrs).sum(); t = float(p.sum())
    if len(p) == 0: return {"net": 0.0, "nights": 0, "pass": False}
    eq = p.cumsum(); dd = float((eq.cummax() - eq).max())
    rec = dict(net=round(t, 2), nights=int(len(p)), per_night=round(t / len(p), 2), pos_years=int((yr > 0).sum()), years=int(len(yr)), pre2020=round(float(yr[yr.index < 2020].sum()), 2),
               max_year_share=round(float(yr.max() / t), 3) if t > 0 else None, max_dd=round(dd, 2), worst_night=round(float(p.min()), 2), by_year={int(y): round(float(v), 2) for y, v in yr.items()})
    full = pnl_full if pnl_full is not None else p.reindex(n.index); cnt = yrs.groupby(yrs).size(); plc = []
    for _ in range(n_plc):
        pick = np.concatenate([rng.choice(n.index[n.year == y], size=min(int(c), int((n.year == y).sum())), replace=False) for y, c in cnt.items()])
        plc.append(float(full.loc[pick].fillna(0).sum()))
    rec.update(beat=int(sum(t > x for x in plc)), n_plc=n_plc, placebo_mean=round(float(np.mean(plc)), 2))
    base = bool(t > 0 and rec["pos_years"] >= 11 and len(p) >= 100 and (rec["max_year_share"] or 1) <= 0.4 and dd < 2000 and rec["beat"] >= 190)
    if champion:
        base = base and t > champion["net"] and dd <= 1.15 * champion["max_dd"] and rec["per_night"] >= champion["per_night"]
    rec["pass"] = base; return rec

out = {"train": {}, "attribution": {}}; M_ALL = {}; CH = {}
N = {p: nights(p) for p in ("MNQ", "MES")}
for prod in ("MNQ", "MES"):
    n = N[prod]; d4 = (n.gap <= -0.5 * n.sd20).fillna(False)
    full = pnl(n, prod); champ = evaluate(n, full, d4, None); out["train"][f"{prod}_D4_champion"] = champ; print(prod, "D4", {k: v for k, v in champ.items() if k != "by_year"}, flush=True)
    V = {"E1_exit0935": dict(ex="x0935"), "E2_exit0945": dict(ex="x0945"), "E3_exit1000": dict(ex="x1000"), "E4_exit0830": dict(ex="x0830"), "E5_gapfill": dict(ex="x_fill"),
         "N1_entry1830": dict(ent="e1830"), "N2_entry2000": dict(ent="e2000"), "N3_entry0300": dict(ent="e0300")}
    for name, kw in V.items():
        p = pnl(n, prod, **kw); r = evaluate(n, p, d4, champ, pnl_full=p); out["train"][f"{prod}_{name}"] = r; print(prod, name, {k: v for k, v in r.items() if k != "by_year"}, flush=True)
    M = {"G1_postclose_drift": (n.drift <= -0.5 * n.sd20_drift), "G2_reopen_jump": (n.jump <= -0.5 * n.sd20_jump), "Z1_gap_le_-0.5sd_cc": (n.gap <= -0.5 * n.sd20_cc),
         "Z2_D4_below_day_low": d4 & (n.o1800 < n.day_low), "Z3_D4_after_down_day": d4 & (n.rth_ret < 0)}
    if prod == "MNQ":
        mes = N["MES"]; mg = mes.gap.reindex(n.index); msd = mes.sd20.reindex(n.index)
        M["C1_D4_mnq_gap_lt_mes_gap"] = d4 & (n.gap < mg); M["C2_D4_and_mes_dip"] = d4 & (mg <= -0.5 * msd)
    M_ALL[prod] = M; CH[prod] = champ
    for name, mask in M.items():
        r = evaluate(n, full, mask.fillna(False), champ, pnl_full=full); out["train"][f"{prod}_{name}"] = r; print(prod, name, {k: v for k, v in r.items() if k != "by_year"}, flush=True)
    size = pd.Series(np.where(n.gap <= -1.0 * n.sd20, 2, 1), index=n.index); pk = pnl(n, prod, size=size)
    r = evaluate(n, pk, d4, champ, pnl_full=pk); out["train"][f"{prod}_K1_size2_at_-1sd"] = r; print(prod, "K1", {k: v for k, v in r.items() if k != "by_year"}, flush=True)
    # attribution on D4 nights (ticks, mean and t)
    att = {}
    for a, bcol in (("e1805", "e2000"), ("e2000", "e0300"), ("e0300", "x0830"), ("x0830", "x0930"), ("x0930", "x0935"), ("x0935", "x1000")):
        mv = ((n[bcol] - n[a]) / SPEC[prod]["tick"])[d4].dropna(); att[f"{a}->{bcol}"] = dict(mean_ticks=round(float(mv.mean()), 2), t=round(float(mv.mean() / mv.std() * np.sqrt(len(mv))), 2), n=int(len(mv)))
    out["attribution"][prod] = att; print(prod, "attribution", att, flush=True)
# P1 portfolio: MNQ D4 + MES D4 summed by night
a, bm = N["MNQ"], N["MES"]; pa = pnl(a, "MNQ")[(a.gap <= -0.5 * a.sd20).fillna(False)]; pb = pnl(bm, "MES")[(bm.gap <= -0.5 * bm.sd20).fillna(False)]
tot = pa.add(pb, fill_value=0).sort_index(); yrs = pd.Series([pd.Timestamp(d).year for d in tot.index], index=tot.index); yr = tot.groupby(yrs).sum(); eq = tot.cumsum()
out["train"]["P1_MNQ_D4_plus_MES_D4"] = dict(net=round(float(tot.sum()), 2), nights=int(len(tot)), pos_years=int((yr > 0).sum()), max_dd=round(float((eq.cummax() - eq).max()), 2), max_year_share=round(float(yr.max() / tot.sum()), 3),
                                              by_year={int(y): round(float(v), 2) for y, v in yr.items()}); print("P1", {k: v for k, v in out["train"]["P1_MNQ_D4_plus_MES_D4"].items() if k != "by_year"}, flush=True)
passers = [k for k, v in out["train"].items() if v.get("pass") and "champion" not in k]; out["passers"] = passers; print("PASSERS", passers, flush=True)
passers_mnq = [k[4:] for k in passers if k.startswith("MNQ_")]
if len(passers_mnq) >= 2:  # pre-declared single combination trial: apply every passing single change at once
    n = N["MNQ"]; mask = (n.gap <= -0.5 * n.sd20).fillna(False); ex, ent = "x0930", "e1805"
    EX = {"E1": "x0935", "E2": "x0945", "E3": "x1000", "E4": "x0830", "E5": "x_fill"}; EN = {"N1": "e1830", "N2": "e2000", "N3": "e0300"}
    for name in passers_mnq:
        if name[:2] in EX: ex = EX[name[:2]]
        elif name[:2] in EN: ent = EN[name[:2]]
        elif name.startswith("K1"): pass
        else: mask = mask & M_ALL["MNQ"][name].fillna(False)
    p = pnl(n, "MNQ", ent=ent, ex=ex); r = evaluate(n, p, mask, CH["MNQ"], pnl_full=p); key = "MNQ_COMBO_" + "+".join(x.split("_")[0] for x in passers_mnq); out["train"][key] = r
    print(key, {k: v for k, v in r.items() if k != "by_year"}, flush=True); out["combo_pass"] = bool(r["pass"])
json.dump(out, open(ROOT / "reports/OVERNIGHT_3_TRAINING.json", "w"), indent=1, default=float); print("DONE")
