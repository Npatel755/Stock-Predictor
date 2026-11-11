"""payout_22 (Claude, 2026-11-10): late-day momentum sleeve on MNQ and a "top-up" use of it for near-miss days. TRAINING 2010-23 only.

PRE-DECLARED (before results).
Hypothesis (Gao, Han, Li & Zhou 2018, "Market intraday momentum", JFE): the first half-hour return predicts the last half-hour return.
Sleeve: 1 MNQ. Signal A = prior 16:00 close -> 10:00 close; signal B = 09:30 open -> 10:00 close. Enter in the signal's direction at the
15:00 or 15:30 bar open, exit at the 16:00 close (15:59 bar), stop 0.50% (stop-first, gap fills at the open). Days whose bars change contract
between the prior close and 16:00 are skipped. Costs and today's-price re-expression as payout_lib (1 pt adverse + $1 fee per round trip).
4 configs. Select on H1 (2010-06..2016-12): PF >= 1.10, highest net/yr. Confirm on H2 (2017-2023), all required: net > 0, PF >= 1.10, >= 4 of 7
years positive, net > 0 with +1 pt round-trip costs, beats >= 190 of 200 random-direction placebos (seed 20261110).
Book test (only if confirmed): base R (payout_17 base) plus the sleeve either (i) every signal day, or (ii) TOP-UP: only on days whose
realised book P&L before the sleeve's entry is in [$0, $150). Concurrent with any open book trade; $400 account stop applies.
Evaluated under the old model (static -$2,000, keep $1,000) and under the real XFA rules (payout_21 account, keep $2,500).
ADOPT a cell only if, under BOTH models: S0/S3/S4 breach-or-closure no worse than base R's + 0.5 points, payouts up vs base in both halves
of the starts, and S0 payouts >= base + 0.3.
"""
import json
import numpy as np, pandas as pd
import payout_lib as pl
from payout_17_bond_filter_train import fast_day_series, scenario as sc17, N0

NY = pl.NY; PX = pl.TODAY["MNQ"]; M = pl.MULT["MNQ"]; STOP = 0.005; H1_END = pd.Timestamp("2017-01-01").date(); SEED = 20261110
H1, H2 = ("2010-07-01", "2016-12-01"), ("2017-01-01", "2023-01-01")


def load():
    ep, bars_for, START, _ = pl.engine()
    m1 = bars_for(dict(instrument="MNQ", bar_minutes=1))[0]
    assert m1.timestamp_utc.max() < pd.Timestamp("2024-01-01", tz="UTC")
    et = pd.to_datetime(m1.timestamp_utc, utc=True).dt.tz_convert(NY)
    sod = (et.dt.hour * 60 + et.dt.minute).to_numpy()
    m = (sod >= 570) & (sod <= 959) & (et.dt.dayofweek.to_numpy() < 5)
    d = pd.DataFrame({"date": et.dt.date.to_numpy()[m], "sod": sod[m], "o": m1.open.to_numpy(float)[m], "h": m1.high.to_numpy(float)[m],
                      "l": m1.low.to_numpy(float)[m], "c": m1.close.to_numpy(float)[m], "k": m1.contract.to_numpy()[m]})
    days = {}
    for dt, g in d.groupby("date", sort=True):
        if g.k.nunique() != 1 or g.sod.iloc[-1] < 955 or g.sod.iloc[0] > 572: continue
        days[dt] = dict(sod=g.sod.to_numpy(), o=g.o.to_numpy(), h=g.h.to_numpy(), l=g.l.to_numpy(), c=g.c.to_numpy(), k=g.k.iloc[0])
    return days


def walk(D, i, side, stop):
    s, o, h, l, c = D["sod"], D["o"], D["h"], D["l"], D["c"]
    for j in range(i, len(s)):
        if side > 0:
            if j > i and o[j] <= stop: return o[j], s[j]
            if l[j] <= stop: return stop, s[j]
        else:
            if j > i and o[j] >= stop: return o[j], s[j]
            if h[j] >= stop: return stop, s[j]
    return c[-1], s[-1]


