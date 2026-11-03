from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtesting.alternative_strategies import SignalRule, prepare_signals, simulate as original
from backtesting.cost_reserve import simulate, sizing_config
from backtesting.cost_reserve_study import register, registered, forward, candidate_directory, risk_audit
from backtesting.engine import estimated_round_trip_cost
from backtesting.optimize import baseline
from test_alternative_strategies import fixture
from test_dvs import candles
from test_generalization_controls import locked


@pytest.mark.parametrize('slip', [2., 4., 8.])
def test_separating_budget_with_matching_costs_preserves_entire_frozen_simulation(slip):
    bars = candles(7000)
    rule = SignalRule('channel_breakout', lookback=20, slow=50, trail_atr=2.)
    cfg = replace(baseline(), slippage_bps=slip)
    features = prepare_signals(bars, rule)
    a = original(bars, rule, cfg, features)
    b = simulate(bars, rule, cfg, features, sizing_slippage_bps=slip)
    assert a[0] == b[0] and a[0]['entries'] > 0
    for expected, actual in zip(a[1:], b[1:]):
        pd.testing.assert_frame_equal(expected, actual, check_exact=True)


@pytest.mark.parametrize('direction', [-1, 1])
def test_unexpected_slippage_does_not_shrink_order_with_fixed_budget(direction):
    bars, features = fixture()
    features['signal'] = [direction, 0, 0, 0]
    rule = SignalRule('ema_cross')
    cfg = baseline()
    entries = []
    for fill in [2., 4., 8.]:
        metrics, _, events = simulate(bars, rule, replace(cfg, slippage_bps=fill), features,
                                     sizing_slippage_bps=2.)
        entries.append(events[events.event == 'entry'].iloc[0])
    assert len({r.quantity for r in entries}) == 1
    assert entries[2].price-entries[0].price == pytest.approx(direction*100*.0006)


@pytest.mark.parametrize('direction', [-1, 1])
def test_reserve_reduces_quantity_without_improving_fills_or_changing_brackets(direction):
    bars, features = fixture()
    features['signal'] = [direction, 0, 0, 0]
    rule = SignalRule('ema_cross')
    cfg = replace(baseline(), slippage_bps=8.)
    a = simulate(bars, rule, cfg, features, sizing_slippage_bps=2.)[0]['open_position']
    b = simulate(bars, rule, cfg, features, sizing_slippage_bps=8.)[0]['open_position']
    assert b['quantity'] < a['quantity']
    for key in ['entry_price', 'stop', 'target', 'entry_time']:
        assert a[key] == b[key]
    projected = 4.+estimated_round_trip_cost(sizing_config(cfg, 8.), 100.)
    assert b['quantity']*projected <= cfg.risk_usd
    assert a['quantity']*projected > cfg.risk_usd


@pytest.mark.parametrize('value', [-1., np.nan, np.inf])
def test_invalid_reserves_are_rejected(value):
    with pytest.raises(ValueError, match='finite and nonnegative'):
        sizing_config(baseline(), value)


def test_future_prices_do_not_change_completed_candidate_trades():
    bars = candles(7000)
    other = bars.copy()
    other.loc[5003:, ['open', 'high', 'low', 'close', 'volume']] *= 3
    rule = SignalRule('channel_breakout')
    a = simulate(bars, rule, baseline())[1]
    b = simulate(other, rule, baseline())[1]
    cutoff = bars.timestamp.iloc[5003]
    pd.testing.assert_frame_equal(a[a.exit_time < cutoff].reset_index(drop=True),
                                  b[b.exit_time < cutoff].reset_index(drop=True), check_exact=True)


@pytest.fixture
def candidate(locked):
    from backtesting.generalization_policy import policy
    repo = Path(__file__).resolve().parents[1]
    for name in ['cost_reserve.py', 'cost_reserve_study.py', 'independent_visuals.py',
                 'post_selection_checks.py', 'market_data.py', 'optimize.py', 'eth_research/data.py']:
        path = locked/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((repo/name).read_bytes())
    register(locked, now='2026-11-03 19:00:00+00:00')
    return locked


