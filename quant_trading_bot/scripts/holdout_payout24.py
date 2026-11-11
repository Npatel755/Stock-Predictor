"""ONE-SHOT frozen holdout check of base R + the payout_24 account rule on validation (2024-25) and test (2026). Requested by Nick 2026-11-10.
Spec, gate and file hashes are frozen in reports/HOLDOUT_PAYOUT24_FREEZE.json (written before this script loaded any 2024-26 data); this
script refuses to run if any frozen file changed. Strategy code is the training code; only the data source differs. No rule may be changed
after this run; the result is reported as is.
"""
import hashlib, json, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
FZ = json.loads((ROOT / "reports/HOLDOUT_PAYOUT24_FREEZE.json").read_text())
for f, h in FZ["sha256"].items():
    assert hashlib.sha256((ROOT / f).read_bytes()).hexdigest() == h, f"frozen file changed: {f}"

import payout_lib as pl
import mass_1m_search as m1
ep, _bt, _st, _gs = pl.engine()                     # sets the VIX/VIX3M day-filter cache (CBOE history runs to 2026-11-06)

SPLITS = {"validation": dict(split="validation", lo="2024-01-01", hi="2026-01-01", warm_split="train", warm="2023-10-01"),
          "test": dict(split="test", lo="2026-01-01", hi="2027-01-01", warm_split="validation", warm="2025-10-01")}


def make_bars_for(cfg):
    cache = {}
    def bars_for(sl):
        k = ep.bars_key(sl); mins = int(sl.get("bar_minutes", ep.BAR_MINUTES))
        if k not in cache:
            w = m1.load_bars(sl["instrument"], mins, cfg["warm"], cfg["lo"], cfg["warm_split"])
            b = m1.load_bars(sl["instrument"], mins, cfg["lo"], cfg["hi"], cfg["split"])
            b = pd.concat([w, b], ignore_index=True).drop_duplicates("timestamp_utc").sort_values("timestamp_utc").reset_index(drop=True)
            c, h, l = b.close.astype(float), b.high.astype(float), b.low.astype(float); prev = c.shift(1)
            atr = pd.concat((h - l, (h - prev).abs(), (l - prev).abs()), axis=1).max(axis=1).rolling(14, min_periods=14).mean()
            cache[k] = (b, mins, pd.Series(atr.to_numpy(), index=pd.DatetimeIndex(b.timestamp_utc)))
        return cache[k]
    return bars_for


def sleeve_trades(bars_for, START, sl, prio, day_filter):
    """payout_lib.sleeve_trades without its training-only assert (same body otherwise)."""
    sl = dict(sl, risk_per_trade=1e9, max_open_risk=1e9, max_contracts=1, hard_drawdown=1e9, funded_drawdown=1e9)
    b, mins, atr = bars_for(sl)
    spec = {"day_filter": "no_backwardation"} if day_filter else {}
    r = ep.run_sleeve(sl, b, START, ep.day_filter_mask(spec, b, sl) if day_filter else None)
    rows = []
    for t in r["trades"]:
        e = pd.Timestamp(t["entry_ts"]); dec = e - pd.Timedelta(minutes=mins); a = float(atr.get(dec, np.nan))
        rows.append(dict(sleeve=sl["name"], prio=prio, inst=sl["instrument"], side=int(t["side"]), entry=float(t["entry_price"]),
                         exit=float(t["exit_price"]), net_then=float(t["net"]), tin=e.tz_convert(pl.NY), tout=pd.Timestamp(t["exit_ts"]).tz_convert(pl.NY),
                         dec=dec.tz_convert(pl.NY), stop_pct=float(sl["stop_atr"]) * a / float(t["entry_price"])))
    return pd.DataFrame(rows)


