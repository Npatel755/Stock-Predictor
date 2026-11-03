import numpy as np
import pandas as pd
import pytest

from backtesting.alternative_strategies import SignalRule, simulate
from backtesting.engine import Broker
from backtesting.independent_visuals import equity_curve, monthly_chart, performance_chart, trade_chart
from backtesting.optimize import baseline
from test_alternative_strategies import fixture


def test_visual_equity_marks_open_positions_and_matches_exact_broker_final():
    bars, signals = fixture()
    for frame in [bars, signals]:
        frame.loc[2, ['open', 'high', 'low', 'close']] = [100., 104., 99., 103.]
    cfg = baseline()
    m, trades, events = simulate(bars, SignalRule('ema_cross'), cfg, signals)
    curve = equity_curve(bars, events, cfg)
    assert len(curve) == len(bars)
    assert curve.equity.iloc[0] == cfg.initial_capital
    assert curve.position_qty.iloc[1] > 0
    # Equity moves before the trade closes; a trade-exit cumulative line would miss it.
    assert curve.equity.iloc[2] > curve.equity.iloc[1]
    assert curve.equity.iloc[-1] == pytest.approx(m['final_equity'], abs=1e-8)
    assert curve.cash.iloc[1] < cfg.initial_capital
    pd.testing.assert_frame_equal(equity_curve(bars.iloc[:3], events[events.bar_open < bars.timestamp.iloc[3]], cfg), curve.iloc[:3])


def test_visual_equity_handles_financing_partial_exits_and_fees_in_order():
    bars, _ = fixture()
    cfg = baseline()
    broker = Broker(cfg)
    broker.enter(1, 2., 100., 90., 120., bars.timestamp.iloc[0], bars.timestamp.iloc[0])
    broker.bar(next(bars.itertuples(index=False)))  # financing at 00:00
    broker.exit(105., bars.timestamp.iloc[1], 'margin_call', 'intrabar', quantity=.5)
    broker.exit(106., bars.timestamp.iloc[2], 'target', 'intrabar')
    curve = equity_curve(bars, pd.DataFrame(broker.events), cfg)
    assert broker.total_swap > 0
    assert curve.position_qty.tolist() == [2., 1.5, 0., 0.]
    assert curve.equity.iloc[-1] == pytest.approx(broker.cash, abs=1e-8)
    assert curve.cash.iloc[0] == pytest.approx(cfg.initial_capital-broker.total_swap-2*broker.trades[0]['entry_price']*.0004)


def test_no_trades_chart_is_flat_and_monthly_marks_reconcile():
    bars, _ = fixture()
    curve = equity_curve(bars, pd.DataFrame(), baseline())
    assert curve.equity.eq(50000).all() and curve.close_drawdown_pct.eq(0).all()
    fig = performance_chart(curve, 50000)
    assert len(fig.data) == 2 and fig.data[1].fill == 'tozeroy'
    curve['timestamp'] = pd.date_range('2025-01-31 23:55', periods=4, freq='5min', tz='UTC')
    curve['equity'] = [50010, 50015, 49995, 50005]
    monthly = monthly_chart(curve, 50000)
    assert list(monthly.data[0].x) == ['2025-01', '2025-02']
    assert list(monthly.data[0].y) == [15., -10.]
    assert sum(monthly.data[0].y) == curve.equity.iloc[-1]-50000


def test_performance_chart_preserves_troughs_peaks_and_initial_capital_drawdown():
    bars, _ = fixture()
    curve = equity_curve(bars, pd.DataFrame(), baseline())
    curve['equity'] = [49900, 50100, 49800, 50000]
    curve['close_drawdown_pct'] = [-.2, 0, -.598802395, -.199600798]
    figure = performance_chart(curve, 50000)
    assert min(figure.data[0].y) == 49800 and max(figure.data[0].y) == 50100
    assert min(figure.data[1].y) < -.59


def test_trade_chart_displays_actual_fills_and_causal_stop_updates():
    bars, signals = fixture()
    for frame in [bars, signals]:
        frame.loc[1, ['open', 'high', 'low', 'close']] = [100., 105., 99., 104.]
        frame.loc[2, ['open', 'high', 'low', 'close']] = [104., 104., 101., 102.]
    rule = SignalRule('ema_cross', reward_r=4, trail_atr=1)
    _, trades, events = simulate(bars, rule, baseline(), signals)
    fig, resolution = trade_chart(bars, trades.iloc[0], events, rule.reward_r)
    assert resolution == '5min' and fig.data[0].type == 'candlestick'
    stop = next(t for t in fig.data if t.name == 'Active stop')
    assert stop.y[0] == 96.
    assert stop.x[1] == bars.timestamp.iloc[2] and stop.y[1] == 102.
    fill = next(t for t in fig.data if t.name == 'Simulated fills')
    np.testing.assert_allclose(fill.y, [trades.iloc[0].entry_price, trades.iloc[0].exit_price])
