"""ONE-SHOT holdout comparison (Nick: "do it", 2026-11-11): the evaluation plan with the posthoc router (INC) vs causal one-position routing
(STRICT_CAUSAL), both with DEF_END sizing and the corrected v2 day semantics, on validation (2024-25) and test (2026).

Secondary evidence: 2024-26 was already read for this book family on 2026-11-10 (holdout_payout24 / holdout_eval1), so it is not a clean
holdout - but this comparison has never been run on it. Frozen in reports/HOLDOUT_EVAL36_FREEZE.json BEFORE any 2024-26 data is loaded;
the script refuses to run if a frozen file changed. Strategy code = training code; only the data source differs.
Books: v5.3 (Crabel 15 D with gap-continuation at 2 micros, TRD60 D, MES TRD30 D; VIX day filter on Crabel / TRD60 as in training) +
portfolio_e MNQ_BRK_E_2c and MES_MOM_3c (1 micro base, priority 10 / 11) + the 0.55%-stop overnight leg; trades with stop risk > $300 per
micro skipped; costs and prices exactly as payout_lib (today's prices). Rules: $4,000 target, static -$2,000 floor on 1-minute MAE, DLL
$1,000, 55% consistency, 90 calendar days, every weekday start with 90 days of data after it, eval_harness.sim_day_v2 + _evaluate.
PRE-DECLARED READING (frozen): the switch to STRICT_CAUSAL (decided on training, eval_36) stands unless STRICT_CAUSAL passes > 2.0 points
LESS than INC in BOTH splits; then the real-Combine plan reverts to INC until forward paper decides. Reported as is; nothing is changed after.
"""
import hashlib, json, os, sys
from pathlib import Path
os.environ["TRAIN_MINI_UNTIL"] = "2019-05-06"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
FZ = json.loads((ROOT / "reports/HOLDOUT_EVAL36_FREEZE.json").read_text())
for f, h in FZ["sha256"].items():
    assert hashlib.sha256((ROOT / f).read_bytes()).hexdigest() == h, f"frozen file changed: {f}"

import numpy as np, pandas as pd
import payout_lib as pl
import mass_1m_search as m1
import eval_harness as eh
from payout_17_bond_filter_train import stop_loss_level
ep, _bt, _st, _gs = pl.engine()
NIGHT_RISK = abs(float(stop_loss_level))
SPLITS = {"validation": dict(split="validation", lo="2024-01-01", hi="2026-01-01", warm_split="train", warm="2023-10-01"),
          "test": dict(split="test", lo="2026-01-01", hi="2027-01-01", warm_split="validation", warm="2025-10-01")}
