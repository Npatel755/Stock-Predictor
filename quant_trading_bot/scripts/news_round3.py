"""News round 3 (pre-registered 2026-11-08): FOMC-afternoon continuation / fade as its own sleeve.

Motivation: round 1 showed the deployed sleeves do slightly better when FOMC afternoons are skipped on MES_MOM and
MNQ_E57 (not enough years to pass), i.e. the post-statement move behaves differently from the sleeves' trend rules.
Hypothesis A (cont): the direction of the 14:00-14:15 ET statement bar continues into the close.
Hypothesis B (fade): the statement bar's direction reverses into the close (the "FOMC whipsaw").
Decision at the close of the 14:00-14:15 bar, fill at the 14:15 open through the standard engine (spread, slippage,
commissions, $150 risk, $400 daily loss, $2k DD, forced flat 15:55 ET).
Sample: only meetings since 2013, when the statement time became a fixed 14:00 ET (2010-2012 statements were released
at 12:30 or 14:15 and our calendar only carries approximate times for them). Train = ES 2013-2019 + MES 2020-2023
(11 years, ~90 scheduled meetings; the 2020-03-03 emergency cut is in the calendar and fires one spurious day).
Grid, fixed before running (16 per instrument): direction {cont, fade} x range filter k in {0, 1.0} x ATR(16) x
target_r {2.0, 6.0} x hold_bars {3 (to 15:00), 6 (to 15:45)}; stop 1.5 ATR, 2 ATR trail, 1 contract.
Negative control: identical rule fired on every non-FOMC weekday ("placebo").
Gate: train total net > 0, >= 60% of train years positive, worst annual DD < $1,000, per-trade net > placebo per-trade.
Passers get one 2024-2025 validation look. 2026 never loaded. Small sample: anything that passes is exploratory.
Output: reports/NEWS_ROUND3.{json,md}; events.jsonl line.
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
from news_round1 import CAL, VALID, load  # noqa: E402

TRAIN = [("ES", y) for y in range(2013, 2020)] + [("MES", y) for y in range(2020, 2024)]
TRAIN_NQ = [("NQ", y) for y in range(2013, 2020)] + [("MNQ", y) for y in range(2020, 2024)]
GRID = [dict(direction=d, k=k, target_r=t, hold_bars=h)
        for d, k, t, h in itertools.product(("cont", "fade"), (0.0, 1.0), (2.0, 6.0), (3, 6))]
BAR_OPEN = 840   # 14:00 ET bar (engine minute = bar open)
DECISION = 855   # its close
FOMC_DAYS = set(CAL[(CAL.family == "FOMC") & (CAL.minute_et == BAR_OPEN)].date_et)


def run(bars, start, variant, placebo=False):
    eng = ep.engine()
    cfg = dict(instrument=bars.instrument.iloc[0], lookback=16, stop_atr=1.5, target_r=variant["target_r"], hold_bars=variant["hold_bars"],
               session_start=DECISION, session_end=945, trailing_atr=2.0, max_contracts=1)
    data = eng["arrays"](bars)
    atr = eng["features"](bars, 16)["atr"]
    local = bars.timestamp_utc.dt.tz_convert("America/New_York")
    decision = (local.dt.hour * 60 + local.dt.minute + 15).to_numpy()
    dates = local.dt.strftime("%Y-%m-%d").to_numpy()
    on_day = np.array([(d not in FOMC_DAYS) if placebo else (d in FOMC_DAYS) for d in dates])
    on_day &= local.dt.day_of_week.to_numpy() < 5
    rng = (bars.high - bars.low).to_numpy()
    move = (bars.close - bars.open).to_numpy()
    fire = on_day & (decision == DECISION) & (rng >= variant["k"] * np.nan_to_num(atr, nan=np.inf))
    sign = np.sign(move) if variant["direction"] == "cont" else -np.sign(move)
    signal = np.where(fire, sign, 0).astype(np.int8)
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
    json.dump(out, open(ROOT / "reports" / "NEWS_ROUND3.json", "w"), indent=1, default=str)
    lines = ["# News round 3: FOMC-afternoon continuation / fade sleeve", "", __doc__.strip(), "",
             "| variant | dir | k | target_r | hold | train total | +years | worst DD | trades | $/trade | placebo $/trade | gate |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for key, t in out["train"].items():
        v = out["verdict"][key]["variant"]; p = out["placebo"][key]
        lines.append(f"| {key} | {v['direction']} | {v['k']} | {v['target_r']} | {v['hold_bars']} | {t['total']:+,.0f} | {t['pos_years']}/{len(t['years'])} | {t['worst_dd']:,.0f} | {t['trades']} | {t['per_trade']:+.1f} | {p['per_trade']:+.1f} | {'PASS' if out['verdict'][key]['passed'] else 'fail'} |")
    lines += ["", f"Passers sent to validation: {passers or 'none'}", ""]
    for key, res in out["validation"].items():
        lines.append(f"- {key}: " + ", ".join(f"{y} event {r['event']['net']:+,.0f} ({r['event']['trades']} tr) vs placebo {r['placebo']['net']:+,.0f}" for y, r in res.items()))
    (ROOT / "reports" / "NEWS_ROUND3.md").write_text("\n".join(lines) + "\n")
    with open(ROOT / "research" / "strategy_memory" / "events.jsonl", "a") as f:
        f.write(json.dumps(dict(ts=pd.Timestamp.now("UTC").isoformat(), experiment="news_round3", kind="result", passers=passers, report="reports/NEWS_ROUND3.md")) + "\n")
    print("\n".join(lines[-(len(passers) + 2):]))


if __name__ == "__main__":
    main()
