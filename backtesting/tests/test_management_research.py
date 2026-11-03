from dataclasses import replace
import json

from backtesting.alternative_strategies import SignalRule
from backtesting.management_research import candidates, eligible


def metrics(net, entries=30, dd=.03):
    return dict(initial_capital=50000., final_equity=50000.+net, entries=entries,
                max_intrabar_drawdown=dd, margin_call_events=0)


def test_management_grid_preserves_entry_geometry_and_fixed_universe():
    parent=SignalRule('channel_breakout',lookback=96,slow=150,stop_atr=1.5,reward_r=4.5,trail_atr=3.)
    rows=candidates(parent)
    assert len(rows)==20 and rows==candidates(parent)
    assert len({json.dumps(r['rule'],sort_keys=True) for r in rows})==20
    assert SignalRule(**rows[0]['rule'])==parent
    for row in rows:
        rule=SignalRule(**row['rule'])
        assert replace(rule,trail_atr=parent.trail_atr,max_holding_bars=parent.max_holding_bars)==parent
        assert rule.trail_atr in {2.,2.5,3.,3.5}
        assert rule.max_holding_bars in {0,72,144,288,576}


def test_management_gate_demands_higher_profit_and_fixes_weak_half_without_risk_increase():
    parent,stress=metrics(9971,entries=397,dd=.0402),metrics(8736)
    checks={name:metrics(500) for name in ['2025_h1','2025_h2','2026_h1','2026_h2','earlier_2020_2022']}
    checks.update(full_4bp=metrics(10000),full_8bp=metrics(6500))
    assert eligible(metrics(12000,entries=350),checks,parent,stress)
    assert not eligible(metrics(9900,entries=350),checks,parent,stress)
    assert not eligible(metrics(12000,entries=350,dd=.041),checks,parent,stress)
    checks['2026_h1']=metrics(-1)
    assert not eligible(metrics(12000,entries=350),checks,parent,stress)
    checks['2026_h1']=metrics(500)
    checks['full_8bp']=metrics(5999)
    assert not eligible(metrics(12000,entries=350),checks,parent,stress)
