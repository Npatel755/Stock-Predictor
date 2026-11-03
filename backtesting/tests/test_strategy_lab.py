from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from backtesting.strategy_lab_signals import FAMILIES, LabRule, prepare, rsi, supertrend_direction
from backtesting.strategy_lab import candidates, training_rank, validation_rank, choose_family
from backtesting.cost_reserve import simulate
from backtesting.optimize import baseline
from test_dvs import candles


@pytest.mark.parametrize('family', FAMILIES)
@pytest.mark.parametrize('hours', [1, 4])
def test_new_families_are_prefix_causal_and_only_signal_after_completed_candles(family, hours):
    bars = candles(18000)
    rule = LabRule(family, hours, 2., 3., 3.)
    a = prepare(bars, rule)
    changed = bars.copy()
    changed.loc[15003:, ['open', 'high', 'low', 'close', 'volume']] *= 3
    b = prepare(changed, rule)
    pd.testing.assert_frame_equal(a.iloc[:15003], b.iloc[:15003], check_exact=True)
    prefix = prepare(bars.iloc[:15003], rule)
    pd.testing.assert_frame_equal(a.iloc[:15003], prefix, check_exact=True)
    signals = a[a.signal.ne(0)]
    assert signals.timestamp.dt.minute.eq(55).all()
    assert signals.timestamp.dt.hour.mod(hours).eq(hours-1).all()
    assert set(a.signal.unique()).issubset({-1, 0, 1})
    if len(signals):
        assert signals.timestamp.min() >= bars.timestamp.iloc[hours*12*200-1]
        assert signals.signal_atr.gt(0).all()


def test_rsi_handles_no_loss_no_gain_and_flat_prices():
    assert rsi(pd.Series(np.arange(50.)), 14).iloc[-1] == 100.
    assert rsi(pd.Series(-np.arange(50.)), 14).iloc[-1] == 0.
    assert rsi(pd.Series(np.ones(50)), 14).iloc[-1] == 50.


def test_supertrend_flips_only_when_a_prior_band_is_crossed():
    close = np.r_[np.arange(100., 130.), np.arange(130., 80., -1.)]
    hours = pd.DataFrame(dict(close=close, high=close+1, low=close-1))
    direction = supertrend_direction(hours, pd.Series(2., index=hours.index))
    assert direction.iloc[0] == 1 and direction.iloc[-1] == -1
    assert direction.diff().eq(-2).sum() == 1
    pd.testing.assert_series_equal(direction.iloc[:40], supertrend_direction(hours.iloc[:40], pd.Series(2., index=hours.index[:40])))


def fold(profit=1000., trades=20, drawdown=.01):
    return dict(closed_net=profit, metrics=dict(closed_trade_legs=trades,
                max_intrabar_drawdown=drawdown, margin_call_events=0))


def test_training_gates_do_not_force_a_winner_or_reward_one_lucky_year():
    assert training_rank([fold() for _ in range(4)])['eligible']
    assert not training_rank([fold(100000.), fold(-1000.), fold(-1000.), fold(-1000.)])['eligible']
    assert not training_rank([fold(trades=2) for _ in range(4)])['eligible']
    assert not training_rank([fold(drawdown=.1) for _ in range(4)])['eligible']
    assert not training_rank([fold(-100.) for _ in range(4)])['eligible']


def test_validation_failure_cannot_be_rescued_by_strong_training():
    training = dict(rank=training_rank([fold() for _ in range(4)]))
    assert validation_rank(training, fold())['eligible']
    assert not validation_rank(training, fold(-1.))['eligible']
    assert not validation_rank(training, fold(trades=9))['eligible']
    assert not validation_rank(training, fold(drawdown=.051))['eligible']


def test_predefined_candidate_budget_and_ties_are_deterministic():
    rows = candidates()
    assert len(rows) == 24 and len({r['id'] for r in rows}) == 24
    assert set(r['rule']['family'] for r in rows) == set(FAMILIES)
    a = dict(candidate=dict(id='a'), rank=dict(eligible=False, score=2000.))
    b = dict(candidate=dict(id='b'), rank=dict(eligible=True, score=100.))
    assert choose_family([a, b]) == b
    assert choose_family([a])['rank']['eligible'] is False


def test_new_family_execution_remains_next_open_with_fixed_risk_and_costs():
    bars = candles(10000)
    rule = LabRule('trend_pullback', 1, 2., 3., 3.)
    features = prepare(bars, rule)
    cfg = replace(baseline(), slippage_bps=8.)
    metrics, trades, events = simulate(bars, rule.execution_rule(), cfg, features, sizing_slippage_bps=8.)
    assert metrics['entries'] > 0 and metrics['total_commission'] > 0
    for entry in events[events.event == 'entry'].itertuples():
        signal_time = entry.bar_open-pd.Timedelta(minutes=5)
        signal = features[features.timestamp == signal_time].iloc[0]
        assert signal.signal != 0
        row = bars[bars.timestamp == entry.bar_open].iloc[0]
        assert entry.price == pytest.approx(row.open+signal.signal*(.02+row.open*.0008))
