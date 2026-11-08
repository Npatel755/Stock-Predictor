import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import numpy as np
import pandas as pd
import pytest
from explore_futures_signals import FAMILIES,FITTED,universe,key,primitives,fit_model,value
from test_novel_futures_signals import bars


def peer(b):
    p=b.copy();p[['open','high','low','close']]=p[['open','high','low','close']].mul(np.exp(.01*np.sin(np.arange(len(p))/70)),axis=0)
    return p


def test_budget_and_disjoint_algorithms():
    from novel_futures_signals import universe as old1
    from frontier_futures_signals import universe as old2
    a=universe();assert a==universe();assert len(a)==len({key(c) for c in a})==2000
    assert not {key(c) for c in a}&{key(c) for c in old1()+old2()}
    assert all(sum(c['family']==f and c['instrument']==s for c in a)==200 for f in FAMILIES for s in ('MNQ','MES'))


@pytest.mark.parametrize('family',FAMILIES)
def test_prefix_and_future_poison(family):
    b=bars();q=peer(b);p=primitives(b,q)
    model=fit_model(p,family,32,b.timestamp_utc.iloc[1800]) if family in FITTED else None
    expected=value(p,family,32,model)
    np.testing.assert_allclose(expected[:2500],value(primitives(b.iloc[:2500],q.iloc[:2500]),family,32,model),equal_nan=True)
    poisoned=b.copy();poisoned.loc[2500:,['open','high','low','close']]*=10
    q.loc[2500:,['open','high','low','close']]*=.2
    np.testing.assert_allclose(expected[:2500],value(primitives(poisoned,q),family,32,model)[:2500],equal_nan=True)


@pytest.mark.parametrize('family',FITTED)
def test_model_cannot_see_evaluated_labels(family):
    b=bars();q=peer(b);cutoff=b.timestamp_utc.iloc[1800]
    m=fit_model(primitives(b,q),family,32,cutoff)
    poisoned=b.copy();poisoned.loc[1800:,['open','high','low','close']]*=10
    q.loc[1800:,['open','high','low','close']]*=.2
    assert m==fit_model(primitives(poisoned,q),family,32,cutoff)
    assert m['ready'] and pd.Timestamp(m['last_label_end'])<=cutoff


@pytest.mark.parametrize('family',FITTED)
def test_validation_prediction_does_not_fit(monkeypatch,family):
    import explore_futures_2k as runner
    b=bars();q=peer(b);v=bars(300);v.timestamp_utc=pd.date_range('2024-01-01',periods=len(v),freq='15min',tz='UTC')
    train={'MNQ':b,'MES':q};frames={'MNQ':v,'MES':peer(v)}
    cache=runner.SignalCache(frames,train,validation=True);cache.model('MNQ',family,32,2024)
    def forbidden(*a,**k):raise AssertionError('New fit during validation')
    monkeypatch.setattr(runner,'fit_model',forbidden)
    c=dict(universe()[0],family=family,instrument='MNQ',lookback=32)
    assert len(cache.signal(c))==len(v)


def test_duration_and_wavelet_restart_at_roll():
    b=bars();b.loc[2500:,'contract']='Y';p=primitives(b,peer(b))
    assert p['duration_state'][2500]==-1
    assert np.isnan(value(p,'wavelet_reversal',32)[2500:2532]).all()


def test_missing_peer_cannot_create_equilibrium_signal():
    b=bars();q=peer(b);p=primitives(b,q)
    m=fit_model(p,'cross_index_equilibrium',32,b.timestamp_utc.iloc[1800])
    q=q.drop(index=2300).reset_index(drop=True)
    assert np.isnan(value(primitives(b,q),'cross_index_equilibrium',32,m)[2300])


def test_probability_scores_are_bounded():
    b=bars();p=primitives(b,peer(b));m=fit_model(p,'direction_probability',32,b.timestamp_utc.iloc[1800])
    v=value(p,'direction_probability',32,m);finite=v[np.isfinite(v)]
    assert len(finite)>100 and np.max(np.abs(finite))<=1


def test_entropy_does_not_trade_flat_price_noise():
    b=bars();b[['open','high','low','close']]=100.;p=primitives(b,b)
    assert np.isnan(value(p,'ordinal_entropy_persistence',32)).all()
