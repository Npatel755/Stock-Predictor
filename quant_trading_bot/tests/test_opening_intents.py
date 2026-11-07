import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from opening_range_study import opening_intents
from quant_futures.data import canonical
from quant_futures.execution import Action
from quant_futures.backtest import run_backtest
from quant_futures.transfer import trading_config


def test_opening_strategy_attempts_once_after_stop_and_is_causal(bars):
    b = bars.iloc[:180].copy()
    b[["open", "close"]] = 6000.
    b["high"], b["low"] = 6001., 5999.
    b.loc[30:, ["open", "close"]] = 6002.
    b.loc[30:, "high"] = 6003.
    b.loc[31, "low"] = 5980.
    signals = opening_intents(b)
    assert (signals == Action.LONG).sum() == 1
    assert signals.iloc[30] == Action.LONG and signals.iloc[31] == Action.HOLD
    pd.testing.assert_series_equal(signals.iloc[:100], opening_intents(b.iloc[:100]))
    cfg = trading_config("MES").model_copy(update={"timeframe_minutes": 1})
    result = run_backtest(b, signals, cfg)
    assert len(result["trades"]) == 1


def test_missing_opening_minute_blocks_entries(bars):
    b = bars.iloc[:100].copy().drop(index=10).reset_index(drop=True)
    b.loc[40:, "close"] += 100
    signals = opening_intents(b)
    assert not signals.isin([Action.LONG, Action.SHORT]).any()
