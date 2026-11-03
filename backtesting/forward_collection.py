"""Collect append-only ETH test inputs without revealing strategy performance."""
from __future__ import annotations

from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import tempfile

import pandas as pd
import requests

from .exit_research import freeze
from .generalization_policy import digest,frozen_profile
from .market_data import BAR,clean_candles,read_archive,utc
from .paths import ROOT
from .reporting import safe_value


@contextmanager
def collection_lock(path):
    """One writer; OS locks release automatically if a collector crashes."""
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+b') as handle:
        handle.seek(0,2)
        if handle.tell()==0:handle.write(b'0');handle.flush()
        handle.seek(0)
        if os.name=='nt':
            import msvcrt
            acquire=lambda:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            release=lambda:(handle.seek(0),msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1))
        else:
            import fcntl
            acquire=lambda:fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            release=lambda:fcntl.flock(handle.fileno(),fcntl.LOCK_UN)
        try:acquire()
        except OSError:raise ValueError('Another forward collector is active; retained data was not changed') from None
        try:yield
        finally:release()


def atomic_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    pending=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,suffix='.tmp',delete=False) as handle:
            pending=Path(handle.name)
            json.dump(safe_value(value),handle,indent=2,allow_nan=False)
        pending.replace(path)
    finally:
        if pending is not None:pending.unlink(missing_ok=True)


def source_identity(directory,period):
    path=directory/f'ETHUSDT-5m-{period}.zip';check=path.with_name(path.name+'.CHECKSUM')
    payload=path.read_bytes();checksum=check.read_text(encoding='utf-8').split()[0]
    actual=hashlib.sha256(payload).hexdigest()
    if actual!=checksum:raise ValueError('Collected archive checksum mismatch')
    return dict(period=period,frequency='daily',archive=path.name,sha256=actual,
                checksum_file_sha256=hashlib.sha256(check.read_bytes()).hexdigest(),
                url=f'https://data.binance.vision/data/futures/um/daily/klines/ETHUSDT/5m/{path.name}')


def collect(root=ROOT,now=None,reader=None):
    frozen_profile(root)
    with collection_lock(root/'artifacts/generalization/forward_collection/collector.lock'):
        return _collect(root,now,reader)


