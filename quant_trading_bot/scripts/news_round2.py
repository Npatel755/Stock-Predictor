"""News round 2 (pre-registered 2026-11-08): post-release continuation as its own sleeve.

Hypothesis: after a high-impact 08:30 ET release, the direction of the 08:30-08:45 15-min bar continues for the next
hours (information is absorbed over time rather than instantly). Entry decision at the close of that bar, fill at the
next bar's open through the standard engine (spread + slippage + commissions, $150 risk, $400 daily loss, $2k DD).
Grid, fixed before running (16 per instrument): event set {high_0830 = CPI, Employment Situation, PPI, retail sales,
GDP, PCE; nfp_cpi}, range filter k in {0, 1.0} x ATR(16), target_r in {2.0, 6.0 (= effectively trail-only)},
hold_bars in {8, 16}; stop 1.5 ATR, 2 ATR trail, 1 contract.
Negative control: the identical rule fired on every weekday that has no scheduled release before 09:30 ("placebo").
Gate: train total net > 0, >= 60% of train years positive, worst annual DD < $1,000, and per-trade net exceeds the
placebo's per-trade net. Passers get one 2024-2025 validation look. 2026 never loaded.
Output: reports/NEWS_ROUND2.{json,md}; events.jsonl line.
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from quant_futures import ensemble_paper as ep  # noqa: E402
from news_round1 import CAL, TRAIN, TRAIN_NQ, VALID, load  # noqa: E402

HIGH_0830 = {"CPI", "EMPLOYMENT", "PPI", "RETAIL_SALES", "GDP", "PERSONAL_INCOME"}
EVENT_SETS = {"high_0830": HIGH_0830, "nfp_cpi": {"EMPLOYMENT", "CPI"}}
GRID = [dict(events=e, k=k, target_r=t, hold_bars=h) for e, k, t, h in itertools.product(EVENT_SETS, (0.0, 1.0), (2.0, 6.0), (8, 16))]
DECISION = 525  # ET minute at which the 08:30-08:45 bar closes


def event_days(name):
    if name == "placebo":
        busy = set(CAL[CAL.minute_et < 570].date_et)
        return None, busy
    sub = CAL[CAL.family.isin(EVENT_SETS[name]) & (CAL.minute_et == 510)]
    return set(sub.date_et), None


def run(bars, start, variant, placebo=False):
    eng = ep.engine()
    cfg = dict(instrument=bars.instrument.iloc[0], lookback=16, stop_atr=1.5, target_r=variant["target_r"], hold_bars=variant["hold_bars"],
               session_start=525, session_end=945, trailing_atr=2.0, max_contracts=1)
    data = eng["arrays"](bars)
    atr = eng["features"](bars, 16)["atr"]
    local = bars.timestamp_utc.dt.tz_convert("America/New_York")
    decision = (local.dt.hour * 60 + local.dt.minute + 15).to_numpy()
    dates = local.dt.strftime("%Y-%m-%d").to_numpy()
    days, busy = event_days("placebo" if placebo else variant["events"])
    on_day = np.array([(d not in busy) for d in dates]) if placebo else np.array([d in days for d in dates])
    on_day &= local.dt.day_of_week.to_numpy() < 5
    rng = (bars.high - bars.low).to_numpy()
    move = (bars.close - bars.open).to_numpy()
    fire = on_day & (decision == DECISION) & (rng >= variant["k"] * np.nan_to_num(atr, nan=np.inf))
    signal = np.where(fire, np.sign(move), 0).astype(np.int8)
    first = int((bars.timestamp_utc < pd.Timestamp(start, tz="UTC")).sum())
    sliced = {kk: np.ascontiguousarray(v[first:]) for kk, v in data.items()}
    sliced["session"] = pd.factorize(sliced["session"], sort=False)[0].astype(np.int64)
    sliced["contract"] = pd.factorize(sliced["contract"], sort=False)[0].astype(np.int64)
    result = eng["execute"](sliced, signal[first:], np.ascontiguousarray(atr[first:]), eng["execution_cfg"](cfg))
    n = int(len(result["trade_net"]))
    return dict(net=round(float(result["cash"][-1] - 50000.0), 2) if len(result["cash"]) else 0.0,
                dd=round(float(50000.0 - result["worst"].min()), 2) if len(result["worst"]) else 0.0, trades=n, signals=int(fire[first:].sum()))


def summarize(res):
    nets = [r["net"] for r in res.values()]
    trades = sum(r["trades"] for r in res.values())
    return dict(total=round(sum(nets), 2), pos_years=int(sum(n > 0 for n in nets)), worst_dd=max(r["dd"] for r in res.values()),
                trades=trades, per_trade=round(sum(nets) / trades, 2) if trades else 0.0, years=res)


def main():
    out = dict(registered="2026-11-08", grid=GRID, train={}, placebo={}, verdict={}, validation={})
    cache = {}
    for inst, years in (("MES", TRAIN), ("MNQ", TRAIN_NQ)):
        for sym, y in years:
            cache[(sym, y)] = load(sym, "train", f"{y - 1}-12-01", f"{y + 1}-01-01")
        for i, v in enumerate(GRID):
            key = f"{inst}/{i}"
            out["train"][key] = summarize({str(y): run(cache[(s, y)], f"{y}-01-01", v) for s, y in years})
            out["placebo"][key] = summarize({str(y): run(cache[(s, y)], f"{y}-01-01", v, placebo=True) for s, y in years})
            t, p = out["train"][key], out["placebo"][key]
            passed = t["total"] > 0 and t["pos_years"] >= 0.6 * len(years) and t["worst_dd"] < 1000 and t["per_trade"] > p["per_trade"]
            out["verdict"][key] = dict(passed=bool(passed), variant=v)
            print(key, v, "train", t["total"], t["pos_years"], t["worst_dd"], t["trades"], t["per_trade"], "placebo", p["total"], p["trades"], p["per_trade"], "PASS" if passed else "", flush=True)
        cache.clear()
    passers = [k for k, v in out["verdict"].items() if v["passed"]]
    for key in passers:
        inst, i = key.split("/")
        v = GRID[int(i)]
        res = {}
        for y in VALID[inst]:
            bars = load(inst, "validation", f"{y - 1}-12-01", f"{y + 1}-01-01")
            res[str(y)] = dict(event=run(bars, f"{y}-01-01", v), placebo=run(bars, f"{y}-01-01", v, placebo=True))
        out["validation"][key] = res
        print("VALIDATION", key, res, flush=True)
    json.dump(out, open(ROOT / "reports" / "NEWS_ROUND2.json", "w"), indent=1, default=str)
    lines = ["# News round 2: post-release continuation sleeve", "", __doc__.strip(), "",
             "| variant | events | k | target_r | hold | train total | +years | worst DD | trades | $/trade | placebo $/trade | gate |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for key, t in out["train"].items():
        v = out["verdict"][key]["variant"]; p = out["placebo"][key]
        lines.append(f"| {key} | {v['events']} | {v['k']} | {v['target_r']} | {v['hold_bars']} | {t['total']:+,.0f} | {t['pos_years']}/{len(t['years'])} | {t['worst_dd']:,.0f} | {t['trades']} | {t['per_trade']:+.1f} | {p['per_trade']:+.1f} | {'PASS' if out['verdict'][key]['passed'] else 'fail'} |")
    lines += ["", f"Passers sent to validation: {passers or 'none'}", ""]
    for key, res in out["validation"].items():
        lines.append(f"- {key}: " + ", ".join(f"{y} event {r['event']['net']:+,.0f} ({r['event']['trades']} tr) vs placebo {r['placebo']['net']:+,.0f}" for y, r in res.items()))
    (ROOT / "reports" / "NEWS_ROUND2.md").write_text("\n".join(lines) + "\n")
    with open(ROOT / "research" / "strategy_memory" / "events.jsonl", "a") as f:
        f.write(json.dumps(dict(ts=pd.Timestamp.utcnow().isoformat(), experiment="news_round2", kind="result", passers=passers, report="reports/NEWS_ROUND2.md")) + "\n")
    print("\n".join(lines[-(len(passers) + 2):]))


if __name__ == "__main__":
    main()
