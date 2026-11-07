from pathlib import Path
import sys
import json
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import mass_research as study
from mass_verify import verify_execution
from quant_futures.data import canonical


def test_entry_regime_is_known_before_entry_candle():
    original=np.array([.1,.9,.2,1.])
    changed=original.copy();changed[2]=9
    assert study.entry_regimes(original).tolist()==[-1,0,1,0]
    np.testing.assert_array_equal(study.entry_regimes(original)[:3],study.entry_regimes(changed)[:3])


def test_resume_preserves_universe_and_completed_experiments(tmp_path):
    folder=tmp_path/'run'
    rows,protocol,connection=study.setup(folder,study.SEED)
    connection.execute('INSERT INTO results VALUES (?,?,?)',(rows[0]['config_id'],'ES','{}'))
    connection.commit(); connection.close()
    again,second,connection=study.setup(folder,study.SEED)
    assert rows==again and protocol==second
    assert connection.execute('SELECT COUNT(*) FROM results').fetchone()[0]==1
    connection.close()
    with pytest.raises(ValueError,match='Frozen'):
        study.setup(folder,study.SEED+1)


def test_physical_holdout_manifest_rejected_before_price_read(tmp_path,monkeypatch):
    path=tmp_path/'market.parquet'
    path.with_suffix('.manifest.json').write_text(json.dumps(dict(split_role='validation',instrument='MNQ')))
    calls=[]
    monkeypatch.setattr(study,'resolve_dataset',lambda selector: calls.append(selector) or path)
    with pytest.raises(PermissionError): study.train_identity('MNQ')
    assert calls==['MNQ:train']


def test_accounting_and_shared_replay_for_synthetic_next_open_trade():
    n=30
    b=canonical(pd.DataFrame(dict(timestamp_utc=pd.date_range('2023-01-03T14:30Z',periods=n,freq='15min'),
        instrument='MNQ',contract='MNQH23',open=15000.,high=15001.,low=14999.,close=15000.,volume=1000)))
    c=dict(instrument='MNQ',stop_atr=1.,target_r=2.,hold_bars=4,session_start=585,session_end=945,max_contracts=2,trailing_atr=1.)
    d=study.arrays(b); s=np.zeros(n,dtype=np.int8);s[0]=1
    cfg=study.execution_cfg(c)
    out=study.execute(d,s,np.ones(n)*10,cfg)
    verified=verify_execution(b,d,s,np.ones(n)*10,c,cfg,out)
    assert verified['passed'] and verified['shared_simulator_replayed']==1
    changed=dict(out,trade_net=out['trade_net']+1)
    with pytest.raises(AssertionError): verify_execution(b,d,s,np.ones(n)*10,c,cfg,changed)


def test_no_trade_folds_are_finite_and_cannot_qualify():
    n=30
    b=canonical(pd.DataFrame(dict(timestamp_utc=pd.date_range('2023-01-03T14:30Z',periods=n,freq='15min'),
        instrument='MNQ',contract='MNQH23',open=15000.,high=15001.,low=14999.,close=15000.,volume=1000)))
    d=study.arrays(b);s=np.zeros(n,dtype=np.int8)
    c=next(c for c in study.generate() if c['instrument']=='MNQ')
    out=study.execute(d,s,np.ones(n)*10,study.execution_cfg(c))
    m=study.summarize_execution(out,d)
    result=study.aggregate(c,[m]*4,s)
    assert not result['qualified'] and result['trades']==0 and result['profit_factor'] is None
    json.dumps(result,allow_nan=False)
