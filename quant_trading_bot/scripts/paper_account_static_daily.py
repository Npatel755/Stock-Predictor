"""Paper account replay for Topstep Labs' $50K Static Daily Payouts+ account (Claude, 2026-11-10). Read-only on the paper ledgers.

Replays the forward paper trades of the v5.3 payout build (ag_arch_d_plus_v2_price_aware_v53; v5.2 until 2026-11-10) and the overnight leg (overnight_dip_v2_stop055)
through two tracks, from the paper start, and writes <root>/_account_static_daily/status.json (plus an "account_static_daily" entry in
<root>/dashboard.json). Notifies (ntfy, same channel as the runner) on a new payout, a size-stage change, or an evaluation pass / fail.
  FUNDED (Fortress 4X since 2026-11-10: 1x <$4,000, 2x from $4,000, 3x from $4,800, 4x from $6,500, payouts above $8,500 - the lines below
    describe the earlier payout_24 rule it replaced; account mechanics are unchanged): balance from $0; floor -$2,000 static until the
    first payout, then $0; DLL $1,000; 1x below a $4,000 balance at the prior close, 2x from $4,000 (account stop $700; since 2026-11-10 a trade
    is TRIMMED to floor($900 / stop risk per micro) micros instead of skipped when 2x would risk more than $900, v55 cell 4); overnight leg only while the balance >= $500; daily payout of profit above $6,000 when >= $250, max $1,500,
    net profit since the last payout > 0.
  EVALUATION (eval_1, k = 3; holdout-checked in reports/HOLDOUT_EVAL1_RESULTS.json): size min(3 x base, floor($900 / stop risk per micro)),
    overnight min(3, floor($900 / risk)); account stop $700; target $4,000 with the 55% consistency rule; floor -$2,000; DLL $1,000; 90 days.
  EVALUATION CHALLENGER (since 2026-11-10, Nick: "yup"; eval_8 "SLEEVES + DEF + ENDGAME", chosen POST HOC on 2010-23 training, 60.0% vs
    53.4%): the v5.3 trades plus two Codex sleeves already on paper in portfolio_e (MNQ_BRK_E_2c, MES_MOM_3c; 1 micro base, skipped when the
    stop risks > $300 per micro), re-routed one position at a time (research rule: by decision time, then priority, v5.3 first); size
    k = 3, k = 2 once the balance is <= -$500, k = 1 at <= -$1,000 ($400 daily stop at k = 1); from calendar day 60, while more than $1,000
    short of the target and above -$500, k = 5. Same $900 per-trade risk cap, target, floor, DLL and 90 days as the 3x card.
  ROLLING STARTS: both evaluation rules are also started on every weekday since the paper start, to collect forward evidence faster
    (overlapping starts share trades, so they are not independent).
  CHAMPION/CHALLENGER TRIGGERS (written 2026-11-10, before any forward result): (a) if the two Codex sleeves' forward net per micro is below
    $0 after >= 40 forward trades, drop them from the challenger (it becomes DEF + ENDGAME on v5.3); (b) once >= 40 rolling starts of both rules
    have resolved, the challenger replaces the 3x rule as the plan for a real Combine only if its pass share >= the 3x rule's and its fail
    share <= the 3x rule's + 5 points. Nothing is promoted automatically.
Known gaps vs research: trades are routed at 1x before sizing (v55 measured the rules this way); the floor is checked on realised day P&L
(the runner's own intrabar drawdown is reported beside it); v5.3 trades the runner rejected while routing cannot come back when a Codex trade
blocks the one that blocked them; portfolio_e's own paper-account locks can stop its sleeves. Paper only; nothing is routed anywhere.
"""
import argparse, json, sys
from pathlib import Path
import numpy as np, pandas as pd

