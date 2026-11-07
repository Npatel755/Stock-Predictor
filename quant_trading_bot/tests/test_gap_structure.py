from pathlib import Path
import sys
from functools import partial
import pandas as pd
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
import session_window_study as engine
from gap_structure_study import WINDOWS, history_value, context, direction
from quant_futures.data import canonical
from quant_futures.execution import Action


def test_gap_direction_uses_only_completed_prior_session_and_opening(bars):
    previous = bars.iloc[:390].copy()
    previous["timestamp_utc"] = pd.date_range("2025-01-06T14:30Z", periods=390, freq="min")
    previous[["open", "close"]] = 6000.
    previous["high"], previous["low"] = 6010., 5990.
    current = previous.copy()
    current["timestamp_utc"] += pd.Timedelta(days=1)
    current[["open", "close"]] = 6004.
    current["high"], current["low"] = 6005., 6003.
    b = canonical(pd.concat([previous, current], ignore_index=True))
    candidate = dict(name="regular_gap_fade", width=1, payoff=2)
    signal_fn = partial(engine.intents, windows=WINDOWS, context_fn=context,
        side_fn=direction, history_value=history_value)
    signal = signal_fn(b, candidate)
    assert signal.iloc[390+14] == Action.SHORT
    pd.testing.assert_series_equal(signal.iloc[:405], signal_fn(b.iloc[:405], candidate))
    changed = b.copy()
    changed.loc[405:, "close"] += 1000
    assert signal_fn(changed, candidate).iloc[404] == Action.SHORT
    rolled = b.copy()
    rolled.loc[390:, "contract"] = "MESH99"
    assert not signal_fn(rolled, candidate).eq(Action.SHORT).any()
    # A missing prior regular minute invalidates that prior session.
    incomplete = b.drop(index=1).reset_index(drop=True)
    assert not signal_fn(incomplete, candidate).eq(Action.SHORT).any()
    # Real futures session groups also contain the previous evening. Those
    # 18:00 candles must not be counted as current 09:30 opening candles.
    night = current.iloc[:20].copy()
    night["timestamp_utc"] = pd.date_range("2025-01-06T23:00Z", periods=20, freq="min")
    full = canonical(pd.concat([previous, night, current], ignore_index=True))
    assert signal_fn(full, candidate).iloc[390+20+14] == Action.SHORT


def test_gap_context_does_not_consume_current_full_session(bars):
    b = canonical(bars.iloc[:200].copy())
    prior = dict(close=5995., high=6005., low=5985., contract=str(b.contract.iloc[0]))
    c = context(b, [prior]*20)
    changed = b.copy()
    changed.loc[30:, ["high", "close"]] += 999
    d = context(changed, [prior]*20)
    assert c["trend"] == d["trend"]
    assert direction(c, "regular_gap_fade", 14) == direction(d, "regular_gap_fade", 14)
    assert history_value(b) is None
