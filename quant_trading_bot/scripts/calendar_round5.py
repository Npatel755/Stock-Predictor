"""Round 5 (pre-registered 2026-11-08): calendar effects from the QuantConnect library (turn of month, pre-holiday,
option-expiration week; QC tutorials 35/83/102, Quantpedia) adapted to a day-session-only MES/MNQ account.

Published versions are close-to-close equity effects, mostly earned overnight, which this account cannot hold. Two
executable adaptations, both training-only (ES/NQ 2010-2019 + MES/MNQ 2020-2023, today's costs), 2026 never loaded:
A. Day filters on the six deployed sleeves (same harness and gate as news round 1): skip_opex_week (Mon-Fri of the
   third-Friday week), skip_opex_friday, skip_tom (last trading day + first 3 of the month), only_tom, skip_preholiday
   (trading day before a weekday with no session). Gate: total > baseline, worst DD <= baseline, >= 60% of years beat.
B. Stand-alone "TOM day-session long": buy at the 09:45 ET open on turn-of-month days, 1.5 ATR(16) stop, no target,
   flat at the 16:00 bar; placebo = same on all other weekdays. Gate: total > 0, >= 60% years positive, worst annual
   DD < $1,000, per-trade net > placebo per-trade. Passers get one 2024-2025 validation look.
Trading-day calendar is derived from the bars themselves (a weekday with no 09:30 bar is a holiday).
Output: reports/CALENDAR_ROUND5.{json,md}; events.jsonl line.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from quant_futures import ensemble_paper as ep  # noqa: E402
import news_round1 as nr1  # noqa: E402

FILTERS = ("baseline", "skip_opex_week", "skip_opex_friday", "skip_tom", "only_tom", "skip_preholiday")
SLEEVES = {s["name"]: s for c in ep.CANDIDATES.values() for s in c["sleeves"]}
_DAYSETS = {}


def day_sets(dates, minute):
    """Trading-day derived sets keyed by the first date in the frame (cached)."""
    key = (dates[0], dates[-1])
    if key in _DAYSETS:
        return _DAYSETS[key]
    tdays = sorted(set(dates[minute == 570]))
    idx = pd.to_datetime(tdays)
    tom, opex_week, opex_fri, preh = set(), set(), set(), set()
    for i, d in enumerate(idx):
        if i + 1 < len(idx) and idx[i + 1].month != d.month:
            tom.update([tdays[i]] + tdays[i + 1:i + 4])
        third_friday = pd.Timestamp(d.year, d.month, 1) + pd.offsets.WeekOfMonth(week=2, weekday=4)
        if d.isocalendar()[1] == third_friday.isocalendar()[1] and d.year == third_friday.year:
            opex_week.add(tdays[i])
            if d == third_friday:
                opex_fri.add(tdays[i])
        if i + 1 < len(idx):
            gap = pd.bdate_range(d, idx[i + 1])
            if len(gap) > 2:  # a weekday between two consecutive trading days has no session -> holiday
                preh.add(tdays[i])
    _DAYSETS[key] = dict(tom=tom, opex_week=opex_week, opex_fri=opex_fri, preh=preh)
    return _DAYSETS[key]


def blocked(variant, dates, decision):
    if variant == "baseline":
        return np.zeros(len(dates), bool)
    sets = day_sets(dates, decision - 15)
    pick = {"skip_opex_week": sets["opex_week"], "skip_opex_friday": sets["opex_fri"], "skip_tom": sets["tom"],
            "only_tom": sets["tom"], "skip_preholiday": sets["preh"]}[variant]
    in_set = np.array([d in pick for d in dates])
    return ~in_set if variant == "only_tom" else in_set


nr1.blocked = blocked


def tom_long(bars, start, placebo=False):
    eng = ep.engine()
    cfg = dict(instrument=bars.instrument.iloc[0], lookback=16, stop_atr=1.5, target_r=50.0, hold_bars=40,
               session_start=585, session_end=945, trailing_atr=0.0, max_contracts=1)
    data = eng["arrays"](bars)
    atr = eng["features"](bars, 16)["atr"]
    local = bars.timestamp_utc.dt.tz_convert("America/New_York")
    minute = (local.dt.hour * 60 + local.dt.minute).to_numpy()
    dates = local.dt.strftime("%Y-%m-%d").to_numpy()
    tom = day_sets(dates, minute)["tom"]
    in_tom = np.array([d in tom for d in dates])
    fire = (minute == 570) & (local.dt.day_of_week.to_numpy() < 5) & (~in_tom if placebo else in_tom)
    signal = np.where(fire, 1, 0).astype(np.int8)
    first = int((bars.timestamp_utc < pd.Timestamp(start, tz="UTC")).sum())
    sliced = {k: np.ascontiguousarray(v[first:]) for k, v in data.items()}
    sliced["session"] = pd.factorize(sliced["session"], sort=False)[0].astype(np.int64)
    sliced["contract"] = pd.factorize(sliced["contract"], sort=False)[0].astype(np.int64)
    result = eng["execute"](sliced, signal[first:], np.ascontiguousarray(atr[first:]), eng["execution_cfg"](cfg))
    n = int(len(result["trade_net"]))
    return dict(net=round(float(result["cash"][-1] - 50000.0), 2) if len(result["cash"]) else 0.0,
                dd=round(float(50000.0 - result["worst"].min()), 2) if len(result["worst"]) else 0.0, trades=n)


def summarize(res):
    nets = [r["net"] for r in res.values()]
    trades = sum(r["trades"] for r in res.values())
    return dict(total=round(sum(nets), 2), pos_years=int(sum(n > 0 for n in nets)), worst_dd=max(r["dd"] for r in res.values()),
                trades=trades, per_trade=round(sum(nets) / trades, 2) if trades else 0.0, years=res)


def main():
    out = dict(registered="2026-11-08", filters={}, tom_long={}, validation={})
    cache = {}
    for inst, years in (("MES", nr1.TRAIN), ("MNQ", nr1.TRAIN_NQ)):
        for sym, y in years:
            cache[(sym, y)] = nr1.load(sym, "train", f"{y - 1}-12-01", f"{y + 1}-01-01")
        # A. filters on sleeves
        for name, cfg in SLEEVES.items():
            if cfg["instrument"] != inst:
                continue
            res = {}
            for f in FILTERS:
                res[f] = summarize({str(y): nr1.run(cfg, cache[(s, y)], f"{y}-01-01", f) for s, y in years})
            base = res["baseline"]
            for f in FILTERS[1:]:
                v = res[f]
                beats = sum(v["years"][y]["net"] > base["years"][y]["net"] for y in v["years"])
                v["passed"] = bool(v["total"] > base["total"] and v["worst_dd"] <= base["worst_dd"] and beats >= 0.6 * len(v["years"]))
                v["beats"] = int(beats)
                print(name, f, "total", v["total"], "vs", base["total"], "dd", v["worst_dd"], "vs", base["worst_dd"], "beats", beats, "PASS" if v["passed"] else "", flush=True)
            out["filters"][name] = res
        # B. TOM long sleeve
        ev = summarize({str(y): tom_long(cache[(s, y)], f"{y}-01-01") for s, y in years})
        pl = summarize({str(y): tom_long(cache[(s, y)], f"{y}-01-01", placebo=True) for s, y in years})
        ev["passed"] = bool(ev["total"] > 0 and ev["pos_years"] >= 0.6 * len(years) and ev["worst_dd"] < 1000 and ev["per_trade"] > pl["per_trade"])
        out["tom_long"][inst] = dict(event=ev, placebo=pl)
        print(inst, "TOM long", ev["total"], ev["pos_years"], ev["worst_dd"], ev["trades"], ev["per_trade"], "placebo", pl["total"], pl["trades"], pl["per_trade"], "PASS" if ev["passed"] else "", flush=True)
        cache.clear()
    passers = [f"{n}/{f}" for n, res in out["filters"].items() for f, v in res.items() if f != "baseline" and v["passed"]]
    passers += [f"TOM_long/{i}" for i, r in out["tom_long"].items() if r["event"]["passed"]]
    for key in passers:
        name, f = key.split("/")
        inst = f if name == "TOM_long" else SLEEVES[name]["instrument"]
        res = {}
        for y in nr1.VALID[inst]:
            bars = nr1.load(inst, "validation", f"{y - 1}-12-01", f"{y + 1}-01-01")
            if name == "TOM_long":
                res[str(y)] = dict(event=tom_long(bars, f"{y}-01-01"), placebo=tom_long(bars, f"{y}-01-01", placebo=True))
            else:
                res[str(y)] = dict(filtered=nr1.run(SLEEVES[name], bars, f"{y}-01-01", f), baseline=nr1.run(SLEEVES[name], bars, f"{y}-01-01", "baseline"))
        out["validation"][key] = res
        print("VALIDATION", key, res, flush=True)
    json.dump(out, open(ROOT / "reports" / "CALENDAR_ROUND5.json", "w"), indent=1, default=str)
    lines = ["# Round 5: calendar effects (TOM, pre-holiday, OpEx) on MES/MNQ day session", "", __doc__.strip(), "",
             "## A. Day filters on the deployed sleeves (train total / worst annual DD / years beating baseline)", "",
             "| sleeve | filter | total | baseline | worst DD | baseline DD | beats | gate |", "|---|---|---|---|---|---|---|---|"]
    for name, res in out["filters"].items():
        base = res["baseline"]
        for f in FILTERS[1:]:
            v = res[f]
            lines.append(f"| {name} | {f} | {v['total']:+,.0f} | {base['total']:+,.0f} | {v['worst_dd']:,.0f} | {base['worst_dd']:,.0f} | {v['beats']}/{len(v['years'])} | {'PASS' if v['passed'] else 'fail'} |")
    lines += ["", "## B. TOM day-session long sleeve", "", "| instrument | total | +years | worst DD | trades | $/trade | placebo $/trade | gate |", "|---|---|---|---|---|---|---|---|"]
    for inst, r in out["tom_long"].items():
        e, p = r["event"], r["placebo"]
        lines.append(f"| {inst} | {e['total']:+,.0f} | {e['pos_years']}/{len(e['years'])} | {e['worst_dd']:,.0f} | {e['trades']} | {e['per_trade']:+.1f} | {p['per_trade']:+.1f} | {'PASS' if e['passed'] else 'fail'} |")
    lines += ["", f"Passers sent to validation: {passers or 'none'}", ""]
    for key, res in out["validation"].items():
        lines.append(f"- {key}: " + "; ".join(f"{y} " + ", ".join(f"{k} {v['net']:+,.0f} ({v['trades']} tr)" for k, v in r.items()) for y, r in res.items()))
    (ROOT / "reports" / "CALENDAR_ROUND5.md").write_text("\n".join(lines) + "\n")
    with open(ROOT / "research" / "strategy_memory" / "events.jsonl", "a") as f:
        f.write(json.dumps(dict(ts=pd.Timestamp.now("UTC").isoformat(), experiment="calendar_round5", kind="result", passers=passers, report="reports/CALENDAR_ROUND5.md")) + "\n")
    print("\n".join(lines[-(len(passers) + 2):]))


if __name__ == "__main__":
    main()