NY = "America/New_York"
MULT = {"MNQ": 2.0, "MES": 5.0}
V52, NIGHT = "ag_arch_d_plus_v2_price_aware_v53", "overnight_dip_v2_stop055"   # v5.3 since 2026-11-10 (v53 cell A: v5.2 minus TRD30PM)
NIGHT_0915 = "overnight_dip_v2_stop055_0915"   # Aegis comparison leg: same overnight dip, exit 09:15 ET
BOOK = "D+ v5.3 payout build (v5.2 without the afternoon trend) + overnight leg; 2x size trimmed to $900 risk"
EXTRA = "portfolio_e"                                     # Codex sleeves added by the challenger evaluation rule (eval_8)
EXTRA_PRIO = {"MNQ_BRK_E_2c": 10, "MES_MOM_3c": 11}      # router priority after the v5.3 sleeves, as in eval_8


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


def extra_rows(trades):
    """Codex sleeve trades for the challenger: 1 micro base (P&L per micro = net / qty), skipped when the stop risks > $300 per micro."""
    rows = []
    for t in trades:
        if t["sleeve"] not in EXTRA_PRIO or t.get("risk") is None or t["risk"] > 300.0: continue
        tin = pd.Timestamp(t["entry_ts"]).tz_convert(NY)
        rows.append(dict(tin=tin, tout=pd.Timestamp(t["exit_ts"]).tz_convert(NY), n_base=1, per_micro=t["net"] / max(1, t.get("qty", 1)),
                         risk=t["risk"], night=False, sleeve=t["sleeve"], prio=EXTRA_PRIO[t["sleeve"]], dec=tin - pd.Timedelta(minutes=t.get("bar_minutes", 15))))
    return rows


def route_book(rows):
    """Research 1-position routing (payout_lib.route): by decision time, then priority; skip a trade decided inside [entry, exit) of one of
    the last six accepted trades. Overnight rows are not routed (as in research)."""
    acc, keep = [], []
    for r in sorted((r for r in rows if not r["night"]), key=lambda r: (r.get("dec", r["tin"]), r.get("prio", 0))):
        dec = r.get("dec", r["tin"])
        if any(a <= dec < b for a, b in acc[-6:]): continue
        acc.append((r["tin"], r["tout"])); keep.append(r)
    return keep + [r for r in rows if r["night"]]


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


# Main funded rule since 2026-11-10 (Nick: "yes"): Antigravity's Fortress 4X, checked in reports/CHECK_FORTRESS_4X_TRAINING.json.
MAIN_LADDER, MAIN_K, MAIN_NAME = ((0.0, 1), (4000.0, 2), (4800.0, 3), (6500.0, 4)), 8500.0, "Fortress 4X"
# previous main rule (payout_24 + cap-aware): ((0.0, 1), (4000.0, 2)), keep $6,000
BALANCED_3X_LADDER, BALANCED_3X_K = ((0.0, 1), (4000.0, 2), (5000.0, 3)), 6500.0  # Consensus Balanced 3x (+23.2% cash, identical risk)
FORTRESS_4X_LADDER, FORTRESS_4X_K = ((0.0, 1), (4000.0, 2), (4800.0, 3), (6500.0, 4)), 8500.0  # Fortress 4X (+35.8% cash, -43% vol risk)
FORTRESS_FAST_4X_LADDER, FORTRESS_FAST_4X_K = ((0.0, 1), (4000.0, 2), (4800.0, 3), (5800.0, 4)), 8500.0  # Improved Option 2 ($35,319 cash, 9.4% vol risk)
CONVEX_4X_LADDER, CONVEX_4X_K = ((0.0, 1), (4000.0, 2), (4600.0, 3), (5400.0, 4)), 8500.0  # Convex 4X Apex ($35,617 pure, $35,512 sprint, 9.4% vol risk)
CHAMELEON_CROWN_LADDER, CHAMELEON_CROWN_K, CHAMELEON_CROWN_GATE = ((0.0, 1), (4000.0, 2), (4600.0, 3), (5400.0, 4)), 8400.0, 8500.0  # Chameleon Crown ($37,027 cash, 221-day P1)
CHAMELEON_FORTIFIED_LADDER, CHAMELEON_FORTIFIED_K, CHAMELEON_FORTIFIED_GATE = ((0.0, 1), (4000.0, 2), (4600.0, 3), (5400.0, 4)), 8500.0, 8550.0  # Chameleon Fortified ($36,672 cash, 221-day P1)
CHAMELEON_3TIER_LADDER, CHAMELEON_3TIER_K, CHAMELEON_3TIER_GATE1, CHAMELEON_3TIER_GATE2 = (
    ((0.0, 1), (4000.0, 2), (4600.0, 3), (5400.0, 4)), 8400.0, 8500.0, 9600.0
)  # Chameleon Apex 3-Tier ($40,635 cash, $10,127 Y1, 221-day P1, 9.4% tail risk)
CHAMELEON_FORTIFIED_3TIER_LADDER, CHAMELEON_FORTIFIED_3TIER_K, CHAMELEON_FORTIFIED_3TIER_GATE1, CHAMELEON_FORTIFIED_3TIER_GATE2 = (
    ((0.0, 1), (4000.0, 2), (4600.0, 3), (5400.0, 4)), 8600.0, 8700.0, 10000.0
)  # Fortified 3-Tier ($40,310 cash, +9.3%/+18.4% vs Fort 4X, +$250 buffer from cliff)
AEGIS_LADDER, AEGIS_K = ((0.0, 1), (2500.0, 2), (4500.0, 3), (6500.0, 4)), 7500.0   # Antigravity's "Aegis Apex 4X" (comparison only)