def build(days):
    rows = []; dates = list(days)
    for k in range(1, len(dates)):
        dt, pv = dates[k], dates[k - 1]; D, P = days[dt], days[pv]
        s = D["sod"]; i10 = np.searchsorted(s, 599, side="right") - 1
        if i10 < 0 or s[i10] < 595: continue
        for sig in ("A", "B"):
            if sig == "A":
                if P["k"] != D["k"]: continue
                r = D["c"][i10] / P["c"][-1] - 1
            else:
                r = D["c"][i10] / D["o"][0] - 1
            if r == 0: continue
            side = 1 if r > 0 else -1
            for E in (900, 930):
                i = int(np.searchsorted(s, E))
                if i >= len(s) or s[i] > E + 2: continue
                e = D["o"][i]; g = {}
                for tag, sd in (("g", side), ("gm", -side)):
                    x, xs = walk(D, i, sd, e * (1 - sd * STOP)); g[tag] = sd * (x - e); g["xs_" + tag] = xs
                t0 = pd.Timestamp(dt).tz_localize(NY)
                rows.append(dict(cfg=f"{sig}_{E}", date=dt, side=side, entry=e, gpts=g["g"], gpts_m=g["gm"], tin=t0 + pd.Timedelta(minutes=E),
                                 dec=t0 + pd.Timedelta(minutes=E - 1), tout=t0 + pd.Timedelta(minutes=int(g["xs_g"]) + 1)))
    return pd.DataFrame(rows)


def dollars(t, col="gpts", extra_pts=0.0):
    return t.assign(net_today=(t[col] * PX / t.entry - 1.0 - extra_pts) * M - 1.0)


def stats(x, yrs):
    n = x.net_today.to_numpy(); pos, neg = n[n > 0].sum(), -n[n < 0].sum()
    return dict(trades=int(len(n)), net_per_year=round(float(n.sum()) / yrs, 0), pf=round(float(pos / neg), 3) if neg else None, avg=round(float(n.mean()), 2))


