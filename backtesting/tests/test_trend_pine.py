from dataclasses import asdict,replace
import hashlib
import json

import pytest

from backtesting.alternative_strategies import SignalRule
from backtesting.optimize import baseline
from backtesting.regime_filters import RegimeFilter
from backtesting.trend_pine import render_trend


def test_trend_export_applies_symmetric_ema_gap_and_retains_actual_volume_filter():
    rule=SignalRule('channel_breakout',lookback=96,slow=150,stop_atr=1.5,reward_r=4.5,trail_atr=3.)
    filters=RegimeFilter(min_rvol=2.,min_trend_gap_bps=200.)
    text,payload,digest=render_trend(rule,replace(baseline(),risk_includes_costs=True),filters)
    assert 'minHourlyTrendBps = input.float(200.0' in text
    assert 'signedLongGap = (close / slow - 1) * 10000' in text
    assert 'signedLongGap >= minHourlyTrendBps' in text and '-signedLongGap >= minHourlyTrendBps' in text
    assert 'longSignal and volumeOK and longGapOK' in text and 'shortSignal and volumeOK and shortGapOK' in text
    assert 'priorMeanVolume = ta.sma(volume[1], 20)' in text
    assert 'minHourlyRVOL = input.float(2.0' in text
    assert payload['filters']==asdict(filters)
    assert hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()==digest
    assert f'Full rule/filter/config SHA-256: {digest}' in text
    with pytest.raises(ValueError,match='supports only'):
        render_trend(rule,replace(baseline(),risk_includes_costs=True),replace(filters,min_signed_slope_bps=5.))
