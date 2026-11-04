import numpy as np
import pandas as pd
import pytest

from research.codex_eth_bnb.execution import simulate


def frame(prices, signals=None, *, atr=10., volume=100000.):
    n = len(prices)
    return pd.DataFrame(dict(timestamp=pd.date_range('2024-01-01', periods=n, freq='1h', tz='UTC'),
                             open=prices, high=np.asarray(prices)+1., low=np.asarray(prices)-1.,
                             close=prices, volume=volume, signal=signals or [0]*n, atr=atr))


def config(**values):
    return {**dict(initial_capital=10000., risk_fraction=.01, fee_bps=0., spread_bps=0.,
                   slippage_bps=0., funding_bps_daily=0., tick_size=.01,
                   participation_cap=.01, stop_atr=2., reward_r=3.), **values}


def test_completed_signal_enters_next_open_and_unused_last_signal():
    data = frame([100., 105., 110.], [1, 1, -1])
    result = simulate(data, config())
    trade = result['trades'].iloc[0]
    assert trade.entry_time == data.timestamp.iloc[1]
    assert trade.entry_price == 105.
    assert trade.direction == 1
    assert result['metrics']['trades'] == 1
    assert result['metrics']['final_equity'] > 10000.


def test_prefix_no_earlier_trade_uses_future_signal():
    data = frame([100.]*6, [0, 1, 1, 1, 1, 1])
    before = simulate(data.iloc[:4], config(force_terminal_close=False))
    data.loc[4:, ['signal', 'close', 'high']] = [(-1, 150., 151.), (-1, 150., 151.)]
    after = simulate(data, config(force_terminal_close=False))
    pd.testing.assert_frame_equal(before['equity'], after['equity'].iloc[:4].reset_index(drop=True))


def test_stop_gap_fills_at_open_not_skipped_stop():
    data = frame([100., 100., 70., 70.], [1]*4)
    result = simulate(data, config())
    assert result['trades'].iloc[0].reason == 'gap_stop'
    assert result['trades'].iloc[0].exit_price == 70.
    assert result['trades'].iloc[0].exit_price < 80.


def test_same_bar_stop_and_target_uses_stop_first():
    data = frame([100., 100., 100.], [1, 1, 1])
    data.loc[1, ['high', 'low']] = [170., 70.]
    result = simulate(data, config())
    assert result['trades'].iloc[0].reason == 'stop'
    assert result['trades'].iloc[0].exit_price == 80.
    assert result['trades'].iloc[0].exit_time == data.timestamp.iloc[1]+pd.Timedelta(hours=1)
    assert result['trades'].iloc[0].exit_time_is_bar_bound


def test_fees_and_actual_signed_funding_reconcile():
    data = frame([100.]*4, [1]*4)
    data['funding_rate'] = [np.nan, .01, .01, np.nan]
    cfg = config()
    cfg.update(fee_bps=5., funding_bps_daily=100.)
    result = simulate(data, cfg)
    trade = result['trades'].iloc[0]
    assert trade.funding == pytest.approx(trade.quantity*100.*.01)
    assert trade.net_pnl == pytest.approx(-trade.entry_fee-trade.exit_fee-trade.funding)
    assert result['metrics']['net_pnl'] == pytest.approx(result['trades'].net_pnl.sum())
    assert result['metrics']['funding_mode'] == 'actual_settlement'


def test_short_receives_positive_funding():
    data = frame([100.]*4, [-1]*4)
    data['funding_rate'] = [np.nan, np.nan, .01, np.nan]
    result = simulate(data, config())
    assert result['metrics']['total_funding'] < 0
    assert result['metrics']['net_pnl'] > 0


def test_entry_capacity_uses_previous_volume_and_quantity_precision():
    data = frame([100.]*3, [1]*3, volume=100000.)
    data.loc[0, 'volume'] = 123.456
    result = simulate(data, config(qty_step=.01))
    assert result['trades'].iloc[0].quantity == pytest.approx(1.23)
    data.loc[1, 'volume'] = 1000000.
    again = simulate(data, config(qty_step=.01))
    assert again['trades'].iloc[0].quantity == result['trades'].iloc[0].quantity


