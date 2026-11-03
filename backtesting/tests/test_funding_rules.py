import hashlib
import io
from types import SimpleNamespace
import zipfile

import pandas as pd
import pytest

from backtesting.funding_data import parse, align, filter_entries, fetch_month


def archive(rows):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as z:
        z.writestr('ETHUSDT.csv', 'calc_time,funding_interval_hours,last_funding_rate\n'+rows)
    return buffer.getvalue()


def settlements():
    return parse(archive('1577836800002,8,0.0001\n1577865600002,8,0.0002\n'), '2020-01')


def test_published_settlement_milliseconds_are_preserved_and_intervals_normalized():
    frame = parse(archive('1577836800002,4,0.0001\n'), '2020-01')
    assert frame.timestamp.iloc[0] == pd.Timestamp('2020-01-01 00:00:00.002Z')
    assert frame.rate_8h_bps.iloc[0] == 2.


def test_asof_feature_cannot_know_funding_before_delayed_publication():
    signals = pd.DataFrame(dict(timestamp=pd.to_datetime(['2020-01-01 08:55Z', '2020-01-01 09:00Z']), signal=[1, 1]))
    rate = align(signals, settlements(), 1)
    assert rate.tolist() == [1., 2.]
    assert align(signals, settlements(), 8).tolist() == [1., 1.]
    old = settlements().iloc[:1]
    assert align(signals, old, 1).tolist() == [1., 1.]


def test_unknown_or_stale_funding_rejects_experiment_instead_of_dropping_arbitrary_trades():
    signals = pd.DataFrame(dict(timestamp=pd.to_datetime(['2020-01-03 09:00Z']), signal=[1]))
    rate = align(signals, settlements(), 1)
    assert rate.isna().all()
    with pytest.raises(ValueError, match='Missing/stale'):
        filter_entries(signals, rate, 1.)


def test_funding_filter_is_directional_and_only_changes_entry_acceptance():
    signals = pd.DataFrame(dict(signal=[1, -1, 1, 0], stop=[90., 110., 90., 90.]))
    rates = pd.Series([2., 2., -2., 2.])
    result = filter_entries(signals, rates, 1.)
    assert result.signal.tolist() == [0, -1, 1, 0]
    pd.testing.assert_series_equal(signals.stop, result.stop)


@pytest.mark.parametrize('rows', ['1577836800000.1,8,0.0001\n', '1577836800000,0,0.0001\n',
                                   '1577836800000,8,NaN\n', '1577836800000,8,2.0\n',
                                   '1577836800000,8,0.0001\n1577836800000,8,0.0002\n'])
def test_malformed_settlements_are_never_rounded_clipped_or_merged(rows):
    with pytest.raises(ValueError):
        parse(archive(rows), '2020-01')


def test_first_checksum_verified_source_cannot_be_replaced(tmp_path, monkeypatch):
    import backtesting.funding_data as module
    payload = archive('1577836800000,8,0.0001\n')
    checksum = (hashlib.sha256(payload).hexdigest()+' source.zip').encode()
    def get(url, **kwargs):
        return SimpleNamespace(content=checksum if url.endswith('CHECKSUM') else payload,
                               raise_for_status=lambda: None)
    monkeypatch.setattr(module.requests, 'get', get)
    a, source = fetch_month(tmp_path, '2020-01')
    assert len(a) == 1 and source['rows'] == 1
    path = tmp_path/'data/eth_funding/ETHUSDT-fundingRate-2020-01.zip'
    altered = archive('1577836800000,8,0.0002\n')
    path.write_bytes(altered)
    path.with_name(path.name+'.CHECKSUM').write_text(hashlib.sha256(altered).hexdigest())
    with pytest.raises(ValueError, match='manifest differs'):
        fetch_month(tmp_path, '2020-01')
