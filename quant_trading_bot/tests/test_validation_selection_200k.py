"""Parity and leakage/order guards without any actual protected market data."""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import validation_selection_200k as batch
from quant_futures.data import canonical


@pytest.mark.parametrize('scale',[1.,2.,4.])
def test_single_execution_validation_metrics_match_frozen_engine_on_synthetic_training_fixture(scale):
    n=480;close=np.round((20000+np.arange(n)*.25+5*np.sin(np.arange(n)/9))/.25)*.25
    bars=canonical(pd.DataFrame(dict(timestamp_utc=pd.date_range('2023-01-02T23:00Z',periods=n,freq='15min'),instrument='MNQ',contract='MNQH23',open=close-.25,high=close+1,low=close-1,close=close,volume=1000.)))
    c=dict(config_id='unit_fixture',instrument='MNQ',family='momentum',lookback=20,threshold=1.,stop_atr=1.25,target_r=4.,hold_bars=8,session_start=585,session_end=945,max_contracts=2,trailing_atr=1.5,risk_scale=scale)
    data=batch.training.engine.arrays(bars);f=batch.training.engine.features(bars,20)
    s=np.zeros(n,dtype=np.int8)
    eligible=np.flatnonzero((data['minute']>=600)&(data['minute']<=840)&(np.arange(n)>96))
    s[eligible[::8]]=1
    expected=batch.training.measured(c,bars,data,[dict(label='validation',start=0,stop=n,embargo_bars=96,purge_bars=16)],f,s)[0]
    row,raw=batch.execute_validation(c,bars,data,f,s)
    assert row['trades']>0
    for key in ('net_pnl',*batch.DD_FIELDS,'trades'):
        assert row[key]==expected[key]
    assert row['net_pnl']==pytest.approx(raw['trade_net'].sum())


def test_validation_rank_respects_risk_gate_and_strict_threshold():
    row=dict(config_id='a',qualified=True,net_pnl=100.,intrabar_drawdown=100.,realized_drawdown=100.,max_drawdown=100.,trades=30,locks=0,funded_breaches=0)
    assert batch.validation_checks(row)==(True,True)
    assert batch.validation_checks(dict(row,intrabar_drawdown=2000))==(False,False)
    assert batch.validation_checks(dict(row,locks=1))==(True,False)
    assert batch.validation_checks(dict(row,net_pnl=0))==(False,False)
    assert batch.order_key(row)<batch.order_key(dict(row,config_id='b',qualified=False,net_pnl=10000))


def test_validation_loader_cannot_run_before_train_completion(tmp_path,monkeypatch):
    monkeypatch.setattr(batch,'RUN',tmp_path)
    monkeypatch.setattr(batch,'verify',lambda:dict(configuration_sha256='frozen'))
    def forbidden(*a,**k):raise AssertionError('Protected prices loaded before TRAIN completed')
    monkeypatch.setattr(batch,'load_validation',forbidden)
    with pytest.raises(FileNotFoundError):batch.validate()
