import sys
from pathlib import Path
import pandas as pd
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from adaptive_opening_study import known_atr, adaptive_config, adaptive_replay, screen_session
from opening_range_study import opening_intents
from quant_futures.backtest import run_backtest


def test_adaptive_replay_matches_fixed_stop_when_prior_atr_is_constant(bars):
    b = bars.iloc[:180].copy()
    b[["open", "close"]] = 6000.
    b["high"], b["low"] = 6001., 5999.
    b.loc[30:, ["open", "close"]] = 6002.
    b.loc[30:, "high"] = 6003.
    b.loc[31, "low"] = 5980.
    signal = opening_intents(b)
    cfg = adaptive_config("MES")
    prior_atr = pd.Series(1., index=b.index)
    prior_atr.iloc[32:] = 100  # Future volatility cannot widen an entered stop.
    actual = adaptive_replay(b, signal, cfg, prior_atr, multiple=2, payoff=2)
    fixed = cfg.model_copy(update={"execution": cfg.execution.model_copy(update={"stop_ticks": 8, "target_ticks": 16})})
    expected = run_backtest(b, signal, fixed)
    pd.testing.assert_frame_equal(actual["trades"], expected["trades"])


def test_atr_prefix_and_screen_match_engine_for_first_bar_stop(bars):
    b = bars.iloc[:180].copy()
    b[["open", "close"]] = 6000.
    b["high"], b["low"] = 6001., 5999.
    b.loc[30:, ["open", "close"]] = 6002.
    b.loc[30:, "high"] = 6003.
    b.loc[31, "low"] = 5980.
    atr = known_atr(b)
    pd.testing.assert_series_equal(atr.iloc[:100], known_atr(b.iloc[:100]))
    candidate = dict(opening=30, long_only=False, multiple=2, payoff=2)
    screen = screen_session(b, candidate, "MES")
    measured = adaptive_replay(b, opening_intents(b), adaptive_config("MES"), atr.shift(), multiple=2, payoff=2)
    assert screen["net_pnl"] == pytest.approx(measured["trades"].net_pnl.sum())
