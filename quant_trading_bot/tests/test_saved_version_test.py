from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import evaluate_saved_frozen_version as evaluation
import profit_drawdown_followup
import pareto_refinement_study
import neighborhood_refinement_study


@pytest.mark.parametrize("runner",[profit_drawdown_followup.main,pareto_refinement_study.main,neighborhood_refinement_study.main])
def test_validation_tuning_entrypoints_are_retired(runner):
    with pytest.raises(PermissionError,match="train"):
        runner()


def test_failed_frozen_attempt_reserves_before_prices_and_cannot_repeat(tmp_path,monkeypatch):
    monkeypatch.setattr(evaluation,"ROOT",tmp_path)
    frozen = dict(test_partition=dict(dataset_version="fixed-dataset",path="must-not-open"),parameters=dict(stop=30))
    manifest = dict(candidate_hash="fixed-candidate")
    monkeypatch.setattr(evaluation,"verify_freeze",lambda directory:(manifest,frozen))
    monkeypatch.setattr(evaluation,"archived_execution",lambda directory:object())
    prices_opened = []
    def fail_after_reservation(*args,**kwargs):
        assert list((tmp_path/"data/manifests/reused_tests").glob("*.json"))
        prices_opened.append(True)
        raise RuntimeError("simulated input failure")
    monkeypatch.setattr(evaluation,"load_dataset",fail_after_reservation)
    directory = tmp_path/"run"
    directory.mkdir()
    with pytest.raises(RuntimeError,match="simulated input failure"):
        evaluation.evaluate(directory)
    with pytest.raises(FileExistsError):
        evaluation.evaluate(directory)
    assert len(prices_opened) == 1
