from pathlib import Path
import sys
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from session_window_study import context, screen, intents, config, keep_indexes
from quant_futures.data import canonical
from quant_futures.backtest import run_backtest
from quant_futures.execution import Action


def test_europe_window_screen_matches_event_replay_and_is_causal(bars):
    b = bars.iloc[:600].copy()
    b["timestamp_utc"] = pd.date_range("2026-01-05T05:00Z", periods=len(b), freq="min")
    b[["open", "close"]] = 6000.
    b["high"], b["low"] = 6000.25, 5999.75
    b = canonical(b)
    candidate = dict(name="europe_open_drift", width=1, payoff=2)
    s = intents(b, candidate)
    pd.testing.assert_series_equal(s.iloc[:200], intents(b.iloc[:200], candidate))
    assert s.eq(Action.LONG).sum() == 1
    measured = run_backtest(b, s, config("MES", candidate))
    fast = screen(context(b, []), candidate, "MES")
    assert fast["net_pnl"] == measured["trades"].net_pnl.sum()
    indexes = keep_indexes(b, candidate)
    compact = run_backtest(b.iloc[indexes].reset_index(drop=True), s.iloc[indexes].reset_index(drop=True), config("MES", candidate))
    pd.testing.assert_frame_equal(measured["trades"], compact["trades"])


def test_reversal_signal_uses_only_completed_opening_prices(bars):
    b = bars.iloc[:200].copy()
    b[["open", "close"]] = 6000.
    b["high"], b["low"] = 6000.25, 5999.75
    b.loc[14, ["close", "high"]] = 6001.
    b = canonical(b)
    candidate = dict(name="us_open_reversal", width=1, payoff=2)
    s = intents(b, candidate)
    assert s.iloc[14] == Action.SHORT
    changed = b.copy()
    changed.loc[15:, "close"] += 100
    assert intents(changed, candidate).iloc[14] == Action.SHORT
