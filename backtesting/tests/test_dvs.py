"""Causality, Pine state transitions and broker ordering regression tests."""
from dataclasses import replace
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock
import zipfile

import numpy as np
import pandas as pd
import pytest

from backtesting.config import StrategyConfig
from backtesting.engine import Broker, backtest
from backtesting.indicators import confirmed_pivots, latest_two_events, prepare_indicators, rma
from backtesting.market_data import clean_candles, load_history, read_archive
from backtesting.reconcile import compare_trades


def candles(n=2000):
    rng = np.random.default_rng(123)
    close = 2000 * np.exp(np.cumsum(rng.normal(0, .002, n)))
    op = np.r_[close[0], close[:-1]]
    times = pd.date_range("2025-01-01", periods=n, freq="5min", tz="UTC")
    return pd.DataFrame({"timestamp": times, "exchange_close_time": times + pd.Timedelta(minutes=5) - pd.Timedelta(milliseconds=1),
                         "ticker": "BINANCE:ETHUSDT.P", "open": op, "close": close,
                         "high": np.maximum(op, close) * 1.001, "low": np.minimum(op, close) * .999,
                         "volume": rng.uniform(10, 100, n)})


def state_fixture(n=35, confirm_at=1):
    bars = candles(n)
    bars[["open", "close"]] = 101.
    bars["high"], bars["low"] = 102., 99.9
    bars.loc[confirm_at, ["open", "close", "high"]] = [100.1, 103., 120.]
    frame = bars.copy()
    for key, value in dict(atr5=1., rv5=0., previous_high=102., previous_low=99., bull_bias=True, bear_bias=False,
                           new15=False, res15=100., sup15=90., p15=99., c15=101., v15=2., segment=1).items():
        frame[key] = value
    frame.loc[0, "new15"] = True
    frame.loc[confirm_at, "rv5"] = 2.
    return bars, frame


def test_future_mutations_do_not_change_indicators_or_strategy_prefix():
    bars = candles(3500)
    baseline = prepare_indicators(bars)
    altered = bars.copy()
    altered.loc[2400:, ["open", "high", "low", "close", "volume"]] *= 2
    second = prepare_indicators(altered)
    pd.testing.assert_frame_equal(baseline.iloc[:2400], second.iloc[:2400])
    a = backtest(bars)
    b = backtest(altered)
    pd.testing.assert_frame_equal(a.signals.iloc[:2400], b.signals.iloc[:2400])
    pd.testing.assert_frame_equal(a.equity.iloc[:2400], b.equity.iloc[:2400])


@pytest.mark.parametrize("length", [580, 601, 717, 860, 1001])
def test_prefix_equivalence_at_incomplete_htf_boundaries(length):
    bars = candles(1400)
    complete = prepare_indicators(bars).iloc[:length].reset_index(drop=True)
    prefix = prepare_indicators(bars.iloc[:length]).reset_index(drop=True)
    pd.testing.assert_frame_equal(prefix, complete)


def test_pivot_only_emits_after_two_right_bars_and_ties_select_rightmost():
    source = pd.Series([1., 2., 5., 3., 2., 1.])
    p = confirmed_pivots(source)
    assert p.iloc[:4].isna().all()
    assert p.iloc[4] == 5
    tied = confirmed_pivots(pd.Series([1., 2., 5., 5., 2., 1.]))
    assert pd.isna(tied.iloc[4])
    assert tied.iloc[5] == 5


def test_valuewhen_counts_equal_events_independently():
    newest, older = latest_two_events(pd.Series([np.nan, 5., np.nan, 5., 7.]))
    assert newest.iloc[3] == older.iloc[3] == 5
    assert newest.iloc[4] == 7 and older.iloc[4] == 5


def test_rma_seeds_with_sma_then_wilder_updates():
    result = rma(pd.Series([1., 2., 3., 6.]), 3)
    assert result.iloc[:2].isna().all()
    assert result.iloc[2] == 2
    assert result.iloc[3] == pytest.approx(10 / 3)


def test_previous_completed_daily_close_only_available_next_day():
    bars = candles(1000)
    expected = bars.iloc[575].close > bars.iloc[287].close
    indicators = prepare_indicators(bars)
    assert bool(indicators.loc[576, "daily_up"]) == expected
    assert not indicators.loc[575, "daily_up"]  # first day has no preceding second close
    assert indicators.loc[576, "close4h"] == bars.iloc[575].close


def test_rvol_excludes_current_candle_from_both_denominators():
    bars = candles(200)
    indicators = prepare_indicators(bars)
    assert indicators.loc[30, "rv5"] == pytest.approx(bars.loc[30, "volume"] / bars.loc[10:29, "volume"].mean())
    fifteen = bars.set_index("timestamp").volume.resample("15min").sum()
    # At 15m index 22, v15 uses candle 21 over SMA at candle 20, including 1..20.
    assert indicators.loc[66, "v15"] == pytest.approx(fifteen.iloc[21] / fifteen.iloc[1:21].mean())


