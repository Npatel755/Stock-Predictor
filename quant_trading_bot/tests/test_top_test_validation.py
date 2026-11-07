from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import evaluate_top_test_validation as study


def test_validation_role_guard_rejects_other_splits():
    valid=dict(split_role='validation',instrument='MNQ',synthetic=False,raw_contract_prices=True)
    study.check_metadata(valid)
    for changes in ({'split_role':'test'},{'split_role':'train'},{'synthetic':True},{'instrument':'NQ'}):
        with pytest.raises(PermissionError): study.check_metadata(dict(valid,**changes))


def test_exclusive_candidate_validation_reservation(tmp_path,monkeypatch):
    monkeypatch.setattr(study,'ROOT',tmp_path)
    frozen=dict(parameters={'lookback':8},validation_partition={'dataset_version':'fixture'})
    path=study.reserve({'candidate_hash':'original'},frozen);original=path.read_bytes()
    with pytest.raises(FileExistsError): study.reserve({'candidate_hash':'second'},frozen)
    assert path.read_bytes()==original
