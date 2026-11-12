import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import numpy as np
from funded_minute_core import replay,market_fill

MINUTE=60000000000;DAY=86400000000000


def run(opens,signals,days=None,low=None,high=None,keep=8500.,equal=False,fraction=0.,night=True,payout=0,cost=1.,news=None,allowed=None,contracts=None,capacity=None):
    opens=np.asarray(opens,float);n=len(opens)
    if days is None:days=np.zeros(n,dtype=np.int64)
    days=np.asarray(days,np.int64);within=np.zeros(n,np.int64)
    for i in range(1,n):within[i]=within[i-1]+1 if days[i]==days[i-1] else 0
    ts=days+within*MINUTE
    o=np.broadcast_to(opens,(2,n)).copy();h=o.copy() if high is None else np.broadcast_to(high,(2,n)).copy()
    l=o.copy() if low is None else np.broadcast_to(low,(2,n)).copy()
    quotes=np.stack([o,h,l,o],axis=1)
    s=np.asarray(signals,float).reshape((-1,9)).copy()
    # Test shorthand: expiry field is quote index, decision field index or-1.
    for row in s:
        row[1]=ts[int(row[1])] if row[1]>=0 else -MINUTE
        row[6]=ts[int(row[6])]
    c=np.ones((2,n),np.int64) if contracts is None else contracts
    result,logs=replay(ts,days,quotes,c,np.full((2,n),20,np.int64) if capacity is None else capacity,np.full(n,20,np.int64) if news is None else news,
        np.ones(n,np.bool_) if allowed is None else allowed,s,days[0],days[-1]+DAY,keep,equal,fraction,night,payout,cost)
    net=0.
    for row in logs:
        asset=int(s[int(row[0]),2]);mult=2. if asset==0 else 5.
        expected=row[3]*row[4]*(row[6]-row[5])*mult-row[8]
        np.testing.assert_allclose(row[7],expected,atol=1e-7);net+=expected
    np.testing.assert_allclose(result[2]+result[1],net-result[14],atol=1e-7)
    return result,logs


def signal(at,expiry,asset=0,side=1,dist=100.,weight=1.,night=0,decision=-1,target=0.):
    return [at,decision,asset,side,dist,target,expiry,weight,night]


def test_round_adverse_market_fills_to_tick():
    assert market_fill(100.1,1,.5)==100.75
    assert market_fill(100.1,-1,.5)==99.5


def test_gap_dll_fill_overshoots_limit_and_account_resumes_next_session():
    d=[0,0,DAY,DAY]
    r,log=run([1000,800,1000,1010],[signal(0,1,weight=3),signal(2,3,dist=10,decision=1)],days=d)
    assert r[8]==1 and r[7]==0 and r[6]==2
    assert log[0,7]<-1000 and log[0,6]==799.5


def test_gap_through_account_floor_debits_full_loss():
    r,log=run([1000,700],[signal(0,1,weight=5)])
    assert r[7]==1 and r[2]<-2000 and log[0,7]<-2000


def test_protective_stop_prevents_false_dll_from_later_bar_low():
    r,log=run([1000,1000],[signal(0,1,weight=4)],low=[700,1000],high=[1100,1000])
    assert r[8]==0 and log[0,9]==3 and log[0,7]>-1000


def test_joint_intrabar_dll_never_credits_later_recovery():
    r,log=run([1000,1100],[signal(0,1,dist=100,weight=4),signal(0,1,asset=1,dist=40,weight=4)],
        low=[850,1100],high=[1200,1100])
    assert r[8]==1 and len(log)==2 and r[2]<-1000
    assert np.all(log[:,9]==6)


def test_both_strategy_stop_and_target_use_stop_first():
    r,log=run([1000,1000],[signal(0,1,dist=10,target=2)],low=[980,1000],high=[1050,1000])
    assert log[0,9]==3 and log[0,7]<0


def test_existing_position_can_survive_news_limit_reduction():
    r,log=run([1000,1000,1010],[signal(0,2,weight=8)],news=np.array([20,3,3]))
    assert r[12]>3 and len(log)==1 and log[0,2]==2


def test_new_entry_is_capped_at_three_during_news_window():
    r,log=run([1000,1001],[signal(0,1,dist=20,weight=10)],news=np.array([3,3]))
    assert r[12]==3


