from pathlib import Path
import sys
import json
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import evaluate_scaled_200k_candidate as study


def test_split_role_is_exact():
    m = dict(split_role='validation', instrument='MNQ', synthetic=False, raw_contract_prices=True)
    study.check_meta(m, 'validation')
    with pytest.raises(PermissionError):
        study.check_meta(m, 'test')
    with pytest.raises(PermissionError):
        study.check_meta(dict(m, split_role='train'), 'validation')
    with pytest.raises(PermissionError):
        study.check_meta(dict(m, instrument='NQ'), 'validation')


def test_test_requires_validation_and_each_stage_is_single_use(tmp_path, monkeypatch):
    monkeypatch.setattr(study, 'ROOT', tmp_path)
    monkeypatch.setattr(study, 'DIRECTORY', tmp_path/'run')
    study.DIRECTORY.mkdir()
    f = dict(
        candidate_id=study.ID,
        parameters={'lookback': 8, 'max_contracts': 2, 'risk_per_trade': 300},
        partitions={p: {'partition': {'dataset_version': p}} for p in ('validation', 'test')}
    )
    manifest = {'candidate_hash': 'frozen_scaled'}
    
    # Attempting test before validation must fail
    with pytest.raises(FileNotFoundError):
        study.reserve('test', manifest, f)
        
    # Validation reservation succeeds
    p_val = study.reserve('validation', manifest, f)
    assert p_val.exists()
    val_bytes = p_val.read_bytes()
    
    # Attempting validation a second time must fail
    with pytest.raises(FileExistsError):
        study.reserve('validation', manifest, f)
    assert p_val.read_bytes() == val_bytes
    
    # Create fake validation result
    val_res = dict(frozen_candidate_hash='frozen_scaled', parameters=f['parameters'])
    (study.DIRECTORY/'validation_result.json').write_text(json.dumps(val_res), encoding='utf-8')
    
    # Now test reservation succeeds
    p_test = study.reserve('test', manifest, f)
    assert p_test.exists()
    assert json.loads(p_test.read_text(encoding='utf-8'))['phase'] == 'test'
    
    # Attempting test a second time must fail
    with pytest.raises(FileExistsError):
        study.reserve('test', manifest, f)
