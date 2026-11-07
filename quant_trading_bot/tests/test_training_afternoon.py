from pathlib import Path
import sys
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import training_afternoon_research as study
from quant_futures.data import canonical
from quant_futures.execution import Action


def prices(bars):
    b = bars.iloc[:79].copy()
    b["timestamp_utc"] = pd.date_range("2023-01-04T14:30Z",periods=len(b),freq="5min")
    b["instrument"],b["contract"] = "NQ","NQH23"
    b["open"] = 20000+np.arange(len(b))*2.
    b["close"] = b.open+1
    b["high"],b["low"] = b.close+2,b.open-2
    return canonical(b)


@pytest.mark.parametrize("name,index",[("midday_trend_5m",29),("midday_reversal_5m",29),("afternoon_trend_5m",53)])
def test_completed_candle_signals_preserve_prefix_and_next_open_entry(bars,name,index):
    b = prices(bars)
    c = dict(name=name,long_only=False,atr_multiple=2,payoff=2,contracts=1)
    signals,atr = study.intent_and_atr(b,c)
    assert signals.iloc[index] in (Action.LONG,Action.SHORT)
    assert sum(signals.isin([Action.LONG,Action.SHORT])) == 1
    prefix,pa = study.intent_and_atr(b.iloc[:index+1],c)
    pd.testing.assert_series_equal(prefix,signals.iloc[:index+1])
    np.testing.assert_allclose(pa,atr.iloc[:index+1],equal_nan=True)
    result = study.replay(b,signals,atr,c)
    assert result["trades"].iloc[0].entry_time == str(b.timestamp_utc.iloc[index+1])
    changed = b.copy()
    changed.loc[index+1:,["high","close"]] += 500
    cs,ca = study.intent_and_atr(changed,c)
    pd.testing.assert_series_equal(cs.iloc[:index+1],prefix)
    np.testing.assert_allclose(ca.iloc[:index+1],pa,equal_nan=True)


def test_missing_morning_bar_blocks_entry(bars):
    c = dict(name="midday_trend_5m",long_only=False,atr_multiple=2,payoff=2,contracts=1)
    b = prices(bars).drop(index=5).reset_index(drop=True)
    signals,_ = study.intent_and_atr(b,c)
    assert not signals.isin([Action.LONG,Action.SHORT]).any()


def test_long_only_does_not_reverse_short_rule(bars):
    b = prices(bars)
    c = dict(name="midday_reversal_5m",long_only=True,atr_multiple=2,payoff=2,contracts=1)
    signals,_ = study.intent_and_atr(b,c)
    assert not signals.isin([Action.LONG,Action.SHORT]).any()
