import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import evaluate_e57_refined_splits as runner


def test_exclusive_validation_reservation_prevents_repeat(tmp_path,monkeypatch):
    monkeypatch.setattr(runner,'ROOT',tmp_path)
    frozen=dict(parameters={'config_id':runner.ID,'risk_scale':1.0},partitions={'validation':{'partition':{'dataset_version':'v'}}})
    manifest=dict(candidate_hash='frozen')
    path,_=runner.reserve('validation',manifest,frozen);original=path.read_bytes()
    with pytest.raises(FileExistsError):runner.reserve('validation',manifest,frozen)
    assert path.read_bytes()==original


def test_test_requires_completed_unchanged_validation(tmp_path,monkeypatch):
    monkeypatch.setattr(runner,'DIRECTORY',tmp_path);monkeypatch.setattr(runner,'ROOT',tmp_path)
    frozen=dict(parameters={'config_id':runner.ID},partitions={'test':{'partition':{'dataset_version':'t'}}})
    with pytest.raises(FileNotFoundError):runner.reserve('test',dict(candidate_hash='h'),frozen)
    record=dict(frozen_candidate_hash='h',parameters=frozen['parameters'])
    (tmp_path/'validation_result.json').write_text(json.dumps(record))
    (tmp_path/'validation_complete.json').write_text(json.dumps(dict(result_sha256='tampered_hash')))
    with pytest.raises(ValueError):runner.reserve('test',dict(candidate_hash='h'),frozen)
    assert not (tmp_path/'data/manifests/reused_tests').exists()
