"""payout_17 (Claude, 2026-11-10): bond-filtered overnight leg in the payout book (Devin's xasset_3 rule). TRAINING 2010-23 only.

PRE-DECLARED (before results). xasset_3 found that skipping overnight-dip nights after a ZN down day (ZN 16:00 ET close vs prior 16:00)
cut the leg's marked drawdown 2,043 -> 1,506 keeping 93.5% of net (193/200 placebos worse), but with the 15:00 ET close only 147/200 (fragile).
payout_10: the overnight leg always on gave 7.14 payouts/12m but 2.6% breach (failed); payout_11 staged it at a $500 balance (6.21, 0.7%).
Question: does the bond filter let the overnight leg run more often (always on, or staged) for more payouts within the risk limits?
Book R = v5.2 intraday (unchanged) + overnight dip 0.55% stop; nights with ZN day return < 0 skipped (missing ZN = trade; Sunday nights use
Friday, ffill <= 3 days). ZN = Databento ZN.c.0 ohlcv-1h (training years only): 16:00 close = close of the 15:00-16:00 ET bar, 15:00 close =
close of the 14:00-15:00 ET bar. Variants: overnight staged at $500 | staged at $0 (labelled "always on" in the first draft; it is off while the balance is below 0). Scenarios S0 / S3 / S4 as payout_13.
ADOPT a variant only if, under BOTH close definitions: S0 breach <= 2%, S3 breach <= 5%, S4 breach <= base R's (0.113), 0 days <= -$1,000,
S0 payouts >= base R + 0.3; AND it beats random skipping: of 200 placebos skipping the same number of nights at random (same variant, S0),
at most 10% are no worse on both payouts and breach. If both variants pass, take the one with more S0 payouts (16:00 definition).
"""
import json
import numpy as np, pandas as pd
import payout_lib as pl

src = (pl.ROOT / "scripts/payout_13_stress_train.py").read_text(encoding="utf-8").split("\nout = {}")[0]
ns = {"__name__": "p13"}; exec(src, ns)
base_intra, nights, stop_loss_level = ns["base_intra"], ns["nights"], ns["stop_loss_level"]
N0 = nights(0.0055).reset_index(drop=True)

zn = pd.read_parquet(pl.ROOT / "data/market/crossasset_train/ZN_c_0_ohlcv1h_2010_2023.parquet")
assert zn.index.max() < pd.Timestamp("2024-01-01", tz="UTC")
zet = zn.index.tz_convert("America/New_York")


def zn_down(close_hour):
    sel = zet.hour == close_hour - 1
    c = pd.Series(zn.close.to_numpy()[sel], index=pd.to_datetime(zet[sel].date)).groupby(level=0).last()
    D = (c / c.shift(1) - 1).dropna()
    nd = pd.to_datetime(N0.tin.dt.date)
    Dn = D.reindex(D.index.union(nd)).ffill(limit=3).reindex(nd).to_numpy()
    return Dn < 0, int(np.isnan(Dn).sum())


def fast_day_series(df, stop=400.0):
    """Same as payout_lib.day_series (account stop on realised same-day P&L before each entry), O(n * trades per day)."""
    df = df.sort_values("tin"); kept_by_day = {}; tot = {}
    for tin, tout, net in zip(df.tin, df.tout, df.net_today):
        dk = tin.date(); prior = kept_by_day.get(dk, [])
        if sum(n for o, n in prior if o <= tin) <= -stop: continue
        kept_by_day.setdefault(tout.date(), []).append((tout, net)); tot[tout.date()] = tot.get(tout.date(), 0.0) + net
    return pd.Series(tot).sort_index()


def scenario(kind, n):
    d = base_intra.copy(); n = n.copy()
    if kind in ("S1", "S3"):
        d["net_today"] -= 1.0 * d.inst.map(pl.MULT) * d.n_contracts; n["net_today"] -= 1.0 * pl.MULT["MNQ"]
    if kind in ("S2", "S3"):
        avg = d.groupby("sleeve").net_today.transform("mean"); d["net_today"] -= 0.25 * avg.clip(lower=0)
        n["net_today"] -= 0.25 * max(float(N0.net_today.mean()), 0.0)
    if kind == "S4":
        d["risk_today"] *= 1.5; d["net_today"] *= 1.5
        stopped = n.net_today <= stop_loss_level + 1e-6; n.loc[~stopped, "net_today"] *= 1.5
    return pl.route(d[d.risk_today <= 300.0])[["tin", "tout", "net_today"]], n[["tin", "tout", "net_today"]]


_INTRA = {}


