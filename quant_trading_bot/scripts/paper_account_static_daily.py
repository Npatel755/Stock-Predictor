"""Paper account replay for Topstep Labs' $50K Static Daily Payouts+ account (Claude, 2026-11-10). Read-only on the paper ledgers.

Replays the forward paper trades of the v5.3 payout build (ag_arch_d_plus_v2_price_aware_v53; v5.2 until 2026-11-10) and the overnight leg (overnight_dip_v2_stop055)
through two tracks, from the paper start, and writes <root>/_account_static_daily/status.json (plus an "account_static_daily" entry in
<root>/dashboard.json). Notifies (ntfy, same channel as the runner) on a new payout, a size-stage change, or an evaluation pass / fail.
  FUNDED (payout_24, adopted; holdout-checked in reports/HOLDOUT_PAYOUT24_RESULTS.json): balance from $0; floor -$2,000 static until the
    first payout, then $0; DLL $1,000; 1x below a $4,000 balance at the prior close, 2x from $4,000 (account stop $700; since 2026-11-10 a trade
    is TRIMMED to floor($900 / stop risk per micro) micros instead of skipped when 2x would risk more than $900, v55 cell 4); overnight leg only while the balance >= $500; daily payout of profit above $6,000 when >= $250, max $1,500,
    net profit since the last payout > 0.
  EVALUATION (eval_1, k = 3; holdout-checked in reports/HOLDOUT_EVAL1_RESULTS.json): size min(3 x base, floor($900 / stop risk per micro)),
    overnight min(3, floor($900 / risk)); account stop $700; target $4,000 with the 55% consistency rule; floor -$2,000; DLL $1,000; 90 days.
Known gaps vs research: trades are routed at 1x before sizing (v55 measured the rules this way); the floor is checked on realised day P&L
(the runner's own intrabar drawdown is reported beside it). Paper only; nothing is routed anywhere.
"""
import argparse, json, sys
from pathlib import Path
import numpy as np, pandas as pd

NY = "America/New_York"
MULT = {"MNQ": 2.0, "MES": 5.0}
V52, NIGHT = "ag_arch_d_plus_v2_price_aware_v53", "overnight_dip_v2_stop055"   # v5.3 since 2026-11-10 (v53 cell A: v5.2 minus TRD30PM)
NIGHT_0915 = "overnight_dip_v2_stop055_0915"   # Aegis comparison leg: same overnight dip, exit 09:15 ET
BOOK = "D+ v5.3 payout build (v5.2 without the afternoon trend) + overnight leg; 2x size trimmed to $900 risk"


def read_trades(path):
    rows = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()] if Path(path).exists() else []
    return [r for r in rows if r.get("kind") == "trade"]


