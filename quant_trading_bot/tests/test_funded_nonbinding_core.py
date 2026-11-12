import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import numpy as np
from funded_nonbinding_core import replay,reference

D=86400000000000


def run(p,lo=None,keep=8500.,fraction=0.,same_day=False,weight=1.,max_m=4.,initial=1.):
    n=len(p);t=np.arange(n,dtype=np.int64)*D;tout=t+D//2
    days=np.array([0],np.int64) if same_day else t.copy();offset=np.array([0,n],np.int64) if same_day else np.arange(n+1,dtype=np.int64)
    if same_day:t=np.arange(n,dtype=np.int64)*100;tout=t+50
    args=(days,offset,t,tout,np.asarray(p,float),np.full(n,50.),np.full(n,weight),
        np.minimum(p,0.) if lo is None else np.asarray(lo,float),np.maximum(p,0.),0,n*D,keep,max_m,initial,900.,fraction)
    a=replay(*args);b=reference(*args);np.testing.assert_allclose(a,b,atol=1e-7,rtol=0)
    return a


def test_global_dd_above2000_can_remain_within_static_account_rules():
    a=run([3000,-600,-600,-600,-600],keep=1e6)
    assert a[9]>=2400 and a[7]==a[8]==0 and a[2]==600


def test_dll_touch_is_unresolved_not_permanent_floor_closure():
    a=run([-1300]);assert a[8]==1 and a[7]==0 and a[0]==0


def test_recovery_after_intratrade_dll_is_never_credited():
    a=run([500],lo=[-1200]);assert a[8]==1 and a[3]==a[0]==0


def test_first_payout_locks_floor_at_zero():
    a=run([3000,-700,-700,-700],keep=2000.)
    assert a[0]==1000 and a[2]==600 and a[7]==1


def test_daily_payout_cap1500_and_profit_split():
    a=run([10000],keep=2000.);assert a[0]==1500 and a[1]==1350 and a[2]==8500


def test_daily_minimum250():
    assert run([2200],keep=2000.)[0]==0
    assert run([2300],keep=2000.)[0]==300


def test_personal_session_stop_checks_completed_loss_before_new_entry():
    a=run([-450,2000],same_day=True);assert a[3]==-450 and a[6]==1


def test_cash_and_gross_withdrawals_reconcile():
    a=run([3000,500,800],keep=2000.)
    np.testing.assert_allclose(a[0]+a[2],a[3],atol=1e-7)


def test_dll_resets_each_day_instead_of_accumulating_daily_losses():
    a=run([3000,-600,-600,-600],keep=1e6);assert a[8]==0


def test_size_budget_uses_prior_cash_not_current_trade_profit():
    a=run([100],fraction=.5);b=run([-100],fraction=.5)
    assert a[10]==b[10]==1


def test_risk_fraction_shrinks_size_instead_of_clipping_trade_return():
    a=run([-150],fraction=.25,weight=10.,max_m=1.)
    assert a[10]==5 and a[3]==-750


def test_integer_contract_limit20_is_never_exceeded():
    a=run([10],weight=100.,initial=4.,max_m=4.);assert a[10]<=18 #900stopcap/50risk


def test_randomized_reference_paths():
    rng=np.random.default_rng(20261111)
    for f in (0.,.25,.5):run(rng.normal(30,80,120),keep=2000.,fraction=f,initial=2.)
