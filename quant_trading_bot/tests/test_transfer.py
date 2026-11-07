import pandas as pd
import pytest
from quant_futures.transfer import validate_partition, transfer_features, trading_config, morning_indexes
from quant_futures.features import build_features
from quant_futures.backtest import run_backtest


def test_transfer_separates_reference_training_and_micro_validation(bars):
    b = bars.iloc[:30].copy()
    b["instrument"], b["contract"] = "ES", "ESH23"
    b["timestamp_utc"] = pd.date_range("2023-01-05T14:30Z", periods=30, freq="min")
    manifest = dict(instrument="ES", split_role="train")
    validate_partition(b, manifest, {}, "ES", "train")
    b["timestamp_utc"] += pd.DateOffset(years=1)
    with pytest.raises(PermissionError, match="before 2024"):
        validate_partition(b, manifest, {}, "ES", "train")
    with pytest.raises(PermissionError):
        validate_partition(b, manifest, {}, "ES", "test")
    b["instrument"], b["contract"] = "MES", "MESH24"
    validate_partition(b, dict(instrument="MES", split_role="validation"), {}, "MES", "validation")


def test_transfer_uses_reference_specs_and_normalized_price_features(bars):
    features = transfer_features(build_features(bars))
    assert "return_1" in features and "relative_volume" not in features and "vwap_deviation" not in features
    mini, micro = trading_config("ES"), trading_config("MES")
    assert mini.instrument == "ES" and mini.initial_balance == 10*micro.initial_balance
    assert mini.execution.stop_ticks == micro.execution.stop_ticks
    assert mini.risk.max_drawdown == 18000 and micro.risk.max_drawdown == 1800
    assert micro.risk.max_contracts == 1


def test_flat_window_compaction_preserves_trades_and_session_equity(bars):
    b = bars.copy()
    b["timestamp_utc"] = pd.date_range("2026-01-05T14:30Z", periods=len(b), freq="15min")
    from quant_futures.data import canonical
    b = canonical(b)
    local = b.timestamp_utc.dt.tz_convert("America/New_York")
    minute = local.dt.hour*60+local.dt.minute
    signal = pd.Series(0, index=b.index)
    signal.loc[(minute >= 585) & (minute < 690)] = 1
    cfg = trading_config("MES")
    full = run_backtest(b, signal, cfg)
    ids = morning_indexes(b)
    compact = run_backtest(b.iloc[ids].reset_index(drop=True), signal.iloc[ids].reset_index(drop=True), cfg)
    pd.testing.assert_frame_equal(full["trades"], compact["trades"])
    pd.testing.assert_series_equal(full["curve"].groupby("session_id").equity.last(), compact["curve"].groupby("session_id").equity.last())
