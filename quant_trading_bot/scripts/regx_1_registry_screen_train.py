"""regx_1 (fork D of Claude's overnight run, 2026-11-11): every registry sleeve through the eval_harness daily-Sharpe screen. TRAINING only.

Why: earlier sleeve searches for the evaluation (eval_5 D, eval_7 B greedy) judged pass rate on a few hand-picked sleeves; none measured
each registry sleeve's lift on the eval_8 book's DAILY Sharpe (the gate learned in eval_13: a stream helps only if it raises it).

PRE-DECLARED (written before any result).
Universe: every sleeve in quant_futures.ensemble_paper.CANDIDATES plus the `_AG_*` dicts on `ep`.
  Day filter: a sleeve's "normal" filter = its candidate has day_filter == "no_backwardation" and the sleeve is not day_filter_exempt.
  The `_AG_*` dicts (no candidate context) are run both with and without the VIX stand-aside (labels _F / _NF).
  De-duplication: signature = all sleeve keys except name / size / account-gate keys (max_contracts, risk_per_trade, max_open_risk,
  hard_drawdown, funded_drawdown, daily_loss, day_filter_exempt) + the filter flag; then a second pass drops ledgers identical in
  (entry time, side). Excluded as already in the book: AG_CRABEL15_D (filtered), AG_TRD60_D (filtered), AG_MES_TRD30_D (unfiltered),
  MNQ_BRK_E (unfiltered), MES_MOM (unfiltered), and the overnight_dip_v2 / _stop055 night leg.
  Overnight candidates (overnight_dip, overnight_dip_mes, the v2 bond / vix / skew / 09:15 variants) run through ep.run_routed on 1-min
  bars and are priced like the book's night leg (raw fill +/- 0.5 pt, today's price, $1 fee). A candidate that errors is skipped and logged.
Ledgers: 1 contract, pl.sleeve_trades -> pl.price_normalize -> mae_per_micro by the v53 mae_pct convention (1-min bars), risk_today from
  the engine stop formula. Saved under reports/regx_ledgers/.
Screen: eval_harness.screen(daily per-micro P&L by exit date, America/New_York). Rank by lift; report the top 10 with sr, rho, lift and
  the per-half lift. Multiplicity check for the top 3: weight and lift chosen on 2010-16 days only, then the lift at that weight on
  2017-23 must be > 0; and vice versa.
Pass-rate stage (separate script regx_2, only if needed): sleeves with screen_pass True AND a positive per-half lift go to
  Harness().pass_rate(extra=ledger, nsize in {F1, K}) under the 2-fold protocol; adopt only if both out-of-fold halves >= 55.5 / 66.6.
"""
import json, sys, hashlib
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import payout_lib as pl
import eval_harness as eh

NY = "America/New_York"; OUTD = ROOT / "reports/regx_ledgers"; OUTD.mkdir(exist_ok=True)
DROP = {"name", "max_contracts", "risk_per_trade", "max_open_risk", "hard_drawdown", "funded_drawdown", "daily_loss", "day_filter_exempt"}
ep, bars_for, START, gs = pl.engine()
m1 = bars_for(dict(instrument="MNQ", bar_minutes=1))[0]; mes1 = bars_for(dict(instrument="MES", bar_minutes=1))[0]
BARS = {k: (pd.to_datetime(b.timestamp_utc, utc=True).dt.as_unit("ns").astype("int64").to_numpy(), b.high.to_numpy(float), b.low.to_numpy(float),
            b.open.to_numpy(float)) for k, b in (("MNQ", m1), ("MES", mes1))}
assert max(BARS["MNQ"][0][-1], BARS["MES"][0][-1]) < pd.Timestamp("2024-01-01", tz="UTC").value


def mae_pct(inst, tin, tout, side, entry):
    ts, Hh, L, _ = BARS[inst]; i0, i1 = int(np.searchsorted(ts, tin.value)), int(np.searchsorted(ts, tout.value))
    if i1 <= i0: return 0.0
    w = L[i0:i1].min() if side > 0 else Hh[i0:i1].max(); return min(0.0, side * (w - entry) / entry)


