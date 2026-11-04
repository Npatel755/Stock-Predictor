"""Isolated, hash-pinned snapshots; no writes to the source checkout."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import shutil
import zipfile

import numpy as np
import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
SOURCE = Path(r'C:\Users\Nick\OneDrive\Attachments\Desktop\Stock Predictor')
START = pd.Timestamp('2021-01-01', tz='UTC')
END = pd.Timestamp('2026-10-28', tz='UTC')
BAR = pd.Timedelta(minutes=5)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def freeze(path, value):
    path = Path(path)
    content = json.dumps(value, sort_keys=True, indent=2, default=str, allow_nan=False)+'\n'
    if path.exists() and path.read_text(encoding='utf-8') != content:
        raise ValueError(f'Frozen file differs: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')


def validate(frame):
    out = frame[['timestamp', 'open', 'high', 'low', 'close', 'volume']].copy()
    out.timestamp = pd.to_datetime(out.timestamp, utc=True).dt.as_unit('ns')
    duplicates = int(out.duplicated().sum())
    out = out.drop_duplicates().sort_values('timestamp').reset_index(drop=True)
    if out.timestamp.duplicated().any():
        raise ValueError('Conflicting duplicate candle timestamps')
    values = out[['open', 'high', 'low', 'close', 'volume']].to_numpy(float)
    if not np.isfinite(values).all() or (values[:, :4] <= 0).any() or (values[:, 4] < 0).any():
        raise ValueError('Invalid prices/volume')
    if (out.high < out[['open', 'low', 'close']].max(axis=1)).any() or (out.low > out[['open', 'high', 'close']].min(axis=1)).any():
        raise ValueError('Inconsistent OHLC')
    if (out.timestamp.astype('int64') % BAR.value != 0).any():
        raise ValueError('Off-grid UTC candle')
    missing = int(((END-START)/BAR)-len(out))
    if out.timestamp.iloc[0] != START or out.timestamp.iloc[-1]+BAR != END or missing:
        raise ValueError(f'Incomplete common history: {missing} candles missing; no filling allowed')
    if not out.timestamp.diff().iloc[1:].eq(BAR).all():
        raise ValueError('Interior data gap')
    return out, dict(rows=len(out), missing_candles=missing, exact_duplicates_removed=duplicates,
                     first_open=str(out.timestamp.iloc[0]), end_exclusive=str(out.timestamp.iloc[-1]+BAR),
                     zero_volume_bars=int(out.volume.eq(0).sum()))


def snapshot():
    inputs = {
        'ETH': [SOURCE/'backtesting/data/ethusd/perpetual_2020_2022/candles.parquet', SOURCE/'backtesting/data/ethusd/perpetual/candles.parquet'],
        'BNB': [SOURCE/'backtesting/data/crypto/bnb/candles.parquet'],
        'BTC': [SOURCE/'backtesting/data/crypto/btc/candles.parquet'],
    }
    manifest = dict(base_commit='432e7bf5ba434644375f4fe6ca9cb8909091b402', market='Binance USD-M linear USDT perpetual',
                    start=str(START), end_exclusive=str(END), assets={}, raw_archives=[])
    for symbol, paths in inputs.items():
        chunks = [pd.read_parquet(path) for path in paths]
        frame = pd.concat(chunks, ignore_index=True)
        frame = frame[(frame.timestamp >= START) & (frame.timestamp < END)]
        clean, quality = validate(frame)
        target = HERE/'data'/f'{symbol}_5m.parquet'
        if not target.exists():
            clean.to_parquet(target, index=False)
        elif not pd.read_parquet(target).equals(clean):
            raise ValueError('Pinned data snapshot differs from source')
        manifest['assets'][symbol] = dict(**quality, snapshot=str(target.relative_to(HERE)), snapshot_sha256=sha(target),
                                        inputs=[dict(path=str(p), sha256=sha(p)) for p in paths])
    # Existing exchange-published checksums validate reused raw ZIP bytes.
    folders = [SOURCE/'backtesting/data/crypto/bnb', SOURCE/'backtesting/data/crypto/btc',
               SOURCE/'backtesting/data/ethusd/perpetual', SOURCE/'backtesting/data/ethusd/perpetual_2020_2022']
    for folder in folders:
        for check in sorted(folder.rglob('*.zip.CHECKSUM')):
            archive = check.with_suffix('')
            if not archive.exists():
                raise ValueError(f'Missing raw source: {archive}')
            actual = sha(archive)
            if actual != check.read_text(encoding='utf-8').split()[0]:
                raise ValueError(f'Raw archive checksum failed: {archive}')
            manifest['raw_archives'].append(dict(path=str(archive), sha256=actual, checksum_sha256=sha(check), read_only_external=True))
    freeze(HERE/'data_manifest.json', manifest)
    train_end = START+int(((END-START)/BAR)*.60)*BAR
    valid_end = START+int(((END-START)/BAR)*.80)*BAR
    split = dict(data_manifest_sha256=sha(HERE/'data_manifest.json'),
                 train=[str(START), str(train_end)], validation=[str(train_end), str(valid_end)],
                 nominal_final=[str(valid_end), str(END)],
                 nominal_final_status='CONTAMINATED_BY_PRIOR_ETH_AND_BNB_SEARCH; PERFORMANCE_ACCESS_DISABLED',
                 all_historical_evidence='retrospective development diagnostics; not independent out-of-sample proof',
                 embargo_days=8, outcome_purge='Reset positions per fold and force terminal accounting; no overlapping fitted event labels.',
                 folds=[dict(id='wf_2022', fit_end='2021-12-24 00:00:00+00:00', eval_start='2022-01-01 00:00:00+00:00', eval_end='2023-01-01 00:00:00+00:00'),
                        dict(id='wf_2023', fit_end='2022-12-24 00:00:00+00:00', eval_start='2023-01-01 00:00:00+00:00', eval_end='2024-01-01 00:00:00+00:00'),
                        dict(id='wf_2024', fit_end='2023-12-24 00:00:00+00:00', eval_start='2024-01-01 00:00:00+00:00', eval_end=str(train_end))],
                 validation_eval_start=str(train_end+pd.Timedelta(days=8)),
                 existing_sealed_future=['2026-11-04 00:00:00+00:00', '2027-05-03 00:00:00+00:00'],
                 new_prospective_reservation=['2026-11-05 00:00:00+00:00', '2027-05-04 00:00:00+00:00'],
                 future_access_policy='Only evaluate after full reservation end and candidate/hash freeze; never schedule live execution.')
    freeze(HERE/'split_manifest.json', split)
    print(json.dumps({s: m for s, m in manifest['assets'].items()}, indent=2), flush=True)
    return manifest, split


def funding_month(symbol, month):
    name = f'{symbol}USDT-fundingRate-{month}.zip'
    directory = HERE/'data/funding'/symbol
    directory.mkdir(parents=True, exist_ok=True)
    archive, check = directory/name, directory/(name+'.CHECKSUM')
    cached = SOURCE/'backtesting/data/eth_funding'/name
    url = f'https://data.binance.vision/data/futures/um/monthly/fundingRate/{symbol}USDT/{name}'
    if not archive.exists():
        if symbol == 'ETH' and cached.exists():
            shutil.copyfile(cached, archive)
            shutil.copyfile(cached.with_name(name+'.CHECKSUM'), check)
        else:
            response = requests.get(url, timeout=40)
            response.raise_for_status()
            proof = requests.get(url+'.CHECKSUM', timeout=40)
            proof.raise_for_status()
            if hashlib.sha256(response.content).hexdigest() != proof.text.split()[0]:
                raise ValueError('Downloaded funding checksum mismatch')
            archive.write_bytes(response.content)
            check.write_bytes(proof.content)
    if sha(archive) != check.read_text(encoding='utf-8').split()[0]:
        raise ValueError('Funding checksum failed')
    with zipfile.ZipFile(archive) as zipped:
        names = [n for n in zipped.namelist() if n.endswith('.csv')]
        if len(names) != 1:
            raise ValueError('Unexpected funding ZIP members')
        frame = pd.read_csv(io.BytesIO(zipped.read(names[0])))
    if not {'calc_time', 'funding_interval_hours', 'last_funding_rate'} <= set(frame.columns):
        raise ValueError('Unexpected funding columns')
    frame['timestamp'] = pd.to_datetime(frame.calc_time, unit='ms', utc=True).dt.as_unit('ns')
    begin = pd.Timestamp(month+'-01', tz='UTC')
    frame = frame[(frame.timestamp >= begin) & (frame.timestamp < begin+pd.offsets.MonthBegin(1))]
    if frame.timestamp.duplicated().any() or not np.isfinite(frame.last_funding_rate).all() or not frame.funding_interval_hours.between(1, 24).all():
        raise ValueError('Invalid funding settlements')
    return frame, dict(url=url, raw_sha256=sha(archive), checksum_sha256=sha(check), rows=len(frame))


def funding():
    months = pd.date_range(START, END, freq='MS').strftime('%Y-%m')
    provenance = {}
    for symbol in ['ETH', 'BNB']:
        with ThreadPoolExecutor(max_workers=4) as pool:
            parts = list(pool.map(lambda month: funding_month(symbol, month), months))
        frame = pd.concat([x[0] for x in parts], ignore_index=True).sort_values('timestamp')
        frame = frame[(frame.timestamp >= START) & (frame.timestamp < END)].reset_index(drop=True)
        if frame.timestamp.duplicated().any():
            raise ValueError('Duplicate funding time')
        # Fail closed on missing settlement intervals, rather than treating them as zero.
        delta = frame.timestamp.diff().dt.total_seconds()/3600
        if ((delta.iloc[1:]-frame.funding_interval_hours.iloc[1:]).abs() > .01).any():
            raise ValueError(f'{symbol} funding interval coverage has gaps')
        target = HERE/'data'/f'{symbol}_funding.parquet'
        if not target.exists():
            frame[['timestamp', 'funding_interval_hours', 'last_funding_rate']].to_parquet(target, index=False)
        provenance[symbol] = dict(archives=[x[1] for x in parts], snapshot_sha256=sha(target), rows=len(frame),
                                  signal_publication_lag_hours=1, cashflow='Actual settled signed rate at event time, trade-price proxy for unavailable mark price.')
        print(f'{symbol} funding: {len(frame)} settlements', flush=True)
    freeze(HERE/'funding_manifest.json', provenance)
    return provenance


def load(symbol, *, development_only=True):
    manifest = json.loads((HERE/'data_manifest.json').read_text())
    target = HERE/manifest['assets'][symbol]['snapshot']
    if sha(target) != manifest['assets'][symbol]['snapshot_sha256']:
        raise ValueError('Snapshot changed')
    frame = pd.read_parquet(target)
    if development_only:
        split = json.loads((HERE/'split_manifest.json').read_text())
        frame = frame[frame.timestamp+BAR <= pd.Timestamp(split['validation'][1])].copy()
    return frame


def resample(frame, timeframe, symbol):
    duration = pd.Timedelta(timeframe)
    indexed = frame.set_index('timestamp')
    grouped = indexed.resample(duration, origin='epoch', label='left', closed='left')
    result = grouped.agg(dict(open='first', high='max', low='min', close='last', volume='sum'))
    result = result[grouped.close.count() == int(duration/BAR)].reset_index()
    if len(result) > 1 and not result.timestamp.diff().iloc[1:].eq(duration).all():
        raise ValueError('Incomplete resampled history')
    path = HERE/'data'/f'{symbol}_funding.parquet'
    if path.exists():
        settlements = pd.read_parquet(path)
        # These snapshots settle every eight hours with <=47ms processing jitter.
        # Raw timestamps remain unchanged. Cashflow eligibility uses the nominal
        # settlement boundary (carried position, before new open entries), a
        # disclosed bar-resolution assumption; signal publication uses EXACT time.
        nominal = settlements.timestamp.dt.floor('8h')
        if (settlements.timestamp-nominal).dt.total_seconds().max() > 1:
            raise ValueError('Settlement jitter exceeds registered one-second timing approximation')
        payments = settlements.assign(timestamp=nominal).rename(columns={'last_funding_rate': 'funding_rate'})
        result = result.merge(payments[['timestamp', 'funding_rate']], on='timestamp', how='left')
        # Settled signal feature is delayed a full hour beyond publication.
        available = settlements.assign(available_at=settlements.timestamp+pd.Timedelta(hours=1))
        left = pd.DataFrame({'available_at': result.timestamp+duration})
        aligned = pd.merge_asof(left, available[['available_at', 'last_funding_rate']], on='available_at', direction='backward')
        result['settled_funding'] = aligned.last_funding_rate.to_numpy()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--funding', action='store_true')
    args = parser.parse_args()
    snapshot()
    if args.funding:
        funding()