def evaluate(kind, nmask, S_night, C=1000.0):
    if kind not in _INTRA:
        i, _ = scenario(kind, N0); _INTRA[kind] = (i, fast_day_series(i).to_dict())
    intra, io = _INTRA[kind]
    _, n = scenario(kind, N0[nmask])
    wn = fast_day_series(pd.concat([intra, n], ignore_index=True)).to_dict()
    days = sorted(set(io) | set(wn)); idx = pd.to_datetime(pd.Series(days).astype(str)).to_numpy(); res = []
    for s0 in pd.date_range("2010-07-01", "2023-01-01", freq="MS"):
        a = int(np.searchsorted(idx, np.datetime64(s0))); b = int(np.searchsorted(idx, np.datetime64(s0 + pd.DateOffset(months=12))))
        bal = 0.0; good = 0; pays = 0; breach = False; dll = 0
        for x in days[a:b]:
            p = (wn if bal >= S_night else io).get(x, 0.0)
            dll += p <= -1000; bal += max(p, -1000.0)
            if bal <= -2000.0: breach = True; break
            good += p >= 150
            if good >= 5 and bal - C > 0: pays += 1; bal = C; good = 0
        res.append((pays, breach, dll))
    r = pd.DataFrame(res, columns=["pays", "breach", "dll"])
    return dict(payouts_12m_mean=round(float(r.pays.mean()), 2), payouts_12m_p10=float(r.pays.quantile(.1)), p_breach_12m=round(float(r.breach.mean()), 3), dll_days=int(r.dll.sum()))


if __name__ == "__main__":
    # check the fast day series against payout_lib's
    i0, _ = scenario("S0", N0); chk = pd.concat([i0, N0[["tin", "tout", "net_today"]]], ignore_index=True)
    a, b = fast_day_series(chk), pl.day_series(chk, stop=400.0)
    assert len(a) == len(b) and np.allclose(a.to_numpy(), b.reindex(a.index).to_numpy()), "fast_day_series differs"
    allm = np.ones(len(N0), bool); out = {}
    for name, S in (("staged $500", 500.0), ("staged $0 (on while balance >= 0)", 0.0)):
        out[f"base R | {name}"] = {k: evaluate(k, allm, S) for k in ("S0", "S3", "S4")}
        print(f"base R | {name}", out[f"base R | {name}"], flush=True)
    base = out["base R | staged $500"]
    rng = np.random.default_rng(20261110)
    for hour in (16, 15):
        down, miss = zn_down(hour); keep = ~down
        print(f"ZN {hour}:00 close: nights {len(N0)}, skipped {int(down.sum())}, ZN missing {miss}", flush=True)
        for name, S in (("staged $500", 500.0), ("staged $0 (on while balance >= 0)", 0.0)):
            c = {k: evaluate(k, keep, S) for k in ("S0", "S3", "S4")}
            c["passes_risk_and_gain"] = bool(c["S0"]["p_breach_12m"] <= 0.02 and c["S3"]["p_breach_12m"] <= 0.05 and c["S4"]["p_breach_12m"] <= base["S4"]["p_breach_12m"]
                                             and c["S0"]["dll_days"] == 0 and c["S0"]["payouts_12m_mean"] >= base["S0"]["payouts_12m_mean"] + 0.3)
            pl_res = []
            for _ in range(200):
                m = np.ones(len(N0), bool); m[rng.choice(len(N0), int(down.sum()), replace=False)] = False
                e = evaluate("S0", m, S); pl_res.append((e["payouts_12m_mean"], e["p_breach_12m"]))
            pr = np.array(pl_res); no_worse = int(((pr[:, 0] >= c["S0"]["payouts_12m_mean"]) & (pr[:, 1] <= c["S0"]["p_breach_12m"])).sum())
            c["placebo"] = dict(payouts_median=float(np.median(pr[:, 0])), breach_median=float(np.median(pr[:, 1])), no_worse_on_both=f"{no_worse}/200")
            c["beats_random"] = bool(no_worse <= 20)
            out[f"ZN{hour} | {name}"] = c
            print(f"ZN{hour} | {name}", c, flush=True)
    adopt = {}
    for name in ("staged $500", "staged $0 (on while balance >= 0)"):
        adopt[name] = bool(all(out[f"ZN{h} | {name}"]["passes_risk_and_gain"] and out[f"ZN{h} | {name}"]["beats_random"] for h in (16, 15)))
    out["adopt"] = adopt
    ok = [n for n, v in adopt.items() if v]
    out["selected"] = max(ok, key=lambda n: out[f"ZN16 | {n}"]["S0"]["payouts_12m_mean"]) if ok else None
    print("adopt:", adopt, "selected:", out["selected"])
    (pl.ROOT / "reports/PAYOUT_17_BOND_FILTER_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
