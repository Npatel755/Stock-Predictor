"""Verify and publish saved evaluation artifacts without rerunning the strategy."""
import os
for key in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"):
    os.environ[key] = "1"
from datetime import datetime, timezone
from pathlib import Path
import json
import numpy as np
import pandas as pd
from quant_futures.config import digest,file_hash
from quant_futures.metrics import summarize
from quant_futures.research import json_write

ROOT = Path(__file__).resolve().parents[1]


def main():
    report = json.loads((ROOT/"reports/saved_version_reused_test.json").read_text())
    folder = Path(report["path"])
    manifest = json.loads((folder/"frozen_candidate.json").read_text())
    frozen = manifest["candidate"]
    assert digest(frozen) == manifest["candidate_hash"] == report["frozen_candidate_hash"]
    assert file_hash(folder/"test_runner.py") == frozen["runner_sha256"]
    for filename,expected in frozen["strategy_hashes"].items():
        assert file_hash(folder/"strategy"/filename) == expected
    assert file_hash(frozen["original_reservation_path"]) == frozen["original_reservation_sha256"]
    assert file_hash(ROOT/"reports/final_candidate_test.json") == frozen["original_test_report_sha256"]
    curve = pd.read_parquet(folder/"test_equity.parquet")
    trades = pd.read_parquet(folder/"test_trades.parquet")
    measured = summarize(dict(curve=curve,trades=trades),50000,trials=2048)
    for key in ("net_pnl","max_drawdown","max_intraday_drawdown_bound","trades"):
        assert np.isclose(measured[key],report["metrics"][key],rtol=0,atol=1e-8)
    assert np.isclose(trades.net_pnl.sum(),measured["net_pnl"],rtol=0,atol=1e-8)
    assert report["no_tuning"] and report["parameter_variants_evaluated"] == report["cost_variants_evaluated"] == 1
    m = report["metrics"]
    lines = ["# Frozen saved-version test evaluation", "",
        f"Saved candidate `{report['candidate_id']}`: **${m['net_pnl']:,.2f} net / ${m['max_drawdown']:,.2f} closing drawdown / ${m['max_intraday_drawdown_bound']:,.2f} intrabar drawdown / {m['trades']} trades**.","",
        "The exact saved version that made $6,622 on reused 2024–2025 development data was frozen before test-price access. "
        "One base-cost replay was evaluated, without fitting, parameter changes, cost variants or tuning against the result.","",
        f"Test coverage: {report['coverage']['start']} through {report['coverage']['end']} UTC. "
        "The 2026 period had already been evaluated for an earlier strategy, so this is a disclosed reused-test diagnostic, not independent out-of-sample confirmation. "
        "The original consumed reservation and original test report remain byte-for-byte unchanged.","",
        "The frozen strategy lost money. It remained below the $2,000 closing/intrabar drawdown limits, but profitability and positive-confidence checks failed. "
        "No parameter adjustment or follow-up variant will use this test outcome. Future strategy selection must use training history; fresh independent confirmation requires untouched forward observations.","",
        f"Parameters: `{json.dumps(report['candidate_parameters'],sort_keys=True)}`.","",
        f"Checks: `{json.dumps(report['checks'],sort_keys=True)}`.","",
        "[Machine-readable outcome](saved_version_reused_test.json) · [Saved development candidates](SAVED_CANDIDATES.md) · [Charts](research_charts.html)",""]
    (ROOT/"reports/SAVED_VERSION_TEST.md").write_text("\n".join(lines),encoding="utf-8")
    receipt = dict(passed=True,verified_at=datetime.now(timezone.utc).isoformat(),
        verification_only_no_replay=True,frozen_source_and_parameters_verified=True,
        equity_and_trade_metrics_reconciled=True,original_test_artifacts_unchanged=True,
        one_parameter_version_one_cost_case=True,
        console_summary_error="The evaluation completed and persisted results before numpy-bool console JSON serialization failed. No simulation rerun performed.",
        report_sha256=file_hash(ROOT/"reports/saved_version_reused_test.json"),
        frozen_candidate_hash=manifest["candidate_hash"])
    json_write(ROOT/"reports/saved_version_test_verification.json",receipt)
    print(json.dumps(dict(verified=True,net=m["net_pnl"],drawdown=m["max_drawdown"],trades=m["trades"],replayed=False)))


if __name__ == "__main__":
    main()
