"""Checksum-verified Binance USD-M perpetual 5m archives for the research universe."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd
import requests

from ..eth_research.perpetual_data import BASE, COLUMNS, download
from ..market_data import BAR, utc
from ..paths import ROOT

# Breakout-listed coins with 5x leverage and large position caps; Binance UM
# perpetual archives exist for all of them from before 2021-01-01.
UNIVERSE = {
    'BTC': dict(breakout='BTCUSD', leverage=10, max_usd=1_000_000),
    'SOL': dict(breakout='SOLUSD', leverage=5, max_usd=500_000),
    'XRP': dict(breakout='XRPUSD', leverage=5, max_usd=300_000),
    'BNB': dict(breakout='BNBUSD', leverage=5, max_usd=400_000),
    'DOGE': dict(breakout='DOGEUSD', leverage=5, max_usd=200_000),
    'LINK': dict(breakout='LINKUSD', leverage=5, max_usd=200_000),
    'LTC': dict(breakout='LTCUSD', leverage=5, max_usd=200_000),
    'ADA': dict(breakout='ADAUSD', leverage=5, max_usd=150_000),
}
START, END = '2021-01-01', '2026-10-28'
DATA = ROOT/'data/crypto'


def ticker(symbol):
    return f'BINANCE:{symbol}USDT.P'


def directory(symbol, data=DATA):
    return Path(data)/symbol.lower()


def read_archive(session, symbol, period, directory, frequency='monthly'):
    name = f'{symbol}USDT-5m-{period}.zip'
    path, check = directory/name, directory/(name+'.CHECKSUM')
    if path.exists() and check.exists():
        payload, checksum = path.read_bytes(), check.read_text(encoding='utf-8')
    else:
        url = f'{BASE}/{frequency}/klines/{symbol}USDT/5m/{name}'
        payload = download(session, url, optional=True)
        if payload is None:
            return None
        checksum = download(session, url+'.CHECKSUM').decode('utf-8')
    if hashlib.sha256(payload).hexdigest() != checksum.split()[0]:
        raise ValueError(f'Checksum mismatch for {name}')
    if not path.exists():
        path.write_bytes(payload)
        check.write_text(checksum, encoding='utf-8')
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        files = [f for f in z.infolist() if f.filename.endswith('.csv')]
        if len(files) != 1 or files[0].file_size > 20_000_000:
            raise ValueError('Unexpected archive CSV contents')
        content = z.read(files[0])
    first = content.decode('utf-8-sig').split('\n', 1)[0].split(',')
    header = None if first[0].strip().isdigit() else 0
    raw = pd.read_csv(io.BytesIO(content), header=header, names=COLUMNS)
    for column in COLUMNS:
        raw[column] = pd.to_numeric(raw[column], errors='raise')
    if raw.empty or raw.isna().any().any():
        raise ValueError('Archive contains missing candle fields')
    unit = 'us' if raw.open_time.max() > 10**15 else 'ms'
    out = raw[['open', 'high', 'low', 'close', 'volume']].copy()
    out.insert(0, 'timestamp', pd.to_datetime(raw.open_time.astype('int64'), unit=unit, utc=True))
    out.insert(1, 'ticker', ticker(symbol))
    out['exchange_close_time'] = pd.to_datetime(raw.close_time.astype('int64'), unit=unit, utc=True)
    return out


def clean(raw, symbol, start=START, end=END):
    """Exact 5m grid between start and end; gaps are reported, never filled."""
    frame = raw.drop_duplicates().copy()
    if not frame.ticker.eq(ticker(symbol)).all():
        raise ValueError(f'Only {ticker(symbol)} data is allowed here')
    frame['timestamp'] = pd.to_datetime(frame.timestamp, utc=True)
    frame = frame.sort_values('timestamp').reset_index(drop=True)
    if frame.timestamp.duplicated().any():
        raise ValueError('Conflicting candles at the same open timestamp')
    if (frame.timestamp.dt.minute.mod(5).ne(0) | frame.timestamp.dt.second.ne(0)).any():
        raise ValueError('Bars must align to five-minute boundaries')
    values = frame[['open', 'high', 'low', 'close', 'volume']].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values[:, :4] <= 0).any() or (values[:, 4] < 0).any():
        raise ValueError('Invalid OHLCV values')
    if ((frame.high < frame[['open', 'close', 'low']].max(axis=1)) |
            (frame.low > frame[['open', 'close', 'high']].min(axis=1))).any():
        raise ValueError('Inconsistent OHLC bar')
    frame = frame[(frame.timestamp >= utc(start)) & (frame.timestamp+BAR <= utc(end))].reset_index(drop=True)
    if frame.empty:
        raise ValueError('No candles in requested range')
    frame['available_at'] = frame.timestamp+BAR
    expected = int((utc(end)-utc(start))/BAR)
    quality = dict(instrument=ticker(symbol), rows=int(len(frame)), expected_rows=expected,
                   missing_bars=int(expected-len(frame)), first_open_utc=str(frame.timestamp.iloc[0]),
                   last_close_exclusive_utc=str(frame.available_at.iloc[-1]),
                   zero_volume_bars=int(frame.volume.eq(0).sum()))
    return frame, quality


def fetch(symbol, start=START, end=END, data=DATA):
    if symbol not in UNIVERSE:
        raise ValueError(f'{symbol} is not in the research universe')
    folder = directory(symbol, data)
    folder.mkdir(parents=True, exist_ok=True)
    cursor, chunks, manifest, missing = utc(start).replace(day=1), [], [], []
    with requests.Session() as session:
        while cursor < utc(end):
            period = cursor.strftime('%Y-%m')
            month_end = cursor+pd.offsets.MonthBegin(1)
            part = read_archive(session, symbol, period, folder)
            days = pd.date_range(max(cursor, utc(start)), min(month_end, utc(end)), inclusive='left', freq='D')
            if part is None:
                absent = list(days)
            else:
                chunks.append(part)
                manifest.append(period)
                present = set(part.timestamp.dt.floor('D'))
                absent = [day for day in days if day not in present]
            # Whole UTC days absent from a monthly archive are repaired from Binance's daily archives, never synthesized.
            repaired = 0
            for day in absent:
                daily = read_archive(session, symbol, day.strftime('%Y-%m-%d'), folder, 'daily')
                if daily is None:
                    missing.append(str(day.date()))
                else:
                    chunks.append(daily)
                    manifest.append(str(day.date()))
                    repaired += 1
            print(f'{symbol} {period}: {"ok" if part is not None else "missing"}' + (f' (+{repaired} daily)' if repaired else ''), flush=True)
            cursor = month_end
    if not chunks:
        raise ValueError(f'No archives available for {symbol}')
    frame, quality = clean(pd.concat(chunks, ignore_index=True), symbol, start, end)
    quality.update(requested_start=start, requested_end_exclusive=end, archives=manifest,
                   missing_archives=missing, downloaded_at_utc=str(pd.Timestamp.now(tz='UTC')))
    output = folder/'candles.parquet'
    frame.to_parquet(output, index=False)
    quality['parquet_sha256'] = hashlib.sha256(output.read_bytes()).hexdigest()
    (folder/'candles.quality.json').write_text(json.dumps(quality, indent=2), encoding='utf-8')
    return output, quality


def load(symbol, data=DATA, expected_sha256=None):
    folder = directory(symbol, data)
    path = folder/'candles.parquet'
    quality = json.loads((folder/'candles.quality.json').read_text(encoding='utf-8'))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != quality['parquet_sha256'] or (expected_sha256 and digest != expected_sha256):
        raise ValueError(f'{symbol} candles changed after their quality audit')
    frame, _ = clean(pd.read_parquet(path), symbol, quality['requested_start'], quality['requested_end_exclusive'])
    return frame, quality


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbols', nargs='*', default=list(UNIVERSE))
    parser.add_argument('--start', default=START)
    parser.add_argument('--end', default=END)
    args = parser.parse_args()
    for sym in args.symbols:
        _, q = fetch(sym, args.start, args.end)
        print(sym, q['rows'], 'bars,', q['missing_bars'], 'missing', flush=True)
