"""Risk-of-ruin Monte Carlo for the three paper candidates (training years only, 2020-2023 MES/MNQ).

For each candidate: run its sleeves with the exact research engine on the 2020-2023 training split (one $50k account
per calendar year, as in all prior reports), build the combined daily series (end-of-day equity change, intraday worst
excursion below the prior close), then draw stationary block-bootstrap paths (mean block 5 trading days) of 60, 120 and
250 trading days. A path breaches when (end-of-day peak - intraday worst) >= $2,000, mirroring the engine's funded rule.
Sensitivities keep the day-to-day dispersion and remove edge by shifting every day's P&L down: "half" = minus half the
training mean per day, "zero" = minus the full mean (the 2010-2019 unseen-years check showed gross edge roughly equal
to costs, so zero net edge is the planning case). Also reported: distribution of maximum drawdown (EOD peak to intraday
low) per path. Model-conditional estimates from 4 training years, not forecasts. 2024-2026 never loaded.
Output: reports/RISK_OF_RUIN_CANDIDATES.{json,md}.
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
from news_round1 import load  # noqa: E402

YEARS = [2020, 2021, 2022, 2023]
HORIZONS = (60, 120, 250)
PATHS = 20000
RNG = np.random.default_rng(20261108)


def daily_series(candidate):
    bars = {inst: load(inst, "train", "2019-12-01", "2024-01-01") for inst in ("MES", "MNQ")}
    days = []
    for y in YEARS:
        cut = np.datetime64(f"{y + 1}-01-01T00:00:00")
        curves = []
        for s in candidate["sleeves"]:
            c = ep.run_sleeve(s, bars[s["instrument"]], f"{y}-01-01T00:00:00+00:00")["curve"]
            keep = pd.DatetimeIndex(c.ts).tz_convert("UTC").tz_localize(None).to_numpy() < cut
            curves.append(c[keep].reset_index(drop=True))
        merged = ep.combine(curves)["equity"]
        worst = None
        for i, c in enumerate(curves):
            part = c[["ts", "worst"]].rename(columns={"worst": f"w{i}"})
            worst = part if worst is None else pd.merge(worst, part, on="ts", how="outer")
        worst = worst.sort_values("ts").ffill().fillna(ep.INITIAL_BALANCE)
        w = sum(worst[c] - ep.INITIAL_BALANCE for c in worst if c.startswith("w"))
        frame = pd.DataFrame(dict(ts=merged.ts, net=merged.net.to_numpy(), worst=w.to_numpy()))
        frame["date"] = frame.ts.dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
        eod = frame.groupby("date").net.last()
        prev = eod.shift(1).fillna(0.0)
        low = frame.groupby("date").worst.min()
        days.append(pd.DataFrame(dict(pnl=(eod - prev).to_numpy(), dip=(low - prev).to_numpy()), index=eod.index))
    return pd.concat(days)


def simulate(days, horizon, shift=0.0):
    pnl = days.pnl.to_numpy() - shift
    dip = np.minimum(days.dip.to_numpy() - shift, 0.0)
    n = len(pnl)
    p = 1.0 / 5.0
    breach = np.zeros(PATHS, dtype=bool)
    final = np.zeros(PATHS)
    maxdd = np.zeros(PATHS)
    for k in range(PATHS):
        idx = np.empty(horizon, dtype=np.int64)
        idx[0] = RNG.integers(n)
        for t in range(1, horizon):
            idx[t] = RNG.integers(n) if RNG.random() < p else (idx[t - 1] + 1) % n
        path = np.cumsum(pnl[idx])
        prev = np.r_[0.0, path[:-1]]
        peak = np.maximum.accumulate(np.r_[0.0, path])[:-1]
        dd = np.maximum(peak - (prev + dip[idx]), peak - path)
        maxdd[k] = dd.max()
        breach[k] = maxdd[k] >= 2000.0
        final[k] = path[-1]
    return dict(p_breach=round(float(breach.mean()), 4), median=round(float(np.median(final)), 0),
                p5=round(float(np.percentile(final, 5)), 0), p95=round(float(np.percentile(final, 95)), 0),
                maxdd_median=round(float(np.median(maxdd)), 0), maxdd_p95=round(float(np.percentile(maxdd, 95)), 0))


def main():
    out = {}
    for key, cand in ep.CANDIDATES.items():
        days = daily_series(cand)
        hist = dict(days=int(len(days)), mean_day=round(float(days.pnl.mean()), 2), sd_day=round(float(days.pnl.std()), 2),
                    worst_day=round(float(days.pnl.min()), 2), worst_dip=round(float(days.dip.min()), 2))
        mean = float(days.pnl.mean())
        out[key] = dict(label=cand["label"], history=hist, full={}, half={}, zero={})
        for h in HORIZONS:
            out[key]["full"][str(h)] = simulate(days, h, 0.0)
            out[key]["half"][str(h)] = simulate(days, h, 0.5 * mean)
            out[key]["zero"][str(h)] = simulate(days, h, mean)
        print(key, hist, out[key]["full"], out[key]["half"], out[key]["zero"], flush=True)
    json.dump(out, open(ROOT / "reports" / "RISK_OF_RUIN_CANDIDATES.json", "w"), indent=1)
    lines = ["# Risk of ruin, paper candidates (training years 2020-2023, block bootstrap)", "", __doc__.strip(), "",
             "| candidate | days | mean/day | sd/day | worst day | horizon | P(breach $2k) full | half edge | zero edge | median net full | 5th pct full | max DD median / p95 (full) | max DD p95 (zero) |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for key, r in out.items():
        h = r["history"]
        for hz in HORIZONS:
            f, hf, z = r["full"][str(hz)], r["half"][str(hz)], r["zero"][str(hz)]
            lines.append(f"| {r['label']} | {h['days']} | {h['mean_day']:+.0f} | {h['sd_day']:.0f} | {h['worst_day']:+.0f} | {hz}d | {f['p_breach']:.1%} | {hf['p_breach']:.1%} | {z['p_breach']:.1%} | {f['median']:+,.0f} | {f['p5']:+,.0f} | {f['maxdd_median']:,.0f} / {f['maxdd_p95']:,.0f} | {z['maxdd_p95']:,.0f} |")
    (ROOT / "reports" / "RISK_OF_RUIN_CANDIDATES.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[5:]))


if __name__ == "__main__":
    main()
