import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import numpy as np
import pandas as pd
import pytest
from novel_futures_signals import FAMILIES,FITTED,universe,key,primitives,fit_model,value


def bars(n=4000):
    rng=np.random.default_rng(70);r=rng.normal(0,.001,n)
    c=100*np.exp(np.cumsum(r));o=np.r_[c[0],c[:-1]]
    return pd.DataFrame(dict(timestamp_utc=pd.date_range('2020-01-01',periods=n,freq='15min',tz='UTC'),contract='X',open=o,high=np.maximum(o,c)*1.001,low=np.minimum(o,c)*.999,close=c,volume=rng.uniform(100,1000,n)))


def test_fixed_budget_semantics_and_family_coverage():
    a=universe();assert a==universe();assert len(a)==len({key(c) for c in a})==len({c['config_id'] for c in a})==2000
    assert {f:sum(c['family']==f for c in a) for f in FAMILIES}=={f:250 for f in FAMILIES}
    assert all(sum(c['instrument']==s and c['family']==f for c in a)==125 for s in ('MNQ','MES') for f in FAMILIES)


@pytest.mark.parametrize('family',FAMILIES)
def test_prefix_invariance_and_future_poison(family):
    b=bars();peer=bars();p=primitives(b,peer)
    cutoff=b.timestamp_utc.iloc[1800];model=fit_model(p,family,32,cutoff) if family in FITTED else None
    original=value(p,family,32,model)
    prefix=primitives(b.iloc[:2500],peer.iloc[:2500]);before=value(prefix,family,32,model)
    np.testing.assert_allclose(original[:2500],before,equal_nan=True)
    poisoned=b.copy();poisoned.loc[2500:,['open','high','low','close']]*=10
    peerpoison=peer.copy();peerpoison.loc[2500:,['open','high','low','close']]*=.1
    after=value(primitives(poisoned,peerpoison),family,32,model)
    np.testing.assert_allclose(original[:2500],after[:2500],equal_nan=True)


@pytest.mark.parametrize('family',FITTED)
def test_fitted_weights_cannot_see_evaluation_labels(family):
    b=bars();peer=bars();cutoff=b.timestamp_utc.iloc[1800]
    m=fit_model(primitives(b,peer),family,32,cutoff)
    changed=b.copy();changed.loc[1800:,['open','high','low','close']]*=7
    changedpeer=peer.copy();changedpeer.loc[1800:,['open','high','low','close']]*=.2
    assert m==fit_model(primitives(changed,changedpeer),family,32,cutoff)
    assert pd.Timestamp(m['last_label_end'])<=cutoff
    assert m['ready']


def test_contract_and_gap_boundaries_do_not_create_returns():
    b=bars();b.loc[2000:,'contract']='Y';b.loc[2000:,['open','high','low','close']]*=10
    p=primitives(b,b)
    assert np.isnan(p['r'][2000]) and np.isnan(p['lag'][2001]) and np.isnan(p['y'][1999])
    assert np.isnan(value(p,'return_skew_exhaustion',32)[2001])


def test_missing_peer_returns_forbid_cross_prediction():
    b=bars();peer=b.drop(index=2300).reset_index(drop=True)
    p=primitives(b,peer);m=fit_model(p,'cross_index_leadlag',32,b.timestamp_utc.iloc[1800])
    v=value(p,'cross_index_leadlag',32,m)
    assert np.isnan(v[2300]) and np.isnan(v[2301])


@pytest.mark.parametrize('family',FITTED)
def test_validation_predictions_never_fit_validation(monkeypatch,family):
    import novel_futures_2k as runner
    train=bars();v=bars(800);v['timestamp_utc']=pd.date_range('2024-01-01',periods=len(v),freq='15min',tz='UTC')
    frames={s:v.assign(instrument=s) for s in runner.SYMBOLS}
    training={s:train.assign(instrument=s) for s in runner.SYMBOLS}
    cache=runner.SignalCache(frames,training,validation=True)
    cache.models[('MNQ',family,32,2024)]=fit_model(cache.fitp['MNQ'],family,32,pd.Timestamp('2023-12-24T00:00Z'))
    def forbidden(*a,**kw):raise AssertionError('Validation attempted a new model fit')
    monkeypatch.setattr(runner,'fit_model',forbidden)
    c=next(x for x in universe() if x['instrument']=='MNQ' and x['family']==family)
    c=dict(c,lookback=32)
    result=cache.signal(c)
    assert len(result)==len(v) and set(result)<=set((-1,0,1))
