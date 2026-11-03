"""Pinned public ETH funding settlements; timestamps are never rounded.

Funding is an optional signal-context feature, not Breakout financing. Only
settled rates plus an explicit publication delay may affect an entry.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import zipfile

import numpy as np
import pandas as pd
import requests

from .exit_research import freeze
from .market_data import BAR, utc


BASE = 'https://data.binance.vision/data/futures/um/monthly/fundingRate/ETHUSDT'
COLUMNS = ['calc_time', 'funding_interval_hours', 'last_funding_rate']


def parse(payload, month):
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = [p for p in archive.namelist() if p.endswith('.csv')]
        if len(members) != 1:
            raise ValueError('Funding archive must contain exactly one CSV')
        frame = pd.read_csv(archive.open(members[0]))
    if list(frame.columns) != COLUMNS:
        raise ValueError('Unexpected funding archive schema')
    for name in COLUMNS:
        frame[name] = pd.to_numeric(frame[name], errors='raise')
    if not np.isfinite(frame[COLUMNS]).all().all():
        raise ValueError('Nonfinite funding records')
    if not frame.calc_time.mod(1).eq(0).all():
        raise ValueError('Funding timestamps must be integer milliseconds')
    if not frame.funding_interval_hours.mod(1).eq(0).all() or not frame.funding_interval_hours.between(1, 24).all():
        raise ValueError('Invalid funding settlement interval')
    if frame.last_funding_rate.abs().gt(1).any():
        raise ValueError('Implausible funding fraction; no clipping is permitted')
    frame['timestamp'] = pd.to_datetime(frame.calc_time, unit='ms', utc=True)
    start = utc(month+'-01'); end = start+pd.offsets.MonthBegin(1)
    # Retain original ZIP bytes; any inclusive boundary row is excluded rather
    # than shifted into a different settlement bucket.
    frame = frame[(frame.timestamp >= start) & (frame.timestamp < end)].copy()
    if frame.timestamp.duplicated().any():
        raise ValueError('Duplicate funding timestamps require source review')
    frame['rate_8h_bps'] = frame.last_funding_rate*10000*8/frame.funding_interval_hours
    return frame.sort_values('timestamp').reset_index(drop=True)


def fetch_month(root, month):
    directory = root/'data/eth_funding'
    directory.mkdir(parents=True, exist_ok=True)
    name = f'ETHUSDT-fundingRate-{month}.zip'
    archive, checksum = directory/name, directory/(name+'.CHECKSUM')
    if archive.exists() != checksum.exists():
        raise ValueError('Partial pinned funding source; inspect before retrying')
    if archive.exists():
        payload, check = archive.read_bytes(), checksum.read_bytes()
    else:
        response = requests.get(f'{BASE}/{name}', timeout=30)
        response.raise_for_status()
        proof = requests.get(f'{BASE}/{name}.CHECKSUM', timeout=30)
        proof.raise_for_status()
        payload, check = response.content, proof.content
    expected = check.decode('utf-8').split()[0]
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        raise ValueError('Funding ZIP differs from its published checksum')
    frame = parse(payload, month)
    source = dict(month=month, url=f'{BASE}/{name}', zip_sha256=actual,
                  checksum_sha256=hashlib.sha256(check).hexdigest(), rows=len(frame))
    freeze(directory/(name+'.source.json'), source)
    if not archive.exists():
        archive.write_bytes(payload)
        checksum.write_bytes(check)
    return frame, source


def collect(root):
    months = pd.date_range('2020-01-01', '2026-10-01', freq='MS').strftime('%Y-%m').tolist()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda month: fetch_month(root, month), months))
    frame = pd.concat([r[0] for r in results], ignore_index=True)
    if frame.timestamp.duplicated().any() or not frame.timestamp.is_monotonic_increasing:
        raise ValueError('Funding settlement sequence is not unique and sorted')
    frame = frame[frame.timestamp < utc('2026-10-28')].reset_index(drop=True)
    return frame, [r[1] for r in results]


def align(signals, settlements, publication_hours=1):
    if publication_hours not in {1, 8}:
        raise ValueError('Only preregistered publication-lag scenarios are supported')
    times = (signals.timestamp+BAR).dt.as_unit('ns')
    source = settlements[['timestamp', 'funding_interval_hours', 'rate_8h_bps']].copy()
    source['available_at'] = (source.timestamp+pd.Timedelta(hours=publication_hours)).dt.as_unit('ns')
    merged = pd.merge_asof(pd.DataFrame(dict(signal_available_at=times)), source,
                           left_on='signal_available_at', right_on='available_at', direction='backward')
    fresh = merged.available_at.notna() & (merged.signal_available_at-merged.available_at <= pd.to_timedelta(2*merged.funding_interval_hours, unit='h'))
    return pd.Series(merged.rate_8h_bps.where(fresh).to_numpy(), index=signals.index)


def filter_entries(signals, settled_rate, maximum_signed_bps):
    if not signals.index.equals(settled_rate.index):
        raise ValueError('Funding features do not match signal rows')
    if (signals.signal.ne(0) & settled_rate.isna()).any():
        raise ValueError('Missing/stale funding at a potential entry; do not select around missing data')
    result = signals.copy()
    result['signal'] = signals.signal.where(signals.signal*settled_rate <= maximum_signed_bps, 0).astype(int)
    return result
