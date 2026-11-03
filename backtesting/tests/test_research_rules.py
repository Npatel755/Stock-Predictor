from dataclasses import replace
from types import SimpleNamespace

import pandas as pd
import pytest

from backtesting.config import StrategyConfig
from backtesting.engine import backtest, estimated_round_trip_cost, research_entry_allowed
from test_v11 import deferred_fixture


def research(**kwargs):
    return StrategyConfig(mode="research", **kwargs)


@pytest.mark.parametrize("option", [dict(min_stop_bps=20), dict(min_stop_atr=1), dict(risk_includes_costs=True),
                                     dict(min_reward_cost_ratio=2), dict(min_atr_bps=5), dict(max_atr_bps=50),
                                     dict(min_trend_gap_bps=50), dict(trade_direction="long"), dict(session="us"),
                                     dict(allow_weekends=False), dict(cooldown_bars=10), dict(breakeven_r=1),
                                     dict(trail_atr=2), dict(max_holding_bars=20)])
def test_research_changes_cannot_modify_parity_mode(option):
    with pytest.raises(ValueError, match="research mode"):
        StrategyConfig(**option)


def test_minimum_stop_distance_and_fee_aware_sizing_bound_initial_risk():
    bars, frame = deferred_fixture(n=3)
    cfg = research(min_stop_bps=400, risk_includes_costs=True, slippage_bps=2)
    result = backtest(bars, cfg, indicators=frame)
    p = result.metrics["open_position"]
    signal = bars.close.iloc[2]
    distance = signal * .04
    assert p["stop"] == pytest.approx(signal - distance)
    assert p["target"] == pytest.approx(signal + 2 * distance)
    modeled_risk = p["quantity"] * (distance + estimated_round_trip_cost(cfg, signal))
    assert 99 < modeled_risk <= 100


def test_entry_cost_filter_rejects_trades_with_inadequate_target():
    bars, frame = deferred_fixture(n=3)
    result = backtest(bars, research(min_reward_cost_ratio=1000), indicators=frame)
    assert result.metrics["entries"] == 0
    assert result.metrics["filtered_entry_signals"] == 1


def test_breakeven_updates_only_after_current_bar_cannot_exit_retroactively():
    bars, frame = deferred_fixture(n=4)
    for data in [bars, frame]:
        # Range crosses the eventual breakeven level before the activating close.
        data.loc[3, ["open", "low", "close", "high"]] = [103, 102, 107, 108]
    cfg = research(reward_r=4, breakeven_r=1)
    result = backtest(bars, cfg, indicators=frame)
    assert result.metrics["closed_trade_legs"] == 0
    assert result.metrics["open_position"]["stop"] > 103
    update = result.events[result.events.event == "stop_update"].iloc[0]
    assert update.effective_at == bars.timestamp.iloc[3] + pd.Timedelta(minutes=5)


def test_time_exit_charges_market_slippage_and_commission():
    bars, frame = deferred_fixture(n=5)
    cfg = research(max_holding_bars=1)
    result = backtest(bars, cfg, indicators=frame)
    assert len(result.trades) == 1
    trade = result.trades.iloc[0]
    assert trade.reason == "time_stop"
    assert trade.exit_price == pytest.approx(bars.close.iloc[3] - cfg.slippage_ticks * cfg.tick_size)
    assert trade.commission > 0


def test_session_direction_and_volatility_filters_use_current_available_information():
    row = SimpleNamespace(timestamp=pd.Timestamp("2025-01-06 14:00", tz="UTC"), close=2000, atr5=2,
                          close4h=2010, ema4h=2000)
    assert research_entry_allowed(research(session="us", min_atr_bps=5, max_atr_bps=20,
                                          min_trend_gap_bps=25, trade_direction="long"), row, 1)
    assert not research_entry_allowed(research(trade_direction="short"), row, 1)
    assert not research_entry_allowed(research(min_atr_bps=15), row, 1)
    assert not research_entry_allowed(research(session="asia"), row, 1)
    assert not research_entry_allowed(research(min_trend_gap_bps=60), row, 1)


def test_low_memory_screening_matches_exact_event_replay():
    bars, frame = deferred_fixture(n=300)
    for cfg in [StrategyConfig(), research(min_stop_atr=2, risk_includes_costs=True, max_holding_bars=10)]:
        complete = backtest(bars, cfg, indicators=frame)
        compact = backtest(bars, cfg, indicators=frame, capture_details=False)
        assert complete.metrics == compact.metrics
        pd.testing.assert_frame_equal(complete.trades, compact.trades)
        pd.testing.assert_frame_equal(complete.events, compact.events)
        assert compact.signals.empty and compact.equity.empty


def test_breakeven_does_not_place_a_stop_beyond_current_market_price():
    bars, frame = deferred_fixture(n=4)
    for data in [bars, frame]:
        data.loc[3, ["open", "low", "close", "high"]] = [103., 102.9, 103.3, 103.4]
    cfg = research(breakeven_r=.01, slippage_bps=50)
    result = backtest(bars, cfg, indicators=frame)
    assert not (result.events.event == "stop_update").any()


def test_cooldown_counts_a_position_that_opens_and_closes_in_the_same_next_bar():
    bars, frame = deferred_fixture(n=8)
    for data in [bars, frame]:
        data.loc[3, ["open", "low", "close", "high"]] = [103., 102., 110., 111.]
        data.loc[4, ["open", "low", "close", "high"]] = [101., 99.9, 101., 102.]
        data.loc[5, ["open", "low", "close", "high"]] = [101., 100.5, 104., 105.]
    frame.loc[3, "new15"] = True
    frame.loc[5, ["rv5", "previous_high"]] = [2., 102.]
    cfg = research(entry_timing="next_open", cooldown_bars=10)
    result = backtest(bars, cfg, indicators=frame)
    assert result.metrics["closed_trade_legs"] == 1
    assert result.metrics["entries"] == 1
    assert result.metrics["filtered_entry_signals"] >= 1


def test_failed_volatility_filter_consumes_setup_instead_of_allowing_later_entry():
    bars, frame = deferred_fixture(n=7)
    # Original confirmation is below the experimental volatility threshold.
    # A later candle passes it, but the already-rejected setup must be gone.
    for data in [bars, frame]:
        data.loc[3, ["open", "low", "close", "high"]] = [103, 102, 121, 122]
    frame.loc[3, ["atr5", "rv5", "previous_high"]] = [4, 2, 120]
    cfg = research(min_atr_bps=200)
    result = backtest(bars, cfg, indicators=frame)
    assert result.metrics["filtered_entry_signals"] == 1
    assert result.metrics["entries"] == 0
    assert result.signals.iloc[2].setup_direction == 0
    assert not result.signals.iloc[3].entered
