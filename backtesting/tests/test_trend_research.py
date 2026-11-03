from dataclasses import asdict
import json

from backtesting.alternative_strategies import SignalRule
from backtesting.regime_filters import RegimeFilter
from backtesting.trend_research import candidates,eligible


def metrics(net,entries=30,dd=.03):
    return dict(initial_capital=50000.,final_equity=50000.+net,entries=entries,max_intrabar_drawdown=dd,margin_call_events=0)


def test_trend_grid_keeps_geometry_rvol_and_cost_sensitive_entry_controls():
    rule=SignalRule('channel_breakout',lookback=96,slow=150,stop_atr=1.5,reward_r=4.5,trail_atr=3.)
    filters=RegimeFilter(min_rvol=2.)
    rows=candidates(rule,filters)
    assert len(rows)==24 and rows==candidates(rule,filters)
    assert len({json.dumps(r['filters'],sort_keys=True) for r in rows})==24
    assert rows[0]['filters']==asdict(filters)
    for row in rows:
        assert row['rule']==asdict(rule) and row['filters']['min_rvol']==2.
        assert row['filters']['min_trend_gap_bps'] in {0.,100.,200.,400.}
        assert row['filters']['min_signed_slope_bps'] in {None,0.,5.,10.,20.,40.}


def test_rounded_9900_baseline_cannot_admit_a_downgrade_from_exact_parent():
    benchmark=dict(main=metrics(9971.4271,entries=397,dd=.0402),stress4=metrics(8735.76),stress8=metrics(6468.48))
    checks={k:metrics(500) for k in ['2025_h1','2025_h2','2026_h1','2026_h2','earlier_2020_2022']}
    checks.update(full_4bp=metrics(9000),full_8bp=metrics(7000))
    assert not eligible(metrics(9950,entries=350),checks,benchmark,9900.)
    assert not eligible(metrics(9971.4271,entries=350),checks,benchmark,9900.)
    assert eligible(metrics(11000,entries=350),checks,benchmark,9900.)
    checks['2026_h1']=metrics(-1)
    assert not eligible(metrics(11000,entries=350),checks,benchmark,9900.)
