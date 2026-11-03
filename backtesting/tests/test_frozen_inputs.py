import pytest

from backtesting.frozen_inputs import retain,recorded_path


def test_extending_current_cache_cannot_change_a_recorded_backtest_input(tmp_path):
    path=tmp_path/'candles.parquet';path.write_bytes(b'original market observations')
    snapshot,digest=retain(path,tmp_path)
    assert recorded_path(tmp_path,'candles.parquet',digest)==path
    path.write_bytes(b'original market observations plus new days')
    assert recorded_path(tmp_path,'candles.parquet',digest)==snapshot
    assert snapshot.read_bytes()==b'original market observations'


def test_modified_snapshot_is_rejected_instead_of_silently_reusing_new_data(tmp_path):
    path=tmp_path/'candles.parquet';path.write_bytes(b'original')
    snapshot,digest=retain(path,tmp_path)
    path.write_bytes(b'new data');snapshot.write_bytes(b'corrupt snapshot')
    with pytest.raises(ValueError,match='exact retained snapshot'):recorded_path(tmp_path,'candles.parquet',digest)