def _collect(root,now,reader):
    p,rule,_,_=frozen_profile(root)
    current=utc(now) if now is not None else pd.Timestamp.now(tz='UTC')
    start,end=utc(p['future_start_utc']),utc(p['future_end_exclusive_utc'])
    warmup=start-pd.Timedelta(hours=5*rule.slow)
    completed_end=min(current.floor('D'),end)
    directory=root/'data/generalization/forward_collection'
    output=root/'artifacts/generalization/forward_collection'
    archives=directory/'archives';archives.mkdir(parents=True,exist_ok=True);output.mkdir(parents=True,exist_ok=True)
    plan=dict(protocol_sha256=digest(p),frozen_version=p['frozen_version'],
              configuration_sha256=p['frozen_configuration_sha256'],
              warmup_start_utc=str(warmup),future_period=[str(start),str(end)],
              source='Official Binance USD-M ETHUSDT five-minute daily public archives',
              rule='Only fully completed UTC days. First successfully retrieved checksum-verified archive is pinned. Retry missing days later; never overwrite a pinned day or evaluate performance while collecting.',
              source_revision_policy='Changed cached day/checksum is rejected. A corrected feed would need a separately recorded provenance decision; no revision is chosen based on returns.',
              missing_data_policy='Report gaps and absent archives. No interpolation, resampling, substitution or fabricated bars.',
              performance_output_permitted=False)
    freeze(output/'manifest.json',plan)
    pinned_path=output/'pinned_archives.json'
    pinned=json.loads(pinned_path.read_text(encoding='utf-8')) if pinned_path.exists() else {}
    # A cached price revision cannot silently enter a new snapshot, even if
    # someone replaces both the ZIP and its locally stored checksum.
    for period,identity in pinned.items():
        if source_identity(archives,period)!=identity:raise ValueError('Pinned forward source archive changed')
    days=pd.date_range(warmup.floor('D'),completed_end,inclusive='left',freq='D') if completed_end>warmup else []
    fetch=reader or read_archive
    def day(stamp):
        period=stamp.strftime('%Y-%m-%d')
        with requests.Session() as session:frame=fetch(session,period,'daily',archives)
        if frame is None:
            if period in pinned:raise ValueError('A pinned forward day became unavailable')
            return period,None,None
        # Require each archive to contain only its declared completed day.
        times=pd.to_datetime(frame.timestamp,utc=True)
        if (times<stamp).any() or (times+BAR>stamp+pd.Timedelta(days=1)).any():
            raise ValueError('Archive candles do not belong to their declared UTC day')
        identity=source_identity(archives,period)
        if period in pinned and identity!=pinned[period]:raise ValueError('Pinned forward source archive changed')
        return period,frame,identity
    with ThreadPoolExecutor(max_workers=4) as pool:parts=list(pool.map(day,days))
    frames=[];absent=[]
    for period,frame,identity in parts:
        if frame is None:absent.append(period);continue
        frames.append(frame);pinned[period]=identity
    # Never remove a day from the pin log. A failed later collection does not
    # erase an earlier retained snapshot.
    atomic_json(pinned_path,pinned)
    status=dict(protocol_sha256=digest(p),configuration_sha256=p['frozen_configuration_sha256'],
                as_of_utc=str(current),warmup_start_utc=str(warmup),
                completed_data_end_exclusive_utc=str(completed_end),
                future_start_utc=str(start),future_end_exclusive_utc=str(end),
                final_evaluation_not_before_utc=str(end),performance_evaluated=False,
                missing_daily_archives=absent,pinned_daily_archives=len(pinned),
                ready_for_funded_trading=False,prospective_validation_complete=False,
                instructions='Only data coverage is visible. This collector never runs strategy signals, returns, trades or selection.')
    if not frames:
        missing=max(0,int((completed_end-warmup)/BAR))
        status.update(state='awaiting_source_archives',rows=0,forward_rows=0,snapshot_path=None,
                      all_required_days_collected=False,warmup_complete=False,missing_bars=missing,
                      gaps=[dict(start=str(warmup),end_exclusive=str(completed_end),missing_bars=missing)] if missing else [])
    else:
        frame,quality=clean_candles(pd.concat(frames,ignore_index=True),start=warmup,end=completed_end)
        snapshot_dir=directory/'snapshots';snapshot_dir.mkdir(exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=snapshot_dir,suffix='.pending.parquet',delete=False) as handle:pending=Path(handle.name)
        try:
            frame.to_parquet(pending,index=False)
            sha=hashlib.sha256(pending.read_bytes()).hexdigest();snapshot=snapshot_dir/f'{sha}.parquet'
            if snapshot.exists():
                if hashlib.sha256(snapshot.read_bytes()).hexdigest()!=sha:raise ValueError('Retained forward snapshot changed')
                pending.unlink()
            else:pending.replace(snapshot)
        finally:pending.unlink(missing_ok=True)
        warmup_end=min(start,completed_end)
        expected_warmup=max(0,int((warmup_end-warmup)/BAR))
        actual_warmup=int((frame.available_at<=warmup_end).sum())
        # The same price snapshot may persist while additional requested days
        # remain unpublished. Keep intrinsic snapshot coverage separate from
        # the changing requested-period gaps recorded in each collection.
        _,intrinsic=clean_candles(frame)
        intrinsic.update(parquet_sha256=sha,source='Checksum-verified pinned daily Binance ETHUSDT perpetual archives')
        quality_path=snapshot.with_suffix('.quality.json')
        freeze(quality_path,intrinsic)
        coverage=frame.timestamp.ge(start)&frame.available_at.le(end)
        status.update(state='ready_for_final_evaluation' if completed_end==end and not quality['missing_bars'] else 'collecting_or_incomplete',
                      rows=len(frame),forward_rows=int(coverage.sum()),missing_bars=quality['missing_bars'],gaps=quality['gaps'],
                      snapshot_path=snapshot.relative_to(root).as_posix(),snapshot_sha256=sha,
                      warmup_complete=completed_end>=start and expected_warmup==actual_warmup,
                      all_required_days_collected=completed_end==end and not quality['missing_bars'])
        lineage=dict(protocol_sha256=digest(p),snapshot_sha256=sha,
                     available_period=[str(frame.timestamp.min()),str(frame.available_at.max())],
                     pinned_sources={period:pinned[period] for period,part,_ in parts if part is not None},
                     strategy_performance_evaluated=False)
        freeze(snapshot.with_suffix('.sources.json'),lineage)
    status_digest=hashlib.sha256(json.dumps(safe_value(status),sort_keys=True).encode()).hexdigest()
    (output/'collections').mkdir(exist_ok=True)
    freeze(output/'collections'/f'{status_digest}.json',status)
    atomic_json(output/'latest.json',status)
    return status


def latest(root=ROOT):
    path=root/'artifacts/generalization/forward_collection/latest.json'
    if not path.exists():return None
    result=json.loads(path.read_text(encoding='utf-8'));p,_,_,_=frozen_profile(root)
    if result['protocol_sha256']!=digest(p):raise ValueError('Collected data belongs to a different forward protocol')
    if result.get('snapshot_path'):
        file=(root/result['snapshot_path']).resolve()
        intended=(root/'data/generalization/forward_collection/snapshots').resolve()
        if not file.is_relative_to(intended):raise ValueError('Unexpected forward snapshot path')
        if hashlib.sha256(file.read_bytes()).hexdigest()!=result['snapshot_sha256']:raise ValueError('Latest retained snapshot was modified')
    return result


if __name__=='__main__':
    print(json.dumps(collect(),indent=2))
