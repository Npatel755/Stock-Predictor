"""Official Binance ETHUSDT spot history, explicitly separate from perps."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import zipfile

import pandas as pd
import requests

from .eth_research.data import validate_bars
from .eth_research.perpetual_data import COLUMNS, download
from .market_data import BAR, utc

TICKER = 'BINANCE:ETHUSDT'
SOURCE = 'Binance ETHUSDT spot official public archives; cross-market proxy, not perpetual futures or Breakout execution'


def validate_proxy(raw):
    frame = validate_bars(raw, expected_ticker=TICKER)
    frame['exchange_close_time'] = pd.to_datetime(frame.exchange_close_time, utc=True)
    frame['available_at'] = frame.timestamp+BAR
    if not ((frame.exchange_close_time >= frame.timestamp) & (frame.exchange_close_time < frame.available_at)).all():
        raise ValueError('Spot source close timestamp outside candle')
    missing = int((frame.timestamp.diff().div(BAR).sub(1).clip(lower=0)).sum())
    return frame, dict(rows=len(frame), missing_bars=missing, instrument=TICKER, source=SOURCE)


def parse_archive(payload):
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        files = [f for f in archive.infolist() if f.filename.endswith('.csv')]
        if len(files) != 1 or files[0].file_size > 20_000_000:
            raise ValueError('Unexpected spot archive contents')
        raw = pd.read_csv(archive.open(files[0]), names=COLUMNS, header=None)
    for column in COLUMNS:
        raw[column] = pd.to_numeric(raw[column], errors='raise')
    if raw.isna().any().any() or raw.empty:
        raise ValueError('Missing spot candle fields')
    unit = 'us' if raw.open_time.max() > 10**15 else 'ms'
    frame = raw[['open', 'high', 'low', 'close', 'volume']].copy()
    frame['timestamp'] = pd.to_datetime(raw.open_time.astype('int64'), unit=unit, utc=True)
    frame['exchange_close_time'] = pd.to_datetime(raw.close_time.astype('int64'), unit=unit, utc=True)
    frame['ticker'] = TICKER
    aligned = frame.timestamp.eq(frame.timestamp.dt.floor('5min'))
    excluded = int((~aligned).sum())
    # Some early exchange archives contain outage-era candles offset by seconds.
    # Never shift them into invented buckets; retain raw ZIP, exclude/report
    # those records and split real five-minute gaps explicitly in the audit.
    frame = validate_proxy(frame.loc[aligned].reset_index(drop=True))[0]
    frame.attrs['excluded_off_grid_rows'] = excluded
    return frame


def fetch(start, end, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    chunks, manifest = [], []
    start, end = utc(start), utc(end)
    with requests.Session() as session:
        for month in pd.date_range(start, end, freq='MS', inclusive='left'):
            period = month.strftime('%Y-%m')
            name = f'ETHUSDT-5m-{period}.zip'
            url = f'https://data.binance.vision/data/spot/monthly/klines/ETHUSDT/5m/{name}'
            path = directory/name
            check = directory/(name+'.CHECKSUM')
            payload = path.read_bytes() if path.exists() and check.exists() else download(session, url, optional=True)
            if payload is None:
                raise ValueError(f'Unavailable spot archive: {period}')
            checksum = check.read_text() if check.exists() and path.exists() else download(session, url+'.CHECKSUM').decode('utf-8')
            digest = hashlib.sha256(payload).hexdigest()
            if digest != checksum.split()[0]:
                raise ValueError(f'Spot checksum mismatch: {period}')
            path.write_bytes(payload)
            check.write_text(checksum)
            frame = parse_archive(payload)
            chunks.append(frame)
            manifest.append(dict(month=period, rows=len(frame), excluded_off_grid_rows=frame.attrs.get('excluded_off_grid_rows', 0), sha256=digest, url=url))
            print(f'SPOT DATA {period}: {len(frame)} checksum verified', flush=True)
    frame, quality = validate_proxy(pd.concat(chunks, ignore_index=True))
    frame = frame[(frame.timestamp >= start) & (frame.available_at <= end)].reset_index(drop=True)
    path = directory/'candles.parquet'
    frame.to_parquet(path, index=False)
    metadata = dict(quality=quality, source=SOURCE, ticker=TICKER, start=str(start), end_exclusive=str(end),
                    archives=manifest, dataset_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    (directory/'metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    return frame, metadata