def test_retest_may_confirm_on_same_bar_but_never_on_breakout_bar():
    bars, indicators = state_fixture()
    result = backtest(bars, indicators=indicators)
    assert not result.signals.iloc[0].retested
    assert result.signals.iloc[1].entered
    assert result.metrics["entries"] == 1
    # Earlier entry-bar high of 120 cannot hit the newly created target retroactively.
    assert not len(result.trades)
    assert result.metrics["open_position"]["entry_price"] == pytest.approx(103.02)
    assert result.metrics["open_position"]["stop"] == pytest.approx(99.8)
    assert result.metrics["open_position"]["quantity"] == pytest.approx(31.25)


@pytest.mark.parametrize("confirm_at,entries", [(24, 1), (25, 0)])
def test_retest_timeout_is_strictly_greater_than_window(confirm_at, entries):
    bars, indicators = state_fixture(confirm_at=confirm_at)
    result = backtest(bars, indicators=indicators)
    assert result.metrics["entries"] == entries


def test_failed_setup_is_cancelled_before_confirmation():
    bars, indicators = state_fixture(confirm_at=2)
    bars.loc[1, ["open", "close", "low"]] = [101., 99., 98.]
    indicators.loc[1, ["open", "close", "low"]] = [101., 99., 98.]
    result = backtest(bars, indicators=indicators)
    assert result.signals.iloc[1].failed
    assert result.metrics["entries"] == 0


def test_short_setup_mirrors_long_retest_and_stop_buffer():
    bars, indicators = state_fixture()
    for frame in [bars, indicators]:
        op, high, low, close = [frame[column].copy() for column in ["open", "high", "low", "close"]]
        frame["open"], frame["close"] = 200 - op, 200 - close
        frame["high"], frame["low"] = 200 - low, 200 - high
    indicators["bull_bias"], indicators["bear_bias"] = False, True
    indicators["sup15"], indicators["p15"], indicators["c15"] = 100., 101., 99.
    indicators["previous_low"] = 98.
    result = backtest(bars, indicators=indicators)
    position = result.metrics["open_position"]
    assert result.metrics["entries"] == 1
    assert position["direction"] == -1
    assert position["entry_price"] == pytest.approx(96.98)
    assert position["stop"] == pytest.approx(100.2)


def test_daily_loss_rule_gates_entries_without_flattening_existing_position():
    bars, indicators = state_fixture(n=300)
    result = backtest(bars, StrategyConfig(max_daily_loss=1.), indicators=indicators)
    assert not result.signals.iloc[2].can_trade
    assert result.equity.iloc[2].position_qty > 0  # gate does not force liquidation
    assert result.signals.iloc[288].can_trade  # UTC daily equity anchor resets
    assert result.signals.iloc[288].entries_today == 0


def test_bias_invalidation_precedes_retest_confirmation():
    bars, indicators = state_fixture()
    indicators.loc[1, "bull_bias"] = False
    result = backtest(bars, indicators=indicators)
    assert result.signals.iloc[1].expired
    assert result.metrics["entries"] == 0


@pytest.mark.parametrize("limit,expected", [(1, 1), (2, 2)])
def test_daily_entry_limit_blocks_new_setups_after_completed_trade(limit, expected):
    bars, indicators = state_fixture(n=8)
    # First position reaches its target before the second setup is evaluated.
    bars.loc[2, ["open", "high", "low", "close"]] = [108., 110., 100., 101.]
    bars.loc[3, ["open", "high", "low", "close"]] = [103., 112., 99.9, 111.]
    for column in ["open", "high", "low", "close"]:
        indicators[column] = bars[column]
    indicators.loc[2, "new15"] = True
    indicators.loc[3, ["rv5", "previous_high"]] = [2., 110.]
    result = backtest(bars, StrategyConfig(max_trades_day=limit), indicators=indicators)
    assert result.metrics["entries"] == expected
    assert bool(result.signals.iloc[2].can_trade) == (limit == 2)


def broker_row(op=104., high=111., low=89., close=100.):
    return SimpleNamespace(timestamp=pd.Timestamp("2025-01-01 00:05", tz="UTC"), open=op, high=high, low=low, close=close)


