import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import numpy as np
from gemini_stack_reserve_core import replay_reserve, reference
from gemini_stack_account_core import replay


def execute(daily, keep=8600., on=8700., off=8700., four=5400., net=None, risk=None, starts=None):
    if net is None: net = np.broadcast_to(np.asarray(daily, dtype=float), (3,4,2,len(daily))).copy()
    n = net.shape[-1]; dates = np.arange(n)
    if risk is None: risk = np.zeros((3,4,n))
    if starts is None: starts = np.array([0])
    ends = np.full(len(starts), n); years = np.full(len(starts), 365)
    result = replay_reserve(net,risk,dates,starts,ends,years,keep,on,off,four)
    for i, start in enumerate(starts):
        np.testing.assert_allclose(result[i], reference(net,risk,dates,start,n,365,keep,on,off,four), atol=1e-8, rtol=0)
    return result


def test_original_policy_exact_parity_randomized_paths():
    rng = np.random.default_rng(411)
    net = rng.normal(30,380,(3,4,2,800)); risk = rng.uniform(0,1500,(3,4,800))
    starts = np.array([0,40,150,300]); dates = np.arange(800)
    a = execute([],net=net,risk=risk,starts=starts)
    old = replay(net,risk,dates,starts,np.full(4,800),np.full(4,365),8600.,8700.,8700.,1500.)
    np.testing.assert_allclose(a[:,:10],old,atol=1e-8,rtol=0)


def test_hysteresis_uses_previous_balance_and_remains_on_at_release_boundary():
    net = np.zeros((3,4,2,5)); net[0,:,:,:] = [9000,-500,1,0,0]
    net[2,:,:,:] = [0,-500,-501,200,200]
    a = execute([],keep=1e6,on=8000,off=7500,net=net)[0]
    # Day0 earns9000 then first500 withdrawal. Day1 starts8500 -> on;
    # day2 starts8000 -> stays on; day3 starts7499 -> off.
    assert a[12] == 2
    assert a[8] == 7999


def test_no_hysteresis_matches_immediate_release():
    net = np.zeros((3,4,2,4)); net[0,:,:,:] = [9000,0,0,0]; net[2,:,:,:] = [0,-1000,50,0]
    a = execute([],keep=1e6,on=8000,off=8000,net=net)[0]
    assert a[8] == 8000 and a[12] == 2


def test_scaling_threshold_uses_start_of_day_balance():
    net = np.zeros((3,4,2,3)); net[:,:,:,0] = 6000
    net[:,2,:,1:] = 100; net[:,3,:,1:] = 500
    a = execute([],keep=1e6,four=6500,net=net)[0]
    b = execute([],keep=1e6,four=5400,net=net)[0]
    assert a[8] == 6200 and b[8] == 7000


def test_payout_caps_and_conservation():
    a = execute([6000]+[10000]*8)[0]
    assert a[0] == 500+1500*8 and a[9] == 9
    assert a[0]+a[7] == a[8]


def test_daily_loss_clip_and_floor_touch():
    a = execute([-9000,-9000,1e6])[0]
    assert a[1] == 1 and a[8] == -2000 and a[10] == 2000


def test_payout_changes_floor_and_room():
    a = execute([6000]+[-1000]*6)[0]
    assert a[0] == 500 and a[1] == 1 and a[11] == -500


def test_withdrawals_are_not_trading_drawdown():
    a = execute([6000]+[2000]*10)[0]
    assert a[0] > 0 and a[10] == 0


def test_future_does_not_change_finished_window_and_state_resets():
    a = execute([9000,-500,200,100],keep=1e6,on=8000,off=7500,starts=np.array([0,2]))
    b = execute([200,100],keep=1e6,on=8000,off=7500)[0]
    np.testing.assert_allclose(a[1],b)


def test_risk_proxy_is_separate_from_actual_floor_closure():
    a = execute([200],risk=np.full((3,4,1),2500.))[0]
    assert a[2] == 1 and a[1] == 0
