import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import test_training_selected_version as evaluation


def test_reservation_precedes_prices_and_failed_attempt_cannot_repeat(tmp_path,monkeypatch):
    monkeypatch.setattr(evaluation,"ROOT",tmp_path)
    monkeypatch.setattr(evaluation,"DIRECTORY",tmp_path)
    frozen = dict(parameters=dict(stop=25),test_partition=dict(dataset_version="fixed",path="never-open-before-reserve"))
    manifest = dict(candidate_hash="fixed-hash")
    monkeypatch.setattr(evaluation,"verify",lambda:(manifest,frozen))
    monkeypatch.setattr(evaluation.archive,"archived_execution",lambda folder:object())
    calls = []
    def load(*args,**kwargs):
        assert list((tmp_path/"data/manifests/reused_tests").glob("*.json"))
        calls.append(True)
        raise RuntimeError("synthetic failure")
    monkeypatch.setattr(evaluation,"load_dataset",load)
    with pytest.raises(RuntimeError,match="synthetic failure"):
        evaluation.evaluate()
    with pytest.raises(FileExistsError):
        evaluation.evaluate()
    assert len(calls) == 1
