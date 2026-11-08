"""Pre-registered check of the three paper candidates on ES/NQ 2010-2019, years their sleeves never saw.

Registered 2026-11-08 before any run. Every sleeve was picked by mass searches trained on MES/MNQ
2019/2020-2023; ES/NQ 2010-2019 was never used to pick them. ES/NQ carry the same index prices as
MES/MNQ, so each sleeve runs on the mini series with micro economics (tick 0.25, $5 / $2 per point).

H1 Each sleeve keeps a positive gross (frictionless) R/yr on 2010-2019.
H2 Today's tick/fee costs were a 4-6x larger share of an ATR stop at 2010s price levels, so friction is
   also restated to the 2020 price level (engine cost factor = median close of the year / median close
   of 2020) as the fair comparison.
H3 The MES momentum sleeve (in all three candidates) is the weakest leg out of sample and the MNQ
   volatility / e57 legs the strongest (Claude round 6 on the same data, 2026-11-08).

Variants: today (engine costs unchanged), restated (factor as above), gross (no commission, slippage,
spread or impact). Bar rules: strict (all 15 source minutes, the research rule) and lenient (>= 1
minute) because Databento omits untraded minutes and early-NQ overnight buckets fail the strict rule.
Annual $50k accounts; lock state resets each year. Outputs reports/UNSEEN_YEARS_2010_2019.{json,md}.
Nothing here touches 2024-2026 data.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from quant_futures import ensemble_paper as ep  # noqa: E402
from quant_futures.data import canonical  # noqa: E402

CATALOG = ROOT / "data" / ("catalog_vm.json" if (ROOT / "data" / "catalog_vm.json").exists() else "catalog.json")
YEARS = list(range(2010, 2020))
MINI = {"MES": "ES", "MNQ": "NQ"}
SELECT = """SELECT time_bucket(INTERVAL '15 minutes', CAST(timestamp_utc AS TIMESTAMPTZ)) AS timestamp_utc,
    instrument, contract, session_id, arg_min(open,timestamp_utc) AS open, max(high) AS high, min(low) AS low,
    arg_max(close,timestamp_utc) AS close, sum(volume)::DOUBLE AS volume
    FROM read_parquet(?) WHERE timestamp_utc >= ? AND timestamp_utc < ? GROUP BY 1,instrument,contract,session_id """
STRICT = SELECT + """HAVING COUNT(*)=15 AND COUNT(DISTINCT timestamp_utc)=15
    AND MIN(CAST(timestamp_utc AS TIMESTAMPTZ))=time_bucket(INTERVAL '15 minutes',MIN(CAST(timestamp_utc AS TIMESTAMPTZ)))
    AND MAX(CAST(timestamp_utc AS TIMESTAMPTZ))-MIN(CAST(timestamp_utc AS TIMESTAMPTZ))=INTERVAL '14 minutes' ORDER BY 1"""
LENIENT = SELECT + "ORDER BY 1"


def load(mini, start, end, rule):
    path = json.load(open(CATALOG))["instruments"][mini]["splits"]["train"]["path"]
    con = duckdb.connect()
    try:
        frame = con.execute(STRICT if rule == "strict" else LENIENT, [str(path), start, end]).fetch_df()
    finally:
        con.close()
    frame = frame[frame.timestamp_utc.notna()].copy()
    frame["high"] = frame[["open", "high", "low", "close"]].max(axis=1)
    frame["low"] = frame[["open", "high", "low", "close"]].min(axis=1)
    frame["volume"] = frame.volume.round()
    frame["instrument"] = {"ES": "MES", "NQ": "MNQ"}[mini]
    return canonical(frame)


def run_sleeve(cfg, bars, start, variant, factor):
    eng = ep.engine()
    data = eng["arrays"](bars)
    features = eng["features"](bars, int(cfg["lookback"]))
    raw = eng["signal_for"](cfg, features).astype(np.int8)
    local = bars.timestamp_utc.dt.tz_convert("America/New_York")
    decision = (local.dt.hour * 60 + local.dt.minute + 15).to_numpy()
    weekdays = local.dt.day_of_week.to_numpy() < 5
    signal = np.where((decision >= cfg["session_start"]) & (decision < cfg["session_end"]) & weekdays, raw, 0).astype(np.int8)
    first = int((bars.timestamp_utc < pd.Timestamp(start, tz="UTC")).sum())
    sliced = {k: np.ascontiguousarray(v[first:]) for k, v in data.items()}
    sliced["session"] = pd.factorize(sliced["session"], sort=False)[0].astype(np.int64)
    sliced["contract"] = pd.factorize(sliced["contract"], sort=False)[0].astype(np.int64)
    ecfg = eng["execution_cfg"](cfg)
    if variant == "gross":
        ecfg.update(commission_per_side=0.0, slippage_ticks=0.0, spread_ticks=0.0, impact_ticks=0.0)
    elif variant == "restated":
        ecfg["factor"] = float(factor)
    result = eng["execute"](sliced, signal[first:], np.ascontiguousarray(features["atr"][first:]), ecfg)
    stamps = pd.to_datetime(sliced["timestamp"], unit="ns", utc=True)
    curve = pd.DataFrame(dict(ts=stamps, cash=result["cash"], equity=result["equity"], worst=result["worst"]))
    net = float(result["cash"][-1] - 50000.0) if len(stamps) else 0.0
    return dict(net=round(net, 2), trades=int(len(result["trade_net"])), r=round(net / (150.0 * int(cfg["max_contracts"])), 2),
                lock=result["lock_reason"], curve=curve)


def main():
    sleeves = {s["name"]: s for spec in ep.CANDIDATES.values() for s in spec["sleeves"]}
    out = dict(registered="2026-11-08", years=YEARS, sleeves={}, ensembles={}, bars={})
    for rule in ("strict", "lenient"):
        bars, price_2020 = {}, {}
        for mini in ("ES", "NQ"):
            ref = load(mini, "2020-01-01", "2021-01-01", rule)
            price_2020[mini] = float(ref.close.median())
            for year in YEARS:
                bars[(mini, year)] = load(mini, f"{year - 1}-12-01", f"{year + 1}-01-01", rule)
                out["bars"][f"{rule}/{mini}/{year}"] = int((bars[(mini, year)].timestamp_utc.dt.year == year).sum())
            print(rule, mini, "loaded", flush=True)
        rows = {}
        for name, cfg in sleeves.items():
            mini = MINI[cfg["instrument"]]
            rows[name] = {}
            for variant in ("today", "restated", "gross"):
                rows[name][variant] = {}
                for year in YEARS:
                    b = bars[(mini, year)]
                    yr = b[b.timestamp_utc.dt.year == year]
                    factor = float(yr.close.median()) / price_2020[mini] if len(yr) else 1.0
                    rows[name][variant][year] = dict(run_sleeve(cfg, b, f"{year}-01-01", variant, factor), factor=round(factor, 3))
                nets = [rows[name][variant][y]["net"] for y in YEARS]
                out["sleeves"].setdefault(f"{rule}/{name}", {})[variant] = dict(
                    years={str(y): {k: v for k, v in rows[name][variant][y].items() if k != "curve"} for y in YEARS},
                    total=round(sum(nets), 2), years_positive=int(sum(n > 0 for n in nets)),
                    r_per_year=round(sum(rows[name][variant][y]["r"] for y in YEARS) / len(YEARS), 2),
                    trades_per_year=round(sum(rows[name][variant][y]["trades"] for y in YEARS) / len(YEARS), 1))
            print(rule, name, {v: (out["sleeves"][f"{rule}/{name}"][v]["r_per_year"], out["sleeves"][f"{rule}/{name}"][v]["years_positive"]) for v in ("today", "restated", "gross")}, flush=True)
        for key, spec in ep.CANDIDATES.items():
            out["ensembles"][f"{rule}/{key}"] = {}
            for variant in ("today", "restated", "gross"):
                years = {}
                for year in YEARS:
                    comb = ep.combine([rows[s["name"]][variant][year]["curve"] for s in spec["sleeves"]])
                    years[str(year)] = dict(net=comb["net"], intrabar_dd=comb["intrabar_drawdown"], breach=bool(comb["intrabar_drawdown"] >= 2000.0))
                nets = [r["net"] for r in years.values()]
                out["ensembles"][f"{rule}/{key}"][variant] = dict(years=years, total=round(sum(nets), 2), years_positive=int(sum(n > 0 for n in nets)),
                                                                breach_years=int(sum(r["breach"] for r in years.values())),
                                                                worst_dd=max(r["intrabar_dd"] for r in years.values()))
            print(rule, key, {v: (d["total"], d["years_positive"], d["breach_years"]) for v, d in out["ensembles"][f"{rule}/{key}"].items()}, flush=True)
    (ROOT / "reports").mkdir(exist_ok=True)
    json.dump(out, open(ROOT / "reports" / "UNSEEN_YEARS_2010_2019.json", "w"), indent=1, default=str)
    lines = ["# Paper candidates on ES/NQ 2010-2019 (years never used to pick them)", "",
             "Registered 2026-11-08; protocol in scripts/unseen_years_replication.py. Annual $50k accounts, micro economics on mini prices, lock state reset yearly.", "",
             "| bars | ensemble | today: total / yrs+ / $2k breaches | restated-to-2020 friction | gross (no costs) | worst annual intrabar DD (today) |", "|---|---|---|---|---|---|"]
    for k, s in out["ensembles"].items():
        rule, key = k.split("/")
        lines.append(f"| {rule} | {key} | {s['today']['total']:+,.0f} / {s['today']['years_positive']}/10 / {s['today']['breach_years']} | "
                     f"{s['restated']['total']:+,.0f} / {s['restated']['years_positive']}/10 / {s['restated']['breach_years']} | "
                     f"{s['gross']['total']:+,.0f} / {s['gross']['years_positive']}/10 | {s['today']['worst_dd']:,.0f} |")
    lines += ["", "| bars | sleeve | today R/yr (yrs+) | restated R/yr (yrs+) | gross R/yr (yrs+) | trades/yr |", "|---|---|---|---|---|---|"]
    for k, s in out["sleeves"].items():
        rule, name = k.split("/")
        t, r, g = s["today"], s["restated"], s["gross"]
        lines.append(f"| {rule} | {name} | {t['r_per_year']:+.1f} ({t['years_positive']}) | {r['r_per_year']:+.1f} ({r['years_positive']}) | {g['r_per_year']:+.1f} ({g['years_positive']}) | {t['trades_per_year']} |")
    (ROOT / "reports" / "UNSEEN_YEARS_2010_2019.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
