from pathlib import Path
import sys
import sqlite3
import json
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import evaluate_positive_training_cohort as study


def test_exact_user_filters_do_not_add_other_gates():
    row=dict(net_pnl=1,max_drawdown=1999.99,realized_drawdown=1999,intrabar_drawdown=1999,trades=1,qualified=False)
    assert study.eligible(row)
    assert not study.eligible(dict(row,net_pnl=0))
    for key in study.DD_KEYS: assert not study.eligible(dict(row,**{key:2000}))


def test_attempt_primary_key_prevents_second_execution():
    db=sqlite3.connect(':memory:')
    db.execute('CREATE TABLE attempts (config_id TEXT PRIMARY KEY,state TEXT,started TEXT,payload TEXT)')
    study.record_attempt(db,dict(config_id='same'))
    with pytest.raises(sqlite3.IntegrityError): study.record_attempt(db,dict(config_id='same'))
    assert db.execute('SELECT state FROM attempts').fetchone()[0]=='started'


def test_reservation_cannot_be_taken_from_another_batch(tmp_path,monkeypatch):
    monkeypatch.setattr(study,'ROOT',tmp_path);monkeypatch.setattr(study,'DIRECTORY',tmp_path/'batch')
    study.DIRECTORY.mkdir();(tmp_path/'data/manifests/reused_tests').mkdir(parents=True)
    c=dict(config_id='c',instrument='MNQ',parameters={'lookback':8})
    frozen=dict(cohort=[c],cached_candidate_id='other',partitions={'MNQ':{'partition':{'dataset_version':'test'}}})
    key=study.reservation_key(c,'test')
    p=tmp_path/'data/manifests/reused_tests'/(key+'.json')
    p.write_text(json.dumps(dict(cohort_hash='first')))
    with pytest.raises(FileExistsError): study.reserve_all({'candidate_hash':'second'},frozen)
    assert json.loads(p.read_text())['cohort_hash']=='first'
