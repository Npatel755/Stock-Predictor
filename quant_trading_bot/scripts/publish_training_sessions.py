"""Verify and describe completed training-only session research; no market replay."""
import os
for key in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"):
    os.environ[key] = "1"
from datetime import datetime,timezone
import json
import argparse
from pathlib import Path
import pandas as pd
import training_session_research as study
from quant_futures.config import file_hash,digest
from quant_futures.research import json_write
from quant_futures.metrics import summarize

ROOT = study.ROOT


def main(kind="opening"):
    afternoon = kind == "afternoon"
    stem = "training_afternoon" if afternoon else "training_session"
    filename = "TRAINING_AFTERNOON_RESEARCH.md" if afternoon else "TRAINING_SESSION_RESEARCH.md"
    report = json.loads((ROOT/"reports"/(stem+"_research.json")).read_text())
    folder = Path(report["path"])
    protocol = report["protocol"]
    if afternoon:
        for filename_,expected in protocol["script_hashes"].items():
            assert file_hash(folder/filename_) == expected
        assert file_hash(protocol["training_cache"]) == protocol["training_cache_sha256"]
    else:
        assert file_hash(folder/"training_session_research.py") == protocol["script_hash"]
        assert file_hash(folder/"overnight_study.py") == protocol["session_loader_hash"]
    assert report["validation_prices_accessed"] is report["test_prices_accessed"] is False
    assert len(protocol["candidates"]) == report["training_cases"] == 24
    attempts = json.loads((folder/"NQ_training_attempts.json").read_text())
    shortlisted = json.loads((folder/"frozen_training_shortlist.json").read_text())["candidates"]
    ranks = [dict(candidate_id=r["candidate_id"],candidate=r["candidate"],base=r["blocks"]) for r in attempts]
    assert [r["candidate_id"] for r in sorted(ranks,key=study.rank,reverse=True)[:4]] == [r["candidate_id"] for r in shortlisted]
    selected = report["selected"]
    if selected:
        manifest = json.loads((folder/"frozen_candidate.json").read_text())
        assert digest(manifest["candidate"]) == manifest["candidate_hash"]
        assert manifest["candidate"]["parameters"] == selected["candidate"]
        for label,_,_ in study.BLOCKS:
            curve = pd.read_parquet(folder/f"selected_{label}_equity.parquet")
            trades = pd.read_parquet(folder/f"selected_{label}_trades.parquet")
            measured = summarize(dict(curve=curve,trades=trades),500000,trials=24)
            for key in ("net_pnl","max_drawdown","max_intraday_drawdown_bound","trades"):
                assert measured[key] == selected["base"][label][key]
    status = (f"A training-qualified candidate was frozen: `{selected['candidate_id']}`." if selected else
              "No candidate passed every declared base/2× training check. No candidate was promoted.")
    lines = ["# Training-only "+("afternoon" if afternoon else "opening-session")+" strategy research", "",status,"",
        "This batch never opened validation or test prices. It compared 24 prespecified settings across three chronological blocks inside the NQ training split. "
        "The highest-ranked four base cases were frozen before doubled-cost training replays. No validation/test result was used by this selection code.","",
        protocol["design"],"",protocol["selection"],"",
        "All P&L below uses actual NQ mini-contract economics. The $20,000 rejection ceiling corresponds to explicitly scaled training risk budgets; it is not a measured $2,000 MNQ result. "
        "Each block resets capital and risk separately, so totals across blocks are attribution sums, not a continuous 2010–2023 account curve.","",
        "## All base training cases", "",
        "| Candidate | Rule | Long only | Stop "+("ATR multiple" if afternoon else "range fraction")+" | Target | 2010–2015 net | 2016–2019 net | 2020–2023 net | Profitable blocks | Risk shutdowns |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in sorted(ranks,key=study.rank,reverse=True):
        c = r["candidate"]
        values = [r["base"][label]["net_pnl"] for label,_,_ in study.BLOCKS]
        locks = sum(m["permanent_risk_lock"] for m in r["base"].values())
        lines.append(f"| {r['candidate_id']} | {c['name']} | {c['long_only']} | {c.get('atr_multiple',c.get('stop_fraction'))} | {c['payoff']} | ${values[0]:,.2f} | ${values[1]:,.2f} | ${values[2]:,.2f} | {sum(v>0 for v in values)} | {locks} |")
    lines += ["", "## Shortlisted doubled-cost training results", "",
        "| Candidate | Block | Base net | Base close DD | 2× net | 2× close DD | 2× intrabar DD | 2× risk shutdown | Qualified across blocks |",
        "|---|---|---:|---:|---:|---:|---:|---|---|"]
    for r in report["shortlist"]:
        for label,_,_ in study.BLOCKS:
            b,s = r["base"][label],r["stress_2x"][label]
            lines.append(f"| {r['candidate_id']} | {label} | ${b['net_pnl']:,.2f} | ${b['max_drawdown']:,.2f} | ${s['net_pnl']:,.2f} | ${s['max_drawdown']:,.2f} | ${s['max_intraday_drawdown_bound']:,.2f} | {s['permanent_risk_lock']} | {r['qualified']} |")
    lines += ["", "## Interpretation", "",protocol["limitations"],"",
        "Historical training qualification is not deployment eligibility. This batch does not authorize another validation/test search. "
        "A training failure remains a failure; it is not repaired by choosing a candidate on the later splits.","",
        f"Run artifacts: `{folder}`. [Machine-readable research]({stem}_research.json) · [Dashboard](http://127.0.0.1:8511)",""]
    (ROOT/"reports"/filename).write_text("\n".join(lines),encoding="utf-8")
    receipt = dict(passed=True,verified_at=datetime.now(timezone.utc).isoformat(),
        protocol_and_source_snapshots_verified=True,training_shortlist_rank_verified=True,
        selected_curve_metrics_verified=selected is not None,validation_prices_accessed=False,test_prices_accessed=False,
        qualified_candidates=report["qualified_candidates"],strategy_replayed=False,
        report_sha256=file_hash(ROOT/"reports"/(stem+"_research.json")))
    json_write(ROOT/"reports"/(stem+"_verification.json"),receipt)
    print(json.dumps(dict(verified=True,qualified=report["qualified_candidates"],selected=None if selected is None else selected["candidate_id"])))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind",choices=("opening","afternoon"),default="opening")
    args = parser.parse_args()
    main(args.kind)