def by_day(rows, start_date):
    days = {}
    for r in rows: days.setdefault(r["tout"].date(), []).append(r)
    return days, sorted(d for d in days if d >= start_date)


def funded(rows, start_date, ladder=MAIN_LADDER, K=MAIN_K, sprint=False, sprint_bal=6000.0, sprint_amt=500.0):
    """Static Daily Payouts+ funded account: size from the ladder (balance at the prior close), cap-aware trimming to $900 risk per trade,
    $400 account stop at 1x / $700 above, overnight only while balance >= $500, daily payouts above K ($250-$1,500), optional sprint early P1."""
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
        payout_made = False
        if sprint and not paid and bal >= sprint_bal:
            w = sprint_amt; bal -= w; paid = True; since = 0.0; pays.append(dict(date=str(d), amount=round(w, 2))); payout_made = True
        if not payout_made and (since > 0 or not paid) and bal - K >= 250.0:
            w = min(1500.0, bal - K); bal -= w; paid = True; since = 0.0; pays.append(dict(date=str(d), amount=round(w, 2)))
        hist.append(dict(date=str(d), pnl=round(p, 2), balance=round(bal, 2), payout=round(w, 2), size=f"{m}x", trades=n))
    return dict(balance=round(bal, 2), floor=0.0 if paid else -2000.0, size_stage=f"{stage}x", payouts=pays, payouts_count=len(pays),
                withdrawn=round(sum(x["amount"] for x in pays), 2), closed_on=closed, stage_changes=stage_log, days=hist[-30:],
                next_payout_needs=None if closed else round(max(0.0, K + 250.0 - bal), 2), keep=K,
                ladder=" / ".join(f"{mm}x from ${th:,.0f}" if th else f"{mm}x" for th, mm in ladder))
    return dict(balance=round(bal, 2), floor=0.0 if paid else -2000.0, size_stage=f"{stage}x", payouts=pays, payouts_count=len(pays),
                withdrawn=round(sum(x["amount"] for x in pays), 2), closed_on=closed, stage_changes=stage_log, days=hist[-30:],
                next_payout_needs=None if closed else round(max(0.0, K + 250.0 - bal), 2), keep=K,
                ladder=" / ".join(f"{mm}x from ${th:,.0f}" if th else f"{mm}x" for th, mm in ladder))


def k3_rule(bal, day, tgt):
    return 3


def combined_rule(bal, day, tgt):
    """eval_8 DEF + ENDGAME: k3; k2 at <= -$500; k1 at <= -$1,000; from day 60, more than $1,000 short and above -$500: k5."""
    if day >= 60 and bal < tgt - 1000.0 and bal > -500.0: return 5
    return 1 if bal <= -1000.0 else (2 if bal <= -500.0 else 3)


