import pandas as pd
import pytest

from research.codex_eth_bnb.data_pipeline import load, resample


def test_snapshot_loader_never_exposes_contaminated_final_performance_period():
    for symbol in ['ETH', 'BNB', 'BTC']:
        frame = load(symbol)
        assert frame.timestamp.max()+pd.Timedelta('5min') <= pd.Timestamp('2025-08-28 19:10', tz='UTC')


def test_complete_aggregates_and_settlement_conservation():
    source = load('ETH').iloc[:288*4]
    for timeframe in ['5m', '15m', '1h', '4h']:
        frame = resample(source, timeframe, 'ETH')
        assert len(frame)*int(pd.Timedelta(timeframe)/pd.Timedelta('5min')) == len(source)
        assert frame.funding_rate.notna().sum() == 12
        assert frame.volume.sum() == pytest.approx(source.volume.sum())
        assert (frame.timestamp+pd.Timedelta(timeframe) <= source.timestamp.iloc[-1]+pd.Timedelta('5min')).all()


def test_incomplete_final_aggregate_is_excluded():
    source = load('BNB').iloc[:289]
    assert len(resample(source, '1h', 'BNB')) == 24
