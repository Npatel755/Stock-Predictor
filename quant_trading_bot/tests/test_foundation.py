import numpy as np
import pandas as pd
import pytest
from quant_futures.contracts import SPECS, continuous, expiration
from quant_futures.data import canonical, validate, resample_complete, session_ids, SessionCalendar
from quant_futures.features import build_features, cross_market_features
from quant_futures.labels import future_returns, triple_barrier


def test_label_end_is_completed_exit_bar_and_barriers_support_timeframes(bars):
    b = bars.iloc[:5].copy()
    b["timestamp_utc"] = pd.date_range("2026-01-05T14:30Z", periods=5, freq="15min")
    labels = future_returns(b, horizon=2, minutes=15)
    assert labels.label_end.iloc[0] == b.timestamp_utc.iloc[2]+pd.Timedelta(minutes=15)
    events = triple_barrier(b, horizon=2, stop_points=100, target_points=100, minutes=15)
    assert events.label.notna().iloc[0]
    assert events.label_end.iloc[0] == b.timestamp_utc.iloc[2]+pd.Timedelta(minutes=15)
from quant_futures.validation import walk_forward, reserve_holdout


def test_specs():
    assert SPECS["MES"].tick_value == 1.25
    assert SPECS["MNQ"].tick_value == 0.5
    assert str(expiration("MESH26")) == "2026-03-20"
    assert str(expiration("MESM26")) == "2026-06-18"
    with pytest.raises(ValueError):
        expiration("MES.c.0")


def test_quality(bars):
    b, report = validate(bars)
    assert report["fatal"] == 0
    assert b.bid.isna().all()
    bad = bars.copy()
    bad.loc[3, "low"] = bad.loc[3, "high"]+1
    bad.loc[5, "volume"] = -1
    assert validate(bad)[1]["fatal"] >= 2
    assert validate(pd.concat([bars.iloc[:3], bars.iloc[:1]]))[1]["counts"]["duplicate"] == 2
    with pytest.raises(ValueError, match="Timezone"):
        canonical(bars.assign(timestamp_utc=bars.timestamp_utc.dt.tz_localize(None)))
    shifted = bars.copy()
    shifted["timestamp_utc"] += pd.Timedelta(seconds=1)
    assert validate(shifted)[1]["counts"]["timestamp_alignment"] == len(bars)


def test_completed_resampling(bars):
    result = resample_complete(bars.iloc[:7], 5)
    assert len(result) == 1
    assert result.available_at.iloc[0] == pd.Timestamp("2026-01-05T14:35Z")
    assert len(resample_complete(bars.drop(index=1).iloc[:6], 5)) == 0


def test_dst_and_early_close():
    assert list(session_ids(pd.to_datetime(["2026-03-09T21:30Z", "2026-03-09T22:30Z"]))) == ["2026-03-09", "2026-03-10"]
    cal = SessionCalendar(pd.DataFrame(dict(session_id=["2026-11-27"], open_utc=["2026-11-27T14:30Z"], close_utc=["2026-11-27T18:00Z"])))
    assert len(cal.expected()) == 210


def test_future_cannot_change_features(bars):
    original = build_features(bars)
    changed = bars.copy()
    changed.loc[500:, ["open", "high", "low", "close"]] *= 10
    changed.loc[500:, "volume"] *= 17
    pd.testing.assert_frame_equal(original.iloc[:500], build_features(changed).iloc[:500])
    pd.testing.assert_frame_equal(original.iloc[:400], build_features(bars.iloc[:400]))


def test_cross_market_no_backfill(bars):
    result = cross_market_features(bars, bars.iloc[500:].copy())
    assert result.return_divergence.iloc[:500].isna().all()


def test_labels_and_purge(bars):
    labels = future_returns(bars, 5)
    assert np.isclose(labels.forward_return.iloc[0], bars.close.iloc[5]/bars.open.iloc[1]-1)
    for train, valid in walk_forward(bars, labels.label_end, embargo=0):
        assert labels.label_end.iloc[train].max() < bars.timestamp_utc.iloc[valid[0]]
    b = bars.iloc[:4].copy()
    b.loc[1, ["open", "close", "high", "low"]] = [6000., 6000., 6010., 5990.]
    result = triple_barrier(b, horizon=2, stop_points=4, target_points=4)
    assert result.ambiguous.iloc[0] and np.isnan(result.label.iloc[0])


def test_roll_uses_previous_volume_and_raw_prices(bars):
    old = bars.iloc[:4].copy()
    old["session_id"] = ["2026-01-05", "2026-01-05", "2026-01-06", "2026-01-06"]
    new = old.copy()
    new["contract"] = "MESM26"
    new[["open", "high", "low", "close"]] += 100
    old["volume"], new["volume"] = [10, 10, 1, 1], [20, 20, 100, 100]
    joined = pd.concat([old, new]).sort_values("timestamp_utc")
    result = continuous(joined)
    assert list(result.contract) == ["MESH26", "MESH26", "MESM26", "MESM26"]
    assert result.adjustment.iloc[2] == -100
    assert result.close.iloc[2]-result.feature_close.iloc[2] == 100


def test_holdout_single_use(tmp_path):
    args = dict(dataset_version="a", dates=["x", "y"], model_version="m", code_commit="c", config_hash="h", source_hash="s")
    reserve_holdout(tmp_path/"test.json", **args)
    with pytest.raises(FileExistsError):
        reserve_holdout(tmp_path/"test.json", **args)
