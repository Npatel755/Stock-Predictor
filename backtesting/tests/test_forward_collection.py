import hashlib
from pathlib import Path

import pandas as pd
import pytest

from backtesting.forward_collection import collect,latest,collection_lock
from backtesting.generalization_policy import initialize
from test_dvs import candles
from test_v15 import write_selection


@pytest.fixture
def protocol_root(tmp_path,monkeypatch):
    import backtesting.save_v15 as exporter
    monkeypatch.setattr(exporter,'ROOT',tmp_path)
    experiment=tmp_path/'original';write_selection(experiment);exporter.save(experiment)
    repo=Path(__file__).resolve().parents[1]
    for name in ['alternative_strategies.py','engine.py','regime_filters.py','indicators.py','config.py']:
        (tmp_path/name).write_bytes((repo/name).read_bytes())
    initialize('2026-11-03 17:13:48+00:00',tmp_path,version='v1.5')
    return tmp_path


def reader(missing=()):
    calls=[]
    def get(session,period,frequency,directory):
        calls.append(period)
        if period in missing:return None
        path=directory/f'ETHUSDT-5m-{period}.zip'
        if not path.exists():
            payload=f'fixed authentic-source stand-in for {period}'.encode()
            path.write_bytes(payload)
            path.with_name(path.name+'.CHECKSUM').write_text(hashlib.sha256(payload).hexdigest()+' '+path.name)
        frame=candles(288)
        frame['timestamp']=pd.date_range(period,periods=288,freq='5min',tz='UTC')
        frame['exchange_close_time']=frame.timestamp+pd.Timedelta(minutes=5)-pd.Timedelta(milliseconds=1)
        return frame
    return get,calls


def test_collection_uses_only_completed_days_and_reveals_no_strategy_outcomes(protocol_root):
    get,calls=reader()
    result=collect(protocol_root,now='2026-11-03 23:59:59+00:00',reader=get)
    assert max(calls)=='2026-11-02' and '2026-11-03' not in calls
    assert result['forward_rows']==0 and not result['performance_evaluated']
    assert result['missing_bars']==0 and not result['warmup_complete']
    assert not {'net','net_pnl','returns','trades','signals'}.intersection(result)
    assert latest(protocol_root)==result


def test_new_day_extends_data_without_overwriting_prior_snapshot(protocol_root):
    get,_=reader()
    first=collect(protocol_root,now='2026-11-03',reader=get)
    path=protocol_root/first['snapshot_path'];original=path.read_bytes()
    second=collect(protocol_root,now='2026-11-05',reader=get)
    assert second['forward_rows']==288 and second['warmup_complete']
    assert second['snapshot_path']!=first['snapshot_path'] and path.read_bytes()==original
    assert not second['all_required_days_collected']


def test_unpublished_later_day_keeps_same_snapshot_but_new_coverage_record(protocol_root):
    get,_=reader(missing={'2026-11-03','2026-11-04'})
    first=collect(protocol_root,now='2026-11-03',reader=get)
    second=collect(protocol_root,now='2026-11-05',reader=get)
    assert second['snapshot_path']==first['snapshot_path']
    assert second['missing_bars']==576 and first['missing_bars']==0
    assert not second['warmup_complete']
    assert latest(protocol_root)==second
    collections=list((protocol_root/'artifacts/generalization/forward_collection/collections').glob('*.json'))
    assert len(collections)==2


def test_even_replacing_both_raw_source_and_checksum_cannot_revise_a_pinned_day(protocol_root):
    get,_=reader();first=collect(protocol_root,now='2026-11-03',reader=get)
    archive=next((protocol_root/'data/generalization/forward_collection/archives').glob('*.zip'))
    changed=b'corrected upstream prices'
    archive.write_bytes(changed)
    archive.with_name(archive.name+'.CHECKSUM').write_text(hashlib.sha256(changed).hexdigest()+' '+archive.name)
    with pytest.raises(ValueError,match='Pinned forward source archive changed'):
        collect(protocol_root,now='2026-11-05',reader=get)
    assert latest(protocol_root)==first


def test_collector_never_fetches_beyond_fixed_window(protocol_root):
    get,calls=reader()
    result=collect(protocol_root,now='2028-01-01',reader=get)
    assert max(calls)=='2027-05-02'
    assert result['all_required_days_collected'] and result['warmup_complete']
    assert result['forward_rows']==180*288
    assert result['state']=='ready_for_final_evaluation' and not result['prospective_validation_complete']


def test_modified_dataset_snapshot_is_rejected_before_display(protocol_root):
    get,_=reader();result=collect(protocol_root,now='2026-11-03',reader=get)
    (protocol_root/result['snapshot_path']).write_bytes(b'modified prices')
    with pytest.raises(ValueError,match='snapshot was modified'):latest(protocol_root)


def test_all_unpublished_sources_produce_missing_coverage_not_a_fake_empty_pass(protocol_root):
    result=collect(protocol_root,now='2026-11-03',reader=lambda *args:None)
    assert result['state']=='awaiting_source_archives' and result['missing_bars']>0
    assert result['rows']==0 and result['snapshot_path'] is None
    assert not result['all_required_days_collected'] and not result['prospective_validation_complete']


def test_archive_rows_outside_declared_day_are_rejected_before_pinning(protocol_root):
    get,_=reader()
    def wrong(session,period,frequency,directory):
        frame=get(session,period,frequency,directory)
        frame['timestamp']+=pd.Timedelta(days=1)
        return frame
    with pytest.raises(ValueError,match='declared UTC day'):
        collect(protocol_root,now='2026-11-03',reader=wrong)
    assert not (protocol_root/'artifacts/generalization/forward_collection/pinned_archives.json').exists()


def test_concurrent_collector_cannot_replace_another_writers_pin_log(protocol_root):
    lock=protocol_root/'artifacts/generalization/forward_collection/collector.lock'
    get,calls=reader()
    with collection_lock(lock):
        with pytest.raises(ValueError,match='Another forward collector is active'):
            collect(protocol_root,now='2026-11-03',reader=get)
        assert not calls
    assert collect(protocol_root,now='2026-11-03',reader=get)['rows']>0
