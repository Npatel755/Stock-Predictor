"""Publish and verify a completed training-selected validation evaluation."""
import os
for key in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"):
    os.environ[key] = "1"
from datetime import datetime, timezone
import json
from pathlib import Path
import pandas as pd
import training_only_selection as selection
from quant_futures.config import digest,file_hash
from quant_futures.metrics import summarize
from quant_futures.research import json_write

ROOT = selection.ROOT


def main():
    report = selection.read(ROOT/"reports/training_selected_validation.json")
    study = selection.read(ROOT/"reports/training_only_selection.json")
    folder = Path(report["path"])
    manifest = selection.read(folder/"frozen_candidate.json")
    frozen = manifest["candidate"]
    assert digest(frozen) == manifest["candidate_hash"] == report["frozen_candidate_hash"]
    ranked = selection.read(folder/"training_ranking.json")
    attempts = selection.read(folder/"NQ_training_selection_attempts.json")
    assert file_hash(folder/"training_ranking.json") == frozen["training_ranking_sha256"]
    assert file_hash(folder/"NQ_training_selection_attempts.json") == frozen["training_results_sha256"]
    assert sorted(attempts,key=selection.rank,reverse=True) == ranked
    assert ranked[0]["candidate_id"] == report["candidate_id"]
    assert frozen["parameters"] == report["candidate"]
    assert report["selection_used_validation"] is False and report["selection_used_test"] is False
    assert report["validation_candidates_evaluated"] == report["validation_cost_cases"] == 1
    curve = pd.read_parquet(folder/"validation_equity.parquet")
    trades = pd.read_parquet(folder/"validation_trades.parquet")
    measured = summarize(dict(curve=curve,trades=trades),50000,trials=2048)
    for field in ("net_pnl","max_drawdown","max_intraday_drawdown_bound","trades"):
        assert measured[field] == report["metrics"][field]
    selected = study["selected"]
    m = report["metrics"]
    lines = ["# Training-selected candidate: one validation evaluation", "",
        f"**MNQ validation: ${m['net_pnl']:,.2f} net, ${m['max_drawdown']:,.2f} closing drawdown, ${m['max_intraday_drawdown_bound']:,.2f} intrabar drawdown, {m['trades']} trades.**", "",
        f"Candidate `{report['candidate_id']}` was selected by the fixed NQ training-only ranking, frozen, then evaluated once at base costs on actual MNQ 2024–2025. "
        "No validation or test metrics entered the selection procedure. No parameters were fitted or adjusted after this validation outcome. Test prices were not opened.", "",
        "This is not a fresh holdout: the inherited strategy design came from earlier validation-guided experiments, and 2024–2025 was already inspected. "
        "A new training-only ranking cannot erase that contamination. Fresh forward observations remain necessary for independent confirmation.", "",
        "## Selection procedure", "", study["protocol"]["design"], "",study["protocol"]["selection_rule"],"",
        f"Training-qualified candidates: {sum(row['training_qualified'] for row in ranked)} / {len(ranked)}. Selected candidate qualified: **{selected['training_qualified']}**. "
        "If no candidate qualified, the fixed procedure still selected the top-ranked diagnostic, as declared before evaluation; that does not make it a qualifying strategy.","",
        "Actual NQ dollars below reflect mini-contract economics and 10× micro risk budgets. They are not MNQ backtest results.","",
        "| Candidate | Base NQ net | Base DD | 2× NQ net | 2× DD | Base lock | 2× lock | Training qualified |",
        "|---|---:|---:|---:|---:|---|---|---|"]
    for row in ranked:
        b,s = row["base"],row["stress_2x"]
        lines.append(f"| {row['candidate_id']} | ${b['net_pnl']:,.2f} | ${b['max_drawdown']:,.2f} | ${s['net_pnl']:,.2f} | ${s['max_drawdown']:,.2f} | {b['permanent_risk_lock']} | {s['permanent_risk_lock']} | {row['training_qualified']} |")
    lines += ["", "## Frozen validation outcome", "",
        f"Parameters: `{json.dumps(report['candidate'],sort_keys=True)}`.","",
        f"Validation checks: `{json.dumps(report['checks'],sort_keys=True)}`.","",
        f"Annual net: `{json.dumps(m['annual_pnl'],sort_keys=True)}`.","",
        f"Session-bootstrap mean-return confidence interval: `{m['uncertainty']['mean_ci']}`. Multiple-testing diagnostic upper p-value: `{m['uncertainty']['multiple_testing_pvalue_upper']}`. "
        "Nominal confidence after extensive prior research does not establish a durable edge.","",
        "No validation-driven adjustment or alternate candidate will follow this result. No live execution is enabled.","",
        "[Dashboard](http://127.0.0.1:8511) · [Training audit](training_only_selection.json) · [Validation result](training_selected_validation.json)",""]
    (ROOT/"reports/TRAINING_SELECTED_VALIDATION.md").write_text("\n".join(lines),encoding="utf-8")
    json_write(ROOT/"reports/training_selection_verification.json",dict(passed=True,
        verified_at=datetime.now(timezone.utc).isoformat(),frozen_parameters_verified=True,
        rank_recomputed_using_only_training_results=True,full_curve_metrics_reconciled=True,
        validation_candidates_evaluated=1,test_prices_accessed=False,independent_confirmation=False,
        validation_result_sha256=file_hash(ROOT/"reports/training_selected_validation.json")))
    print(json.dumps(dict(verified=True,net=m["net_pnl"],drawdown=m["max_drawdown"],
        training_qualified=selected["training_qualified"],validation_checks=report["checks"])))


if __name__ == "__main__":
    main()