def atr_lookup(bars_1m, minutes):
    b = bars_1m.set_index("ts").sort_index()
    g = b.resample(f"{minutes}min", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    prev = g.close.shift(1)
    tr = pd.concat([g.high - g.low, (g.high - prev).abs(), (g.low - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(14, min_periods=14).mean()


def stop_risk_per_micro(trades, specs, bars):
    """Engine stop-risk formula (payout_lib.price_normalize, at actual prices): stop_atr x ATR(decision bar) x multiplier + $1 + 0.75 x multiplier."""
    cache = {}
    for t in trades:
        sp = specs.get(t["sleeve"])
        if sp is None: t["risk"] = None; continue
        inst, mins = sp["instrument"], int(sp.get("bar_minutes", 15))
        if (inst, mins) not in cache: cache[(inst, mins)] = atr_lookup(bars[inst], mins)
        dec = pd.Timestamp(t["entry_ts"]) - pd.Timedelta(minutes=mins)
        a = cache[(inst, mins)].get(dec, np.nan)
        t["risk"] = float(sp["stop_atr"]) * float(a) * MULT[inst] + 1.0 + 0.75 * MULT[inst] if np.isfinite(a) else None
        t["inst"] = inst
    return trades


def group_intraday(trades):
    """Crabel base + gap-addon records of the same trade become one position with n_base = 2 (research: 2 micros on continuation)."""
    out = {}
    for t in trades:
        key = (t["entry_ts"], t["exit_ts"], t["side"], "CRABEL" in t["sleeve"])
        if key[3] and key in out:
            out[key]["n_base"] += 1; out[key]["net_total"] += t["net"]; continue
        out[key if key[3] else (t["entry_ts"], t["exit_ts"], t["side"], t["sleeve"])] = dict(t, n_base=1, net_total=t["net"])
    rows = []
    for v in out.values():
        rows.append(dict(tin=pd.Timestamp(v["entry_ts"]).tz_convert(NY), tout=pd.Timestamp(v["exit_ts"]).tz_convert(NY), n_base=v["n_base"],
                         per_micro=v["net_total"] / (v["n_base"] * max(1, v.get("qty", 1))), risk=v.get("risk"), night=False, sleeve=v["sleeve"]))
    return rows


def night_rows(trades):
    rows = []
    for t in trades:
        e = float(t["entry_price"])
        rows.append(dict(tin=pd.Timestamp(t["entry_ts"]).tz_convert(NY), tout=pd.Timestamp(t["exit_ts"]).tz_convert(NY), n_base=1,
                         per_micro=t["net"] / max(1, t.get("qty", 1)), risk=0.0055 * e * MULT["MNQ"] + 1.0 + 0.75 * MULT["MNQ"], night=True, sleeve=t["sleeve"]))
    return rows


def day_pnl(rows, size_of, stop, night_on):
    """One day's realised P&L: entries in time order, no new entry once realised same-day P&L <= -stop; DLL caps the day at -$1,000."""
    real = 0.0; taken = []
    for r in sorted(rows, key=lambda r: r["tin"]):
        if r["night"] and not night_on: continue
        q = size_of(r)
        if q < 1: continue
        if sum(x["net"] for x in taken if x["tout"] <= r["tin"]) <= -stop: continue
        taken.append(dict(tout=r["tout"], net=r["per_micro"] * q))
    return max(sum(x["net"] for x in taken), -1000.0), len(taken)


MAIN_LADDER, MAIN_K = ((0.0, 1), (4000.0, 2)), 6000.0
AEGIS_LADDER, AEGIS_K = ((0.0, 1), (2500.0, 2), (4500.0, 3), (6500.0, 4)), 7500.0   # Antigravity's "Aegis Apex 4X" (comparison only)


def by_day(rows, start_date):
    days = {}
    for r in rows: days.setdefault(r["tout"].date(), []).append(r)
    return days, sorted(d for d in days if d >= start_date)


def funded(rows, start_date, ladder=MAIN_LADDER, K=MAIN_K):
    """Static Daily Payouts+ funded account: size from the ladder (balance at the prior close), cap-aware trimming to $900 risk per trade,
    $400 account stop at 1x / $700 above, overnight only while balance >= $500, daily payouts above K ($250-$1,500)."""
    days, order = by_day(rows, start_date)
    bal = 0.0; paid = False; since = 0.0; pays = []; closed = None; stage_log = []; stage = 1; hist = []
    for d in order:
        m = max((mm for th, mm in ladder if bal >= th), default=ladder[0][1])
        if m != stage: stage_log.append(dict(date=str(d), stage=f"{m}x")); stage = m
        def size(r, m=m):
            if m == 1: return r["n_base"]
            if r["risk"] is None: return r["n_base"]                      # unknown stop risk: stay at 1x
            return int(min(m * r["n_base"], np.floor(900.0 / r["risk"])))  # trim to the $900 cap instead of skipping
        p, n = day_pnl(days[d], size, 400.0 if m == 1 else 700.0, bal >= 500.0)
        bal += p; since += p
        if bal <= (0.0 if paid else -2000.0): closed = str(d); hist.append(dict(date=str(d), pnl=round(p, 2), balance=round(bal, 2))); break
        w = 0.0
        if (since > 0 or not paid) and bal - K >= 250.0:
            w = min(1500.0, bal - K); bal -= w; paid = True; since = 0.0; pays.append(dict(date=str(d), amount=round(w, 2)))
        hist.append(dict(date=str(d), pnl=round(p, 2), balance=round(bal, 2), payout=round(w, 2), size=f"{m}x", trades=n))
    return dict(balance=round(bal, 2), floor=0.0 if paid else -2000.0, size_stage=f"{stage}x", payouts=pays, payouts_count=len(pays),
                withdrawn=round(sum(x["amount"] for x in pays), 2), closed_on=closed, stage_changes=stage_log, days=hist[-30:],
                next_payout_needs=None if closed else round(max(0.0, K + 250.0 - bal), 2), keep=K,
                ladder=" / ".join(f"{mm}x from ${th:,.0f}" if th else f"{mm}x" for th, mm in ladder))


def replay(rows, start_date, today=None):
    days, order = by_day(rows, start_date)
    funded_main = funded(rows, start_date)
    # EVALUATION track (k = 3)
    def esize(r):
        if r["risk"] is None: return 0
        return int(min(3 * r["n_base"], np.floor(900.0 / r["risk"]))) if not r["night"] else int(min(3, np.floor(900.0 / r["risk"])))
    bal = 0.0; best = 0.0; status = "open"; when = None; end = start_date + pd.Timedelta(days=90).to_pytimedelta()
    for d in order:
        if d >= end: status = "expired"; break
        p, _ = day_pnl(days[d], esize, 700.0, True); bal += p; best = max(best, p)
        if bal <= -2000.0: status = "failed"; when = str(d); break
        if bal >= max(4000.0, best / 0.55): status = "passed"; when = str(d); break
    if status == "open" and (today or pd.Timestamp.now(tz=NY).date()) >= end: status = "expired"
    evaluation = dict(status=status, on=when, balance=round(bal, 2), target=round(max(4000.0, best / 0.55), 2), best_day=round(best, 2),
                      days_left=max(0, (end - (today or pd.Timestamp.now(tz=NY).date())).days), expires=str(end))
    return dict(funded=funded_main, evaluation=evaluation)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); ap.add_argument("--root", required=True); a = ap.parse_args(argv)
    root = Path(a.root); here = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(here / "src"))
    from quant_futures import ensemble_paper as ep
    specs = {sl["name"]: sl for k in (V52, NIGHT) for sl in ep.CANDIDATES[k]["sleeves"]}
    bars = {}
    for inst in ("MNQ", "MES"):
        b = pd.read_csv(root / "bars" / f"{inst}_1m.csv")
        tcol = next(c for c in b.columns if "time" in c.lower() or c.lower() in ("ts", "timestamp"))
        bars[inst] = b.rename(columns={tcol: "ts"}).assign(ts=lambda x: pd.to_datetime(x.ts, utc=True))[["ts", "open", "high", "low", "close"]]
    v = stop_risk_per_micro(read_trades(root / V52 / "ledger.jsonl"), specs, bars)
    n = read_trades(root / NIGHT / "ledger.jsonl")
    start = pd.Timestamp((root / "start.txt").read_text().strip()).date() if (root / "start.txt").exists() else min(
        [pd.Timestamp(t["exit_ts"]).tz_convert(NY).date() for t in v + n], default=pd.Timestamp.now(tz=NY).date())
    res = replay(group_intraday(v) + night_rows(n), start)
    n915 = read_trades(root / NIGHT_0915 / "ledger.jsonl")
    res["aegis"] = dict(funded(group_intraday(v) + night_rows(n915), start, AEGIS_LADDER, AEGIS_K), overnight_exit="09:15 ET", overnight_trades=len(n915),
                        name="Aegis Apex 4X (Antigravity)", status="comparison only, not adopted",
                        caution="training: +45% dollars vs the main rule with the same end-of-day closures, but worst-case intraday closures in the cost+edge stress test 15.8% vs 5.0%; 09:15 exit not better in both halves (reports/V55_CHECK_AEGIS_TRAINING.json)")
    names = {f"AG_CRABEL15_D_1c_{v}": "Crabel 15-min opening-range breakout" for v in ("v52", "v53")}
    names.update({f"AG_CRABEL15_D_GAP_{v}": "Crabel gap-continuation add-on (+1 micro when the trade agrees with the opening gap)" for v in ("v52", "v53")})
    names.update({f"AG_TRD60_D_1c_{v}": "60-min trend" for v in ("v52", "v53")}); names.update({f"AG_MES_TRD30_D_1c_{v}": "30-min trend" for v in ("v52", "v53")})
    names.update({"AG_TRD30PM_1c_v52": "30-min afternoon trend",
             "OVN_DIP2_STOP_1c": "Overnight reopen dip, 0.55% stop (only once the balance is >= $500)"})
    res["strategies"] = [dict(sleeve=sl["name"], name=names.get(sl["name"], sl["name"]), instrument=sl["instrument"], bar_minutes=int(sl.get("bar_minutes", 15)),
                              trades=sum(1 for t in v + n if t["sleeve"] == sl["name"]), net_1x=round(sum(t["net"] for t in v + n if t["sleeve"] == sl["name"]), 2))
                         for sl in ep.CANDIDATES[V52]["sleeves"] + ep.CANDIDATES[NIGHT]["sleeves"]]
    st = json.loads((root / V52 / "status.json").read_text()) if (root / V52 / "status.json").exists() else {}
    res.update(updated=pd.Timestamp.now(tz="UTC").isoformat(), paper_start=str(start), source_ledgers=[V52, NIGHT], book=BOOK,
               runner_intrabar_drawdown_v52=st.get("intrabar_drawdown"), trades_without_risk=sum(1 for t in v if t.get("risk") is None),
               rules="see scripts/paper_account_static_daily.py docstring; paper only, simulated fills, no orders routed")
    out = root / "_account_static_daily"; out.mkdir(exist_ok=True); prev = {}
    if (out / "status.json").exists():
        try: prev = json.loads((out / "status.json").read_text())
        except Exception: prev = {}
    (out / "status.json").write_text(json.dumps(res, indent=1, default=str))
    dash = root / "dashboard.json"
    if dash.exists():
        d = json.loads(dash.read_text())
        d["account_static_daily"] = dict(funded_balance=res["funded"]["balance"], funded_payouts=res["funded"]["payouts_count"], funded_withdrawn=res["funded"]["withdrawn"],
                                         size_stage=res["funded"]["size_stage"], evaluation=res["evaluation"]["status"], evaluation_balance=res["evaluation"]["balance"],
                                         aegis_balance=res["aegis"]["balance"], aegis_payouts=res["aegis"]["payouts_count"], aegis_stage=res["aegis"]["size_stage"])
        dash.write_text(json.dumps(d, indent=1, sort_keys=True, default=str))
    pf, pe, pa = prev.get("funded", {}), prev.get("evaluation", {}), prev.get("aegis", {})
    if res["aegis"]["payouts_count"] > pa.get("payouts_count", 0):
        last = res["aegis"]["payouts"][-1]; ep.notify("Aegis paper: payout", f"${last['amount']:,.2f} on {last['date']}; balance ${res['aegis']['balance']:,.2f}")
    if res["aegis"]["closed_on"] and not pa.get("closed_on"):
        ep.notify("Aegis paper: CLOSED", f"floor reached on {res['aegis']['closed_on']}")
    if res["funded"]["payouts_count"] > pf.get("payouts_count", 0):
        last = res["funded"]["payouts"][-1]; ep.notify("Paper account: payout", f"${last['amount']:,.2f} on {last['date']}; balance ${res['funded']['balance']:,.2f}, {res['funded']['payouts_count']} payouts")
    if pf and res["funded"]["size_stage"] != pf.get("size_stage"):
        ep.notify("Paper account: size stage", f"now {res['funded']['size_stage']} at balance ${res['funded']['balance']:,.2f}")
    if res["funded"]["closed_on"] and not pf.get("closed_on"):
        ep.notify("Paper account: CLOSED", f"floor reached on {res['funded']['closed_on']}")
    if res["evaluation"]["status"] != pe.get("status", "open") and res["evaluation"]["status"] != "open":
        ep.notify(f"Paper evaluation: {res['evaluation']['status']}", f"balance ${res['evaluation']['balance']:,.2f} on {res['evaluation']['on']}")
    print(json.dumps({k: res[k] for k in ("funded", "evaluation")}, default=str)[:1500])


if __name__ == "__main__":
    main()
