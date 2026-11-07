from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from mass_execution import execute


def data(n=8):
    timestamp = pd.date_range("2023-01-03T14:30Z",periods=n,freq="15min").as_unit("ns").asi8
    return dict(timestamp=timestamp,session=np.zeros(n,dtype=np.int64),month=np.ones(n,dtype=np.int64),year=np.full(n,2023),
        minute=np.arange(n)*15+570,contract=np.zeros(n,dtype=np.int64),
        open=np.full(n,6000.),high=np.full(n,6000.25),low=np.full(n,5999.75),close=np.full(n,6000.),volume=np.full(n,1000.))


def cfg(**changes):
    result = dict(multiplier=5.,tick=.25,commission_per_side=1.,spread_ticks=0.,slippage_ticks=0.,
        risk_per_trade=500.,max_open_risk=500.,maxqty=1,stop_ticks=16,target_ratio=2.,hold_bars=2,
        flat_minute=955,entry_end=930,hard_drawdown=1800.,daily_loss=300.)
    result.update(changes)
    return result


def test_next_open_zero_is_hold_and_fee_accounting():
    d = data()
    s = np.zeros(8,dtype=np.int8)
    s[0] = 1
    result = execute(d,s,np.ones(8),cfg())
    assert result["trade_entry"].tolist() == [1]
    assert result["trade_exit"].tolist() == [3]
    assert result["trade_reason"].tolist() == [2]
    assert result["trade_net"].tolist() == [-2.]
    assert result["trade_fees"].tolist() == [2.]
    assert result["equity"][-1] == 49998
    assert result["equity"][-1]-50000 == result["trade_net"].sum()


@pytest.mark.parametrize("side",[1,-1])
def test_stop_first_on_ambiguous_bar_for_both_sides(side):
    d = data()
    d["high"][1],d["low"][1] = 6010.,5990.
    result = execute(d,np.array([side,0,0,0,0,0,0,0]),np.ones(8),cfg())
    assert result["trade_reason"].tolist() == [3]
    assert result["trade_net"][0] == -22.
    assert result["worst"][1] <= result["cash"][1]


def test_target_touch_requires_tick_through_and_retains_adverse_bound():
    d = data()
    d["high"][1] = 6008.
    d["low"][1] = 5998.
    d["high"][2] = 6008.25
    d["low"][2] = 5998.
    result = execute(d,np.array([1,0,0,0,0,0,0,0]),np.ones(8),cfg(hold_bars=7))
    assert result["trade_exit"].tolist() == [2]
    assert result["trade_reason"].tolist() == [4]
    assert result["trade_net"].tolist() == [38.]
    assert result["worst"][2] <= 49988. # target bar's earlier adverse mark survives


def test_scheduled_time_exit_precedes_current_bar_target():
    d = data()
    d["high"][2] = 6010.
    result = execute(d,np.array([1,0,0,0,0,0,0,0]),np.ones(8),cfg(hold_bars=1))
    assert result["trade_reason"].tolist() == [2]
    assert result["trade_exitprice"].tolist() == [6000.]


def test_adverse_gap_stop_and_gap_recovery_are_not_assumed_stop_prices():
    d = data()
    d["open"][2],d["high"][2],d["low"][2],d["close"][2] = 5990.,5990.25,5989.75,5990.
    s = np.array([1,0,0,0,0,0,0,0])
    result = execute(d,s,np.ones(8),cfg(hold_bars=7,slippage_ticks=1))
    assert result["trade_reason"].tolist() == [3]
    assert result["trade_exitprice"][0] == 5989.75
    g = data()
    g["timestamp"][2:] += 3600000000000
    g["minute"][2:] += 60
    g["open"][2],g["high"][2],g["low"][2],g["close"][2] = 5990.,5990.25,5989.75,5990.
    gap_result = execute(g,s,np.ones(8),cfg(hold_bars=7))
    assert gap_result["lock"] == 2 and gap_result["trade_reason"].tolist() == [5]


def test_liquidity_uses_previous_volume_and_ioc_integer_fills():
    d = data()
    d["volume"][0] = 150
    s = np.array([1,0,0,0,0,0,0,0])
    partial = execute(d,s,np.ones(8),cfg(maxqty=3))
    assert partial["trade_qty"].tolist() == [1]
    d["volume"][0] = 300
    full = execute(d,s,np.ones(8),cfg(maxqty=3))
    assert full["trade_qty"].tolist() == [3]
    assert full["trade_fees"].tolist() == [6.]


def test_open_roll_rejects_and_flat_roll_cancels_pending():
    d = data()
    d["contract"][2:] = 1
    s = np.array([1,0,0,0,0,0,0,0])
    with pytest.raises(RuntimeError,match="raw contract"):
        execute(d,s,np.ones(8),cfg(hold_bars=7))
    d["contract"][1:] = 1
    flat = execute(d,s,np.ones(8),cfg())
    assert len(flat["trade_net"]) == 0


def test_hard_lock_survives_next_session_and_daily_lock_resets():
    d = data()
    d["session"][4:] = 1
    d["high"][1],d["low"][1] = 6000.25,5990.
    s = np.array([1,0,1,0,1,0,0,0])
    permanent = execute(d,s,np.ones(8),cfg(hard_drawdown=20,daily_loss=300))
    assert permanent["lock"] == 1
    assert len(permanent["trade_net"]) == 1
    daily = execute(d,s,np.ones(8),cfg(hard_drawdown=1800,daily_loss=20))
    assert daily["lock"] == 0
    assert daily["trade_entry"].tolist() == [1,5]


