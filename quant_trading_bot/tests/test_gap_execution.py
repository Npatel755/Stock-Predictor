import json
import numpy as np
import pandas as pd
import pytest
from quant_futures.backtest import Simulator, run_backtest
from quant_futures.config import ResearchConfig, Costs, Execution, RiskLimits
from quant_futures.execution import Action, PaperBroker, Order
from quant_futures.free_data import raw_anchor_sample


def stable_bars(bars, n=8):
    b = bars.iloc[:n].copy()
    b[["open", "close"]] = 6000.
    b["high"], b["low"] = 6000.25, 5999.75
    return b


def test_hold_exit_and_reduce(bars):
    b = stable_bars(bars)
    cfg = ResearchConfig(risk=RiskLimits(max_contracts=2, max_correlated_contracts=2, max_trade_risk=100))
    result = run_backtest(b, [Action.LONG, Action.HOLD, Action.REDUCE_POSITION, Action.HOLD, Action.EXIT, Action.HOLD, Action.HOLD, Action.HOLD], cfg)
    assert list(result["trades"].reason) == ["reduce_position", "signal_exit"]
    assert list(result["trades"].quantity) == [1, 1]
    assert result["curve"].quantity.iloc[2] == 2 and result["curve"].quantity.iloc[3] == 1


def test_roll_books_old_contract_only(bars):
    b = stable_bars(bars)
    cfg = ResearchConfig(costs=Costs(commission_per_side=0, exchange_per_side=0, regulatory_per_side=0, spread_ticks=0, slippage_ticks=0))
    sim = Simulator(cfg)
    sim.step(next(b.iloc[:1].itertuples(index=False)), 1)
    sim.step(next(b.iloc[1:2].itertuples(index=False)), Action.HOLD)
    old, new = b.iloc[2].copy(), b.iloc[2].copy()
    old[["open", "high", "low", "close"]] += 1
    new[["open", "high", "low", "close"]] += 100
    new["contract"] = "MESM26"
    sim.roll_to(old, new)
    sim.step(next(pd.DataFrame([new]).itertuples(index=False)), 0)
    assert sim.cash == 50005 and sim.trades[-1]["reason"] == "roll_exit"


def test_delayed_stop_adverse_gap(bars):
    b = stable_bars(bars, 5)
    b.loc[1, "low"] = 5990.
    b.loc[2, ["open", "high", "low", "close"]] = [5980., 5981., 5979., 5980.]
    cfg = ResearchConfig(execution=Execution(stop_delay_bars=1))
    result = run_backtest(b, [1, Action.HOLD, Action.HOLD, 0, 0], cfg)
    assert result["trades"].reason.iloc[0] == "delayed_stop"
    assert result["trades"].exit_price.iloc[0] <= 5980


def test_cancelled_order_cannot_fill():
    broker = PaperBroker()
    broker.connect()
    order = Order("one", "MES", "MESH26", 1, 1, pd.Timestamp("2026-01-01T00:00Z"))
    broker.submit_order(order)
    broker.cancel_order("one")
    with pytest.raises(RuntimeError):
        broker.fill(order, 6000, 1, pd.Timestamp("2026-01-01T00:01Z"))


def test_time_exit_uses_open_before_intrabar_target(bars):
    b = stable_bars(bars, 4)
    b.loc[2, "high"] = 6010.
    cfg = ResearchConfig(execution=Execution(max_hold_bars=1), costs=Costs(commission_per_side=0,
        exchange_per_side=0, regulatory_per_side=0, spread_ticks=0, slippage_ticks=0))
    result = run_backtest(b, [1, Action.HOLD, Action.HOLD, Action.HOLD], cfg)
    assert result["trades"].reason.iloc[0] == "time_exit"
    assert result["trades"].exit_price.iloc[0] == 6000


def test_public_sample_requires_provenance():
    times = pd.date_range("2026-11-02T00:00Z", periods=12, freq="10s")
    sample = pd.DataFrame(dict(ts=times, open=6000., high=6001., low=5999., close=6000., volume=1))
    ledger = dict(anchor_contract="MESZ26-CME", adjustments={"MESZ26-CME": 0},
        rolls=[dict(to_contract="MESZ26-CME", switch_utc="2026-09-14T22:00Z")],
        last_utc=str(times[-1]+pd.Timedelta(milliseconds=3)), as_of_utc="2026-11-03T00:00Z")
    result = raw_anchor_sample(sample, ledger, "MES")
    assert len(result) == 2 and result.contract.eq("MESZ26").all() and result.volume.eq(6).all()
    ledger["adjustments"]["MESZ26-CME"] = 1
    with pytest.raises(ValueError, match="adjusted"):
        raw_anchor_sample(sample, ledger, "MES")