COLS = ["tin", "tout", "per_micro", "mae_per_micro", "n_contracts", "risk_today"]


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
         "MES30": (dict(ep._AG_MES_TRD30_D, name="AG_MES_TRD30_D_1c"), False)}
    T = {k: pl.price_normalize(sleeve_trades(bars_for, START, sl, i, flt)) for i, (k, (sl, flt)) in enumerate(S.items())}
    gs = ep.gap_sign_by_day(bars_for(S["CRABEL"][0])[0])
    c = T["CRABEL"]; cont = np.array([int(r.side) * gs.get(r.tin.date(), 0) >= 0 for r in c.itertuples()]); c.loc[cont, "net_today"] *= 2.0
    for k in T: T[k]["n_contracts"] = 1.0
    T["CRABEL"].loc[cont, "n_contracts"] = 2.0
    X = []
    for prio, nm in enumerate(("MNQ_BRK_E_2c", "MES_MOM_3c"), start=10):
        sl = next(s for s in ep.CANDIDATES["portfolio_e"]["sleeves"] if s["name"] == nm)
        x = pl.price_normalize(sleeve_trades(bars_for, START, dict(sl), prio, False)); x["n_contracts"] = 1.0; X.append(x)
    pre = pd.concat(list(T.values()) + X, ignore_index=True)
    B = {}
    for inst in ("MNQ", "MES"):
        b = bars_for(dict(instrument=inst, bar_minutes=1))[0]
        B[inst] = (pd.to_datetime(b.timestamp_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy(), b.high.to_numpy(float), b.low.to_numpy(float))
    def mae_pct(inst, tin, tout, side, entry):
        ts, Hh, L = B[inst]; i0, i1 = int(np.searchsorted(ts, tin.value)), int(np.searchsorted(ts, tout.value))
        if i1 <= i0: return 0.0
        w = L[i0:i1].min() if side > 0 else Hh[i0:i1].max(); return min(0.0, side * (w - entry) / entry)
    pre["mae_per_micro"] = [(mae_pct(r.inst, r.tin, r.tout, r.side, r.entry) * pl.TODAY[r.inst] - pl.ADV) * pl.MULT[r.inst] for r in pre.itertuples()]
    mn = bars_for(dict(instrument="MNQ", bar_minutes=1))[0]; ms = bars_for(dict(instrument="MES", bar_minutes=1))[0]
    ov = list(ep.run_routed(ep.CANDIDATES["overnight_dip_v2"], {"MNQ@1": mn, "MES@1": ms}, START).values())[0]["trades"]
    ts = pd.to_datetime(mn.timestamp_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy(); O, L = mn.open.to_numpy(float), mn.low.to_numpy(float)
    rows = []
    for t in ov:                                       # payout_10 nights(0.0055), as holdout_payout24
        e_raw = float(t["entry_price"]) - pl.ADV; x_raw = float(t["exit_price"]) + pl.ADV
        tin, tout = pd.Timestamp(t["entry_ts"]), pd.Timestamp(t["exit_ts"]); stop = e_raw * (1 - 0.0055)
        i0, i1 = int(np.searchsorted(ts, tin.value)), int(np.searchsorted(ts, tout.value)); hit = np.nonzero(L[i0:i1] <= stop)[0]
        if len(hit): j = i0 + int(hit[0]); x_raw = min(stop, O[j]) if j > i0 else stop
        lowest = x_raw if len(hit) else (L[i0:i1].min() if i1 > i0 else e_raw); pm = (((x_raw - e_raw) / e_raw) * pl.TODAY["MNQ"] - 2 * pl.ADV) * pl.MULT["MNQ"] - pl.FEE
        rows.append(dict(tin=tin.tz_convert(pl.NY), tout=tout.tz_convert(pl.NY), per_micro=pm, n_contracts=1.0, risk_today=NIGHT_RISK,
                         mae_per_micro=min(pm, (min(0.0, (lowest - e_raw) / e_raw) * pl.TODAY["MNQ"] - pl.ADV) * pl.MULT["MNQ"])))
    nights = pd.DataFrame(rows)
    lo = pd.Timestamp(cfg["lo"], tz=pl.NY)
    pre = pre[pre.tin >= lo]; nights = nights[nights.tin >= lo] if len(nights) else nights
    sess = sorted(d for d in set(pd.to_datetime(mn.timestamp_utc, utc=True).dt.tz_convert(pl.NY).dt.date)
                  if pd.Timestamp(d).dayofweek < 5 and d >= lo.date())
    return pre, nights, pd.Timestamp(mn.timestamp_utc.max()).tz_convert(pl.NY).date(), sess


def DEF_END(bal, day, tgt, sleft):
    if day >= 60 and bal < tgt - 1000.0 and bal > -500.0: return 5
    return 1 if bal <= -1000.0 else (2 if bal <= -500.0 else 3)


def score(book, starts):
    f = book[COLS].assign(noise=False).sort_values(["tin", "tout", "per_micro"], kind="stable").reset_index(drop=True)
    PD = eh.Harness._per_day(f); td = sorted(PD); tix = pd.to_datetime(pd.Series(td).astype(str)).to_numpy()
    DAY = {k: {d: eh.Harness.sim_day_v2(PD[d], float(k)) for d in td} for k in (1, 2, 3, 5)}
    return eh.Harness._evaluate(None, DAY, starts, td, tix, DEF_END)


out = {}
for name in ("validation", "test"):
    pre, nights, last, sess = build(name)
    starts = [s for s in sess if (pd.Timestamp(s) + pd.Timedelta(days=90)).date() <= last]
    p = pre[pre.risk_today <= 300.0]
    books = {"INC": pl.route(p).copy(), "STRICT_CAUSAL": eh.Harness.route_strict_causal(p).copy()}
    res = dict(starts=len(starts), first=str(starts[0]) if starts else None, last=str(starts[-1]) if starts else None, sleeve_trades=p.sleeve.value_counts().to_dict())
    for nm, r in books.items():
        r["per_micro"] = r.net_today / r.n_contracts
        bk = pd.concat([r[COLS], nights[COLS]], ignore_index=True)
        res[nm] = score(bk, starts); res[nm]["trades"] = int(len(r))
    res["strict_minus_inc"] = round(res["STRICT_CAUSAL"]["pass_"] - res["INC"]["pass_"], 1)
    out[name] = res; print(name, res, flush=True)
worse = all(out[s]["strict_minus_inc"] < -2.0 for s in out)
out["reading"] = "REVERT to INC until forward paper decides" if worse else "STRICT_CAUSAL switch stands"
print("reading", out["reading"], flush=True)
(ROOT / "reports/HOLDOUT_EVAL36_RESULTS.json").write_text(json.dumps(out, indent=1, default=str))
