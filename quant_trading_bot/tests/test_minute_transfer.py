import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from minute_transfer_support import price_features, batches, train_streaming_logistic, predict


def test_minute_features_are_prefix_causal_and_volume_independent(bars):
    full = price_features(bars)
    prefix = price_features(bars.iloc[:400])
    pd.testing.assert_frame_equal(full.iloc[:400], prefix)
    altered = bars.copy()
    altered["volume"] *= 100
    pd.testing.assert_frame_equal(full, price_features(altered))
    assert full.dtypes.eq("float32").all()


def test_external_batches_purge_label_end_and_stream_all_eligible_rows(tmp_path):
    rng = np.random.default_rng(3)
    x = rng.normal(size=(200, 3)).astype(np.float32)
    y = (x[:, 0] > 0).astype(np.float32)
    times = pd.date_range("2020-12-31T22:00Z", periods=200, freq="min").as_unit("ns").asi8
    ends = times+20*60*10**9
    path = tmp_path/"source.npz"
    np.savez_compressed(path, x=x, y=y, timestamp=times, label_end=ends)
    shards = [dict(path=str(path))]
    kept = list(batches(shards, end="2021-01-01T00:00Z"))
    assert sum(len(y) for _, y in kept) == 100
    model = train_streaming_logistic(shards, end="2021-01-01T00:00Z")
    assert model["fitting_rows"] == 100
    assert np.isfinite(predict(model, x)).all()


def test_external_memory_boosting_uses_purged_shards(tmp_path):
    import pytest
    pytest.importorskip("xgboost")
    from minute_transfer_support import train_external_xgboost, calibrate
    rng = np.random.default_rng(9)
    x = rng.normal(size=(200, 3)).astype(np.float32)
    y = (x[:, 0] > 0).astype(np.float32)
    times = pd.date_range("2020-12-31T22:00Z", periods=200, freq="min").as_unit("ns").asi8
    path = tmp_path/"batch.npz"
    np.savez_compressed(path, x=x, y=y, timestamp=times, label_end=times+20*60*10**9)
    shards = [dict(path=str(path))]
    fitted = train_external_xgboost(shards, "2021-01-01T00:00Z", tmp_path/"cache")
    assert fitted["fitting_rows"] == 100
    calibrate(fitted, shards, "2021-01-01T00:00Z", "2021-01-01T02:00Z")
    assert fitted["calibration_rows"] == 80
    assert np.isfinite(predict(fitted, x)).all()
