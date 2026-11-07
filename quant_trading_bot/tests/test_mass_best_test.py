from pathlib import Path
import sys
import json
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import evaluate_mass_best_test as study


def test_exclusive_reservation_prevents_repeated_evaluation(tmp_path,monkeypatch):
    monkeypatch.setattr(study,'ROOT',tmp_path)
    frozen=dict(parameters={'lookback':8},test_partition={'dataset_version':'fixture'})
    first=study.reserve({'candidate_hash':'frozen'},frozen)
    original=first.read_bytes()
    with pytest.raises(FileExistsError): study.reserve({'candidate_hash':'another-runner'},frozen)
    assert first.read_bytes()==original
    assert json.loads(original)['failure_consumes_reservation']


def test_existing_reservation_blocks_before_loading_test_prices(tmp_path,monkeypatch):
    monkeypatch.setattr(study,'ROOT',tmp_path)
    monkeypatch.setattr(study,'DIRECTORY',tmp_path/'evaluation')
    frozen=dict(parameters={'lookback':8},test_partition={'dataset_version':'fixture'})
    manifest={'candidate_hash':'frozen'}
    study.reserve(manifest,frozen)
    monkeypatch.setattr(study,'verify',lambda:(manifest,frozen))
    def forbidden(*args): raise AssertionError('Test prices must not be loaded twice')
    monkeypatch.setattr(study,'load_test',forbidden)
    monkeypatch.setattr(study,'archived_execution',forbidden)
    with pytest.raises(FileExistsError): study.evaluate()
