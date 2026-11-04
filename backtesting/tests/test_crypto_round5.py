import numpy as np
import pandas as pd
import pytest

from backtesting.crypto_research import round5
from backtesting.tests.test_crypto_round3 import synthetic_bars


def universe(days=300):
    frames = {s: synthetic_bars(days=days, seed=i) for i, s in enumerate(round5.UNIVERSE)}
    return frames, round5.daily_closes(frames)


def test_manifest_is_fixed():
    assert len(round5.candidates()) == 6 and len(round5.candidates('BTC')) == 4
    assert sum(len(round5.candidates(s)) for s in round5.UNIVERSE) == 46
    with pytest.raises(ValueError):
        round5.SourceRule('xs_momentum', 45)
    assert round5.SourceRule('session_breakout', 'trend').execution_rule().max_holding_bars == 288


def test_cross_sectional_signals_are_completed_day_and_mutually_exclusive():
    frames, closes = universe()
    fired = {}
    for symbol in ['SOL', 'BNB']:
        out = round5.Features(frames[symbol], symbol, closes).signals(round5.SourceRule('xs_momentum', 30))
        rows = out[out.signal != 0]
        assert len(rows) > 0 and set(rows.timestamp.dt.hour) == {23} and set(rows.timestamp.dt.minute) == {55}
        assert (out.exit_signal != 0).any()
        fired[symbol] = rows
    # On any day at most 2 coins can be long and 2 short; each coin's own long/short never coincide.
    for symbol, rows in fired.items():
        assert not rows.timestamp.duplicated().any()
    longs = sum(((round5.Features(frames[s], s, closes).signals(round5.SourceRule('xs_momentum', 30)).signal == 1)).astype(int)
                for s in round5.UNIVERSE)
    assert longs.max() <= 2


def test_relative_strength_skips_btc_and_uses_ratio():
    frames, closes = universe()
    out = round5.Features(frames['LINK'], 'LINK', closes).signals(round5.SourceRule('rel_strength_btc', 30))
    assert (out.signal != 0).sum() > 0 and (out.exit_signal != 0).sum() > 0
    assert all(c['rule']['family'] != 'rel_strength_btc' for c in round5.candidates('BTC'))


def test_session_breakout_fires_once_per_day_after_asia_with_range_stop():
    frames, closes = universe(days=120)
    out = round5.Features(frames['XRP'], 'XRP', closes).signals(round5.SourceRule('session_breakout', 'notrend'))
    rows = out[out.signal != 0]
    assert len(rows) > 0 and (rows.timestamp.dt.hour >= 8).all() and set(rows.timestamp.dt.minute) == {55}
    assert not rows.timestamp.dt.floor('D').duplicated().any()
    assert (rows.signal_atr > 0).all()