def test_partial_exit_retains_exposure_and_ledger_reconciles():
    data = frame([100., 100., 90., 90., 90.], [1, 0, 0, 0, 0])
    data.loc[1, 'volume'] = 100.
    result = simulate(data, config())
    assert result['metrics']['partial_exit_legs'] == 1
    assert result['equity'].position_qty.iloc[2] > 0
    assert result['metrics']['net_pnl'] == pytest.approx(result['trades'].net_pnl.sum())


def test_outage_skips_entries_and_delay_never_executes_early():
    data = frame([100.]*5, [1]*5)
    cfg = config(execution_delay_bars=2, skip_entry_timestamps=[str(data.timestamp.iloc[2])])
    result = simulate(data, cfg)
    assert result['trades'].iloc[0].entry_time == data.timestamp.iloc[3]


def test_signal_zero_goes_flat_next_open():
    data = frame([100., 101., 102., 103.], [1, 0, 0, 0])
    result = simulate(data, config())
    assert result['trades'].iloc[0].exit_time == data.timestamp.iloc[2]
    assert result['trades'].iloc[0].reason == 'signal'


def test_precision_costs_are_adverse_and_risk_is_bounded():
    data = frame([100.01]*3, [1]*3)
    cfg = config()
    cfg.update(fee_bps=5., slippage_bps=2., spread_bps=1.)
    result = simulate(data, cfg)
    trade = result['trades'].iloc[0]
    assert trade.entry_price > 100.01
    assert trade.exit_price < 100.01
    assert trade.net_pnl < 0
    assert result['metrics']['net_pnl'] == pytest.approx(trade.net_pnl)


def test_invalid_candles_and_missing_intervals_are_rejected():
    data = frame([100.]*3)
    data.loc[1, 'high'] = 90.
    with pytest.raises(ValueError, match='OHLC ordering'):
        simulate(data, config())
    with pytest.raises(ValueError, match='Missing or irregular'):
        simulate(frame([100.]*4).iloc[[0, 1, 3]], config())


def test_flat_baseline_never_pays_costs_or_funding():
    result = simulate(frame([100., 150., 70.]), config())
    assert result['metrics']['net_pnl'] == 0
    assert result['metrics']['trades'] == 0
    assert result['metrics']['total_fees'] == 0


def test_buy_hold_allocates_unlevered_notional_without_atr_or_brackets():
    data = frame([100., 100., 200.], [1]*3, atr=float('nan'))
    data.loc[2, ['high', 'low']] = [201., 50.]
    result = simulate(data, config(sizing='buy_hold', stop_atr=0., reward_r=0., max_hold_bars=0))
    trade = result['trades'].iloc[0]
    assert trade.quantity == 100.
    assert trade.reason == 'terminal_accounting'
    assert result['metrics']['final_equity'] == 20000.


def test_notional_mode_allocates_configured_fraction_and_disables_brackets():
    data = frame([100., 100., 200.], [1]*3, atr=float('nan'))
    result = simulate(data, config(sizing_mode='notional', notional_fraction=.5,
                                   stop_atr=0., reward_r=0., max_hold_bars=0))
    assert result['trades'].iloc[0].quantity == 50.
    assert result['metrics']['final_equity'] == 15000.


def test_close_drawdown_separated_from_intrabar_bound():
    data = frame([100., 100., 120.], [1]*3)
    data.loc[2, ['low', 'high']] = [81., 121.]
    result = simulate(data, config())
    assert result['metrics']['max_drawdown'] == 0.
    assert result['metrics']['max_intrabar_drawdown'] > 0.
    assert 'bound' in result['metrics']['intrabar_drawdown_convention']


def test_trailing_stop_uses_adverse_tick_rounding():
    data = frame([100., 100., 110., 110.], [1]*4, atr=2.333)
    data.loc[2, 'low'] = 105.
    data.loc[3, 'low'] = 105.
    result = simulate(data, config(trail_atr=1., tick_size=.1))
    stopped = result['trades'][result['trades'].reason.eq('stop')]
    assert len(stopped) > 0
    assert stopped.iloc[0].exit_price == pytest.approx(107.6)


@pytest.mark.parametrize('margin', [0., 1., float('nan'), -1.])
def test_invalid_maintenance_margin_rejected(margin):
    with pytest.raises(ValueError, match='Maintenance margin'):
        simulate(frame([100.]*3), config(maintenance_margin=margin))
