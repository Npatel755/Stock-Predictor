"""Round 4 (pre-registered 2026-11-08): market intraday momentum (Gao, Han, Li, Zhou 2018, JFE 129(2)) on MES/MNQ.

Source: QuantConnect Strategy Library "Intraday ETF Momentum" -> Gao et al.: the first half-hour return (from the prior
close) predicts the last half-hour return of the S&P 500 ETF; the 12th half-hour (15:00-15:30) also predicts it; the
effect is stronger on volatile days. Adapted hypothesis, not the equity curve: take a position for the last half hour
of the CME day session in the direction of the predictor.
Mechanics: decision at the close of the 15:15-15:30 ET bar, fill at the 15:30 open through the standard engine (spread,
slippage, commissions, $150 risk, $400 daily loss, $2k DD), forced flat at the 16:00 bar open (engine flat_minute 955),
stop 1.5 ATR(16), 2 ATR trail. Predictors: first30_prevclose = close(10:00) - prior session 16:00 close;
first30_open = close(10:00) - open(09:30); h12 = close(15:30) - close(15:00). Filter |pred| >= k * ATR(16), k in {0, 1}.
target_r in {2.0, 6.0}. 3 x 2 x 2 = 12 variants per instrument, fixed before running.
Negative control ("placebo"): same predictor and sign, but the position is taken 12:30-13:00 (h12 placebo uses the
12:00-12:30 half hour). If the edge is specific to the last half hour, the placebo should not share it.
Train = ES 2010-2019 + MES 2020-2023 (NQ/MNQ for MNQ); gate: train total > 0, >= 60% train years positive, worst annual
DD < $1,000, per-trade net > placebo per-trade. Passers get one 2024-2025 validation look. 2026 never loaded.
Output: reports/INTRADAY_MOMENTUM_ROUND4.{json,md}; events.jsonl line.
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
from news_round1 import TRAIN, TRAIN_NQ, VALID, load  # noqa: E402

PREDICTORS = ("first30_prevclose", "first30_open", "h12")
GRID = [dict(pred=p, k=k, target_r=t) for p, k, t in itertools.product(PREDICTORS, (0.0, 1.0), (2.0, 6.0))]
REAL = dict(decision_bar=915, session_start=930, session_end=945)       # fill 15:30, flat 16:00 bar
PLACEBO = dict(decision_bar=735, session_start=750, session_end=780)    # fill 12:30, flat 13:00 bar


def per_day(bars, local):
    """Point-in-time daily anchors keyed by ET date: 09:30 open, 10:00 close, prior-session 16:00 close."""
    minute = (local.dt.hour * 60 + local.dt.minute).to_numpy()
    date = local.dt.strftime("%Y-%m-%d").to_numpy()
    frame = pd.DataFrame(dict(date=date, minute=minute, open=bars.open.to_numpy(), close=bars.close.to_numpy()))
    o930 = frame[frame.minute == 570].groupby("date").open.first()
    c1000 = frame[frame.minute == 585].groupby("date").close.first()
    c1600 = frame[frame.minute == 945].groupby("date").close.first()
    prev_close = c1600.shift(1)
    return o930, c1000, prev_close


def run(bars, start, variant, placebo=False):
    eng = ep.engine()
    win = PLACEBO if placebo else REAL
    cfg = dict(instrument=bars.instrument.iloc[0], lookback=16, stop_atr=1.5, target_r=variant["target_r"], hold_bars=4,
               session_start=win["session_start"], session_end=win["session_end"], trailing_atr=2.0, max_contracts=1)
    data = eng["arrays"](bars)
    atr = eng["features"](bars, 16)["atr"]
    local = bars.timestamp_utc.dt.tz_convert("America/New_York")
    minute = (local.dt.hour * 60 + local.dt.minute).to_numpy()
    dates = local.dt.strftime("%Y-%m-%d").to_numpy()
    o930, c1000, prev_close = per_day(bars, local)
    close = bars.close.to_numpy()
    if variant["pred"] == "first30_prevclose":
        pred = c1000.reindex(dates).to_numpy() - prev_close.reindex(dates).to_numpy()
    elif variant["pred"] == "first30_open":
        pred = c1000.reindex(dates).to_numpy() - o930.reindex(dates).to_numpy()
    else:  # h12: close of the decision bar minus close two bars earlier (same ET date)
        pred = np.full(len(bars), np.nan)
        same = np.r_[False, False, dates[2:] == dates[:-2]]
        pred[2:] = np.where(same[2:], close[2:] - close[:-2], np.nan)
    at_bar = minute == win["decision_bar"]
    fire = at_bar & (local.dt.day_of_week.to_numpy() < 5) & np.isfinite(pred) & (np.abs(pred) >= variant["k"] * np.nan_to_num(atr, nan=np.inf)) & (pred != 0)
    signal = np.where(fire, np.sign(np.nan_to_num(pred)), 0).astype(np.int8)
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
    json.dump(out, open(ROOT / "reports" / "INTRADAY_MOMENTUM_ROUND4.json", "w"), indent=1, default=str)
    lines = ["# Round 4: market intraday momentum (last half hour) on MES/MNQ", "", __doc__.strip(), "",
             "| variant | predictor | k | target_r | train total | +years | worst DD | trades | $/trade | placebo $/trade | gate |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for key, t in out["train"].items():
        v = out["verdict"][key]["variant"]; p = out["placebo"][key]
        lines.append(f"| {key} | {v['pred']} | {v['k']} | {v['target_r']} | {t['total']:+,.0f} | {t['pos_years']}/{len(t['years'])} | {t['worst_dd']:,.0f} | {t['trades']} | {t['per_trade']:+.1f} | {p['per_trade']:+.1f} | {'PASS' if out['verdict'][key]['passed'] else 'fail'} |")
    lines += ["", f"Passers sent to validation: {passers or 'none'}", ""]
    for key, res in out["validation"].items():
        lines.append(f"- {key}: " + ", ".join(f"{y} event {r['event']['net']:+,.0f} ({r['event']['trades']} tr) vs placebo {r['placebo']['net']:+,.0f}" for y, r in res.items()))
    (ROOT / "reports" / "INTRADAY_MOMENTUM_ROUND4.md").write_text("\n".join(lines) + "\n")
    with open(ROOT / "research" / "strategy_memory" / "events.jsonl", "a") as f:
        f.write(json.dumps(dict(ts=pd.Timestamp.now("UTC").isoformat(), experiment="intraday_momentum_round4", kind="result", passers=passers, report="reports/INTRADAY_MOMENTUM_ROUND4.md")) + "\n")
    print("\n".join(lines[-(len(passers) + 2):]))


if __name__ == "__main__":
    main()