def evaluation(rows, start_date, rule=k3_rule, today=None):
    """$50K Static Combine from start_date: size min(k x base, floor($900 / stop risk)), k = rule(balance at prior close, calendar day, target)."""
    today = today or pd.Timestamp.now(tz=NY).date()
    days, order = by_day(rows, start_date)
    bal = 0.0; best = 0.0; status = "open"; when = None; end = start_date + pd.Timedelta(days=90).to_pytimedelta()
    for d in order:
        if d >= end: status = "expired"; break
        k = rule(bal, (d - start_date).days, max(4000.0, best / 0.55))
        def esize(r, k=k):
            if r["risk"] is None: return 0
            return int(min(k * r["n_base"], np.floor(900.0 / r["risk"])))
        p, _ = day_pnl(days[d], esize, 400.0 if k == 1 else 700.0, True); bal += p; best = max(best, p)
        if bal <= -2000.0: status = "failed"; when = str(d); break
        if bal >= max(4000.0, best / 0.55): status = "passed"; when = str(d); break
    if status == "open" and today >= end: status = "expired"
    tgt = max(4000.0, best / 0.55)
    return dict(status=status, on=when, balance=round(bal, 2), target=round(tgt, 2), best_day=round(best, 2),
                days_left=max(0, (end - today).days), expires=str(end),
                size_now=f"{rule(bal, (today - start_date).days, tgt)}x" if status == "open" else None)


def rolling(rows, first, rule, today=None):
    """One attempt started on every weekday from first to today (forward evidence; overlapping attempts share trades)."""
    today = today or pd.Timestamp.now(tz=NY).date()
    st = [evaluation(rows, s.date(), rule, today)["status"] for s in pd.bdate_range(first, today)]
    return dict(starts=len(st), passed=st.count("passed"), failed=st.count("failed"), expired=st.count("expired"), open=st.count("open"))