def test_opposite_virtual_positions_in_one_instrument_are_rejected():
    r,log=run([1000,1000,1000],[signal(0,2),signal(1,2,side=-1)])
    assert r[6]==1


def test_night_gate_uses_account_cash_before_entry():
    r,_=run([1000,1000],[signal(0,1,night=1)],night=False);assert r[6]==0
    r,_=run([1000,1000],[signal(0,1,night=1)],night=True);assert r[6]==1


def test_hybrid_payout_uses_five_winning_days_cap_and_half_balance():
    prices=[];days=[];s=[]
    for day in range(5):
        i=2*day;prices.extend([1000,1501.5 if day<4 else 4001.5]);days.extend([day*DAY,day*DAY]);s.append(signal(i,i+1,dist=400,decision=-1))
    r,_=run(prices,s,days=days,keep=5000,payout=1)
    assert r[1]==5000 and r[0]==4500 and r[2]==5000


def test_daily_path_stays_capped_at1500():
    r,_=run([1000,6001.5],[signal(0,1,dist=400)],keep=2000.)
    assert r[1]==1500 and r[0]==1350


def test_large_global_drawdown_is_not_an_account_floor_failure():
    prices=[];days=[];s=[]
    for day in range(6):
        i=2*day;prices.extend([1000,5501 if day==0 else 700]);days.extend([day*DAY]*2);s.append(signal(i,i+1,dist=400))
    r,_=run(prices,s,days=days,keep=100000.)
    assert r[11]>2000 and r[7]==0 and r[8]==0 and r[2]>0


def test_roll_blackout_is_an_exante_entry_rule():
    r,_=run([1000,1000],[signal(0,1)],allowed=np.array([False,False]));assert r[6]==0


def test_active_contract_change_fails_data_gate():
    c=np.ones((2,2),np.int64);c[0,1]=2
    r,_=run([1000,1000],[signal(0,1)],contracts=c);assert r[10]==1


def test_inactivity_is_separate_from_floor_failure():
    r,_=run([1000,1001,1000],[signal(0,1)],days=[0,0,31*DAY])
    assert r[9]==1 and r[7]==0


def test_capacity_is_shared_by_simultaneous_same_asset_entries():
    r,_=run([1000,1001],[signal(0,1,dist=20,weight=2),signal(0,1,dist=20,weight=2)],capacity=np.full((2,2),2,np.int64))
    assert r[6]==1 and r[12]==2


def test_expired_calendar_slot_does_not_enter():
    r,_=run([1000,1001],[signal(0,0)])
    assert r[6]==0


def test_trade_date_clock_handles_dst_and_evening_rollover():
    import pandas as pd
    from funded_minute_prepare import trade_dates
    clock=pd.to_datetime(['2020-11-01T05:30Z','2020-11-01T06:30Z','2020-11-02T22:59Z','2020-11-02T23:00Z'])
    dates=pd.to_datetime(trade_dates(clock))
    assert dates[0]==dates[1]==pd.Timestamp('2020-11-01')
    assert dates[2]==pd.Timestamp('2020-11-02') and dates[3]==pd.Timestamp('2020-11-03')


def test_roll_blackout_is_calendar_based_and_known_before_entry():
    from funded_minute_prepare import roll_allowed
    assert not roll_allowed('2020-03-06') and not roll_allowed('2020-03-20')
    assert roll_allowed('2020-03-05') and roll_allowed('2020-03-23')


def test_planned_overnight_exit_does_not_use_realized_safety_timestamp():
    import pandas as pd
    from funded_minute_prepare import planned_night_expiry
    assert planned_night_expiry('2012-04-05T22:05Z')==pd.Timestamp('2012-04-06T13:45Z')
    assert planned_night_expiry('2020-03-08T22:05Z')==pd.Timestamp('2020-03-09T13:45Z')


def test_cashholiday_guard_covers_goodfriday_and_known_exceptional_closures():
    import pandas as pd
    from funded_minute_prepare import cash_closed_dates
    closed=cash_closed_dates()
    for date in ('2012-04-06','2012-10-30','2018-12-05','2022-06-20'):
        assert pd.Timestamp(date).date() in closed
    for date in ('2021-06-18','2021-12-31','2012-04-05'):
        assert pd.Timestamp(date).date() not in closed