def sig(sl, flag):
    return hashlib.md5(json.dumps({k: v for k, v in sorted(sl.items()) if k not in DROP} | {"_flag": bool(flag)}, sort_keys=True, default=str).encode()).hexdigest()[:10]


BOOK_SIGS = {sig(ep._AG_CRABEL15_D, True), sig(ep._AG_TRD60_D, True), sig(ep._AG_MES_TRD30_D, False)}
for cand in ("portfolio_e",):
    for s in ep.CANDIDATES[cand]["sleeves"]: BOOK_SIGS.add(sig(s, False))
BOOK_NIGHT = {"overnight_dip_v2", "overnight_dip_v2_stop055"}

todo = {}; log = []
for ck, spec in ep.CANDIDATES.items():
    if spec.get("overnight"): continue
    filt = spec.get("day_filter") == "no_backwardation"
    for s in spec.get("sleeves", []):
        if s.get("bar_minutes") == 1 or "OVN" in s["name"]: continue
        f = filt and not s.get("day_filter_exempt"); g = sig(s, f)
        if g in BOOK_SIGS: log.append(f"in book: {ck}/{s['name']} flag={f}"); continue
        todo.setdefault(g, (f"{s['name']}{'_F' if f else '_NF'}", dict(s), f, ck))
for a in [x for x in dir(ep) if x.startswith("_AG_")]:
    for f in (False, True):
        s = dict(getattr(ep, a), name=a.strip("_") + "_1c"); g = sig(s, f)
        if g in BOOK_SIGS: log.append(f"in book: {a} flag={f}"); continue
        todo.setdefault(g, (f"{a.strip('_')}{'_F' if f else '_NF'}", s, f, "ep." + a))
print("unique intraday sleeves to run:", len(todo), flush=True)

LED = {}; seen = {}
for g, (lab, s, f, src) in todo.items():
    try:
        x = pl.price_normalize(pl.sleeve_trades(ep, bars_for, START, s, 20, f))
    except Exception as e:  # noqa: BLE001
        log.append(f"error {lab} ({src}): {type(e).__name__}: {e}"); print("error", lab, e, flush=True); continue
    if len(x) == 0: log.append(f"no trades {lab}"); continue
    key = hashlib.md5(("|".join(f"{a.value}:{b}" for a, b in zip(x.tin, x.side))).encode()).hexdigest()
    if key in seen: log.append(f"duplicate ledger {lab} = {seen[key]}"); continue
    seen[key] = lab
    x["mae_per_micro"] = [(mae_pct(r.inst, r.tin, r.tout, r.side, r.entry) * pl.TODAY[r.inst] - pl.ADV) * pl.MULT[r.inst] for r in x.itertuples()]
    x["per_micro"] = x.net_today; x["n_contracts"] = 1.0; x["source"] = src
    LED[lab] = x; print("ran", lab, len(x), round(float(x.per_micro.sum()), 0), flush=True)

