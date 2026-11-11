"""cl_1 (Claude, 2026-11-10): crude-oil sleeves (CL 1-minute research data, MCL execution) for the 50K payout book. TRAINING 2010-23 ONLY.

PRE-DECLARED (written before any crude result was computed).
Goal: more days with net >= $150 on days the NQ book (base R) does not already supply, without breaking the account's risk limits.
Data: Databento GLBX.MDP3 ohlcv-1m CL.v.0 (volume-front, unadjusted; every bar carries its contract id), 2010-06-07 .. 2023-12-29.
  Day = ET date, bars 08:00-14:29 ET. A day is skipped if Databento flags it degraded, if the contract changes between 08:00 and 14:29
  (no trade spans a roll), or if fewer than 300 of the 330 bars 09:00-14:29 exist. One trade per family per day, flat by the 14:29 bar close.
Fills: decision at a bar close, entry at the next bar's open. Stop checked first on every bar including the entry bar; a bar opening through
  the stop fills at that open; a target fills only if the stop is not touched in the same bar.
Contract (CME): MCL = 100 barrels, $0.01 tick = $1.00, so $100 per $1.00/bbl. Trades are re-priced at today's WTI (~$85, 2026-11-10, same %
  move). Costs per MCL round trip: $1.22 commission + 1.75 ticks spread + 1 tick slippage per side = $4.97. Signals and fills come from CL
  bars (MCL only listed 2021), so this is an indicative transfer, not a verified MCL fill model.
Sizing (fixed, not tuned): MCL = clip(floor($200 / (stop risk per MCL incl. costs)), 1, 5); skip a trade whose 1-MCL risk exceeds $300.
Families (8 configs each, 24 total):
  F1 opening-range breakout: range 09:00-09:00+L (L 15|30 min); first close beyond it before 12:00 enters; stop = far side of the range |
     range midpoint; exit 14:29 close | target 1x range width (else 14:29).
  F2 EIA inventory report (Wednesday 10:30 ET; weeks with a US federal holiday Mon-Wed skipped, since those releases move): move from the
     10:29 close to the close W minutes after 10:30 (W 5|15); trade only if |move| >= 0.20%; with the move | fade it; stop beyond the
     window's low (longs) or high (shorts); exit 11:30 | 14:29.
  F3 into-settlement momentum (Gao-Han-Li-Zhou style): signal = prior 14:29 close (same contract) -> 09:30, or 09:00 open -> bar before
     entry; enter at 14:00 | 13:30 open in the signal's direction if |signal| >= 0 | 0.5%; stop 0.40%; exit 14:29 close.
Selection (training first half H1 = 2010-06..2016-12 only): per family, among configs with H1 PF >= 1.10 and >= 20 trades/yr, the highest H1
  net per year. Confirmation on H2 = 2017-2023 (also training, unused for selection), all required: net > 0, PF >= 1.10, >= 4 of 7 years
  positive, net > 0 with costs +$4/MCL, and the real directions beat >= 190 of 200 random-direction placebos (same days, entry times,
  stop distances and exits; seed 20261110). Report only: H2 net re-priced at $68 and $102.
Book test (sleeves that pass confirmation, together): base R = v5.2 + overnight dip staged at $500 (payout_17's base, which must reproduce),
  $400 account stop on realised same-day P&L across both markets, static -$2,000, $1k DLL, $1,000 buffer, 151 monthly 12-month starts.
  Cells: crude always on | crude only while the balance >= $500. Stresses as payout_13 (crude S1 +$4/MCL round trip; S2 -25% of the sleeve's
  average net per trade; S4 stop risk x1.5 with sizing recomputed and net per MCL x1.5).
  ADOPT only if: S0 breach <= 2%, S3 breach <= 5%, S4 breach <= base R's, 0 days <= -$1,000, S0 payouts >= base + 0.5, and payouts up vs base
  in both halves of the starts (2010-07..2016-12 and 2017-01..2023-01). If both cells pass, take the one with more S0 payouts.
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
NY = "America/New_York"
P_TODAY, PT, COST, R_TRADE, K_MAX, RISK_SKIP = 85.0, 100.0, 4.97, 200.0, 5, 300.0
H1_END, SEED = pd.Timestamp("2017-01-01").date(), 20261110


def load_days():
    df = pd.read_parquet(ROOT / "data/market/crossasset_train/CL_v_0_ohlcv1m_2010_2023.parquet")
    assert df.index.max() < pd.Timestamp("2024-01-01", tz="UTC")
    bad = {s.split()[0] for s in json.loads((ROOT / "data/market/crossasset_train/CL_v_0_ohlcv1m_checks.json").read_text())["degraded_days"]}
    et = df.index.tz_convert(NY); sod = np.asarray(et.hour * 60 + et.minute)
    m = (sod >= 480) & (sod <= 869) & (np.asarray(et.dayofweek) < 5)
    d = pd.DataFrame({"date": np.asarray(et.date)[m], "sod": sod[m], "o": df.open.to_numpy()[m], "h": df.high.to_numpy()[m],
                      "l": df.low.to_numpy()[m], "c": df.close.to_numpy()[m], "iid": df.instrument_id.to_numpy()[m]})
    days, skipped = {}, dict(degraded=0, roll=0, thin=0)
    for dt, g in d.groupby("date", sort=True):
        if str(dt) in bad: skipped["degraded"] += 1; continue
        if g.iid.nunique() != 1: skipped["roll"] += 1; continue
        if int((g.sod >= 540).sum()) < 300: skipped["thin"] += 1; continue
        days[dt] = dict(sod=g.sod.to_numpy(), o=g.o.to_numpy(), h=g.h.to_numpy(), l=g.l.to_numpy(), c=g.c.to_numpy(), iid=int(g.iid.iloc[0]))
    return days, skipped


def walk(D, i, side, stop, tgt, exit_sod):
    s, o, h, l, c = D["sod"], D["o"], D["h"], D["l"], D["c"]
    for j in range(i, len(s)):
        if j > i and s[j] > exit_sod: return c[j - 1], s[j - 1]
        if side > 0:
            if j > i and o[j] <= stop: return o[j], s[j]
            if l[j] <= stop: return stop, s[j]
            if tgt is not None and h[j] >= tgt: return (o[j] if (j > i and o[j] > tgt) else tgt), s[j]
        else:
            if j > i and o[j] >= stop: return o[j], s[j]
            if h[j] >= stop: return stop, s[j]
            if tgt is not None and l[j] <= tgt: return (o[j] if (j > i and o[j] < tgt) else tgt), s[j]
        if s[j] >= exit_sod: return c[j], s[j]
    return c[-1], s[-1]


def trade(rows, fam, cfg, dt, D, i, side, stop, tgt, exit_sod):
    """Record the real-direction outcome and the mirrored one (same entry, stop distance, target distance, exit) for placebos."""
    e = D["o"][i]
    if (side > 0 and e <= stop) or (side < 0 and e >= stop): return
    out = {}
    for tag, sd in (("g", side), ("gm", -side)):
        st = stop if sd == side else 2 * e - stop
        tg = None if tgt is None else (tgt if sd == side else 2 * e - tgt)
        x, xs = walk(D, i, sd, st, tg, exit_sod); out[tag] = sd * (x - e) / e; out["xs_" + tag] = xs
    t0 = pd.Timestamp(dt).tz_localize(NY)
    rows.append(dict(fam=fam, cfg=cfg, date=dt, side=side, entry=e, stop_pct=abs(e - stop) / e, g=out["g"], gm=out["gm"],
                     tin=t0 + pd.Timedelta(minutes=int(D["sod"][i])), tout=t0 + pd.Timedelta(minutes=int(out["xs_g"]) + 1)))


def first_idx(D, sod):
    k = np.searchsorted(D["sod"], sod); return int(k) if k < len(D["sod"]) else None


def close_at(D, sod):
    k = np.searchsorted(D["sod"], sod, side="right") - 1; return D["c"][k] if k >= 0 else None


def build(days):
    rows = []; dates = list(days)
    hol = set(USFederalHolidayCalendar().holidays(start="2010-01-01", end="2024-01-31").date)
    prev = {dates[k]: dates[k - 1] for k in range(1, len(dates))}
    for dt in dates:
        D = days[dt]; s = D["sod"]
        # F1 opening-range breakout
        for L in (15, 30):
            m = (s >= 540) & (s < 540 + L)
            if m.sum() < L - 2: continue
            hi, lo = D["h"][m].max(), D["l"][m].min()
            idx = np.where((s >= 540 + L) & (s < 720))[0]
            hit = next((j for j in idx if D["c"][j] > hi or D["c"][j] < lo), None)
            if hit is None or hit + 1 >= len(s): continue
            side = 1 if D["c"][hit] > hi else -1
            for sm in ("far", "mid"):
                stop = (lo if side > 0 else hi) if sm == "far" else (hi + lo) / 2
                for xm in ("time", "tgt1"):
                    e = D["o"][hit + 1]; tgt = None if xm == "time" else e + side * (hi - lo)
                    trade(rows, "F1", f"L{L}_{sm}_{xm}", dt, D, hit + 1, side, stop, tgt, 869)
        # F2 EIA report, Wednesdays outside holiday weeks
        wd = pd.Timestamp(dt)
        if wd.dayofweek == 2 and not any((wd - pd.Timedelta(days=k)).date() in hol for k in range(3)):
            pre = close_at(D, 629)
            for W in (5, 15):
                wm = (s >= 630) & (s < 630 + W); i = first_idx(D, 630 + W)
                if pre is None or wm.sum() < W - 1 or i is None or s[i] > 630 + W + 2: continue
                post = close_at(D, 630 + W - 1); r = post / pre - 1
                if abs(r) < 0.002: continue
                whi, wlo = D["h"][wm].max(), D["l"][wm].min()
                for mode in ("mom", "fade"):
                    side = int(np.sign(r)) * (1 if mode == "mom" else -1)
                    stop = wlo if side > 0 else whi
                    for X in (690, 869):
                        trade(rows, "F2", f"W{W}_{mode}_x{X}", dt, D, i, side, stop, None, X - 1 if X == 690 else X)
        # F3 into-settlement momentum
        pv = prev.get(dt)
        for sig in ("ovn", "day"):
            for start in (840, 810):
                i = first_idx(D, start)
                if i is None or s[i] > start + 2: continue
                if sig == "ovn":
                    if pv is None or days[pv]["iid"] != D["iid"] or days[pv]["sod"][-1] < 865: continue
                    a, b = days[pv]["c"][-1], close_at(D, 569)
                else:
                    a = D["o"][first_idx(D, 540)] if first_idx(D, 540) is not None else None; b = D["c"][i - 1]
                if a is None or b is None: continue
                r = b / a - 1
                for th in (0.0, 0.005):
                    if abs(r) < max(th, 1e-12): continue
                    side = 1 if r > 0 else -1; e = D["o"][i]
                    trade(rows, "F3", f"{sig}_{start}_th{th}", dt, D, i, side, e * (1 - side * 0.004), None, 869)
    return pd.DataFrame(rows)


def dollars(t, kind="S0", P=P_TODAY, col="g"):
    vol = 1.5 if kind == "S4" else 1.0; cost = COST + (4.0 if kind in ("S1", "S3") else 0.0)
    risk1 = (t.stop_pct * P * PT + cost) * vol
    q = np.clip(np.floor(R_TRADE / risk1), 1, K_MAX)
    net = (t[col] * P * PT - cost) * vol * q
    out = t.assign(q=q, risk1=risk1, net_today=net)[risk1 <= RISK_SKIP]
    if kind in ("S2", "S3"):
        out = out.assign(net_today=out.net_today - 0.25 * out.groupby("cfg").net_today.transform("mean").clip(lower=0))
    return out


def stats(x):
    n = x.net_today.to_numpy(); yrs = max(1e-9, (pd.Timestamp(x.date.max()) - pd.Timestamp(x.date.min())).days / 365.25) if len(x) else 1
    pos, neg = n[n > 0].sum(), -n[n < 0].sum()
    return dict(trades=int(len(n)), per_year=round(len(n) / yrs, 1), net=round(float(n.sum()), 0), net_per_year=round(float(n.sum()) / yrs, 0),
                pf=round(float(pos / neg), 3) if neg > 0 else None, avg=round(float(n.mean()), 2) if len(n) else None)


def main():
    days, skipped = load_days()
    T = build(days)
    out = dict(days_used=len(days), days_skipped=skipped, trades_by_family=T.groupby("fam").size().to_dict())
    print(out, flush=True)
    S0 = dollars(T); h1 = S0[S0.date < H1_END]; h2 = S0[S0.date >= H1_END]
    sel = {}
    for fam in ("F1", "F2", "F3"):
        grid = {c: stats(g) for c, g in h1[h1.fam == fam].groupby("cfg")}
        h1span = (pd.Timestamp("2017-01-01") - pd.Timestamp("2010-06-07")).days / 365.25
        for c, v in grid.items(): v["per_year"] = round(v["trades"] / h1span, 1); v["net_per_year"] = round(v["net"] / h1span, 0)
        ok = {c: v for c, v in grid.items() if v["pf"] and v["pf"] >= 1.10 and v["per_year"] >= 20}
        pick = max(ok, key=lambda c: ok[c]["net_per_year"]) if ok else None
        out[fam] = dict(h1_grid=grid, selected=pick)
        print(fam, "H1 grid:", {c: (v["net_per_year"], v["pf"], v["per_year"]) for c, v in grid.items()}, "-> selected", pick, flush=True)
        if not pick: continue
        x2 = h2[h2.cfg == pick]; st = stats(x2)
        yr = x2.groupby(pd.to_datetime(x2.date).dt.year).net_today.sum()
        c2 = dollars(T[(T.cfg == pick) & (T.date >= H1_END)], "S1")
        rng = np.random.default_rng(SEED); raw = T[(T.cfg == pick) & (T.date >= H1_END)]
        base_risk = dollars(raw)
        pn = []
        for _ in range(200):
            flip = rng.random(len(raw)) < 0.5
            pr = raw.assign(g=np.where(flip, raw.gm, raw.g))
            pn.append(float(dollars(pr).net_today.sum()))
        beaten = int((np.array(pn) < st["net"]).sum())
        gates = dict(net_pos=st["net"] > 0, pf=bool(st["pf"] and st["pf"] >= 1.10), years=int((yr > 0).sum()) >= 4,
                     cost_stress=float(c2.net_today.sum()) > 0, placebo=beaten >= 190)
        out[fam].update(h2=st, h2_by_year={int(k): round(float(v), 0) for k, v in yr.items()}, h2_cost_stress_net=round(float(c2.net_today.sum()), 0),
                        placebo_beaten=f"{beaten}/200", placebo_median=round(float(np.median(pn)), 0), gates=gates, confirmed=all(gates.values()),
                        h2_net_at_68=round(float(dollars(raw, P=68.0).net_today.sum()), 0), h2_net_at_102=round(float(dollars(raw, P=102.0).net_today.sum()), 0),
                        h2_mcl_median=float(base_risk.q.median()))
        if all(gates.values()): sel[fam] = pick
        print(fam, pick, "H2", st, "by yr", out[fam]["h2_by_year"], "cost+", out[fam]["h2_cost_stress_net"], "placebo", f"{beaten}/200", "gates", gates, flush=True)
    out["confirmed"] = sel
    if sel:
        out["book"] = book_test(T, sel)
    (ROOT / "reports/CL_1_PAYOUT_SLEEVES_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
    print("saved", flush=True)


def book_test(T, sel):
    import payout_17_bond_filter_train as p17
    H1, H2 = ("2010-07-01", "2016-12-01"), ("2017-01-01", "2023-01-01")
    CL = {k: dollars(T[T.cfg.isin(list(sel.values()))], k)[["tin", "tout", "net_today"]] for k in ("S0", "S3", "S4")}
    SER = {}
    for k in ("S0", "S3", "S4"):
        i, n = p17.scenario(k, p17.N0)
        for nt in (False, True):
            for ct in (False, True):
                SER[(k, nt, ct)] = p17.fast_day_series(pd.concat([i] + ([n] if nt else []) + ([CL[k]] if ct else []), ignore_index=True)).to_dict()

    def ev(k, S_cl, start_from="2010-07-01", start_to="2023-01-01", S_night=500.0, C=1000.0):
        ser = {key[1:]: v for key, v in SER.items() if key[0] == k}
        days = sorted(set().union(*[set(s) for s in ser.values()])); idx = pd.to_datetime(pd.Series(days).astype(str)).to_numpy(); res = []
        for s0 in pd.date_range(start_from, start_to, freq="MS"):
            a = int(np.searchsorted(idx, np.datetime64(s0))); b = int(np.searchsorted(idx, np.datetime64(s0 + pd.DateOffset(months=12))))
            bal = 0.0; good = 0; pays = 0; breach = False; dll = 0; q = 0
            for x in days[a:b]:
                p = ser[(bal >= S_night, S_cl is not None and bal >= S_cl)].get(x, 0.0)
                dll += p <= -1000; bal += max(p, -1000.0)
                if bal <= -2000.0: breach = True; break
                good += p >= 150; q += p >= 150
                if good >= 5 and bal - C > 0: pays += 1; bal = C; good = 0
            res.append((pays, breach, dll, q))
        r = pd.DataFrame(res, columns=["pays", "breach", "dll", "q"])
        return dict(payouts_12m_mean=round(float(r.pays.mean()), 2), payouts_12m_p10=float(r.pays.quantile(.1)), p_breach_12m=round(float(r.breach.mean()), 3),
                    dll_days=int(r.dll.sum()), days_ge150_12m=round(float(r.q.mean()), 1))

    def cell(S_cl):
        return dict(S0=ev("S0", S_cl), S3=ev("S3", S_cl), S4=ev("S4", S_cl), H1=ev("S0", S_cl, *H1), H2=ev("S0", S_cl, *H2))

    out = {"base R": cell(None)}; b = out["base R"]
    ref = json.loads((ROOT / "reports/PAYOUT_17_BOND_FILTER_TRAINING.json").read_text())["base R | staged $500"]
    out["base_reproduces_payout_17"] = bool(all(abs(b[k]["payouts_12m_mean"] - ref[k]["payouts_12m_mean"]) < 1e-9 and abs(b[k]["p_breach_12m"] - ref[k]["p_breach_12m"]) < 1e-9
                                                for k in ("S0", "S3", "S4")))
    print("base", b, "| reproduces payout_17:", out["base_reproduces_payout_17"], flush=True)
    cl_day = pd.Series(SER[("S0", True, True)]) - pd.Series(SER[("S0", True, False)]).reindex(pd.Series(SER[("S0", True, True)]).index, fill_value=0)
    bk = pd.Series(SER[("S0", True, False)]); u = bk.index.union(cl_day.index)
    both = pd.DataFrame({"book": bk.reindex(u, fill_value=0), "cl": cl_day.reindex(u, fill_value=0)})
    out["diag"] = dict(corr_daily=round(float(both.book.corr(both.cl)), 3),
                       new_ge150_days_per_year=round(float(((both.book < 150) & (both.book + both.cl >= 150)).sum() / 13.5), 1),
                       lost_ge150_days_per_year=round(float(((both.book >= 150) & (both.book + both.cl < 150)).sum() / 13.5), 1))
    print("diag", out["diag"], flush=True)
    for name, S in (("crude always on", -1e12), ("crude above $500", 500.0)):
        c = out[name] = cell(S)
        c["adopt"] = bool(c["S0"]["p_breach_12m"] <= 0.02 and c["S3"]["p_breach_12m"] <= 0.05 and c["S4"]["p_breach_12m"] <= b["S4"]["p_breach_12m"]
                          and c["S0"]["dll_days"] == 0 and c["S0"]["payouts_12m_mean"] >= b["S0"]["payouts_12m_mean"] + 0.5
                          and c["H1"]["payouts_12m_mean"] > b["H1"]["payouts_12m_mean"] and c["H2"]["payouts_12m_mean"] > b["H2"]["payouts_12m_mean"])
        print(name, c, flush=True)
    ok = [n for n in ("crude always on", "crude above $500") if out[n]["adopt"]]
    out["selected"] = max(ok, key=lambda n: out[n]["S0"]["payouts_12m_mean"]) if ok else None
    return out


if __name__ == "__main__":
    main()