def test_candidate_has_separate_preregistration_and_does_not_promote_or_unlock_parent(candidate):
    from backtesting.generalization_policy import policy, frozen_profile, assert_search_allowed
    p = policy(candidate)
    plan = registered(candidate)
    assert plan['parent_protocol_sha256']
    assert plan['number_of_candidate_hypotheses'] == 1
    assert plan['future_period'] == ['2026-11-04 00:00:00+00:00', '2027-05-03 00:00:00+00:00']
    assert p['frozen_version'] == 'v1.5'
    frozen_profile(candidate)
    with pytest.raises(ValueError, match='optimization is disabled'):
        assert_search_allowed(candidate)
    assert not (candidate/'configs/eth_strategy_v1_12.json').exists()
    directory = candidate_directory(candidate)
    pine = (directory/'ETH_Strategy_v1_12_candidate.pine').read_bytes()
    assert pine == (directory/'ETH_Strategy_v1_12_candidate.txt').read_bytes()
    assert b'input.float(8.0, "Fixed slippage budget for sizing only' in pine
    assert b'v1.12 candidate' in pine


def test_candidate_cannot_rewrite_protocol_or_export_after_registration(candidate):
    path = candidate_directory(candidate)/'config.json'
    data = json.loads(path.read_text())
    data['sizing_slippage_bps'] = 4.
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='Candidate or parent protocol changed'):
        registered(candidate)


def test_candidate_future_evaluation_does_not_read_prices_before_end(candidate):
    result = forward(candidate/'DOES_NOT_EXIST.parquet', candidate, now='2027-01-01')
    assert result['status'] == 'awaiting_candidate_future_window'
    assert result['prices_read'] is False and not result['passed']


def test_candidate_future_rejects_missing_data(candidate):
    bars = candles(20)
    bars['timestamp'] = pd.date_range('2026-11-03', periods=20, freq='5min', tz='UTC')
    bars['exchange_close_time'] = bars.timestamp+pd.Timedelta(minutes=5)-pd.Timedelta(milliseconds=1)
    path = candidate/'gapped.parquet'
    bars.to_parquet(path, index=False)
    with pytest.raises(ValueError, match='complete coverage'):
        forward(path, candidate, now='2027-05-03')


def test_risk_audit_exposes_unexpected_cost_underbudgeting():
    bars, features = fixture()
    rule, cfg = SignalRule('ema_cross'), baseline()
    events = [simulate(bars, rule, cfg, features, sizing_slippage_bps=budget)[2] for budget in [2., 8.]]
    a, b = [risk_audit(features, e, rule, cfg) for e in events]
    assert a['above_planned_budget'] == 1 and a['maximum_estimated_usd'] > 100
    assert b['above_planned_budget'] == 0 and b['maximum_estimated_usd'] <= 100
    assert not b['includes_next_open_gap_or_financing']


def test_completed_candidate_future_is_immutable_and_never_promotes(candidate):
    from backtesting.generalization_policy import frozen_profile
    _, rule, _, _ = frozen_profile(candidate)
    start, end = map(pd.Timestamp, registered(candidate)['future_period'])
    warmup = start-pd.Timedelta(hours=rule.slow*5)
    bars = candles(int((end-warmup)/pd.Timedelta(minutes=5)))
    bars['timestamp'] = pd.date_range(warmup, periods=len(bars), freq='5min')
    bars['exchange_close_time'] = bars.timestamp+pd.Timedelta(minutes=5)-pd.Timedelta(milliseconds=1)
    path = candidate/'complete.parquet'
    bars.to_parquet(path, index=False)
    result = forward(path, candidate, now=end)
    assert result['prospective_validation_complete'] and not result['promoted']
    assert not result['ready_for_funded_trading'] and len(result['scenarios']) == 6
    bars.loc[0, 'volume'] += 1
    bars.to_parquet(path, index=False)
    with pytest.raises(ValueError, match='manifest differs'):
        forward(path, candidate, now=end)