@pytest.mark.parametrize("op,reason,fill", [(104., "target", 110.), (96., "stop", 89.98), (85., "stop", 84.98), (115., "target", 115.)])
def test_broker_path_and_gap_execution(op, reason, fill):
    broker = Broker(StrategyConfig())
    t = pd.Timestamp("2025-01-01", tz="UTC")
    broker.enter(1, 1., 100., 90., 110., t, t + pd.Timedelta(minutes=5))
    broker.bar(broker_row(op, high=max(111., op), low=min(89., op)))
    assert broker.trades[0]["reason"] == reason
    assert broker.trades[0]["exit_price"] == pytest.approx(fill)
    assert broker.trades[0]["entry_price"] == pytest.approx(100.02)
    assert broker.trades[0]["commission"] == pytest.approx((100.02 + fill) * .0005)


def test_research_stop_first_is_explicit_and_parity_rejects_it():
    with pytest.raises(ValueError):
        StrategyConfig(intrabar_policy="stop_first")
    broker = Broker(StrategyConfig(mode="research", intrabar_policy="stop_first"))
    t = pd.Timestamp("2025-01-01", tz="UTC")
    broker.enter(1, 1., 100., 90., 110., t, t)
    broker.bar(broker_row())
    assert broker.trades[0]["reason"] == "stop"


def test_margin_call_uses_four_times_truncated_cover_and_records_partial_leg():
    broker = Broker(StrategyConfig(initial_capital=1000.))
    t = pd.Timestamp("2025-01-01", tz="UTC")
    broker.enter(1, 50., 100., 80., 120., t, t)
    deficit = 50 * 100 * .2 - broker.equity_at(100)
    expected = 4 * np.floor(deficit / .2 / 100 * 1000) / 1000
    broker._margin(100., t, "open")
    assert broker.margin_calls == 1
    assert broker.trades[0]["quantity"] == pytest.approx(expected)
    assert broker.position.quantity == pytest.approx(50 - expected)


def test_gap_rejected_in_parity_and_segmented_only_in_research():
    bars = candles(100).drop(index=50)
    with pytest.raises(ValueError, match="Missing candles"):
        backtest(bars)
    research = backtest(bars, StrategyConfig(mode="research", gap_policy="segment"))
    assert research.quality["missing_bars"] == 1


def test_true_duplicates_removed_conflicts_rejected_and_out_of_order_reported():
    bars = candles(50)
    cleaned, quality = clean_candles(pd.concat([bars.iloc[::-1], bars.iloc[:1]]))
    assert len(cleaned) == 50
    assert quality["true_duplicates_removed"] == 1
    assert quality["out_of_order_input"]
    conflict = bars.iloc[:1].copy()
    conflict["volume"] += 1
    with pytest.raises(ValueError, match="Conflicting"):
        clean_candles(pd.concat([bars, conflict]))


def test_subsecond_open_timestamps_are_rejected_not_rounded():
    bars = candles(50)
    bars["timestamp"] += pd.Timedelta(milliseconds=1)
    with pytest.raises(ValueError, match="five-minute boundaries"):
        clean_candles(bars)


@pytest.mark.parametrize("unit", ["ms", "us"])
def test_archive_preserves_exchange_millisecond_and_microsecond_timestamps(tmp_path, unit):
    start = pd.Timestamp("2025-01-01", tz="UTC")
    end = start + pd.Timedelta(minutes=5) - pd.Timedelta(1, unit=unit)
    divisor = 10**6 if unit == "ms" else 10**3
    row = [start.value // divisor, 2000, 2005, 1995, 2001, 10, end.value // divisor, 20000, 10, 5, 10000, 0]
    path = tmp_path / "ETHUSDT-5m-2025-01.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("ETHUSDT-5m-2025-01.csv", ",".join(map(str, row)) + "\n")
    path.with_name(path.name + ".CHECKSUM").write_text(hashlib.sha256(path.read_bytes()).hexdigest() + " " + path.name)
    session = Mock()
    result = read_archive(session, "2025-01", "monthly", tmp_path)
    assert result.timestamp.iloc[0] == start
    assert result.exchange_close_time.iloc[0] == end
    session.get.assert_not_called()


def test_modified_parquet_cannot_reuse_an_old_quality_audit(tmp_path):
    path = tmp_path / "candles.parquet"
    candles(50).to_parquet(path, index=False)
    path.with_suffix(".quality.json").write_text(json.dumps({"parquet_sha256": "not-the-current-file"}))
    with pytest.raises(ValueError, match="changed after its quality audit"):
        load_history(path)


def test_tradingview_reconciliation_does_not_silently_accept_naive_timestamps():
    local = pd.DataFrame([dict(entry_bar_open="2025-01-01T00:00:00Z", exit_bar_open="2025-01-01T01:00:00Z",
                              direction="LONG", quantity=1., entry_price=2000., exit_price=2010.)])
    assert compare_trades(local, local)["summary"]["matched_this_export"]
    naive = local.copy()
    naive["entry_bar_open"] = "2025-01-01 00:00:00"
    with pytest.raises(ValueError, match="UTC offset"):
        compare_trades(local, naive)