def main():
    T = build(load()); out = {"trades": T.groupby("cfg").size().to_dict()}
    S = dollars(T); y1 = (pd.Timestamp("2017-01-01") - pd.Timestamp("2010-06-07")).days / 365.25; y2 = 7.0
    grid = {c: stats(g, y1) for c, g in S[S.date < H1_END].groupby("cfg")}
    ok = {c: v for c, v in grid.items() if v["pf"] and v["pf"] >= 1.10}
    pick = max(ok, key=lambda c: ok[c]["net_per_year"]) if ok else None
    out.update(h1_grid=grid, selected=pick); print("H1 grid", grid, "-> selected", pick, flush=True)
    if pick is None:
        (pl.ROOT / "reports/PAYOUT_22_CLOSE_MOMENTUM_TRAINING.json").write_text(json.dumps(out, indent=1, default=str)); return
    raw = T[(T.cfg == pick) & (T.date >= H1_END)]; x2 = dollars(raw); st = stats(x2, y2)
    yr = x2.groupby(pd.to_datetime(x2.date).dt.year).net_today.sum()
    rng = np.random.default_rng(SEED); pn = []
    for _ in range(200):
        f = rng.random(len(raw)) < 0.5; pn.append(float(dollars(raw.assign(gpts=np.where(f, raw.gpts_m, raw.gpts))).net_today.sum()))
    beaten = int((np.array(pn) < x2.net_today.sum()).sum()); cost = float(dollars(raw, extra_pts=1.0).net_today.sum())
    gates = dict(net_pos=bool(x2.net_today.sum() > 0), pf=bool(st["pf"] and st["pf"] >= 1.10), years=int((yr > 0).sum()) >= 4, cost=cost > 0, placebo=beaten >= 190)
    out.update(h2=st, h2_by_year={int(k): round(float(v), 0) for k, v in yr.items()}, h2_cost_net=round(cost, 0), placebo_beaten=f"{beaten}/200",
               gates=gates, confirmed=all(gates.values()))
    print("H2", st, out["h2_by_year"], "cost", round(cost), "placebo", beaten, "gates", gates, flush=True)
    if all(gates.values()): out["book"] = book(dollars(T[T.cfg == pick]))
    (pl.ROOT / "reports/PAYOUT_22_CLOSE_MOMENTUM_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))


def book(sl):
    from payout_21_real_rules_books_train import run as run_real
    SER = {}
    for kind in ("S0", "S3", "S4"):
        i, n = sc17(kind, N0); s = sl.copy()
        if kind == "S3":
            s["net_today"] -= 1.0 * M; s["net_today"] -= 0.25 * max(float(s.net_today.mean()), 0.0)
        if kind == "S4": s["net_today"] *= 1.5
        s = s[["tin", "tout", "net_today"]]
        for nt in (False, True):
            bk = pd.concat([i] + ([n] if nt else []), ignore_index=True)
            # realised book P&L on the sleeve's day before its entry (closed trades only)
            real = {}
            for r in s.itertuples():
                m = (bk.tout.dt.date == r.tin.date()) & (bk.tout <= r.tin)
                real[r.Index] = float(bk.net_today[m].sum())
            top = s[[0.0 <= real[k] < 150.0 for k in s.index]]
            SER[(kind, "base", nt)] = fast_day_series(bk).to_dict()
            SER[(kind, "always", nt)] = fast_day_series(pd.concat([bk, s], ignore_index=True)).to_dict()
            SER[(kind, "topup", nt)] = fast_day_series(pd.concat([bk, top], ignore_index=True)).to_dict()

    def old(ser, start_from="2010-07-01", start_to="2023-01-01", S_night=500.0, C=1000.0):
        days = sorted(set(ser[False]) | set(ser[True])); idx = pd.to_datetime(pd.Series(days).astype(str)).to_numpy(); res = []
        for s0 in pd.date_range(start_from, start_to, freq="MS"):
            a = int(np.searchsorted(idx, np.datetime64(s0))); b = int(np.searchsorted(idx, np.datetime64(s0 + pd.DateOffset(months=12))))
            bal = 0.0; good = 0; pays = 0; br = False
            for x in days[a:b]:
                p = max((ser[True] if bal >= S_night else ser[False]).get(x, 0.0), -1000.0); bal += p
                if bal <= -2000: br = True; break
                good += p >= 150
                if good >= 5 and bal - C > 0: pays += 1; bal = C; good = 0
            res.append((pays, br))
        r = pd.DataFrame(res, columns=["pays", "br"])
        return dict(payouts_12m_mean=round(float(r.pays.mean()), 2), breach=round(float(r.br.mean()), 3))

    out = {}
    for cell in ("base", "always", "topup"):
        c = out[cell] = {}
        for k in ("S0", "S3", "S4"):
            ser = {nt: SER[(k, cell, nt)] for nt in (False, True)}
            c[f"old_{k}"] = old(ser); c[f"real_{k}"] = run_real(ser, 500.0, ("keep", 2500.0))
        ser0 = {nt: SER[("S0", cell, nt)] for nt in (False, True)}
        c["old_H1"], c["old_H2"] = old(ser0, *H1), old(ser0, *H2)
        c["real_H1"], c["real_H2"] = run_real(ser0, 500.0, ("keep", 2500.0), *H1), run_real(ser0, 500.0, ("keep", 2500.0), *H2)
        print(cell, {k: v for k, v in c.items()}, flush=True)
    b = out["base"]
    for cell in ("always", "topup"):
        c = out[cell]
        risk_ok = all(c[f"old_{k}"]["breach"] <= b[f"old_{k}"]["breach"] + 0.005 and c[f"real_{k}"]["closed_12m"] <= b[f"real_{k}"]["closed_12m"] + 0.005 for k in ("S0", "S3", "S4"))
        gain = (c["old_S0"]["payouts_12m_mean"] >= b["old_S0"]["payouts_12m_mean"] + 0.3 and c["real_S0"]["payouts_12m_mean"] >= b["real_S0"]["payouts_12m_mean"] + 0.3
                and all(c[f"{m}_{h}"]["payouts_12m_mean"] > b[f"{m}_{h}"]["payouts_12m_mean"] for m in ("old", "real") for h in ("H1", "H2")))
        c["adopt"] = bool(risk_ok and gain); print(cell, "adopt", c["adopt"], flush=True)
    return out


if __name__ == "__main__":
    main()
