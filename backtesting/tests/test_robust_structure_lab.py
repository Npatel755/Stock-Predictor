from dataclasses import replace

import numpy as np
import pandas as pd

from backtesting.paths import ROOT
from backtesting.generalization_policy import frozen_profile
from backtesting.robust_structure_lab import (TARGET_ATR, GROUPS, Features, candidates, baseline_candidate, geometry,
                                              fresh_guard, combine, evaluate)
from backtesting.regime_filters import RegimeFilter, apply_filter, prepare_features
from backtesting.cost_reserve import simulate
from test_dvs import candles


def profile():
    _, rule, cfg, meta = frozen_profile(ROOT)
    return rule, replace(cfg, slippage_bps=8.), meta['entry_filters']


def test_candidate_universe_is_fixed_and_structural_only():
    rows = candidates()
    assert len(rows) == 10 and len({r['id'] for r in rows}) == 10
    assert {r['group'] for r in rows} == set(GROUPS)
    assert rows == candidates()
    rule, _, _ = profile()
    for row in rows:
        g = geometry(rule, row)
        assert abs(g.stop_atr*g.reward_r-TARGET_ATR) < 1e-9 and g.trail_atr == rule.trail_atr
        assert g.lookback == rule.lookback and g.slow == rule.slow
    base = geometry(rule, baseline_candidate())
    assert (base.stop_atr, base.reward_r) == (rule.stop_atr, rule.reward_r)


def test_fresh_guard_is_prefix_causal_and_only_removes_crowded_entries():
    rule, _, filters = profile()
    bars = candles(40000)
    frame = apply_filter(prepare_features(bars, rule), RegimeFilter(**filters))
    guarded = fresh_guard(bars, frame, rule)
    assert guarded.prior_same_direction_breakouts.ge(0).all()
    assert guarded.signal.ne(0).sum() <= frame.signal.ne(0).sum()
    removed = frame.signal.ne(0) & guarded.signal.eq(0)
    assert guarded.loc[removed, 'prior_same_direction_breakouts'].gt(2).all()
    kept = guarded.signal.ne(0)
    assert guarded.loc[kept, 'prior_same_direction_breakouts'].le(2).all()
    assert (guarded.loc[kept, 'signal'] == frame.loc[kept, 'signal']).all()
    changed = bars.copy()
    changed.loc[30003:, ['open', 'high', 'low', 'close', 'volume']] *= 3
    later = fresh_guard(changed, apply_filter(prepare_features(changed, rule), RegimeFilter(**filters)), rule)
    pd.testing.assert_frame_equal(guarded.iloc[:30003], later.iloc[:30003], check_exact=True)


def test_guard_counts_prior_hours_only():
    rule, _, filters = profile()
    bars = candles(40000)
    frame = apply_filter(prepare_features(bars, rule), RegimeFilter(**filters))
    guarded = fresh_guard(bars, frame, rule, window=72, max_prior=2)
    wide = fresh_guard(bars, frame, rule, window=72, max_prior=1000)
    assert wide.signal.equals(frame.signal)
    strict = fresh_guard(bars, frame, rule, window=72, max_prior=0)
    assert strict.signal.ne(0).sum() <= guarded.signal.ne(0).sum()


def test_ensemble_sums_independent_sub_accounts_and_bounds_drawdown():
    rule, cfg, filters = profile()
    bars = candles(40000)
    features = Features(bars, rule, filters)
    candidate = dict(id='ensemble_test', group='parameter_ensemble', stop_atr=1.5, fresh_guard=False,
                     members=[dict(lookback=48, min_rvol=2.4), dict(lookback=72, min_rvol=2.8)])
    start, end = bars.timestamp.iloc[20000], bars.timestamp.iloc[-1]+pd.Timedelta(minutes=5)
    result = evaluate(features, candidate, start, end, cfg)
    parts = []
    for member in candidate['members']:
        member_rule, frame = features.member(member['lookback'], member['min_rvol'], False)
        from backtesting.optimize import subset
        b, f = subset(bars, frame, start, end)
        parts.append(simulate(b, geometry(member_rule, candidate), replace(cfg, risk_usd=50.), f, sizing_slippage_bps=8.))
    metrics, trades, events, curve = combine(parts, b, cfg)
    assert result['metrics']['entries'] == sum(m['entries'] for m, _, _ in parts)
    assert abs(result['closed_net']-sum(t.net_pnl.sum() if len(t) else 0. for _, t, _ in parts)) < 1e-6
    assert abs(metrics['final_equity']-(sum(m['final_equity'] for m, _, _ in parts)-cfg.initial_capital)) < 1e-6
    assert metrics['max_intrabar_drawdown'] >= metrics['bar_close_combined_drawdown'] >= 0
    assert curve.equity.iloc[0] <= cfg.initial_capital+1e-6 or len(trades) == 0
    assert set(['timestamp', 'cash', 'equity', 'position_qty', 'close_drawdown_pct']) <= set(curve.columns)
    if len(trades):
        assert set(trades.member.unique()) <= {0, 1}
        assert trades.entry_time.is_monotonic_increasing


def test_single_candidate_matches_direct_simulation():
    rule, cfg, filters = profile()
    bars = candles(40000)
    features = Features(bars, rule, filters)
    candidate = candidates()[0]
    start, end = bars.timestamp.iloc[20000], bars.timestamp.iloc[-1]+pd.Timedelta(minutes=5)
    result = evaluate(features, candidate, start, end, cfg)
    from backtesting.optimize import subset
    member_rule, frame = features.member(rule.lookback, filters['min_rvol'], False)
    b, f = subset(bars, frame, start, end)
    metrics, trades, _ = simulate(b, geometry(member_rule, candidate), cfg, f, sizing_slippage_bps=8.)
    assert result['metrics']['entries'] == metrics['entries']
    assert abs(result['closed_net']-(trades.net_pnl.sum() if len(trades) else 0.)) < 1e-9