def test_trailing_stop_uses_previous_close_and_is_prefix_invariant():
    d = data()
    d["high"][1],d["low"][1],d["close"][1] = 6005.,5999.75,6004.
    d["open"][2],d["high"][2],d["low"][2],d["close"][2] = 6004.,6005.,6002.,6003.
    s = np.array([1,0,0,0,0,0,0,0])
    result = execute(d,s,np.ones(8),cfg(hold_bars=7,trailing_atr=1))
    assert result["trade_exit"].tolist() == [2]
    assert result["trade_exitprice"].tolist() == [6003.]
    changed = {k:v.copy() for k,v in d.items()}
    changed["high"][1] += 100
    other = execute(changed,s,np.ones(8),cfg(hold_bars=7,trailing_atr=1,target_ratio=50))
    original = execute(d,s,np.ones(8),cfg(hold_bars=7,trailing_atr=1,target_ratio=50))
    np.testing.assert_array_equal(other["trade_net"],original["trade_net"])


def test_eod_floor_ratchets_only_completed_cash_and_caps():
    d = data(6)
    d["session"][:] = [0,0,0,1,1,1]
    d["open"][2],d["high"][2],d["low"][2],d["close"][2] = 6100.,6100.25,6099.75,6100.
    s = np.array([1,0,0,0,0,0])
    result = execute(d,s,np.ones(6),cfg(multiplier=50.,risk_per_trade=1000,max_open_risk=1000,hold_bars=1,target_ratio=100))
    assert result["funded_floor"][2] == 48000
    assert result["funded_floor"][3] == 50100
    assert result["equity"][-1]-50000 == result["trade_net"].sum()


def test_supported_subset_matches_shared_simulator_trade_economics():
    from quant_futures.backtest import run_backtest
    from quant_futures.config import ResearchConfig,Costs,Execution,RiskLimits
    from quant_futures.data import canonical
    from quant_futures.execution import Action
    d = data()
    b = canonical(pd.DataFrame(dict(timestamp_utc=pd.to_datetime(d["timestamp"],utc=True),instrument="MES",contract="MESH23",
        open=d["open"],high=d["high"],low=d["low"],close=d["close"],volume=d["volume"])))
    config = ResearchConfig(instrument="MES",timeframe_minutes=15,costs=Costs(commission_per_side=1,exchange_per_side=0,regulatory_per_side=0,
        spread_ticks=0,slippage_ticks=0),execution=Execution(stop_ticks=16,target_ticks=32,max_hold_bars=2,max_gap_minutes=20,session_flat_minute_et=955),
        risk=RiskLimits(max_trade_risk=500,max_open_risk=500,max_daily_loss=300,max_drawdown=1800))
    shared = run_backtest(b,[Action.LONG]+[Action.HOLD]*7,config)
    fast = execute(d,np.array([1,0,0,0,0,0,0,0]),np.ones(8),cfg())
    np.testing.assert_allclose(fast["trade_net"],shared["trades"].net_pnl.to_numpy())
    np.testing.assert_allclose(fast["equity"],shared["curve"].equity.to_numpy())


@pytest.mark.parametrize("symbol,mult,fee",[("ES",50.,1.75),("NQ",20.,1.75),("MES",5.,.5),("MNQ",2.,.5)])
def test_cost_and_rounding_parity_across_contract_specs(symbol,mult,fee):
    from quant_futures.backtest import run_backtest
    from quant_futures.config import ResearchConfig,Costs,Execution,RiskLimits
    from quant_futures.data import canonical
    from quant_futures.execution import Action
    from quant_futures.transfer import ReferenceConfig
    d = data()
    d["open"][2:],d["high"][2:],d["low"][2:],d["close"][2:] = 6001.,6001.25,6000.75,6001.
    b = canonical(pd.DataFrame(dict(timestamp_utc=pd.to_datetime(d["timestamp"],utc=True),instrument=symbol,contract=symbol+"H23",
        open=d["open"],high=d["high"],low=d["low"],close=d["close"],volume=d["volume"])))
    klass = ReferenceConfig if symbol in ("ES","NQ") else ResearchConfig
    config = klass(instrument=symbol,timeframe_minutes=15,costs=Costs(commission_per_side=fee,exchange_per_side=0,regulatory_per_side=0,
        spread_ticks=1,slippage_ticks=1),execution=Execution(stop_ticks=16,target_ticks=32,max_hold_bars=2,max_gap_minutes=20,session_flat_minute_et=955),
        risk=RiskLimits(max_trade_risk=1000,max_open_risk=1000,max_daily_loss=300,max_drawdown=1800))
    shared = run_backtest(b,[Action.SHORT]+[Action.HOLD]*7,config)
    fast = execute(d,np.array([-1,0,0,0,0,0,0,0]),np.ones(8),cfg(multiplier=mult,commission_per_side=fee,spread_ticks=1,slippage_ticks=1,
        risk_per_trade=1000,max_open_risk=1000))
    np.testing.assert_allclose(fast["trade_net"],shared["trades"].net_pnl.to_numpy())
    np.testing.assert_allclose(fast["trade_entryprice"],shared["trades"].entry_price.to_numpy())
    np.testing.assert_allclose(fast["trade_exitprice"],shared["trades"].exit_price.to_numpy())
    np.testing.assert_allclose(fast["equity"],shared["curve"].equity.to_numpy())


def test_fractional_signal_is_rejected_instead_of_silently_cast():
    d = data()
    with pytest.raises(ValueError,match="Signals"):
        execute(d,np.array([1.5,0,0,0,0,0,0,0]),np.ones(8),cfg())
