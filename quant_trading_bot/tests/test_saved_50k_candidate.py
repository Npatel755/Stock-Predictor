from pathlib import Path
import sys
import json
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import evaluate_saved_50k_candidate as study


def test_split_role_is_exact():
    m=dict(split_role='validation',instrument='MNQ',synthetic=False,raw_contract_prices=True)
    study.check_meta(m,'validation')
    with pytest.raises(PermissionError): study.check_meta(m,'test')
    with pytest.raises(PermissionError): study.check_meta(dict(m,split_role='train'),'validation')


def test_test_requires_validation_and_each_stage_is_single_use(tmp_path,monkeypatch):
    monkeypatch.setattr(study,'ROOT',tmp_path);monkeypatch.setattr(study,'DIRECTORY',tmp_path/'run');study.DIRECTORY.mkdir()
    f=dict(parameters={'lookback':8},partitions={p:{'partition':{'dataset_version':p}} for p in ('validation','test')})
    manifest={'candidate_hash':'frozen'}
    with pytest.raises(FileNotFoundError): study.reserve('test',manifest,f)
    p=study.reserve('validation',manifest,f);before=p.read_bytes()
    with pytest.raises(FileExistsError): study.reserve('validation',manifest,f)
    assert p.read_bytes()==before
    (study.DIRECTORY/'validation_result.json').write_text(json.dumps(dict(frozen_candidate_hash='frozen',parameters=f['parameters'])))
    p=study.reserve('test',manifest,f)
    assert json.loads(p.read_text())['phase']=='test'
    with pytest.raises(FileExistsError): study.reserve('test',manifest,f)
