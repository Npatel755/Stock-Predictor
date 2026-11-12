import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import numpy as np
from stack_trade_budget_core import allocate,reference

DAY=86400000000000


def run(p,risks=None,cap=1.,limit=450.,fraction=.5,cost=1.,night=None,overlap=False):
    n=len(p);tin=np.arange(n,dtype=np.int64)*DAY;tout=tin+DAY//2
    if overlap and n>1:tout[0]=tin[1]+DAY//4
    args=(tin,tout,np.array(p,dtype=float),np.array(risks if risks is not None else [100.]*n),
        np.ones(n),np.full(n,2.),np.zeros(n,dtype=np.bool_) if night is None else np.array(night),
        np.zeros(n,dtype=np.int64),0,n*DAY,cap,limit,fraction,cost)
    a=allocate(*args);b=reference(*args)
    for x,y in zip(a,b):np.testing.assert_allclose(x,y,atol=1e-9,rtol=0)
    return a


def test_loss_fill_never_clipped_to_limit():
    a=run([-2500],fraction=0.)
    assert a[0][0]==-2500 and a[0][1]==2500 and a[0][8]==1


def test_quantity_uses_entry_risk_not_future_trade_pnl():
    a=run([100]);b=run([-100])
    np.testing.assert_array_equal(a[3],b[3])


def test_drawdown_budget_reduces_contracts_before_next_entry():
    a=run([-400,10],cap=3,limit=900,fraction=.5)
    assert a[3][0]==3 and a[3][1]==3 # room600 -> budget300, exactly3
    b=run([-450,10],cap=3,limit=900,fraction=.5)
    assert b[3][1]==2


def test_overnight_waits_for_completed_profit_buffer():
    a=run([1000,600,100],night=[True,False,True])
    np.testing.assert_array_equal(a[3],[0,1,1])


def test_position_overlap_cannot_use_early_posted_profit():
    a=run([1000,1000,100],overlap=True)
    assert a[3][1]==0 and a[0][2]==2


def test_integer_sizing_skips_unaffordable_risk():
    a=run([100,100],risks=[600,100])
    np.testing.assert_array_equal(a[3],[0,1])


def test_entry_fee_is_included_in_cash_drawdown():
    a=run([100])
    assert a[0][1]==.5


def test_higher_costs_cannot_increase_identical_fill_returns():
    a=run([100,-100,200],fraction=0.,cost=1);b=run([100,-100,200],fraction=0.,cost=2)
    np.testing.assert_array_equal(a[3],b[3]);assert b[0][0]<a[0][0]


def test_cash_equals_sum_of_trade_and_annual_net():
    a=run([100,-200,300,200]);assert a[0][0]==a[1].sum()==400


def test_randomized_independent_reconciliation():
    rng=np.random.default_rng(1151)
    for fraction in (0.,.25,.5,1.):
        run(rng.normal(30,200,150),risks=rng.uniform(20,500,150),cap=3.,limit=450.,fraction=fraction,cost=2.)
