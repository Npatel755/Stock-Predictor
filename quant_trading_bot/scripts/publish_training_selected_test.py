"""Verify saved split results and publish a comparison without simulation."""
import os
for key in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"):
    os.environ[key] = "1"
from datetime import datetime,timezone
import json
from pathlib import Path
import pandas as pd
from quant_futures.config import digest,file_hash
from quant_futures.metrics import summarize
from quant_futures.research import json_write

ROOT = Path(__file__).resolve().parents[1]


def main():
    test = json.loads((ROOT/"reports/training_selected_test.json").read_text())
    validation = json.loads((ROOT/"reports/training_selected_validation.json").read_text())
    folder = Path(test["path"])
    manifest = json.loads((folder/"frozen_candidate.json").read_text())
    frozen = manifest["candidate"]
    assert digest(frozen) == manifest["candidate_hash"] == test["frozen_candidate_hash"]
    assert test["candidate"] == validation["candidate"] == frozen["parameters"]
    assert test["training_freeze_hash"] == validation["frozen_candidate_hash"]
    assert file_hash(folder/"test_runner.py") == frozen["runner_sha256"]
    for filename,expected in frozen["strategy_hashes"].items():
        assert file_hash(folder/"strategy"/filename) == expected
    for path,expected in frozen["preserved_files"].items():
        assert file_hash(path) == expected
    curve = pd.read_parquet(folder/"test_equity.parquet")
    trades = pd.read_parquet(folder/"test_trades.parquet")
    metrics = summarize(dict(curve=curve,trades=trades),50000,trials=2048)
    for key in ("net_pnl","max_drawdown","max_intraday_drawdown_bound","trades"):
        assert metrics[key] == test["metrics"][key]
    assert abs(float(trades.net_pnl.sum())-metrics["net_pnl"]) < 1e-8
    assert test["parameter_variants_evaluated"] == test["cost_variants_evaluated"] == 1
    lines = ["# Frozen training-selected strategy: validation and test", "",
        f"Candidate `{test['candidate_id']}` used the exact same frozen parameters in both evaluations. No fitting or tuning used either outcome.","",
        "| Period | Net P&L | Closing DD | Intrabar DD | Trades | Permanent shutdown |",
        "|---|---:|---:|---:|---:|---|"]
    for label,result in (("Validation: 2024–2025",validation),("Testing: 2026",test)):
        m = result["metrics"]
        lines.append(f"| {label} | ${m['net_pnl']:,.2f} | ${m['max_drawdown']:,.2f} | ${m['max_intraday_drawdown_bound']:,.2f} | {m['trades']} | {m['permanent_risk_lock']} |")
    lines += ["", "The strategy lost $126 in the test evaluation. It remained under the $2,000 closing/intrabar drawdown ceilings but failed profitability and positive-confidence checks. "
        "The positive validation result did not carry over to test profitability. No adjustments, cost variants or alternate candidates followed this test result.","",
        f"Test coverage: {test['coverage']['start']} through {test['coverage']['end']} UTC. "
        "The 2026 testing period was already used for earlier strategies, and the 2024–2025 validation period was previously observed. "
        "Neither is fresh independent confirmation. The new ranking used NQ training results only, but inherited design contamination and the training-consistency failure remain disclosed.","",
        "The existing validation evaluation was preserved without replay. Earlier test reports, reservations and validation artifacts remain byte-identical. "
        "A new exclusive reservation was written before reading test prices; failure would also have consumed this version's attempt.","",
        f"Frozen parameters: `{json.dumps(test['candidate'],sort_keys=True)}`.","",
        f"Test checks: `{json.dumps(test['checks'],sort_keys=True)}`.","",
        f"Test session-bootstrap confidence interval for mean daily return: `{test['metrics']['uncertainty']['mean_ci']}`.","",
        "No strategy is enabled for live trading. Fresh forward observations are needed for independent confirmation.","",
        "[Training selection audit](TRAINING_SELECTED_VALIDATION.md) · [Validation result](training_selected_validation.json) · [Test result](training_selected_test.json) · [Dashboard](http://127.0.0.1:8511)",""]
    (ROOT/"reports/TRAINING_SELECTED_SPLITS.md").write_text("\n".join(lines),encoding="utf-8")
    json_write(ROOT/"reports/training_selected_test_verification.json",dict(passed=True,
        verified_at=datetime.now(timezone.utc).isoformat(),verification_only_no_replay=True,
        exact_parameters_match_training_and_validation=True,source_archive_verified=True,
        saved_curve_and_trade_metrics_reconciled=True,prior_artifacts_preserved=True,
        validation_replayed=False,test_parameter_versions=1,test_cost_cases=1,
        independent_confirmation=False,report_sha256=file_hash(ROOT/"reports/training_selected_test.json")))
    print(json.dumps(dict(verified=True,validation_net=validation["metrics"]["net_pnl"],test_net=test["metrics"]["net_pnl"],simulation_replayed=False)))


if __name__ == "__main__":
    main()
