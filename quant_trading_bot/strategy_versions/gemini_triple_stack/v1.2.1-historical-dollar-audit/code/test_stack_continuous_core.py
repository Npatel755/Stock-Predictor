import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import numpy as np
from stack_continuous_core import continuous,reference

D=86400000000000


def simulate(p,lo=None,hi=None,target=1850,frac=.5,cap=1,marked=False,cost=1,years=None,valid=None):
    n=len(p);a=np.arange(n,dtype=np.int64)*D;b=a+D//2
    args=(a,b,np.array(p,dtype=float),np.full(n,100.),np.ones(n),np.full(n,2.),
        np.minimum(p,0.) if lo is None else np.asarray(lo,dtype=float),
        np.maximum(p,0.) if hi is None else np.asarray(hi,dtype=float),
        np.ones(n,dtype=np.bool_) if valid is None else np.asarray(valid),
        np.zeros(n,dtype=np.int64) if years is None else np.asarray(years),0,n*D,
        float(cap),450.,frac,float(target),marked,float(cost))
    x=continuous(*args);y=reference(*args)
    for v,w in zip(x,y):np.testing.assert_allclose(v,w,atol=1e-9,rtol=0)
    return x


def test_complete_gap_loss_debited_without_clipping():
    x=simulate([-2400]);assert x[0][0]==-2400 and x[0][1]==2400 and x[0][-1]==1


def test_current_excursion_does_not_choose_entry_quantity():
    a=simulate([100],lo=[-50],hi=[150]);b=simulate([100],lo=[-1800],hi=[150])
    assert a[3][0]==b[3][0]==1


def test_pessimistic_intrabar_order_bounds_range():
    x=simulate([100],lo=[-300],hi=[500]);assert x[0][2]==800


def test_drawdown_and_risk_state_do_not_reset_on_calendar_year():
    x=simulate([-900,10],lo=[-900,0],hi=[0,10],target=1000,years=[0,1])
    assert x[3][1]==0 and x[0][0]==-900


def test_completed_favorable_peak_can_reduce_later_allocation():
    a=simulate([100,100],hi=[1800,100],marked=True)
    b=simulate([100,100],hi=[1800,100],marked=False)
    assert a[3][1]==0 and b[3][1]==1


def test_unknown_path_fails_closed_instead_of_zero_mae():
    x=simulate([100],valid=[False]);assert x[0][6]==1 and x[0][7]==1


def test_doubled_entry_fee_in_cash_drawdown():
    assert simulate([100],cost=2)[0][1]==1


def test_quantity_integer_and_no_hidden_risk_budget_reset():
    x=simulate([-1500,100,100],target=1600,frac=.5)
    np.testing.assert_array_equal(x[3],[1,0,0])


def test_all_years_trade_cash_conservation():
    x=simulate([100,200,300],years=[0,7,13]);assert x[0][0]==x[1].sum()==600


def test_random_path_reference_parity():
    rng=np.random.default_rng(20261111)
    for marked in (False,True):
        p=rng.normal(25,70,150)
        simulate(p,lo=np.minimum(p,0)-rng.uniform(1,100,150),hi=np.maximum(p,0)+rng.uniform(1,100,150),marked=marked)
