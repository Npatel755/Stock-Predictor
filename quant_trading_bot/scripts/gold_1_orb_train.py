"""gold_1 (Claude, 2026-11-10): opening-range breakout at the COMEX open on gold (research on free spot data, executed as MGC). TRAINING ONLY.

PRE-DECLARED (written while the spot data was still downloading; no gold minute data had been opened).
Mechanism: the opening-range breakout is the one setup that works in our NQ book (AG_CRABEL15); transfer it to gold at the 08:20 ET COMEX open.
Data: free spot XAU/USD 1-minute bars 2010-06..2023-12 (planned: Dukascopy; it throttled with HTTP 503, so HistData.com yearly files were used
instead). DATA FIX after the proxy gate first failed (corr 0.40) and before any strategy result was computed: HistData's clock is New York time
with daylight saving, and from 2019 its timestamps are inconsistent in the weeks between the US and EU clock changes, so every year's spring
[2nd Sun Mar, last Sun Mar) and fall [last Sun Oct, 1st Sun Nov) gap weeks are dropped. The gate itself is unchanged. PROXY GATE (must pass before any result is used): hourly
returns of the spot data vs CME GC.v.0 ohlcv-1h over matching ET hours, correlation >= 0.95; median |spot - futures| level gap reported.
Day = ET weekday; a day is used if >= 80% of the minutes 08:20-13:29 exist. One trade per day, flat by the 13:29 bar close (COMEX day close).
Configs (8): range 08:20 -> 08:20+L (L 15 | 30 min); first 1-minute close beyond it before 11:30 enters at the next bar's open; stop = far side
of the range | range midpoint; exit 13:29 close | target 1x range width (else 13:29). Stop checked first on every bar including the entry bar;
a bar opening through the stop fills at its open; a target fills only if the stop is not touched in the same bar.
MGC at today's price (~$4,150; 10 oz, $10 per $1): costs $4.97 per micro round trip (1.75 ticks spread + 1 tick slippage per side + $1.22).
Size: clip(floor($200 / (1-micro stop risk incl. costs)), 1, 5) micros; skip a trade whose 1-micro risk exceeds $300.
SELECTION on 2010-06..2016-12: PF >= 1.10 after costs, >= 20 trades/yr, highest net per year. CONFIRMATION on 2017-2023, all required: net > 0,
PF >= 1.10, >= 4 of 7 years positive, net > 0 with +$4 per micro round trip, beats >= 190 of 200 random-direction placebos (same entries, stop
distances and exits mirrored; seed 20261110).
BOOK TEST (only if confirmed): payout_24 account (1x below $4,000, 2x from $4,000, daily payouts above $6,000) with base R plus the gold sleeve
at its own size (not doubled), concurrent positions allowed, $400 / $700 account stop across both. Cells: gold always on | gold only while the
balance >= $500. Stresses for gold: S3 +$4/micro and -25% of its average net; S4 net and risk x1.5. ADOPT a cell only if: 24-month dollars
withdrawn >= base x 1.10 in both halves of the starts, closure (S0, S3, S4) <= base + 0.005, and S0 near-miss (lowest balance before the first
payout <= -$1,500) <= base's.
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts"))
NY = "America/New_York"; PX, PT, COST, R, KMAX, SKIP = 4150.0, 10.0, 4.97, 200.0, 5, 300.0
H1_END, SEED = pd.Timestamp("2017-01-01").date(), 20261110


def dst_gap(idx):
    """True for minutes on the ET dates between the US and EU clock changes (spring and fall), every year."""
    d = pd.Series(idx.tz_convert(NY).date, index=idx); out = np.zeros(len(idx), bool); dates = pd.to_datetime(d.values)
    for y in range(2010, 2024):
        mar = pd.date_range(f"{y}-03-01", f"{y}-03-31"); octo = pd.date_range(f"{y}-10-01", f"{y}-10-31"); nov = pd.date_range(f"{y}-11-01", f"{y}-11-07")
        us_start = mar[mar.dayofweek == 6][1]; eu_start = mar[mar.dayofweek == 6][-1]; eu_end = octo[octo.dayofweek == 6][-1]; us_end = nov[nov.dayofweek == 6][0]
        out |= ((dates >= us_start) & (dates < eu_start)) | ((dates >= eu_end) & (dates < us_end))
    return out


def proxy_gate(spot):
    cme = pd.read_parquet(ROOT / "data/market/crossasset_train/GC_v_0_ohlcv1h_2010_2023.parquet")
    s = spot.close.resample("1h").last().dropna(); c = cme.close
    j = pd.concat([s.rename("spot"), c.rename("cme")], axis=1).dropna()
    r = j.pct_change().dropna(); r = r[(r.abs() < 0.05).all(axis=1)]            # drop contract-roll jumps
    return dict(hours=int(len(r)), corr=round(float(r.spot.corr(r.cme)), 4), median_level_gap=round(float((j.spot - j.cme).abs().median()), 2),
                passed=bool(r.spot.corr(r.cme) >= 0.95))


def load_days(spot):
    et = spot.index.tz_convert(NY); sod = np.asarray(et.hour * 60 + et.minute)
    m = (sod >= 500) & (sod <= 809) & (np.asarray(et.dayofweek) < 5)
    d = pd.DataFrame({"date": np.asarray(et.date)[m], "sod": sod[m], "o": spot.open.to_numpy()[m], "h": spot.high.to_numpy()[m],
                      "l": spot.low.to_numpy()[m], "c": spot.close.to_numpy()[m]})
    days = {}
    for dt, g in d.groupby("date", sort=True):
        if len(g) < 0.8 * 310: continue
        days[dt] = {k: g[k].to_numpy() for k in ("sod", "o", "h", "l", "c")}
    return days


def walk(D, i, side, stop, tgt, exit_sod=809):
    s, o, h, l, c = D["sod"], D["o"], D["h"], D["l"], D["c"]
    for j in range(i, len(s)):
        if j > i and s[j] > exit_sod: return c[j - 1]
        if side > 0:
            if j > i and o[j] <= stop: return o[j]
            if l[j] <= stop: return stop
            if tgt is not None and h[j] >= tgt: return o[j] if (j > i and o[j] > tgt) else tgt
        else:
            if j > i and o[j] >= stop: return o[j]
            if h[j] >= stop: return stop
            if tgt is not None and l[j] <= tgt: return o[j] if (j > i and o[j] < tgt) else tgt
        if s[j] >= exit_sod: return c[j]
    return c[-1]


def build(days):
    rows = []
    for dt, D in days.items():
        s = D["sod"]
        for L in (15, 30):
            m = (s >= 500) & (s < 500 + L)
            if m.sum() < L - 2: continue
            hi, lo = D["h"][m].max(), D["l"][m].min()
            idx = np.where((s >= 500 + L) & (s < 690))[0]
            hit = next((j for j in idx if D["c"][j] > hi or D["c"][j] < lo), None)
            if hit is None or hit + 1 >= len(s): continue
            side = 1 if D["c"][hit] > hi else -1; i = hit + 1; e = D["o"][i]
            for sm in ("far", "mid"):
                stop = (lo if side > 0 else hi) if sm == "far" else (hi + lo) / 2
                if (side > 0 and e <= stop) or (side < 0 and e >= stop): continue
                for xm in ("time", "tgt1"):
                    tgt = None if xm == "time" else e + side * (hi - lo)
                    g = side * (walk(D, i, side, stop, tgt) - e) / e
                    gm = -side * (walk(D, i, -side, 2 * e - stop, None if tgt is None else 2 * e - tgt) - e) / e
                    t0 = pd.Timestamp(dt).tz_localize(NY)
                    rows.append(dict(cfg=f"L{L}_{sm}_{xm}", date=dt, side=side, stop_pct=abs(e - stop) / e, g=g, gm=gm,
                                     tin=t0 + pd.Timedelta(minutes=int(s[i])), tout=t0 + pd.Timedelta(minutes=810)))
    return pd.DataFrame(rows)


def dollars(t, col="g", extra=0.0, vol=1.0):
    risk1 = (t.stop_pct * PX * PT + COST + extra) * vol
    q = np.clip(np.floor(R / risk1), 1, KMAX)
    return t.assign(q=q, risk1=risk1, net_today=(t[col] * PX * PT - COST - extra) * vol * q)[risk1 <= SKIP]


def stats(x, yrs):
    n = x.net_today.to_numpy(); pos, neg = n[n > 0].sum(), -n[n < 0].sum()
    return dict(trades=int(len(n)), per_year=round(len(n) / yrs, 1), net_per_year=round(float(n.sum()) / yrs, 0), pf=round(float(pos / neg), 3) if neg else None,
                avg=round(float(n.mean()), 2) if len(n) else None)


def main():
    spot = pd.read_parquet(ROOT / "data/external/histdata_xauusd/xauusd_1m_2010_2023.parquet")
    spot = spot[~dst_gap(spot.index)]
    assert spot.index.max() < pd.Timestamp("2024-01-01", tz="UTC")
    out = {"proxy_gate": proxy_gate(spot)}; print("proxy gate:", out["proxy_gate"], flush=True)
    if not out["proxy_gate"]["passed"]:
        (ROOT / "reports/GOLD_1_ORB_TRAINING.json").write_text(json.dumps(out, indent=1, default=str)); return
    days = load_days(spot); T = build(days); out["days_used"] = len(days)
    S = dollars(T); y1 = (pd.Timestamp("2017-01-01") - pd.Timestamp("2010-06-01")).days / 365.25
    grid = {c: stats(g, y1) for c, g in S[S.date < H1_END].groupby("cfg")}
    ok = {c: v for c, v in grid.items() if v["pf"] and v["pf"] >= 1.10 and v["per_year"] >= 20}
    pick = max(ok, key=lambda c: ok[c]["net_per_year"]) if ok else None
    out.update(h1_grid=grid, selected=pick); print("H1:", {c: (v["net_per_year"], v["pf"], v["per_year"]) for c, v in grid.items()}, "->", pick, flush=True)
    if pick:
        raw = T[(T.cfg == pick) & (T.date >= H1_END)]; x2 = dollars(raw); st = stats(x2, 7.0)
        yr = x2.groupby(pd.to_datetime(x2.date).dt.year).net_today.sum()
        rng = np.random.default_rng(SEED)
        pn = [float(dollars(raw.assign(g=np.where(rng.random(len(raw)) < 0.5, raw.gm, raw.g))).net_today.sum()) for _ in range(200)]
        beaten = int((np.array(pn) < x2.net_today.sum()).sum()); cost = float(dollars(raw, extra=4.0).net_today.sum())
        gates = dict(net=bool(x2.net_today.sum() > 0), pf=bool(st["pf"] and st["pf"] >= 1.10), years=int((yr > 0).sum()) >= 4, cost=cost > 0, placebo=beaten >= 190)
        out.update(h2=st, h2_by_year={int(k): round(float(v), 0) for k, v in yr.items()}, h2_cost_stress=round(cost, 0), placebo_beaten=f"{beaten}/200",
                   gates=gates, confirmed=all(gates.values()))
        print("H2:", st, out["h2_by_year"], "cost", round(cost), "placebo", beaten, "gates", gates, flush=True)
        if all(gates.values()): out["book"] = book_test(T[T.cfg == pick])
    (ROOT / "reports/GOLD_1_ORB_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))


def book_test(raw):
    src = (ROOT / "scripts/payout_25_early_protection_train.py").read_text(encoding="utf-8").split("\nVAR = {}\n")[0]
    P = {"__name__": "p25"}; exec(src, P)
    pl, stressed_intra, sc17, N0, fds, NIGHT_RISK = P["pl"], P["stressed_intra"], P["sc17"], P["N0"], P["fast_day_series"], P["P24"]["NIGHT_RISK"]
    HALVES = P["HALVES"]
    def gold(kind):
        if kind == "S0": g = dollars(raw)
        elif kind == "S3": g = dollars(raw, extra=4.0); g = g.assign(net_today=g.net_today - 0.25 * max(float(g.net_today.mean()), 0.0))
        else: g = dollars(raw, vol=1.5)
        return g[["tin", "tout", "net_today"]]
    SER = {}
    for kind in ("S0", "S3", "S4"):
        e = stressed_intra(kind); _, n = sc17(kind, N0); gd = gold(kind)
        for m in (1, 2):
            em = e[e.risk_today * e.n_contracts * m <= (900.0 if m > 1 else 1e9)]
            i = pl.route(em)[["tin", "tout", "net_today"]].assign(net_today=lambda x: x.net_today * m)
            nm = n.assign(net_today=n.net_today * m) if (m == 1 or NIGHT_RISK * (1.5 if kind == "S4" else 1) * m <= 900.0) else n.iloc[0:0]
            stop = 400.0 if m == 1 else 700.0
            for night in (False, True):
                for g_on in (False, True):
                    parts = [i] + ([nm] if night else []) + ([gd] if g_on else [])
                    SER[(kind, m, night, g_on)] = fds(pd.concat(parts, ignore_index=True), stop).to_dict()
    def run(kind, S_gold, start_from="2010-07-01", start_to="2022-01-01"):
        keys = [k for k in SER if k[0] == kind]
        days = sorted(set().union(*[set(SER[k]) for k in keys])); ix = pd.to_datetime(pd.Series(days).astype(str)).to_numpy(); rows = []
        for s0 in pd.date_range(start_from, start_to, freq="MS"):
            a = int(np.searchsorted(ix, np.datetime64(s0))); b = int(np.searchsorted(ix, np.datetime64(s0 + pd.DateOffset(months=24))))
            bal = 0.0; paid = False; since = 0.0; usd = 0.0; closed = False; low = 0.0; pays = 0
            for x in days[a:b]:
                m = 2 if bal >= 4000 else 1
                p = max(SER[(kind, m, bal >= 500.0, S_gold is not None and bal >= S_gold)].get(x, 0.0), -1000.0); bal += p; since += p
                if not paid: low = min(low, bal)
                if bal <= (0.0 if paid else -2000.0): closed = True; break
                if (since > 0 or not paid) and bal - 6000.0 >= 250.0:
                    w = min(1500.0, bal - 6000.0); bal -= w; usd += w; paid = True; since = 0.0; pays += 1
            rows.append((usd, closed, low <= -1500.0, pays))
        r = pd.DataFrame(rows, columns=["usd", "closed", "near", "pays"])
        return dict(withdrawn_24m=round(float(r.usd.mean()), 0), closed_24m=round(float(r.closed.mean()), 3), near_miss=round(float(r.near.mean()), 3),
                    payouts_24m=round(float(r.pays.mean()), 2))
    def cell(S):
        c = {k: run(k, S) for k in ("S0", "S3", "S4")}; c["half1"] = run("S0", S, *HALVES[0]); c["half2"] = run("S0", S, *HALVES[1]); return c
    out = {"base": cell(None)}; b = out["base"]; print("book base", b, flush=True)
    for name, S in (("gold always on", -1e12), ("gold from $500", 500.0)):
        c = out[name] = cell(S)
        c["adopt"] = bool(all(c[h]["withdrawn_24m"] >= 1.10 * b[h]["withdrawn_24m"] for h in ("half1", "half2"))
                          and all(c[k]["closed_24m"] <= b[k]["closed_24m"] + 0.005 for k in ("S0", "S3", "S4")) and c["S0"]["near_miss"] <= b["S0"]["near_miss"])
        print(name, c, flush=True)
    return out


if __name__ == "__main__":
    main()
