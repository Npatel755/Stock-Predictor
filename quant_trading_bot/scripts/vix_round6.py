"""Round 6 (pre-registered 2026-11-08): VIX regime filters on the six deployed sleeves (QC tutorial 58 "VIX predicts
stock index returns" -> adapted as a point-in-time regime gate, not as a return forecast).

Data: CBOE VIX_History.csv (free, research/external/). Point-in-time value for trade date D = VIX close of the prior
trading day (forward-filled over holidays); rolling percentiles use the prior 252 closes, excluding D-1 itself... i.e.
every number used on day D was printed before D's session opened.
Filters (fixed before running), applied as entry blocks on each sleeve through the news-round-1 harness:
  skip_vix_gt30      block when VIX(D-1) > 30
  skip_vix_lt15      block when VIX(D-1) < 15
  only_vix_top30     trade only when VIX(D-1) >= 70th pct of the prior 252 closes
  skip_vix_top10     block when VIX(D-1) >= 90th pct
  skip_vix_bottom20  block when VIX(D-1) <= 20th pct
  only_vix_falling   trade only when VIX(D-1) < SMA10 of VIX(D-2..D-11)
Train = ES/NQ 2010-2019 + MES/MNQ 2020-2023 at today's costs. Gate per sleeve: total > baseline, worst annual DD <=
baseline, >= 60% of years beat baseline. Passers get one 2024-2025 validation look. 2026 never loaded.
Output: reports/VIX_ROUND6.{json,md}; events.jsonl line.
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

FILTERS = ("baseline", "skip_vix_gt30", "skip_vix_lt15", "only_vix_top30", "skip_vix_top10", "skip_vix_bottom20", "only_vix_falling")
SLEEVES = {s["name"]: s for c in ep.CANDIDATES.values() for s in c["sleeves"]}

_vix = pd.read_csv(ROOT / "research" / "external" / "VIX_History.csv")
_vix["date"] = pd.to_datetime(_vix.DATE, format="%m/%d/%Y")
_vix = _vix.set_index("date").CLOSE.sort_index()
_prior = _vix.shift(1)                                    # value known before D's open
_rank = _vix.rolling(252).apply(lambda w: (w[:-1] <= w[-1]).mean(), raw=True).shift(1)  # pct rank of D-1 within prior 252
_sma10 = _vix.rolling(10).mean().shift(2)                 # SMA of D-2..D-11
FEAT = pd.DataFrame(dict(v=_prior, pct=_rank, sma=_sma10)).reindex(pd.date_range("2009-01-01", "2026-12-31")).ffill()


def blocked(variant, dates, decision):
    if variant == "baseline":
        return np.zeros(len(dates), bool)
    f = FEAT.reindex(pd.to_datetime(dates))
    v, pct, sma = f.v.to_numpy(), f.pct.to_numpy(), f.sma.to_numpy()
    rule = {"skip_vix_gt30": v > 30, "skip_vix_lt15": v < 15, "only_vix_top30": ~(pct >= 0.70),
            "skip_vix_top10": pct >= 0.90, "skip_vix_bottom20": pct <= 0.20, "only_vix_falling": ~(v < sma)}[variant]
    return np.nan_to_num(rule.astype(float), nan=0.0).astype(bool)


nr1.blocked = blocked


def summarize(res):
    nets = [r["net"] for r in res.values()]
    return dict(total=round(sum(nets), 2), pos_years=int(sum(n > 0 for n in nets)), worst_dd=max(r["dd"] for r in res.values()),
                trades=sum(r["trades"] for r in res.values()), years=res)


def main():
    out = dict(registered="2026-11-08", filters={}, validation={})
    cache = {}
    for inst, years in (("MES", nr1.TRAIN), ("MNQ", nr1.TRAIN_NQ)):
        for sym, y in years:
            cache[(sym, y)] = nr1.load(sym, "train", f"{y - 1}-12-01", f"{y + 1}-01-01")
        for name, cfg in SLEEVES.items():
            if cfg["instrument"] != inst:
                continue
            res = {f: summarize({str(y): nr1.run(cfg, cache[(s, y)], f"{y}-01-01", f) for s, y in years}) for f in FILTERS}
            base = res["baseline"]
            for f in FILTERS[1:]:
                v = res[f]
                beats = sum(v["years"][y]["net"] > base["years"][y]["net"] for y in v["years"])
                v["passed"] = bool(v["total"] > base["total"] and v["worst_dd"] <= base["worst_dd"] and beats >= 0.6 * len(v["years"]))
                v["beats"] = int(beats)
                print(name, f, "total", v["total"], "vs", base["total"], "dd", v["worst_dd"], "vs", base["worst_dd"], "beats", beats, "trades", v["trades"], "vs", base["trades"], "PASS" if v["passed"] else "", flush=True)
            out["filters"][name] = res
        cache.clear()
    passers = [f"{n}/{f}" for n, res in out["filters"].items() for f, v in res.items() if f != "baseline" and v["passed"]]
    for key in passers:
        name, f = key.split("/")
        inst = SLEEVES[name]["instrument"]
        res = {}
        for y in nr1.VALID[inst]:
            bars = nr1.load(inst, "validation", f"{y - 1}-12-01", f"{y + 1}-01-01")
            res[str(y)] = dict(filtered=nr1.run(SLEEVES[name], bars, f"{y}-01-01", f), baseline=nr1.run(SLEEVES[name], bars, f"{y}-01-01", "baseline"))
        out["validation"][key] = res
        print("VALIDATION", key, res, flush=True)
    json.dump(out, open(ROOT / "reports" / "VIX_ROUND6.json", "w"), indent=1, default=str)
    lines = ["# Round 6: VIX regime filters on the deployed sleeves", "", __doc__.strip(), "",
             "| sleeve | filter | total | baseline | worst DD | baseline DD | beats | trades | gate |", "|---|---|---|---|---|---|---|---|---|"]
    for name, res in out["filters"].items():
        base = res["baseline"]
        for f in FILTERS[1:]:
            v = res[f]
            lines.append(f"| {name} | {f} | {v['total']:+,.0f} | {base['total']:+,.0f} | {v['worst_dd']:,.0f} | {base['worst_dd']:,.0f} | {v['beats']}/{len(v['years'])} | {v['trades']}/{base['trades']} | {'PASS' if v['passed'] else 'fail'} |")
    lines += ["", f"Passers sent to validation: {passers or 'none'}", ""]
    for key, res in out["validation"].items():
        lines.append(f"- {key}: " + "; ".join(f"{y} filtered {r['filtered']['net']:+,.0f} ({r['filtered']['trades']} tr) vs baseline {r['baseline']['net']:+,.0f} ({r['baseline']['trades']} tr)" for y, r in res.items()))
    (ROOT / "reports" / "VIX_ROUND6.md").write_text("\n".join(lines) + "\n")
    with open(ROOT / "research" / "strategy_memory" / "events.jsonl", "a") as f:
        f.write(json.dumps(dict(ts=pd.Timestamp.now("UTC").isoformat(), experiment="vix_round6", kind="result", passers=passers, report="reports/VIX_ROUND6.md")) + "\n")
    print("\n".join(lines[-(len(passers) + 2):]))


if __name__ == "__main__":
    main()