def replay(rows, start_date, today=None):
    return dict(funded=funded(rows, start_date), evaluation=evaluation(rows, start_date, k3_rule, today))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); ap.add_argument("--root", required=True); a = ap.parse_args(argv)
    root = Path(a.root); here = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(here / "src"))
    from quant_futures import ensemble_paper as ep
    specs = {sl["name"]: sl for k in (V52, NIGHT, EXTRA) for sl in ep.CANDIDATES[k]["sleeves"]}
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
    res["funded"]["name"] = MAIN_NAME
    # EVALUATION challenger (eval_8): v5.3 + the two Codex sleeves, re-routed, defensive + endgame sizing
    x = stop_risk_per_micro([dict(t, bar_minutes=int(specs[t["sleeve"]].get("bar_minutes", 15))) for t in read_trades(root / EXTRA / "ledger.jsonl")
                             if t["sleeve"] in EXTRA_PRIO], specs, bars)
    prio = {sl["name"]: i for i, sl in enumerate(ep.CANDIDATES[V52]["sleeves"])}
    vr = group_intraday(v)
    for r in vr:
        r["prio"] = prio.get(r["sleeve"], 0); r["dec"] = r["tin"] - pd.Timedelta(minutes=int(specs.get(r["sleeve"], {}).get("bar_minutes", 15)))
    book_c = route_book(vr + extra_rows(x) + night_rows(n)); book_3 = group_intraday(v) + night_rows(n)
    res["evaluation"].update(name="v5.3 book at 3x, champion", rolling=rolling(book_3, start, k3_rule))
    res["evaluation_combined"] = dict(evaluation(book_c, start, combined_rule), name="v5.3 + 2 Codex sleeves, defensive + endgame",
                                      rolling=rolling(book_c, start, combined_rule), extra_trades=len(x),
                                      extra_taken=sum(1 for r in book_c if r["sleeve"] in EXTRA_PRIO),
                                      extra_net_per_micro=round(sum(t["net"] / max(1, t.get("qty", 1)) for t in x), 2),
                                      rule="3x; 2x at <= -$500; 1x at <= -$1,000; from day 60, > $1,000 short and above -$500: 5x; $900 risk cap per trade",
                                      caution="chosen after seeing all of 2010-23 (training 60.0% vs 53.4%, no clean holdout left); forward paper decides")
    n915 = read_trades(root / NIGHT_0915 / "ledger.jsonl")
    res["aegis"] = dict(funded(group_intraday(v) + night_rows(n915), start, AEGIS_LADDER, AEGIS_K), overnight_exit="09:15 ET", overnight_trades=len(n915),
                        name="Aegis Apex 4X (Antigravity)", status="comparison only, not adopted",
                        caution="training: +45% dollars vs the main rule with the same end-of-day closures, but worst-case intraday closures in the cost+edge stress test 15.8% vs 5.0%; 09:15 exit not better in both halves (reports/V55_CHECK_AEGIS_TRAINING.json)")
    names = {f"AG_CRABEL15_D_1c_{v}": "Crabel 15-min opening-range breakout" for v in ("v52", "v53")}
    names.update({f"AG_CRABEL15_D_GAP_{v}": "Crabel gap-continuation add-on (+1 micro when the trade agrees with the opening gap)" for v in ("v52", "v53")})
    names.update({f"AG_TRD60_D_1c_{v}": "60-min trend" for v in ("v52", "v53")}); names.update({f"AG_MES_TRD30_D_1c_{v}": "30-min trend" for v in ("v52", "v53")})
    names.update({"AG_TRD30PM_1c_v52": "30-min afternoon trend",
             "OVN_DIP2_STOP_1c": "Overnight reopen dip, 0.55% stop (only once the balance is >= $500)",
             "MNQ_BRK_E_2c": "Codex MNQ 15-min breakout (challenger evaluation only)", "MES_MOM_3c": "Codex MES 15-min momentum (challenger evaluation only)"})
    res["strategies"] = [dict(sleeve=sl["name"], name=names.get(sl["name"], sl["name"]), instrument=sl["instrument"], bar_minutes=int(sl.get("bar_minutes", 15)),
                              trades=sum(1 for t in v + n if t["sleeve"] == sl["name"]), net_1x=round(sum(t["net"] for t in v + n if t["sleeve"] == sl["name"]), 2))
                         for sl in ep.CANDIDATES[V52]["sleeves"] + ep.CANDIDATES[NIGHT]["sleeves"]]
    res["strategies"] += [dict(sleeve=sl["name"], name=names[sl["name"]], instrument=sl["instrument"], bar_minutes=int(sl.get("bar_minutes", 15)),
                               trades=sum(1 for t in x if t["sleeve"] == sl["name"]),
                               net_1x=round(sum(t["net"] / max(1, t.get("qty", 1)) for t in x if t["sleeve"] == sl["name"]), 2), challenger=True)
                          for sl in ep.CANDIDATES[EXTRA]["sleeves"] if sl["name"] in EXTRA_PRIO]
    st = json.loads((root / V52 / "status.json").read_text()) if (root / V52 / "status.json").exists() else {}
    res.update(updated=pd.Timestamp.now(tz="UTC").isoformat(), paper_start=str(start), source_ledgers=[V52, NIGHT, EXTRA], book=BOOK,
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
                                         aegis_balance=res["aegis"]["balance"], aegis_payouts=res["aegis"]["payouts_count"], aegis_stage=res["aegis"]["size_stage"],
                                         evaluation_combined=res["evaluation_combined"]["status"], evaluation_combined_balance=res["evaluation_combined"]["balance"])
        dash.write_text(json.dumps(d, indent=1, sort_keys=True, default=str))
    pf, pe, pa, pc = prev.get("funded", {}), prev.get("evaluation", {}), prev.get("aegis", {}), prev.get("evaluation_combined", {})
    if res["evaluation_combined"]["status"] != pc.get("status", "open") and res["evaluation_combined"]["status"] != "open":
        ep.notify(f"Paper evaluation (challenger): {res['evaluation_combined']['status']}",
                  f"balance ${res['evaluation_combined']['balance']:,.2f} on {res['evaluation_combined']['on']}")
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
    print(json.dumps({k: res[k] for k in ("funded", "evaluation", "evaluation_combined")}, default=str)[:2500])


if __name__ == "__main__":
    main()
