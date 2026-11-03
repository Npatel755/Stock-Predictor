"""Version-specific source regressions: retain v1 and implement supplied v1.1."""
from pathlib import Path
import hashlib

import pandas as pd
import pytest

from backtesting.config import StrategyConfig
from backtesting.engine import Broker, backtest
from backtesting.paths import PINE, PINE_V1
from test_dvs import state_fixture


def deferred_fixture(n=35, confirm_at=2):
    bars, indicators = state_fixture(n=n, confirm_at=confirm_at)
    # Retest level=100 +/- .25 ATR. The confirmation candle must leave that
    # neighborhood, or v1.1 advances lastRetestBar again and blocks confirmation.
    for frame in [bars, indicators]:
        frame.loc[confirm_at, "open"] = 100.6
        frame.loc[confirm_at, "low"] = 100.5
    return bars, indicators


def test_v11_is_default_with_version_specific_commission_and_source_hash():
    assert StrategyConfig().strategy_version == "v1.1"
    assert StrategyConfig().commission_bps == 4
    assert StrategyConfig(strategy_version="v1").commission_bps == 5
    with pytest.raises(ValueError, match="Pine-fixed"):
        StrategyConfig(commission_bps=5)
    bars, indicators = deferred_fixture()
    for version, source in [("v1", PINE_V1), ("v1.1", PINE)]:
        result = backtest(bars, StrategyConfig(strategy_version=version), indicators=indicators)
        assert result.provenance["pine_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()


def test_v11_forbids_same_bar_retest_confirmation_that_v1_allowed():
    bars, indicators = state_fixture()
    original = backtest(bars, StrategyConfig(strategy_version="v1"), indicators=indicators)
    fixed = backtest(bars, StrategyConfig(), indicators=indicators)
    assert original.signals.iloc[1].entered
    assert not fixed.signals.iloc[1].entered
    assert fixed.metrics["entries"] == 0


def test_v11_accepts_separate_confirmation_and_does_not_use_prior_intrabar_high():
    bars, indicators = deferred_fixture()
    result = backtest(bars, indicators=indicators)
    assert result.signals.iloc[1].retested
    assert result.signals.iloc[1].last_retest_bar == 1
    assert result.signals.iloc[2].entered
    assert result.metrics["entries"] == 1
    assert result.metrics["closed_trade_legs"] == 0
    assert result.metrics["open_position"]["entry_price"] == pytest.approx(103.02)
    assert result.metrics["open_position"]["stop"] == pytest.approx(99.8)


def test_v11_every_nearby_bar_postpones_confirmation_not_just_first_retest():
    bars, indicators = state_fixture(n=8, confirm_at=2)
    # Row 2 is simultaneously nearLevel and a would-be confirmation.
    # Row 3 is a real later confirmation outside the near-level zone.
    for frame in [bars, indicators]:
        frame.loc[3, ["open", "close", "low", "high"]] = [103., 121., 102., 122.]
    indicators.loc[3, ["rv5", "previous_high"]] = [2., 120.]
    result = backtest(bars, indicators=indicators)
    assert not result.signals.iloc[2].entered
    assert result.signals.iloc[2].last_retest_bar == 2
    assert result.signals.iloc[3].entered


def test_v11_daily_lock_survives_equity_recovery_until_utc_reset():
    bars, indicators = deferred_fixture(n=300)
    # Entry fees + slippage breach the $1 gate on row 3. Row 4 recovers
    # unrealized equity, but remains below the target and cannot unlock v1.1.
    for frame in [bars, indicators]:
        frame.loc[3, ["open", "close", "low", "high"]] = [103., 103., 102.8, 103.2]
        frame.loc[4, ["open", "close", "low", "high"]] = [103., 106., 102.8, 106.2]
    result = backtest(bars, StrategyConfig(max_daily_loss=1), indicators=indicators)
    assert result.signals.iloc[3].daily_locked
    assert result.equity.iloc[4].equity > 50000
    assert result.signals.iloc[4].daily_locked and not result.signals.iloc[4].can_trade
    assert result.equity.iloc[4].position_qty > 0  # still no forced liquidation
    assert not result.signals.iloc[288].daily_locked
    assert result.signals.iloc[288].can_trade


def test_v11_clears_waiting_setup_when_daily_limit_blocks_new_entries():
    bars, indicators = deferred_fixture(n=300)
    # Enter first, then close the position profitably on row 3. Daily entry
    # limit blocks any new setup; resetting tomorrow does not restore one.
    for frame in [bars, indicators]:
        frame.loc[3, ["open", "close", "high", "low"]] = [110., 110., 111., 109.]
    indicators.loc[3, "new15"] = True
    result = backtest(bars, StrategyConfig(max_trades_day=1), indicators=indicators)
    assert result.signals.iloc[3].setup_direction == 0
    assert not result.signals.iloc[3].can_trade
    assert result.signals.iloc[288].setup_direction == 0


def test_v11_point_value_scales_quantity_and_broker_accounting():
    bars, indicators = deferred_fixture(n=5)
    one = backtest(bars, StrategyConfig(point_value=1), indicators=indicators)
    ten = backtest(bars, StrategyConfig(point_value=10), indicators=indicators)
    assert ten.metrics["open_position"]["quantity"] == pytest.approx(3.125)
    assert one.metrics["open_position"]["quantity"] == pytest.approx(31.25)
    assert ten.metrics["final_equity"] == pytest.approx(one.metrics["final_equity"])
    assert ten.metrics["total_commission"] == pytest.approx(one.metrics["total_commission"])


def test_closed_equity_drawdown_does_not_treat_open_trade_runup_as_realized_peak():
    broker = Broker(StrategyConfig(initial_capital=1000))
    now = pd.Timestamp("2025-01-01", tz="UTC")
    broker.enter(1, 1, 100, 90, 130, now, now)
    broker.mark(120)  # unrealized gain, not a new realized equity peak
    broker.mark(99)
    assert broker.closed_equity_drawdown_usd == pytest.approx(1.060008)
    assert broker.max_drawdown > .02
    assert broker.closed_equity_drawdown_fraction < .002


def test_v11_signal_and_equity_history_does_not_change_when_future_prices_change():
    from test_dvs import candles
    bars = candles(2000)
    changed = bars.copy()
    changed.loc[1300:, ["open", "close", "high", "low", "volume"]] *= 2
    first, second = backtest(bars), backtest(changed)
    pd.testing.assert_frame_equal(first.signals.iloc[:1300], second.signals.iloc[:1300])
    pd.testing.assert_frame_equal(first.equity.iloc[:1300], second.equity.iloc[:1300])
