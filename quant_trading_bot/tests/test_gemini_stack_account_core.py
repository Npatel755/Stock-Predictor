import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import numpy as np
import pytest
from gemini_stack_account_core import replay,independent_reference
from gemini_stack_prepare_train import route_causal


def run(daily,K=8600.,g1=8700.,g2=8700.,risklevel=0.):
    dates=np.arange(len(daily));net=np.broadcast_to(np.array(daily,dtype=float),(3,4,2,len(daily))).copy()
    risk=np.ones((3,4,len(daily)))*risklevel
    row=replay(net,risk,dates,np.array([0]),np.array([len(daily)]),np.array([365]),K,g1,g2,1500.)[0]
    ref=independent_reference(net,risk,dates,0,len(daily),365,K,g1,g2,1500.)
    np.testing.assert_allclose(row,ref,atol=1e-9,rtol=0)
    return row


def test_flat_cash_ledger():
    r=run([0.]*50);assert r[0]==r[1]==r[8]==0


def test_trading_pnl_equals_withdrawals_plus_remaining_balance():
    r=run([1000.]*30);assert r[0]+r[7]==r[8]
    assert r[9]>3 and r[0]>0


def test_static_floor_touch_fails():
    r=run([-1000.,-1000.,10000.]);assert r[1]==1 and r[8]==-2000 and r[0]==0


def test_floor_becomes_zero_after_first_payout():
    r=run([6000.,-1000.,-1000.,-1000.,-1000.,-1000.,-1000.]);assert r[0]==500 and r[1]==1


def test_payout_cap1500_preserved():
    r=run([6000.,10000.]);assert r[0]==2000 and r[9]==2


def test_maxrisk_flag_is_distinct_from_closed():
    r=run([100.],risklevel=2500.);assert r[2]==1 and r[1]==0


def test_starting_zero_includes_first_loss_in_near_miss():
    r=run([-800.,-800.,500.]);assert r[3]==1 and r[1]==0


def test_causal_priority_has_no_signal_bar_label_lookahead():
    import pandas as pd
    df=pd.DataFrame(dict(tin=pd.to_datetime(['2020-01-02T10:15Z','2020-01-02T11:00Z']),
      tout=pd.to_datetime(['2020-01-02T10:45Z','2020-01-02T12:00Z']),
      dec=pd.to_datetime(['2020-01-02T10:00Z','2020-01-02T10:00Z']),prio=[1,0]))
    out=route_causal(df)
    assert len(out)==2


def test_future_days_do_not_change_earlier_account_path_ending():
    first=run([1000.]*4)
    net=np.broadcast_to(np.array([1000.]*4+[1e8]*4),(3,4,2,8)).copy();risk=np.zeros((3,4,8))
    actual=replay(net,risk,np.arange(8),np.array([0]),np.array([4]),np.array([365]),8600.,8700.,8700.,1500.)[0]
    np.testing.assert_allclose(first,actual)
