from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from backtesting.alternative_strategies import SignalRule, prepare_signals, simulate
from backtesting.alternative_research import candidates
from backtesting.optimize import baseline
from test_dvs import candles


@pytest.mark.parametrize('family', ['ema_cross', 'channel_breakout', 'bollinger_reversion'])
def test_independent_signals_are_causal_and_prefix_equivalent(family):
    bars = candles(7000)
    rule = SignalRule(family=family)
    frame = prepare_signals(bars, rule)
    assert frame.signal.ne(0).any()
    assert frame.loc[frame.signal.ne(0), 'signal_atr'].notna().all()
    altered = bars.copy()
    altered.loc[5003:, ['open', 'high', 'low', 'close', 'volume']] *= 3
    other = prepare_signals(altered, rule)
    pd.testing.assert_frame_equal(frame.iloc[:5003], other.iloc[:5003])
    prefix = prepare_signals(bars.iloc[:5003], rule)
    pd.testing.assert_frame_equal(prefix, frame.iloc[:5003])
    assert frame.loc[frame.signal.ne(0), 'timestamp'].dt.minute.eq(55).all()
    a = simulate(bars, rule, baseline(), signals=frame)[1]
    b = simulate(altered, rule, baseline(), signals=other)[1]
    assert len(a) > 0 and len(b) > 0
    # No future mutation can change a completed pre-cutoff trade.
    cutoff = bars.timestamp.iloc[5003]
    if len(a) and len(b):
        pd.testing.assert_frame_equal(a[a.exit_time < cutoff].reset_index(drop=True), b[b.exit_time < cutoff].reset_index(drop=True))


def fixture():
    bars = candles(4)
    bars[['open', 'close']] = 100.
    bars['high'], bars['low'] = 101., 99.
    signals = bars.copy()
    signals['signal'] = [1, 0, 0, 0]
    signals['signal_atr'] = 2.
    signals['management_atr'] = 2.
    return bars, signals


def test_independent_entries_use_next_open_and_cost_aware_risk():
    bars, signals = fixture()
    # An earlier high cannot hit the target before an order exists.
    for frame in [bars, signals]:
        frame.loc[0, 'high'] = 200.
        frame.loc[1, ['open', 'close', 'high', 'low']] = [102., 102., 103., 101.]
    cfg = baseline()
    m, trades, events = simulate(bars, SignalRule('ema_cross'), cfg, signals)
    assert m['entries'] == 1 and trades.empty
    p = m['open_position']
    assert p['entry_bar_open'] == bars.timestamp.iloc[1]
    assert p['entry_price'] == pytest.approx(102+.02+102*.0002)
    assert p['stop'] == 96 and p['target'] == 108
    assert p['quantity']*(4+2*100*.0006+.04) <= 100
    assert len(events[events.event == 'entry']) == 1


def test_independent_ambiguous_bracket_uses_pessimistic_stop_and_charges_costs():
    bars, signals = fixture()
    for frame in [bars, signals]:
        frame.loc[1, ['high', 'low']] = [110., 95.]
    m, trades, _ = simulate(bars, SignalRule('ema_cross'), baseline(), signals)
    assert len(trades) == 1 and trades.iloc[0].reason == 'stop'
    assert trades.iloc[0].exit_phase == 'research_stop_first'
    assert trades.iloc[0].commission > 0 and trades.iloc[0].net_pnl < -99


def test_independent_trailing_stop_cannot_fill_retroactively():
    bars, signals = fixture()
    for frame in [bars, signals]:
        frame.loc[1, ['open', 'high', 'low', 'close']] = [100., 105., 99., 104.]
        frame.loc[2, ['open', 'high', 'low', 'close']] = [104., 104., 101., 102.]
    m, trades, events = simulate(bars, SignalRule('ema_cross', reward_r=4, trail_atr=1), baseline(), signals)
    assert len(trades) == 1
    assert trades.iloc[0].exit_bar_open == bars.timestamp.iloc[2]
    update = events[events.event == 'stop_update'].iloc[0]
    assert update.price == 102 and update.effective_at == bars.timestamp.iloc[2]


def test_independent_time_stop_financing_and_gap_rejection():
    bars, signals = fixture()
    # Entry exactly at a four-hour financing snapshot.
    for frame in [bars, signals]:
        frame['timestamp'] += pd.Timedelta(hours=3, minutes=55)
        frame['exchange_close_time'] += pd.Timedelta(hours=3, minutes=55)
    m, trades, _ = simulate(bars, SignalRule('ema_cross', max_holding_bars=1), baseline(), signals)
    assert trades.iloc[0].reason == 'time_stop'
    assert trades.iloc[0].swap > 0 and m['total_swap'] == pytest.approx(trades.swap.sum())
    with pytest.raises(ValueError, match='missing'):
        simulate(bars.drop(index=1), SignalRule('ema_cross'), baseline())
    with pytest.raises(ValueError, match='next-open'):
        simulate(bars, SignalRule('ema_cross'), replace(baseline(), entry_timing='signal_close'))


@pytest.mark.parametrize('family,prices,lookback,slow,expected', [
    ('ema_cross', [100, 100, 100, 110, 120, 100, 80, 70, 100, 120], 2, 3, {3: 1, 5: -1, 8: 1}),
    ('channel_breakout', list(range(100, 160)), 20, 50, {h: 1 for h in range(49, 60)}),
    ('bollinger_reversion', [100]*55+[80, 95, 100], 20, 50, {56: 1}),
])
def test_family_rules_emit_expected_signals_on_known_hourly_prices(family, prices, lookback, slow, expected):
    bars = candles(len(prices)*12)
    for i, price in enumerate(prices):
        rows = slice(i*12, (i+1)*12-1)
        bars.loc[rows, ['open', 'close']] = price
        bars.loc[rows, 'high'], bars.loc[rows, 'low'] = price+.1, price-.1
    frame = prepare_signals(bars, SignalRule(family, lookback=lookback, slow=slow))
    actual = {int(i)//12: int(value) for i, value in frame.loc[frame.signal.ne(0), 'signal'].items()}
    assert actual == expected


def test_independent_universe_is_small_fixed_and_contains_three_families():
    universe = candidates()
    assert len(universe) == 12 and universe == candidates()
    assert {row['rule']['family'] for row in universe} == {'ema_cross', 'channel_breakout', 'bollinger_reversion'}
    assert len({tuple(sorted(row['rule'].items())) for row in universe}) == 12


def test_channel_followup_retains_parent_and_varies_only_bounded_exit_geometry():
    from backtesting.channel_refine import channel_candidates
    universe = channel_candidates()
    assert len(universe) == 24 and universe == channel_candidates()
    assert universe[0]['rule'] == candidates()[7]['rule']
    assert len({tuple(sorted(row['rule'].items())) for row in universe}) == 24
    for row in universe:
        r = SignalRule(**row['rule'])
        assert r.family == 'channel_breakout' and r.lookback in {40, 55, 80}
        assert r.stop_atr in {2., 3.} and r.reward_r in {2., 3., 4.} and r.trail_atr in {2., 3., 4.}
