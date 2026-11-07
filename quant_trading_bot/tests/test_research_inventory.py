from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from research_inventory import inventory


def test_reruns_and_other_markets_do_not_inflate_distinct_strategy_count(tmp_path):
    for name, market in (("mes_market_20260101", "MES"), ("mes_market_20260102", "MES"), ("mnq_market_20260103", "MNQ")):
        directory = tmp_path/"runs"/name
        directory.mkdir(parents=True)
        (directory/"experiment.json").write_text(json.dumps(dict(instrument=market, timeframe=5, synthetic=False)))
        (directory/"attempts.json").write_text(json.dumps([dict(candidate=dict(family="baseline", name="ema"), status="completed", metrics=dict(net_pnl=1))]))
    result = inventory(tmp_path)
    assert result["distinct_strategy_definitions"] == 1
    assert result["unique_parameter_configurations"] == 1
    assert result["unique_market_configuration_cases"] == 2
    assert result["completed_run_attempts"] == 3
    assert result["repeated_completed_attempts"] == 1


def test_execution_settings_are_distinct_configurations_but_not_new_definitions(tmp_path):
    for index, minute in enumerate((990, 1000, 990)):
        folder = tmp_path/"runs"/f"mes_market_2026010{index}"
        folder.mkdir(parents=True)
        (folder/"experiment.json").write_text(json.dumps(dict(instrument="MES", timeframe=15, synthetic=False,
            config=dict(execution=dict(session_flat_minute_et=minute)))))
        (folder/"attempts.json").write_text(json.dumps([dict(candidate=dict(family="baseline", name="ema"), status="completed")]))
    result = inventory(tmp_path)
    assert result["distinct_strategy_definitions"] == 1
    assert result["unique_parameter_configurations"] == 2
    assert result["unique_market_configuration_cases"] == 2
    assert result["completed_run_attempts"] == 3


def test_invalidated_engineering_runs_are_preserved_as_diagnostics(tmp_path):
    folder = tmp_path/"runs"/"gap_structure_minutes_20260101"
    folder.mkdir(parents=True)
    (folder/"ES_screen_attempts.json").write_text(json.dumps([dict(candidate=dict(name="gap_fade"))]))
    (folder/"interruption.json").write_text(json.dumps(dict(status="invalidated_engineering_diagnostic")))
    result = inventory(tmp_path)
    assert result["distinct_strategy_definitions"] == result["completed_run_attempts"] == 0
    assert result["failed_or_diagnostic_records"] == 1
