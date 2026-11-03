import json

from backtesting.filter_research import candidates, eligible
from backtesting.regime_filters import RegimeFilter


def metrics(net, entries=200, dd=.03):
    return dict(initial_capital=50000., final_equity=50000.+net, entries=entries,
                max_intrabar_drawdown=dd, margin_call_events=0)


def test_filter_universe_is_reproducible_unique_and_contains_neutral_control():
    rows = candidates()
    assert len(rows) == 48 and rows == candidates()
    assert len({json.dumps(c['filters'], sort_keys=True) for c in rows}) == 48
    assert RegimeFilter(**rows[0]['filters']) == RegimeFilter()
    assert any(c['filters']['min_signed_slope_bps'] == 0 for c in rows)
    assert any(c['filters']['direction'] == 'long' for c in rows)
    assert any(c['filters']['direction'] == 'short' for c in rows)


def test_gate_requires_profit_drawdown_cost_and_recent_regime_improvement():
    parent, stressed_parent = metrics(6034, dd=.0492), metrics(4722)
    checks = {name: metrics(500) for name in ['2025_h1', '2025_h2', '2026_selection', 'earlier_2020_2022']}
    checks['full_4bp'] = metrics(7000)
    assert eligible(metrics(8000), checks, parent, stressed_parent)
    assert not eligible(metrics(6000), checks, parent, stressed_parent)
    assert not eligible(metrics(8000, dd=.05), checks, parent, stressed_parent)
    checks['2026_selection'] = metrics(-1)
    assert not eligible(metrics(8000), checks, parent, stressed_parent)
    checks['2026_selection'] = metrics(500)
    checks['full_4bp'] = metrics(4700)
    assert not eligible(metrics(8000), checks, parent, stressed_parent)


def test_volume_followup_keeps_two_fixed_geometries_and_bounded_entry_changes():
    from backtesting.alternative_strategies import SignalRule
    from backtesting.volume_refine import candidates as volume_candidates
    parent = SignalRule('channel_breakout', lookback=96, slow=150, stop_atr=1.5, reward_r=4.5, trail_atr=3.)
    rows = volume_candidates(parent)
    assert len(rows) == 18 and rows == volume_candidates(parent)
    assert len({json.dumps({'rule': r['rule'], 'filters': r['filters']}, sort_keys=True) for r in rows}) == 18
    assert rows[0]['rule']['lookback'] == 96 and rows[9]['rule']['lookback'] == 64
    assert rows[0]['filters']['min_rvol'] == rows[9]['filters']['min_rvol'] == 0
    for row in rows:
        settings = RegimeFilter(**row['filters'])
        assert settings.min_rvol in {0., 1.2, 1.5, 2., 2.5}
        assert settings.direction == 'both' and settings.min_trend_gap_bps == 0