# overnight candidates
for ck, spec in ep.CANDIDATES.items():
    if not spec.get("overnight") or ck in BOOK_NIGHT: continue
    try:
        res = ep.run_routed(spec, {"MNQ@1": m1, "MES@1": mes1}, START)
    except Exception as e:  # noqa: BLE001
        log.append(f"error overnight {ck}: {type(e).__name__}: {e}"); print("error", ck, e, flush=True); continue
    rows = []
    for nm, rr in res.items():
        inst = "MES" if "MES" in nm else "MNQ"
        for t in rr["trades"]:
            side = int(t.get("side", 1)); e_raw = float(t["entry_price"]) - side * pl.ADV; x_raw = float(t["exit_price"]) + side * pl.ADV
            tin, tout = pd.Timestamp(t["entry_ts"]), pd.Timestamp(t["exit_ts"])
            if tout >= pd.Timestamp("2024-01-01", tz="UTC"): continue
            pct = side * (x_raw - e_raw) / e_raw; pm = (pct * pl.TODAY[inst] - 2 * pl.ADV) * pl.MULT[inst] - pl.FEE
            mp = mae_pct(inst, tin, tout, side, e_raw)
            sp = float(spec.get("stop_pct", 0.0055))
            rows.append(dict(tin=tin.tz_convert(NY), tout=tout.tz_convert(NY), side=side, inst=inst, per_micro=pm, net_today=pm,
                             mae_per_micro=min(pm, (mp * pl.TODAY[inst] - pl.ADV) * pl.MULT[inst]),
                             risk_today=sp * pl.TODAY[inst] * pl.MULT[inst] + 1.0 + 0.75 * pl.MULT[inst], n_contracts=1.0, source=ck))
    if not rows: log.append(f"no trades overnight {ck}"); continue
    x = pd.DataFrame(rows); lab = f"OVN:{ck}"
    key = hashlib.md5(("|".join(f"{a.value}:{b}" for a, b in zip(x.tin, x.side))).encode()).hexdigest()
    if key in seen: log.append(f"duplicate ledger {lab} = {seen[key]}"); continue
    seen[key] = lab; LED[lab] = x; print("ran", lab, len(x), round(float(x.per_micro.sum()), 0), flush=True)

# ---------------- screen
b = pd.read_csv(eh.DAILY, parse_dates=["day"]); b["day"] = b.day.dt.date; book = b.set_index("day").k3
H1 = np.array([d < eh.H1_END for d in book.index])


def half_pick(n):
    """weight chosen on one half's days, lift evaluated on the other half."""
    o = {}
    for fit, test, nm in ((H1, ~H1, "pick_h1_test_h2"), (~H1, H1, "pick_h2_test_h1")):
        bf, nf, bt, nt = book[fit], n[fit], book[test], n[test]
        w = max(eh.WEIGHTS, key=lambda w: eh._sr(bf + w * nf))
        o[nm] = dict(w=w, lift_fit=round(eh._sr(bf + w * nf) - eh._sr(bf), 4), lift_test=round(eh._sr(bt + w * nt) - eh._sr(bt), 4))
    return o


rows = []
for lab, x in LED.items():
    x.to_csv(OUTD / f"{lab.replace(':', '_')}.csv", index=False)
    daily = x.per_micro.groupby(x.tout.dt.tz_convert(NY).dt.date).sum()
    s = eh.screen(daily, lab); n = pd.Series(daily); n.index = [pd.Timestamp(i).date() for i in n.index]
    n = n.groupby(level=0).sum().reindex(book.index, fill_value=0.0)
    s["two_fold"] = half_pick(n); s["trades"] = len(x); s["net_per_micro"] = round(float(x.per_micro.sum()), 0); s["source"] = x.source.iloc[0]
    rows.append(s)
rows.sort(key=lambda r: r["lift"], reverse=True)
out = dict(n_screened=len(rows), log=log, ranking=rows,
           to_pass_rate=[r["name"] for r in rows if r["screen_pass"] and all(r["halves"][h]["lift_at_best_w"] > 0 for h in ("h1", "h2"))])
for r in rows[:10]:
    print(f"{r['name']:<34} n={r['trades']:>5} net={r['net_per_micro']:>8} sr={r['sr']:.4f} rho={r['rho']:+.3f} lift={r['lift']:+.4f} "
          f"h1={r['halves']['h1']['lift_at_best_w']:+.4f} h2={r['halves']['h2']['lift_at_best_w']:+.4f} w={r['best_w']} pass={r['screen_pass']} "
          f"2fold={r['two_fold']['pick_h1_test_h2']['lift_test']:+.4f}/{r['two_fold']['pick_h2_test_h1']['lift_test']:+.4f}", flush=True)
print("to pass-rate:", out["to_pass_rate"], flush=True)
(ROOT / "reports/REGX_1_REGISTRY_SCREEN_TRAINING.json").write_text(json.dumps(out, indent=1, default=str))
