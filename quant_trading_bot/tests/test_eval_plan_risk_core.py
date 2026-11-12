import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import numpy as np
import pytest
from eval_plan_risk_core import day,evaluate,configurations


def run(per,mae=None,a=None,b=None,k=3,bal=0.,risk=None,fraction=0.,cap=900.,lock=False,best=0.):
    per=np.array(per,float);n=len(per)
    mae=np.minimum(per,0.) if mae is None else np.array(mae,float)
    a=np.arange(n)*10 if a is None else np.array(a)
    b=a+1 if b is None else np.array(b)
    risk=np.ones(n)*100 if risk is None else np.array(risk,float)
    return day(per,mae,np.ones(n),risk,a,b,k,bal,best,fraction,cap,lock,np.zeros(n))


def test_budget_unique_before_research():
    configs=configurations();assert len(configs)==45 and len({c['name'] for c in configs})==45
    assert configs[0]['name']=='INCUMBENT'


def test_open_trade_final_pnl_cannot_block_next_entry():
    # Earlier trade not closed: its final loss must not trigger realised stop.
    p,w=run([-250,100],[-250,-10],a=[0,1],b=[3,2])
    assert p==-450 and w<=-750


def test_already_closed_loss_does_block_new_entry():
    p,w=run([-250,100],[-250,-10],a=[0,4],b=[3,5])
    assert p==-750


def test_mae_never_better_than_final_loss():
    p,w=run([-100],mae=[-10]);assert p==-300 and w==-300


def test_room_sizing_does_not_use_current_trade_outcome():
    # q=floor((2000+0)*.15/100)=3 regardless of future outcome.
    p1,_=run([100],fraction=.15)
    p2,_=run([-100],fraction=.15)
    assert p1==300 and p2==-300


def test_buffer_fraction_reduces_quantity_near_floor():
    p,_=run([100],fraction=.15,bal=-1500.,k=3)
    assert p==0 # allowed75<risk100,skip rather than useMAE to choose


def test_daily_loss_caps_negative_day_and_bounds():
    p,w=run([-400],mae=[-400]);assert p==-1000 and w<=-1200


def test_static_floor_touch_fails_before_target():
    args=[np.array([0,1]),np.array([2000.]),np.array([-2100.]),np.ones(1),np.array([100.]),np.array([0]),np.array([1]),np.array([0]),np.array([0])]
    s,days,end,lo=evaluate(*args,np.array([0.,900.,0.,3.,5.,60.]),np.zeros(1))
    assert s[0]==2


def test_90_calendar_day_deadline_excludes_day90():
    args=[np.array([0,1,2]),np.array([0.,2000.]),np.zeros(2),np.ones(2),np.ones(2)*100,np.array([0,1]),np.array([0,1]),np.array([0,90]),np.array([0])]
    s,days,end,lo=evaluate(*args,np.array([0.,900.,0.,3.,5.,60.]),np.zeros(2))
    assert s[0]==0 and end[0]==0


def test_lock_pass_cannot_use_future_earlier_trade_profit():
    # Day1 trade still open at trade2 entry; no pass-lock yet.
    p,_=run([500,100],mae=[0,0],a=[0,1],b=[4,2],bal=3000.,best=1000.,lock=True)
    assert p==1800


def test_deployed_daily_stop_not_selected_using_future_sizes():
    p,w=run([-220,1000],mae=[-220,0],risk=[800,100],a=[0,3],b=[2,4],k=3)
    # Firsttradeq1 loss220 is above700stop; secondtrade stilleligible.
    assert p==2780
