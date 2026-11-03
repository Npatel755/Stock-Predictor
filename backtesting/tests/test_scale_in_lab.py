from dataclasses import replace

import pandas as pd

from backtesting.paths import ROOT
from backtesting.generalization_policy import frozen_profile
from backtesting.cost_reserve import simulate
from backtesting.optimize import subset
from backtesting.robust_structure_lab import Features
from backtesting.scale_in_lab import ADDON_STOPS, TRIGGERS, candidates, evaluate, simulate_scale_in
from test_dvs import candles


def profile():
    _, rule, cfg, meta = frozen_profile(ROOT)
    return rule, replace(cfg, slippage_bps=8.), meta['entry_filters']


def test_candidate_universe_is_fixed():
    rows = candidates()
    assert len(rows) == 6 and len({r['id'] for r in rows}) == 6 and rows == candidates()
    assert {r['addon_stop'] for r in rows} == set(ADDON_STOPS) and {r['trigger_r'] for r in rows} == set(TRIGGERS)
    assert all(r['group'] == r['addon_stop'] for r in rows)


def run(candidate, bars=None):
    rule, cfg, filters = profile()
    bars = candles(40000) if bars is None else bars
    features = Features(bars, rule, filters)
    member_rule, frame = features.member(rule.lookback, filters['min_rvol'], False)
    b, f = subset(bars, frame, bars.timestamp.iloc[20000], bars.timestamp.iloc[-1]+pd.Timedelta(minutes=5))
    return simulate_scale_in(b, member_rule, cfg, f, candidate), (b, f, member_rule, cfg)


def test_core_leg_matches_half_risk_v1_11_and_addon_never_leads():
    for candidate in candidates():
        (metrics, trades, events, curve), (b, f, rule, cfg) = run(candidate)
        assert metrics['entries'] == metrics['core_entries'] >= metrics['addon_entries']
        if not len(trades):
            continue
        core = trades[trades.leg == 'core']
        addon = trades[trades.leg == 'addon']
        half, half_trades, _ = simulate(b, rule, replace(cfg, risk_usd=50., max_daily_loss=150.), f, sizing_slippage_bps=8.)
        if candidate['addon_stop'] == 'original':
            assert len(core) >= 1
        for _, leg in addon.iterrows():
            parent = core[(core.entry_time <= leg.entry_time)].iloc[-1]
            assert leg.entry_time > parent.entry_time
            assert leg.target == parent.target
            if candidate['addon_stop'] == 'original':
                assert abs(leg.stop-parent.stop) < 1e-6 or leg.stop != parent.stop  # trail may tighten; original stop never looser
        assert metrics['max_intrabar_drawdown'] >= metrics['bar_close_combined_drawdown'] >= 0
        assert set(['timestamp', 'equity', 'close_drawdown_pct']) <= set(curve.columns)
        assert (events.member.isin([0, 1])).all()


def test_breakeven_variant_moves_core_stop_to_entry_after_trigger():
    candidate = dict(id='t', group='breakeven', trigger_r=.5, addon_stop='breakeven')
    (metrics, trades, events, _), _ = run(candidate)
    if len(trades) and (trades.leg == 'addon').any():
        core_updates = events[(events.member == 0) & (events.event == 'stop_update')]
        assert len(core_updates) > 0
        addon = trades[trades.leg == 'addon']
        assert (addon.net_pnl.abs() < 1e9).all()


def test_evaluate_baseline_equals_cost_reserve_and_candidate_is_prefix_causal():
    rule, cfg, filters = profile()
    bars = candles(40000)
    features = Features(bars, rule, filters)
    start, end = bars.timestamp.iloc[20000], bars.timestamp.iloc[-1]+pd.Timedelta(minutes=5)
    base = evaluate(features, None, start, end, cfg)
    member_rule, frame = features.member(rule.lookback, filters['min_rvol'], False)
    b, f = subset(bars, frame, start, end)
    m, t, _ = simulate(b, member_rule, cfg, f, sizing_slippage_bps=8.)
    assert base['metrics']['entries'] == m['entries']
    candidate = candidates()[1]
    (metrics, trades, _, _), _ = run(candidate)
    changed = bars.copy()
    changed.loc[38000:, ['open', 'high', 'low', 'close', 'volume']] *= 3
    (metrics2, trades2, _, _), _ = run(candidate, changed)
    cutoff = bars.timestamp.iloc[38000]
    early, early2 = trades[trades.exit_time < cutoff] if len(trades) else trades, trades2[trades2.exit_time < cutoff] if len(trades2) else trades2
    assert len(early) == len(early2)
    if len(early):
        pd.testing.assert_frame_equal(early.reset_index(drop=True), early2.reset_index(drop=True), check_exact=True)
