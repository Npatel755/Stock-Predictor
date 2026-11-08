"""One-use protection and validation-before-test guards, without market data."""
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import evaluate_collaborative_top5_splits as runner


def fixture_cohort(tmp_path,monkeypatch):
    folder=tmp_path/'evaluation';folder.mkdir()
    monkeypatch.setattr(runner,'ROOT',tmp_path)
    monkeypatch.setattr(runner,'DIRECTORY',folder)
    candidates=[dict(candidate_id=cid,parameters={'config_id':cid,'max_contracts':2}) for cid in runner.IDS]
    frozen=dict(candidates=candidates,partitions={p:dict(partition=dict(dataset_version=p+'_v1')) for p in runner.PHASES})
    return folder,dict(cohort_hash='frozen_hash'),frozen


def test_repeated_stage_cannot_reserve_again(tmp_path,monkeypatch):
    folder,manifest,frozen=fixture_cohort(tmp_path,monkeypatch)
    reservations,_=runner.reserve_phase('validation',manifest,frozen)
    assert len(reservations)==5
    original={p:Path(p).read_bytes() for p in reservations.values()}
    with pytest.raises(FileExistsError): runner.reserve_phase('validation',manifest,frozen)
    assert all(Path(p).read_bytes()==v for p,v in original.items())


def test_test_cannot_reserve_before_all_validation_results(tmp_path,monkeypatch):
    folder,manifest,frozen=fixture_cohort(tmp_path,monkeypatch)
    with pytest.raises(FileNotFoundError): runner.reserve_phase('test',manifest,frozen)
    assert not (folder/'test_reservation.json').exists()


def test_changed_validation_result_blocks_test_before_reservation(tmp_path,monkeypatch):
    folder,manifest,frozen=fixture_cohort(tmp_path,monkeypatch)
    hashes={}
    for c in frozen['candidates']:
        p=runner.case_path(c,'validation')
        p.write_text(json.dumps(dict(cohort_hash=manifest['cohort_hash'],parameters=c['parameters'])))
        hashes[str(p)]=runner.file_hash(p)
    (folder/'validation_complete.json').write_text(json.dumps(dict(cohort_hash=manifest['cohort_hash'],all_five_completed=True,result_hashes=hashes)))
    candidate=frozen['candidates'][0]
    record=runner.read(runner.case_path(candidate,'validation')); record['parameters']['max_contracts']=3
    runner.case_path(candidate,'validation').write_text(json.dumps(record))
    with pytest.raises(ValueError): runner.reserve_phase('test',manifest,frozen)
    assert not (folder/'test_reservation.json').exists()
