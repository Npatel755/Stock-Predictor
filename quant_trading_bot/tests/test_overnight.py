import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from overnight_study import night_data, night_config, overnight_intents, replay_indexes, screen_trade
from quant_futures.data import canonical
from quant_futures.backtest import run_backtest


def test_night_screen_matches_event_trade_and_exits_before_morning_high(bars):
    b = bars.iloc[:850].copy()
    b["timestamp_utc"] = pd.date_range("2026-01-04T23:00Z", periods=len(b), freq="min")
    b[["open", "close"]] = 6000.
    b["high"], b["low"] = 6000.25, 5999.75
    b.loc[836, "high"] = 6100.  # 07:56 ET: opening exit happens first.
    b = canonical(b)
    candidate = dict(entry=1095, width=1, payoff=2, direction="long")
    signal = overnight_intents(b, candidate)
    pd.testing.assert_series_equal(signal.iloc[:400], overnight_intents(b.iloc[:400], candidate))
    result = run_backtest(b, signal, night_config("MES", candidate))
    screen = screen_trade(night_data(b, []), candidate, "MES")
    assert len(result["trades"]) == 1
    assert screen["net_pnl"] == result["trades"].net_pnl.iloc[0]
    assert result["trades"].reason.iloc[0] == "signal_exit"
    ids = replay_indexes(b)
    compact = run_backtest(b.iloc[ids].reset_index(drop=True), signal.iloc[ids].reset_index(drop=True), night_config("MES", candidate))
    pd.testing.assert_frame_equal(result["trades"], compact["trades"])


def test_night_screen_never_uses_new_contract_gap_as_old_position_profit(bars):
    b = bars.iloc[:850].copy()
    b["timestamp_utc"] = pd.date_range("2026-01-04T23:00Z", periods=len(b), freq="min")
    b[["open", "close"]] = 6000.
    b["high"], b["low"] = 6000.25, 5999.75
    b.loc[20:, "contract"] = "MESM26"
    b.loc[20:, ["open", "close", "high", "low"]] += 100
    b = canonical(b)
    result = screen_trade(night_data(b, []), dict(entry=1095, width=1, payoff=2, direction="long"), "MES")
    assert result is None
