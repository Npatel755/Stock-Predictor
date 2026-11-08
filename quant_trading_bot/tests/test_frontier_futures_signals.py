import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import numpy as np
import pandas as pd
import pytest
from frontier_futures_signals import FAMILIES,FITTED,universe,key,primitives,fit_model,value
from test_novel_futures_signals import bars


def test_budget_uniqueness_and_disjoint_mechanisms():
    from novel_futures_signals import FAMILIES as old,universe as previous
    a=universe();assert a==universe();assert len(a)==len({key(c) for c in a})==2000
    assert not set(FAMILIES)&set(old)
    assert not {key(c) for c in a}&{key(c) for c in previous()}
    assert all(sum(c['family']==f and c['instrument']==s for c in a)==200 for f in FAMILIES for s in ('MNQ','MES'))


@pytest.mark.parametrize('family',FAMILIES)
def test_prefix_and_future_poison_invariance(family):
    b=bars();p=primitives(b,b)
    m=fit_model(p,family,32,b.timestamp_utc.iloc[1800]) if family in FITTED else None
    expected=value(p,family,32,m)
    prefix=primitives(b.iloc[:2500],b.iloc[:2500])
    np.testing.assert_allclose(expected[:2500],value(prefix,family,32,m),equal_nan=True)
    poisoned=b.copy();poisoned.loc[2500:,['open','high','low','close']]*=10
    np.testing.assert_allclose(expected[:2500],value(primitives(poisoned,poisoned),family,32,m)[:2500],equal_nan=True)


def test_analog_fit_excludes_all_evaluation_labels():
    b=bars();cutoff=b.timestamp_utc.iloc[1800]
    m=fit_model(primitives(b,b),FITTED[0],32,cutoff)
    poisoned=b.copy();poisoned.loc[1800:,['open','high','low','close']]*=10
    assert m==fit_model(primitives(poisoned,poisoned),FITTED[0],32,cutoff)
    assert pd.Timestamp(m['last_label_end'])<=cutoff and m['observations']<=2048


def test_analog_validation_prediction_cannot_refit(monkeypatch):
    import frontier_futures_2k as runner
    b=bars();v=bars(300);v.timestamp_utc=pd.date_range('2024-01-01',periods=len(v),freq='15min',tz='UTC')
    training={s:b.assign(instrument=s) for s in runner.SYMBOLS};frames={s:v.assign(instrument=s) for s in runner.SYMBOLS}
    cache=runner.SignalCache(frames,training,validation=True)
    cache.model('MNQ',FITTED[0],32,2024)
    def forbidden(*a,**k):raise AssertionError('Validation attempted fitting')
    monkeypatch.setattr(runner,'fit_model',forbidden)
    c=dict(universe()[-2],instrument='MNQ',family=FITTED[0],lookback=32)
    assert len(cache.signal(c))==len(v)


def test_profile_publication_waits_for_completed_closing_bar():
    b=bars(300);p=primitives(b,b);clock=p['clock'];end=np.flatnonzero(clock==945)[0]
    assert np.isnan(p['previous_rth_close'][end])
    assert p['previous_rth_close'][end+1]==b.close.iloc[end]
    assert np.isfinite(p['prior_poc'][end+1])


def test_contract_change_discards_auction_references():
    b=bars(300);b.loc[150:,'contract']='Y';p=primitives(b,b)
    assert np.isnan(p['previous_rth_close'][150]) and np.isnan(p['prior_poc'][150])


def test_cusum_resets_at_contract_boundary():
    b=bars();b.loc[2500:,'contract']='Y';p=primitives(b,b)
    v=value(p,'sequential_change_detection',32)
    assert np.isnan(v[2500:2533]).all()


def test_invalid_rth_profile_is_not_silently_completed():
    b=bars(300);initial=primitives(b,b);end=np.flatnonzero(initial['clock']==945)[0]
    b=b.drop(index=end-4).reset_index(drop=True);p=primitives(b,b)
    end=np.flatnonzero(p['clock']==945)[0]
    assert np.isnan(p['previous_rth_close'][end+1]) and np.isnan(p['prior_poc'][end+1])


def test_missing_closing_bar_discards_stale_auction_reference():
    b=bars(400);p=primitives(b,b)
    close_ids=np.flatnonzero(p['clock']==945)
    missing=close_ids[1]
    b=b.drop(index=missing).reset_index(drop=True);p=primitives(b,b)
    opening=np.flatnonzero((p['clock']==570)&(np.arange(len(b))>missing))[0]
    assert np.isnan(p['previous_rth_close'][opening])
