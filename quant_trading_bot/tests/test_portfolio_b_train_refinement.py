import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import itertools
import numpy as np
import pandas as pd
import pytest
import portfolio_b_train_refinement as p


def raw(cash,equity=None,worst=None,quantity=None,entry=None,exit=None,qty=None,net=None):
    cash=np.array(cash,dtype=float);n=len(cash)
    entry=[] if entry is None else entry;exit=[] if exit is None else exit
    if net is None:net=[cash[-1]-50000.] if entry else []
    return dict(cash=cash,equity=np.array(equity if equity is not None else cash,dtype=float),
      worst=np.array(worst if worst is not None else equity if equity is not None else cash,dtype=float),quantity=np.array(quantity if quantity is not None else [0]*n),
      trade_entry=np.array(entry,dtype=int),trade_exit=np.array(exit,dtype=int),trade_qty=np.array(qty if qty is not None else [1]*len(entry),dtype=int),trade_net=np.array(net,dtype=float),lock=0,funded_failed=False)


def data(n=3,start='2020-01-02T14:30Z'):
    return dict(timestamp=pd.date_range(start,periods=n,freq='15min').as_unit('ns').asi8)


def test_shared_starting_balance_and_fee_cash_reconcile():
    a=raw([50000,49999,50100],entry=[1],exit=[2],net=[100])
    b=raw([50000,49998,50050],entry=[1],exit=[2],net=[50])
    m,c=p.combine([a,b],[data(),data()],[dict(max_open_risk=150)]*2,paths=True)
    assert m['net_pnl']==150 and c.cash.iloc[0]==50000 and c.cash.iloc[1]==49997


def test_drawdown_uses_marked_equity_peak_not_cash_peak():
    a=raw([50000,50000,50010],equity=[50000,51000,50010],entry=[1],exit=[2],net=[10])
    b=raw([50000]*3)
    m=p.combine([a,b],[data(),data()],[dict(max_open_risk=150)]*2)
    assert m['cash_drawdown']==0 and m['intrabar_drawdown']==990 and m['closing_drawdown']==990


def test_joint_risk_limit_can_reject_individually_permitted_sleeves():
    a=raw([50000]*3,entry=[1],exit=[2],qty=[4],net=[0]);b=raw([50000]*3,entry=[1],exit=[2],qty=[3],net=[0])
    m=p.combine([a,b],[data(),data()],[dict(max_open_risk=600),dict(max_open_risk=450)])
    assert m['maximum_simultaneous_contracts']==7 and not m['risk_pass']


def test_joint_intrabar_exposure_includes_same_bar_round_trips():
    a=raw([50000]*3,entry=[1],exit=[1],qty=[3],net=[0]);b=raw([50000]*3,entry=[1],exit=[1],qty=[3],net=[0])
    m=p.combine([a,b],[data(),data()],[dict(max_open_risk=450)]*2)
    assert m['maximum_simultaneous_contracts']==6 and m['maximum_allocated_initial_risk']==900


def test_missing_quote_with_open_position_rejects_path():
    a=raw([50000]*2,quantity=[1,0],entry=[0],exit=[1],net=[0]);b=raw([50000]*3)
    da=dict(timestamp=data()['timestamp'][[0,2]])
    m=p.combine([a,b],[da,data()],[dict(max_open_risk=150)]*2)
    assert m['missing_quote_exposure']==1 and not m['risk_pass']


def test_missing_bar_carries_last_close_not_previous_intrabar_low():
    a=raw([50000]*2,worst=[49000,50000]);b=raw([50000]*3)
    da=dict(timestamp=data()['timestamp'][[0,2]])
    _,curve=p.combine([a,b],[da,data()],[dict(max_open_risk=150)]*2,paths=True)
    assert curve.worst_bound.iloc[1]==50000


def test_joint_daily_loss_is_checked_in_addition_to_trailing_dd():
    a=raw([50000,48400,48400],entry=[0],exit=[1],net=[-1600]);b=raw([50000]*3)
    m=p.combine([a,b],[data(),data()],[dict(max_open_risk=150)]*2)
    assert m['intrabar_drawdown']==1600 and not m['risk_pass']


def test_negative_starting_drawdown_is_measured_against_initial_balance():
    a=raw([49900,49900,49900],entry=[0],exit=[0],net=[-100]);b=raw([50000]*3)
    m=p.combine([a,b],[data(),data()],[dict(max_open_risk=150)]*2)
    assert m['cash_drawdown']==100 and m['intrabar_drawdown']==100


def test_generator_does_not_mutate_parent_or_duplicate_active_portfolios():
    parent=[dict(instrument='MES',family='momentum',lookback=16,threshold=1.5,stop_atr=1.75,target_r=2.5,hold_bars=32,session_start=585,session_end=945,max_contracts=3,trailing_atr=2.),
            dict(instrument='MNQ',family='breakout',lookback=32,threshold=.75,stop_atr=1.,target_r=3.,hold_bars=24,session_start=600,session_end=720,max_contracts=1,trailing_atr=2.)]
    identity=p.portfolio_id(parent);rows=list(itertools.islice(p.generate(parent),200))
    assert p.portfolio_id(parent)==identity and len({r[1] for r in rows})==200 and identity not in {r[1] for r in rows}
    assert all(sum(c['max_contracts'] for c in r[2])<=6 for r in rows)


def test_loader_refuses_any_observation_beyond_train(monkeypatch,tmp_path):
    monkeypatch.setattr(p,'RUN',tmp_path)
    monkeypatch.setattr(p.e,'load_training',lambda *a:(pd.DataFrame(dict(timestamp_utc=[pd.Timestamp('2024-01-01T00:00Z')])),{}))
    with pytest.raises(PermissionError):p.Research()
