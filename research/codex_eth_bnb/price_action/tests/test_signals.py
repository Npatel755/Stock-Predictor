import numpy as np
import pandas as pd
import pytest

from research.codex_eth_bnb.price_action.signals import library,detect,signalize


def frame(n=400):
    out=pd.DataFrame(dict(timestamp=pd.date_range('2023-01-02',periods=n,freq='15min',tz='UTC'),
                          open=100.,high=100.3,low=99.7,close=100.,volume=100.,atr=1.,regime='range',session_vwap=100.))
    out.attrs['timeframe']='15m'
    return out


def candle(out,i,o,h,l,c,v=100.):
    out.loc[i,['open','high','low','close','volume']]=[o,h,l,c,v]


def test_sweep_requires_close_reclaim_not_merely_a_wick():
    out=frame();candle(out,210,100.3,102.,99.7,99.9,200.)
    event=detect(out).query("family=='sweep_reclaim'")
    assert event['index'].tolist()==[210] and event.direction.tolist()==[-1]
    candle(out,210,100.3,102.,99.7,101.9,200.)
    assert detect(out).query("family=='sweep_reclaim'").empty


def test_failed_breakout_confirmation_is_after_breakout():
    out=frame();candle(out,210,100.,102.2,99.9,102.,150.);candle(out,211,101.,101.1,99.7,99.9)
    event=detect(out).query("family=='failed_breakout'")
    assert event['index'].tolist()==[211] and event.origin_index.tolist()==[210]


def test_break_retest_confirmation_cannot_occur_on_retest_candle():
    out=frame();candle(out,210,100.,102.2,99.9,102.,150.)
    candle(out,211,101.,101.1,100.2,100.5)
    candle(out,212,100.6,101.7,100.6,101.5)
    event=detect(out).query("family=='break_retest'")
    assert event['index'].tolist()==[212] and event.origin_index.tolist()==[210]


def test_imbalance_needs_a_later_touch_not_lookback_fill():
    out=frame();candle(out,209,100.,102.2,99.9,102.)
    candle(out,210,102.,102.4,101.,102.2)
    candle(out,211,101.2,101.8,100.8,101.6)
    event=detect(out).query("family=='imbalance_retest'")
    assert event['index'].tolist()==[211] and event.origin_index.tolist()==[210]
    assert event.available_at.iloc[0]==str(out.timestamp.iloc[211]+pd.Timedelta('15min'))


def test_shock_waits_for_reversal_confirmation():
    out=frame();candle(out,210,100.,103.2,99.8,103.,300.);candle(out,211,102.,102.2,100.7,100.9)
    event=detect(out).query("family=='shock_reversal'")
    assert event['index'].tolist()==[211] and event.origin_index.tolist()==[210]


def test_opening_range_uses_all_completed_bars_and_respects_utc_session_end():
    out=frame();i=128  # Second day08:00UTC.
    candle(out,i,100.5,101.7,100.5,101.5,200.)
    events=detect(out)
    opening=events.query("family=='opening_breakout'")
    assert opening['index'].tolist()==[i]
    assert pd.Timestamp(opening.available_at.iloc[0]).hour==8
    clipped=out.iloc[:i].copy()
    assert detect(clipped).query("family=='opening_breakout'").empty
    assert all(pd.Timestamp(r.available_at)<pd.Timestamp(r.session_end) for r in opening.itertuples())


def test_two_exit_profiles_share_raw_entry_but_have_different_fixed_targets():
    out=frame();candle(out,210,100.3,102.,99.7,99.9,200.)
    events=detect(out)
    specs=[s for s in library() if s['family']=='sweep_reclaim' and s['timeframe']=='15m']
    signals=[signalize(out,s,events) for s in specs]
    assert signals[0].signal.iloc[210]==signals[1].signal.iloc[210]==-1
    assert signals[0].setup_id.iloc[210]==signals[1].setup_id.iloc[210]
    assert signals[1].planned_target.iloc[210]<signals[0].planned_target.iloc[210]


def test_all_rules_are_prefix_equivalent_and_immune_to_future_price_poisoning():
    rng=np.random.default_rng(29);out=frame(1500)
    close=100*np.exp(np.cumsum(rng.normal(0,.004,len(out))))
    out.open=np.r_[close[0],close[:-1]];out.close=close
    out.high=np.maximum(out.open,out.close)+.4;out.low=np.minimum(out.open,out.close)-.4
    out.volume=rng.lognormal(5,.6,len(out))
    day=out.timestamp.dt.floor('D')
    out.session_vwap=((out.high+out.low+out.close)/3*out.volume).groupby(day).cumsum()/out.volume.groupby(day).cumsum()
    full=detect(out);prefix=detect(out.iloc[:1000].copy())
    pd.testing.assert_frame_equal(full[full['index']<1000].reset_index(drop=True),prefix.reset_index(drop=True))
    for spec in [s for s in library() if s['timeframe']=='15m']:
        pd.testing.assert_frame_equal(signalize(out,spec,full).iloc[:1000].reset_index(drop=True),
                                      signalize(out.iloc[:1000].copy(),spec,prefix).reset_index(drop=True))
    poison=out.copy();poison.loc[1000:,['open','high','low','close']]*=5
    later=detect(poison)
    pd.testing.assert_frame_equal(full[full['index']<1000].reset_index(drop=True),later[later['index']<1000].reset_index(drop=True))