def build(name):
    cfg = SPLITS[name]; bars_for = make_bars_for(cfg); START = cfg["lo"] + "T00:00:00Z"
    S = {"CRABEL": (dict(ep._AG_CRABEL15_D, name="AG_CRABEL15_D_1c"), True), "TRD60": (dict(ep._AG_TRD60_D, name="AG_TRD60_D_1c"), True),
         "MES30": (dict(ep._AG_MES_TRD30_D, name="AG_MES_TRD30_D_1c"), False), "TRD30PM": (dict(ep._AG_TRD30PM, name="AG_TRD30PM_1c"), False)}
    T = {k: pl.price_normalize(sleeve_trades(bars_for, START, sl, i, flt)) for i, (k, (sl, flt)) in enumerate(S.items())}
    gs = ep.gap_sign_by_day(bars_for(S["CRABEL"][0])[0])
    c = T["CRABEL"]; cont = np.array([int(r.side) * gs.get(r.tin.date(), 0) >= 0 for r in c.itertuples()]); c.loc[cont, "net_today"] *= 2.0
    base = pd.concat(list(T.values()), ignore_index=True); base["n_contracts"] = 1.0
    ci = base.index[base.sleeve.str.contains("CRABEL")]; base.loc[ci[cont], "n_contracts"] = 2.0
    mn = bars_for(dict(instrument="MNQ", bar_minutes=1))[0]; ms = bars_for(dict(instrument="MES", bar_minutes=1))[0]
    ov = list(ep.run_routed(ep.CANDIDATES["overnight_dip_v2"], {"MNQ@1": mn, "MES@1": ms}, START).values())[0]["trades"]
    ts = pd.to_datetime(mn.timestamp_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy(); O, L = mn.open.to_numpy(float), mn.low.to_numpy(float)
    rows = []
    for t in ov:                                       # payout_10 nights(0.0055), unchanged
        e_raw = float(t["entry_price"]) - pl.ADV; x_raw = float(t["exit_price"]) + pl.ADV
        tin, tout = pd.Timestamp(t["entry_ts"]), pd.Timestamp(t["exit_ts"]); stop = e_raw * (1 - 0.0055)
        i0, i1 = int(np.searchsorted(ts, tin.value)), int(np.searchsorted(ts, tout.value)); hit = np.nonzero(L[i0:i1] <= stop)[0]
        if len(hit): j = i0 + int(hit[0]); x_raw = min(stop, O[j]) if j > i0 else stop
        lowest = x_raw if len(hit) else (L[i0:i1].min() if i1 > i0 else e_raw); pm = (((x_raw - e_raw) / e_raw) * pl.TODAY["MNQ"] - 2 * pl.ADV) * pl.MULT["MNQ"] - pl.FEE
        rows.append(dict(tin=tin.tz_convert(pl.NY), tout=tout.tz_convert(pl.NY), net_today=pm,
                         mae_per_micro=min(pm, (min(0.0, (lowest - e_raw) / e_raw) * pl.TODAY["MNQ"] - pl.ADV) * pl.MULT["MNQ"])))
    nights = pd.DataFrame(rows)
    lo = pd.Timestamp(cfg["lo"], tz=pl.NY)
    base = base[base.tin >= lo]; nights = nights[nights.tin >= lo] if len(nights) else nights
    return base, nights, mn.timestamp_utc.max(), bars_for


def series(base, nights, NIGHT_RISK, kind="S0"):
    from payout_17_bond_filter_train import fast_day_series
    e = base.copy()
    if kind == "S1": e["net_today"] -= 1.0 * e.inst.map(pl.MULT) * e.n_contracts
    n = nights[["tin", "tout", "net_today"]].copy()
    if kind == "S1" and len(n): n["net_today"] -= 1.0 * pl.MULT["MNQ"]
    e = e[e.risk_today <= 300.0]; SER = {}
    for m in (1, 2):
        em = e[e.risk_today * e.n_contracts * m <= (900.0 if m > 1 else 1e9)]
        i = pl.route(em)[["tin", "tout", "net_today"]].assign(net_today=lambda x: x.net_today * m)
        nm = n.assign(net_today=n.net_today * m) if (m == 1 or NIGHT_RISK * m <= 900.0) else n.iloc[0:0]
        stop = 400.0 if m == 1 else min(400.0 * m, 700.0)
        SER[(m, False)] = fast_day_series(i, stop).to_dict()
        SER[(m, True)] = fast_day_series(pd.concat([i, nm], ignore_index=True), stop).to_dict()
    return SER


def account(SER, K, M_MAX, start=None, months=None):
    days = sorted(set().union(*[set(s) for s in SER.values()]))
    if start is not None: days = [d for d in days if d >= start]
    if months is not None: days = [d for d in days if d < (pd.Timestamp(start) + pd.DateOffset(months=months)).date()]
    bal = 0.0; paid = False; since = 0.0; pays = []; closed = False; low = 0.0
    for x in days:
        m = min(M_MAX, 2 if bal >= 4000 else 1)
        p = max(SER[(m, bal >= 500.0)].get(x, 0.0), -1000.0); bal += p; since += p; low = min(low, bal)
        if bal <= (0.0 if paid else -2000.0): closed = True; break
        if (since > 0 or not paid) and bal - K >= 250.0:
            w = min(1500.0, bal - K); bal -= w; pays.append(w); paid = True; since = 0.0
    return dict(payouts=len(pays), withdrawn=round(float(sum(pays)), 0), end_balance=round(bal, 0), closed=closed, lowest_balance=round(low, 0),
                first_payout_day=None if not pays else "see log", days=len(days))


def book_stats(SER):
    d = pd.Series(SER[(1, True)]).sort_index(); yrs = max(len(d) / 252 * (252 / max(1, len(d))) , 1e-9)
    eq = d.cumsum(); by_year = d.groupby(pd.to_datetime(pd.Series(d.index).astype(str)).dt.year.to_numpy()).sum()
    return dict(trade_days=int(len(d)), net=round(float(d.sum()), 0), days_ge150=int((d >= 150).sum()), worst_day=round(float(d.min()), 0),
                max_drawdown=round(float((eq.cummax() - eq).max()), 0), net_by_year={int(k): round(float(v), 0) for k, v in by_year.items()})


def main():
    out = {"freeze": "reports/HOLDOUT_PAYOUT24_FREEZE.json"}
    NIGHT_RISK = None
    for name in ("validation", "test"):
        base, nights, last_bar, _bf = build(name)
        if NIGHT_RISK is None:
            from payout_17_bond_filter_train import stop_loss_level
            NIGHT_RISK = abs(stop_loss_level)              # same per-micro overnight risk figure as training (payout_24)
        SER = series(base, nights, NIGHT_RISK); SER1 = series(base, nights, NIGHT_RISK, "S1")
        trades = pl.route(base[base.risk_today <= 300.0]); n = trades.net_today.to_numpy()
        o = out[name] = dict(last_bar_utc=str(last_bar), intraday_trades=int(len(trades)), overnight_nights=int(len(nights)),
                             intraday_net=round(float(n.sum()), 0), intraday_pf=round(float(n[n > 0].sum() / -n[n < 0].sum()), 3),
                             overnight_net=round(float(nights.net_today.sum()), 0) if len(nights) else 0.0, book_1x=book_stats(SER))
        first = min(set().union(*[set(s) for s in SER.values()]))
        o["account_adopted_single_path"] = account(SER, 6000.0, 2, start=first)
        o["account_reference_1x_keep4000_single_path"] = account(SER, 4000.0, 1, start=first)
        o["account_adopted_costs_plus_1pt"] = account(SER1, 6000.0, 2, start=first)
        if name == "validation":
            o["rolling_12m_adopted"] = [dict(start=str(s0.date()), **account(SER, 6000.0, 2, start=s0.date(), months=12))
                                        for s0 in pd.date_range("2024-01-01", "2025-01-01", freq="MS")]
        print(name, json.dumps({k: v for k, v in o.items() if k != "rolling_12m_adopted"}, default=str), flush=True)
    v, t = out["validation"], out["test"]
    gate = dict(G1_book_net_positive=bool(v["book_1x"]["net"] > 0 and t["book_1x"]["net"] > 0),
                G2_not_closed=bool(not v["account_adopted_single_path"]["closed"] and not t["account_adopted_single_path"]["closed"]),
                G3_validation_payouts_ge_8=bool(v["account_adopted_single_path"]["payouts"] >= 8),
                G4_test_made_2000=bool(t["account_adopted_single_path"]["end_balance"] + t["account_adopted_single_path"]["withdrawn"] >= 2000))
    out["gate"] = gate; out["did_good"] = all(gate.values())
    r = out["validation"]["rolling_12m_adopted"]
    out["validation"]["rolling_12m_summary"] = dict(starts=len(r), closed=sum(x["closed"] for x in r), payouts_mean=round(float(np.mean([x["payouts"] for x in r])), 2),
                                                    withdrawn_mean=round(float(np.mean([x["withdrawn"] for x in r])), 0))
    print("rolling 12m (validation):", out["validation"]["rolling_12m_summary"]); print("gate:", gate, "did_good:", out["did_good"])
    (ROOT / "reports/HOLDOUT_PAYOUT24_RESULTS.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
