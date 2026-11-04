from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from backtesting.alternative_strategies import SignalRule
from backtesting.crypto_research import round4
from backtesting.crypto_research.lab import validator
from backtesting.generalization_policy import frozen_profile
from backtesting.paths import ROOT
from backtesting.tests.test_crypto_round3 import synthetic_bars


def test_manifest_is_fixed_and_literal():
    rows = round4.candidates()
    assert len(rows) == 13 and len({r['id'] for r in rows}) == 13
    assert all(round4.RULES[r['rule']['family']][4].startswith('youtu.be/') for r in rows)
    with pytest.raises(ValueError):
        round4.YouTubeRule('yt_turn_of_month', '4h')
    assert round4.FIRST_VERSION == 6 and len(round4.EXCLUDED) >= 5


def test_signals_and_exits_sit_on_completed_candles():
    bars = synthetic_bars()
    feats = round4.Features(bars)
    for candidate in round4.candidates():
        rule = round4.YouTubeRule(**candidate['rule'])
        out = feats.signals(rule)
        fired = out.loc[out.signal != 0]
        assert len(fired) > 0, candidate['id']
        hours = {'1h': set(range(24)), '4h': {3, 7, 11, 15, 19, 23}, '1D': {23}}[rule.timeframe]
        assert set(fired.timestamp.dt.hour) <= hours and set(fired.timestamp.dt.minute) == {55}, candidate['id']
        assert (fired.signal_atr > 0).all(), candidate['id']
        if rule.spec[3]:
            assert (fired.signal == 1).all() and (out.exit_signal >= 0).all(), candidate['id']
        if rule.spec[2] == round4.BIG_TARGET:
            assert (out.exit_signal != 0).any(), candidate['id']


def test_turn_of_month_dates():
    bars = synthetic_bars(days=120)
    out = round4.Features(bars).signals(round4.YouTubeRule('yt_turn_of_month', '1D'))
    entries = out.loc[out.signal == 1, 'timestamp']
    exits = out.loc[out.exit_signal == 1, 'timestamp']
    assert set(entries.dt.day) <= {23, 24, 25, 26} and set(exits.dt.day) == {3}


def test_exit_signal_closes_only_matching_direction():
    bars = synthetic_bars(days=120)
    cfg = replace(frozen_profile(ROOT)[2], slippage_bps=8.)
    frame = bars.copy()
    frame['signal'], frame['exit_signal'], frame['signal_atr'], frame['management_atr'] = 0, 0, np.nan, np.nan
    frame.loc[5000, ['signal', 'signal_atr']] = [1, 5.]
    frame.loc[5010, 'exit_signal'] = -1   # asks shorts to flatten; long must stay open
    frame.loc[5020, 'exit_signal'] = 1
    rule = SignalRule('ema_cross', lookback=20, slow=200, stop_atr=100., reward_r=100., trail_atr=0.)
    metrics, trades, _ = round4.simulate(bars, rule, cfg, frame, validator=validator('BNB'))
    assert len(trades) == 1 and trades.iloc[0]['reason'] == 'signal_exit'
    assert pd.Timestamp(trades.iloc[0]['exit_bar_open']) == bars.timestamp[5020]


def test_detailed_reconciles_signal_exits_with_equity_curve(tmp_path):
    bars = synthetic_bars(days=200)
    cfg = replace(frozen_profile(ROOT)[2], slippage_bps=8.)
    rule = round4.YouTubeRule('yt_cci14', '4h')
    result = round4.detailed('BNB', bars, round4.Features(bars).signals(rule), rule.execution_rule(), cfg, tmp_path)
    assert result['metrics']['closed_trade_legs'] > 0 and (tmp_path/'equity.parquet').exists()
