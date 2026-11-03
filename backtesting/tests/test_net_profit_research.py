from dataclasses import asdict

import pytest

from backtesting.alternative_strategies import SignalRule
from backtesting.net_profit_research import candidates, eligible


def metrics(net, entries=200, dd=.03):
    return dict(initial_capital=50000., final_equity=50000.+net, entries=entries,
                max_intrabar_drawdown=dd, margin_call_events=0)


def test_profit_search_is_reproducible_bounded_and_retains_saved_geometry():
    rows = candidates()
    assert len(rows) == 64 and rows == candidates()
    assert len({tuple(sorted(c['rule'].items())) for c in rows}) == 64
    assert rows[0]['rule'] == asdict(SignalRule('channel_breakout', lookback=80, slow=200, stop_atr=2., reward_r=3., trail_atr=3.))
    for row in rows:
        r = SignalRule(**row['rule'])
        assert r.family == 'channel_breakout' and r.lookback < r.slow
        assert r.stop_atr >= 1.5 and r.reward_r <= 5 and r.max_holding_bars == 0
    with pytest.raises(ValueError):
        candidates(1)


def test_historical_gate_cannot_pass_without_exceeding_previous_profit_at_costs():
    checks = {name: metrics(500) for name in ['2025_h1', '2025_h2', 'earlier_2020_2022', '2026_selected_period']}
    checks['full_4bp'] = metrics(5000)
    assert eligible(metrics(6000), checks, 4344.93)
    assert not eligible(metrics(4300), checks, 4344.93)
    assert not eligible(metrics(6000, dd=.051), checks, 4344.93)
    assert not eligible(metrics(6000, entries=99), checks, 4344.93)
    checks['full_4bp'] = metrics(4200)
    assert not eligible(metrics(6000), checks, 4344.93)
    checks['full_4bp'] = metrics(5000)
    checks['2025_h1'] = metrics(-1)
    assert not eligible(metrics(6000), checks, 4344.93)


def test_profit_followup_has_fixed_neighborhoods_and_unique_rules():
    from backtesting.profit_refine import candidates as refine_candidates
    rows = refine_candidates()
    assert len(rows) == 64 and rows == refine_candidates()
    assert len({tuple(sorted(c['rule'].items())) for c in rows}) == 64
    assert rows[0]['rule']['lookback'] == 64 and rows[1]['rule']['lookback'] == 96
    for row in rows:
        r = SignalRule(**row['rule'])
        assert 1.5 <= r.stop_atr <= 2.25 and 2.5 <= r.reward_r <= 5
        assert 2.5 <= r.trail_atr <= 3.5 and r.max_holding_bars == 0
