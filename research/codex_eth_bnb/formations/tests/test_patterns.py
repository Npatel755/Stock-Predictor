import numpy as np
import pandas as pd
import pytest

from research.codex_eth_bnb.formations.patterns import detect,signalize,library,recognize
from research.codex_eth_bnb.formations.execution import simulate
from research.codex_eth_bnb.execution import simulate as original


def head_frame(inverse=False):
    knots={0:85.,65:100.,80:110.,85:100.,90:115.,95:100.,100:110.,104:101.,105:99.,110:97.,130:90.}
    close=np.interp(np.arange(131),list(knots),list(knots.values()))
    if inverse:
        close=200-close
    frame=pd.DataFrame(dict(timestamp=pd.date_range('2023-01-01',periods=len(close),freq='15min',tz='UTC'),
                            open=close,high=close+.1,low=close-.1,close=close,volume=100000.,atr=2.,regime='range'))
    frame.attrs['timeframe']='15m'
    return frame


@pytest.mark.parametrize('inverse',[False,True])
def test_head_shoulders_waits_for_right_confirmation_and_neckline_cross(inverse):
    frame=head_frame(inverse)
    events,pivots=detect(frame,'responsive')
    hs=events[events.family.eq('head_shoulders')]
    assert len(hs)==1
    event=hs.iloc[0]
    assert event['index']==105 and event.direction==(1 if inverse else -1)
    assert event.formed_at>=102
    assert event.available_at==str(frame.timestamp.iloc[105]+pd.Timedelta('15min'))
    spec=next(s for s in library() if s['id']=='head_shoulders_15m_responsive')
    signals=signalize(frame,spec,events)
    assert signals.signal.iloc[:105].eq(0).all()
    assert signals.signal.iloc[105]==event.direction


def test_neckline_cross_before_confirmation_cannot_be_backdated():
    frame=head_frame()
    frame.loc[101:104,['open','close']]=99.
    frame.loc[101:104,'high']=99.1;frame.loc[101:104,'low']=98.9
    events,_=detect(frame,'responsive')
    assert events[events.family.eq('head_shoulders')].empty


@pytest.mark.parametrize('sensitivity',['responsive','selective'])
def test_events_and_signals_are_prefix_equivalent_and_future_poison_safe(sensitivity):
    rng=np.random.default_rng(17)
    close=100*np.exp(np.cumsum(rng.normal(0,.005,1500)))
    frame=pd.DataFrame(dict(timestamp=pd.date_range('2023-01-01',periods=len(close),freq='15min',tz='UTC'),
                            open=close,high=close+.4,low=close-.4,close=close,volume=10000.,atr=1.,regime='range'))
    frame.attrs['timeframe']='15m'
    full,_=detect(frame,sensitivity)
    prefix,_=detect(frame.iloc[:1000].copy(),sensitivity)
    pd.testing.assert_frame_equal(full[full['index']<1000].reset_index(drop=True),prefix.reset_index(drop=True))
    for spec in [s for s in library() if s['timeframe']=='15m' and s['sensitivity']==sensitivity]:
        pd.testing.assert_frame_equal(signalize(frame,spec,full).iloc[:1000].reset_index(drop=True),
                                      signalize(frame.iloc[:1000].copy(),spec,prefix).reset_index(drop=True))
    poisoned=frame.copy()
    poisoned.loc[1000:,['open','high','low','close']]*=10
    later,_=detect(poisoned,sensitivity)
    pd.testing.assert_frame_equal(full[full['index']<1000].reset_index(drop=True),later[later['index']<1000].reset_index(drop=True))


def test_six_confirmed_contacts_make_converging_triangle():
    p=[dict(index=i,kind=k,price=v,confirmed_at=i+2) for i,k,v in
       [(80,1,110.),(84,-1,100.),(88,1,109.),(92,-1,101.),(96,1,108.),(100,-1,102.)]]
    templates=recognize(p,1.,1.25,.25,np.ones(120)*105,np.ones(120)*100,102)
    assert 'triangle' in templates
    assert len(templates['triangle']['points'])==6


def execution_frame():
    return pd.DataFrame(dict(timestamp=pd.date_range('2023-01-01',periods=12,freq='15min',tz='UTC'),
                             open=100.,high=107.,low=97.,close=100.,volume=100000.,atr=1.,signal=1,regime='range'))


def test_one_successful_entry_per_formation_not_reentries_after_stop():
    frame=execution_frame();frame['setup_id']='formation-A'
    cfg=dict(fee_bps=0.,slippage_bps=0.,spread_bps=0.,stop_atr=2.,reward_r=3.,funding_bps_daily=0.)
    result=simulate(frame,cfg)
    assert result['metrics']['trades']==1
    assert result['trades'].reason.eq('stop').all()
    assert result['trades'].entry_time.nunique()==1  # Partial exits are not new trades.
    frame.loc[6:,'setup_id']='formation-B'
    assert simulate(frame,cfg)['metrics']['trades']==2


def test_parent_fill_parity_when_pattern_columns_absent():
    frame=execution_frame()
    cfg=dict(fee_bps=5.,slippage_bps=2.,spread_bps=1.,stop_atr=2.,reward_r=3.,funding_bps_daily=0.)
    old,new=original(frame,cfg),simulate(frame,cfg)
    pd.testing.assert_frame_equal(old['trades'],new['trades'].drop(columns='setup_id'))
    pd.testing.assert_frame_equal(old['equity'],new['equity'])
    assert old['metrics']['final_equity']==new['metrics']['final_equity']


def test_structural_brackets_come_from_previous_completed_bar():
    frame=execution_frame().iloc[:3].copy()
    frame.high=104.;frame.low=99.;frame['setup_id']='structure'
    frame['planned_stop']=[97.,90.,90.];frame['planned_target']=[103.,1000.,1000.]
    result=simulate(frame,dict(fee_bps=0.,slippage_bps=0.,spread_bps=0.,funding_bps_daily=0.))
    assert result['metrics']['trades']==1
    assert result['trades'].exit_price.iloc[0]==103.
    assert result['trades'].reason.iloc[0]=='target'
