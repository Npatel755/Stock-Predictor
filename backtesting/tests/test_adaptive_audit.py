import pandas as pd
import pytest

from backtesting.adaptive_audit import choose, close_at_boundary, trailing_evidence
from backtesting.config import StrategyConfig
from backtesting.engine import backtest
from test_v11 import deferred_fixture


def shadow_series():
    dates = pd.date_range("2020-01-01", "2022-07-01", freq="D", tz="UTC")
    equity = pd.DataFrame({"timestamp": dates, "equity": 50000 + pd.Series(range(len(dates))) * 3.,
                           "intrabar_worst_equity": 49999 + pd.Series(range(len(dates))) * 3.})
    trades = pd.DataFrame({"exit_time": pd.date_range("2020-01-01", "2022-07-01", freq="10D", tz="UTC")})
    return equity, trades


def test_allocation_scores_do_not_change_when_future_equity_or_exits_change():
    equity, trades = shadow_series()
    boundary = pd.Timestamp("2022-01-01", tz="UTC")
    initial = trailing_evidence(equity, trades, boundary)
    assert initial["eligible"]
    modified = equity.copy()
    modified.loc[modified.timestamp > boundary, ["equity", "intrabar_worst_equity"]] *= 10
    more_trades = pd.concat([trades, pd.DataFrame({"exit_time": [boundary + pd.Timedelta(days=1)] * 100})])
    assert trailing_evidence(modified, more_trades, boundary) == initial
    assert choose({"candidate": initial}) == "candidate"


def test_cash_is_chosen_without_enough_evidence_or_positive_scored_profit():
    equity, trades = shadow_series()
    insufficient = trailing_evidence(equity, trades.iloc[:2], "2022-01-01")
    assert not insufficient["eligible"]
    assert choose({"too_few": insufficient}) == "cash"
    assert choose({"weak": {"eligible": True, "score": -1}}) == "cash"
    assert not trailing_evidence(equity, trades, "2020-06-01")["eligible"]


def test_scheduled_rebalance_liquidates_using_actual_broker_friction_once():
    bars, frame = deferred_fixture(n=4)
    cfg = StrategyConfig(mode="research", slippage_bps=2.)
    result = backtest(bars, cfg, indicators=frame)
    assert result.metrics["open_position"] is not None
    fixed = close_at_boundary(result, bars, cfg)
    assert fixed.metrics["open_position"] is None
    assert fixed.trades.iloc[-1].reason == "scheduled_rebalance"
    assert fixed.trades.iloc[-1].exit_price == pytest.approx(bars.close.iloc[-1] - .02 - bars.close.iloc[-1] * .0002)
    assert fixed.metrics["final_cash"] == pytest.approx(50000 + fixed.trades.net_pnl.sum())
    assert fixed.equity.equity.iloc[-1] == fixed.metrics["final_cash"]
    assert fixed.metrics["total_commission"] == pytest.approx(fixed.trades.commission.sum())
