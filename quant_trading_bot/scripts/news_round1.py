"""News round 1 (pre-registered 2026-11-08): do scheduled US releases change the paper sleeves' results?

Calendar: research/news/official_calendar_2010_2026.csv (scheduled times only; see scripts/news_calendar_build.py).
Sleeves: the six distinct sleeve rules behind the three paper candidates (quant_futures.ensemble_paper.CANDIDATES).
Variants (all decided before running; a variant only removes entries, it never adds information):
  baseline          unchanged sleeve
  blackout_high_15  no new entry whose decision bar opens within +-15 min of a high-impact scheduled release
  blackout_high_30  same, +-30 min
  blackout_all_15   +-15 min around any scheduled release (high or medium)
  fomc_afternoon    no new entry at or after 12:00 ET on an FOMC statement day
  fomc_day          no new entry on an FOMC statement day
  nfp_cpi_day       no new entry on Employment Situation or CPI days
Data: TRAIN = ES/NQ 2010-2019 (never used to pick the sleeves) + MES/MNQ 2019/2020-2023 train split, run as annual
$50k accounts at today's engine costs (micro economics on mini prices). Gate, fixed in advance: a variant passes if
its total train net beats baseline AND its worst annual intrabar DD is no worse AND it beats baseline net in >= 60%
of train years. Passers only are then run once on the 2024-2025 validation split. 2026 is consumed and never loaded.
Output: reports/NEWS_ROUND1.{json,md}; an events.jsonl line in research/strategy_memory.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from quant_futures import ensemble_paper as ep  # noqa: E402
from quant_futures.data import canonical  # noqa: E402
from unseen_years_replication import STRICT  # noqa: E402

CATALOG = ROOT / "data" / ("catalog_vm.json" if (ROOT / "data" / "catalog_vm.json").exists() else "catalog.json")
CAL = pd.read_csv(ROOT / "research" / "news" / "official_calendar_2010_2026.csv")
VARIANTS = ["baseline", "blackout_high_15", "blackout_high_30", "blackout_all_15", "fomc_afternoon", "fomc_day", "nfp_cpi_day"]
TRAIN = [("ES", y) for y in range(2010, 2020)] + [("MES", y) for y in range(2020, 2024)]
TRAIN_NQ = [("NQ", y) for y in range(2010, 2020)] + [("MNQ", y) for y in range(2020, 2024)]
VALID = {"MES": [2024, 2025], "MNQ": [2024, 2025]}


def load(symbol, split, start, end):
    path = json.load(open(CATALOG))["instruments"][symbol]["splits"][split]["path"]
    con = duckdb.connect()
    try:
        frame = con.execute(STRICT, [str(path), start, end]).fetch_df()
    finally:
        con.close()
    frame = frame[frame.timestamp_utc.notna()].copy()
    frame["high"] = frame[["open", "high", "low", "close"]].max(axis=1)
    frame["low"] = frame[["open", "high", "low", "close"]].min(axis=1)
    frame["volume"] = frame.volume.round()
    frame["instrument"] = {"ES": "MES", "NQ": "MNQ"}.get(symbol, symbol)
    return canonical(frame)


def blocked(variant, dates, decision):
    """Boolean per bar: entry decisions blocked by the variant. dates = ET date strings, decision = ET minute of the entry bar open."""
    if variant == "baseline":
        return np.zeros(len(dates), bool)
    cal = CAL[CAL.date_et.isin(set(dates))]
    out = np.zeros(len(dates), bool)
    if variant.startswith("blackout"):
        width = int(variant.split("_")[-1])
        sub = cal if variant == "blackout_all_15" else cal[cal.impact == "high"]
        by_day = sub.groupby("date_et").minute_et.apply(np.array).to_dict()
        for i, (d, m) in enumerate(zip(dates, decision)):
            mins = by_day.get(d)
            if mins is not None and np.any(np.abs(mins - m) <= width):
                out[i] = True
        return out
    fams = {"fomc_afternoon": ["FOMC"], "fomc_day": ["FOMC"], "nfp_cpi_day": ["EMPLOYMENT", "CPI"]}[variant]
    days = set(cal[cal.family.isin(fams)].date_et)
    in_day = np.array([d in days for d in dates])
    return in_day & (decision >= 720) if variant == "fomc_afternoon" else in_day


def run(cfg, bars, start, variant):
    eng = ep.engine()
    data = eng["arrays"](bars)
    features = eng["features"](bars, int(cfg["lookback"]))
    raw = eng["signal_for"](cfg, features).astype(np.int8)
    local = bars.timestamp_utc.dt.tz_convert("America/New_York")
    decision = (local.dt.hour * 60 + local.dt.minute + 15).to_numpy()
    weekdays = local.dt.day_of_week.to_numpy() < 5
    block = blocked(variant, local.dt.strftime("%Y-%m-%d").to_numpy(), decision)
    signal = np.where((decision >= cfg["session_start"]) & (decision < cfg["session_end"]) & weekdays & ~block, raw, 0).astype(np.int8)
    first = int((bars.timestamp_utc < pd.Timestamp(start, tz="UTC")).sum())
    sliced = {k: np.ascontiguousarray(v[first:]) for k, v in data.items()}
    sliced["session"] = pd.factorize(sliced["session"], sort=False)[0].astype(np.int64)
    sliced["contract"] = pd.factorize(sliced["contract"], sort=False)[0].astype(np.int64)
    result = eng["execute"](sliced, signal[first:], np.ascontiguousarray(features["atr"][first:]), eng["execution_cfg"](cfg))
    net = float(result["cash"][-1] - 50000.0) if len(result["cash"]) else 0.0
    return dict(net=round(net, 2), dd=round(float(50000.0 - result["worst"].min()), 2) if len(result["worst"]) else 0.0,
                trades=int(len(result["trade_net"])), blocked_bars=int(block[first:].sum()))


def main():
    sleeves = {s["name"]: s for spec in ep.CANDIDATES.values() for s in spec["sleeves"]}
    out = dict(registered="2026-11-08", variants=VARIANTS, train={}, validation={}, verdict={})
    cache = {}
    for name, cfg in sleeves.items():
        years = TRAIN if cfg["instrument"] == "MES" else TRAIN_NQ
        out["train"][name] = {}
        for variant in VARIANTS:
            res = {}
            for sym, y in years:
                key = (sym, y)
                if key not in cache:
                    cache[key] = load(sym, "train", f"{y - 1}-12-01", f"{y + 1}-01-01")
                res[str(y)] = run(cfg, cache[key], f"{y}-01-01", variant)
            nets = [r["net"] for r in res.values()]
            out["train"][name][variant] = dict(years=res, total=round(sum(nets), 2), worst_dd=max(r["dd"] for r in res.values()),
                                               trades=sum(r["trades"] for r in res.values()))
        base = out["train"][name]["baseline"]
        for variant in VARIANTS[1:]:
            v = out["train"][name][variant]
            beats = sum(v["years"][y]["net"] > base["years"][y]["net"] for y in v["years"])
            passed = v["total"] > base["total"] and v["worst_dd"] <= base["worst_dd"] and beats >= 0.6 * len(v["years"])
            out["verdict"][f"{name}/{variant}"] = dict(passed=bool(passed), beats_years=int(beats), total_delta=round(v["total"] - base["total"], 2),
                                                        dd_delta=round(v["worst_dd"] - base["worst_dd"], 2))
        print(name, {v: (out["train"][name][v]["total"], out["train"][name][v]["worst_dd"]) for v in VARIANTS}, flush=True)
    passers = [k for k, v in out["verdict"].items() if v["passed"]]
    for key in passers:
        name, variant = key.split("/")
        cfg = sleeves[name]
        res = {}
        for y in VALID[cfg["instrument"]]:
            bars = load(cfg["instrument"], "validation", f"{y - 1}-12-01", f"{y + 1}-01-01")
            res[str(y)] = {v: run(cfg, bars, f"{y}-01-01", v) for v in ("baseline", variant)}
        out["validation"][key] = res
        print("VALIDATION", key, {y: (r["baseline"]["net"], r[variant]["net"]) for y, r in res.items()}, flush=True)
    (ROOT / "reports").mkdir(exist_ok=True)
    json.dump(out, open(ROOT / "reports" / "NEWS_ROUND1.json", "w"), indent=1, default=str)
    lines = ["# News round 1: scheduled-release filters on the paper sleeves", "",
             "Registered 2026-11-08 (protocol in scripts/news_round1.py). TRAIN = ES/NQ 2010-2019 + MES/MNQ 2020-2023, annual $50k accounts, today's costs. "
             "Gate: beats baseline total net, worst annual DD no worse, beats baseline in >= 60% of years. Passers get one 2024-2025 validation look. 2026 untouched.", "",
             "| sleeve | variant | train total | worst annual DD | trades | years beating baseline | gate |", "|---|---|---|---|---|---|---|"]
    for name in sleeves:
        for variant in VARIANTS:
            t = out["train"][name][variant]
            vd = out["verdict"].get(f"{name}/{variant}", {})
            lines.append(f"| {name} | {variant} | {t['total']:+,.0f} | {t['worst_dd']:,.0f} | {t['trades']} | "
                         f"{vd.get('beats_years', '-')}/{len(t['years'])} | {'PASS' if vd.get('passed') else ('baseline' if variant == 'baseline' else 'fail')} |")
    lines += ["", f"Passers sent to validation: {passers or 'none'}", ""]
    for key, res in out["validation"].items():
        variant = key.split("/")[1]
        lines.append(f"- {key}: " + ", ".join(f"{y} baseline {r['baseline']['net']:+,.0f} -> variant {r[variant]['net']:+,.0f}" for y, r in res.items()))
    (ROOT / "reports" / "NEWS_ROUND1.md").write_text("\n".join(lines) + "\n")
    with open(ROOT / "research" / "strategy_memory" / "events.jsonl", "a") as f:
        f.write(json.dumps(dict(ts=pd.Timestamp.utcnow().isoformat(), experiment="news_round1", kind="result",
                                passers=passers, report="reports/NEWS_ROUND1.md")) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
