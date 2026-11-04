"""Local-file paper signal interface. No orders, credentials, APIs or scheduler.

Frozen payloads identify the exact strategy, code, input manifests and reserved
prospective period. This module emits desired paper exposure only; it does not
simulate fills, allocate capital or claim prospective PnL.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from .strategies import build_signal


ROOT = Path(__file__).resolve().parent
TIMEFRAMES = {'5m': pd.Timedelta(minutes=5), '15m': pd.Timedelta(minutes=15),
              '1h': pd.Timedelta(hours=1), '4h': pd.Timedelta(hours=4)}


def _digest(payload):
    text = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _utc(value, label):
    when = pd.Timestamp(value)
    if when.tzinfo is None:
        raise ValueError(f'{label} must be explicitly UTC-aware')
    return when.tz_convert('UTC')


def _validate_payload(payload):
    if payload.get('mode') != 'paper_only':
        raise ValueError('Frozen configuration must explicitly use mode=paper_only')
    strategy = payload.get('strategy', {})
    if not all(key in strategy for key in ['id', 'family', 'timeframe']):
        raise ValueError('Frozen strategy id/family/timeframe are required')
    if strategy['timeframe'] not in TIMEFRAMES:
        raise ValueError('Frozen strategy timeframe is unsupported')
    hashes = payload.get('code_hashes', {})
    if not isinstance(hashes, dict) or not hashes:
        raise ValueError('Frozen code hashes are required')
    for label, digest in list(hashes.items())+[(name, payload.get(name)) for name in ['data_manifest_sha256', 'split_manifest_sha256']]:
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError(f'Invalid SHA256 for {label}')
    reservation = payload.get('prospective_reservation', {})
    if not isinstance(reservation, dict) or not {'start', 'end'}.issubset(reservation):
        raise ValueError('Frozen prospective reservation start/end are required')
    start, end = _utc(reservation['start'], 'Reservation start'), _utc(reservation['end'], 'Reservation end')
    if start >= end:
        raise ValueError('Prospective reservation end must follow its start')


def freeze_payload(payload):
    """Return a new JSON-only envelope with an exact immutable payload hash."""
    body = json.loads(json.dumps(payload, allow_nan=False))
    body.pop('freeze_sha256', None)
    _validate_payload(body)
    return {**body, 'freeze_sha256': _digest(body)}


def verify_freeze(config):
    """Check payload identity without accessing bars or prospective outcomes."""
    _validate_payload(config)
    body = {key: value for key, value in config.items() if key != 'freeze_sha256'}
    if config.get('freeze_sha256') != _digest(body):
        raise ValueError('Frozen payload hash changed')
    return config


def _local_file(root, relative, *, suffix):
    root = Path(root).resolve()
    path = (root/relative).resolve()
    if not path.is_relative_to(root) or path.suffix != suffix:
        raise ValueError('Frozen paths must stay inside the research directory with the expected file type')
    if not path.is_file():
        raise ValueError(f'Frozen local file is unavailable: {relative}')
    return path


def validate_frozen_files(config, root=None):
    """Verify local code and manifest hashes; no credential files are read."""
    verify_freeze(config)
    root = ROOT if root is None else Path(root)
    for relative, digest in config['code_hashes'].items():
        path = _local_file(root, relative, suffix='.py')
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f'Frozen code hash changed: {relative}')
    for relative, key in [('data_manifest.json', 'data_manifest_sha256'), ('split_manifest.json', 'split_manifest_sha256')]:
        path = _local_file(root, relative, suffix='.json')
        if hashlib.sha256(path.read_bytes()).hexdigest() != config[key]:
            raise ValueError(f'Frozen manifest hash changed: {relative}')
    return config


def load_frozen_config(path, root=None, *, validate_code=True):
    """Read a JSON envelope; optional code validation defaults to enabled.

    ``root`` is the isolated research directory containing the code/manifests,
    rather than the directory of an arbitrary output candidate JSON file.
    """
    config = json.loads(Path(path).read_text(encoding='utf-8'))
    verify_freeze(config)
    if validate_code:
        validate_frozen_files(config, root)
    return config


def assert_prospective_ready(config, now, *, root=None):
    """Refuse early prospective access, then verify freeze identity and files.

    Passing this gate is permission to perform a separately controlled final
    evaluation, not proof the evaluation ran or passed. This function reads no
    price, trade, outcome or performance file.
    """
    verify_freeze(config)
    observed = _utc(now, 'Current time')
    end = _utc(config['prospective_reservation']['end'], 'Reservation end')
    if observed < end:
        raise ValueError(f'Prospective reservation remains sealed until {end.isoformat()}')
    validate_frozen_files(config, root)
    return True


def _completed_frame(frame, span, observed, label):
    if frame.empty or 'timestamp' not in frame:
        raise ValueError(f'{label} must contain nonempty timestamped candles')
    out = frame.copy()
    times = pd.DatetimeIndex(out.timestamp)
    if times.tz is None or str(times.tz) not in {'UTC', 'utc'}:
        raise ValueError(f'{label} timestamps must be UTC-aware')
    if not times.is_monotonic_increasing or times.has_duplicates:
        raise ValueError(f'{label} timestamps must be unique and ordered')
    if len(times) > 1 and not ((times[1:]-times[:-1]) == span).all():
        raise ValueError(f'{label} candles must be complete and gap-free')
    if (times+span > observed).any():
        raise ValueError(f'{label} contains a future or incomplete candle')
    out['timestamp'] = times
    return out


def emit_paper_signal(frame, frozen_spec, context=None, observed_at=None):
    """Compute desired paper direction from completed data; never execute it.

    Reject future/incomplete target OR contextual candles rather than silently
    discarding them. Source timestamps are bar opens. The earliest information
    availability is the completed signal bar's close; there is no fill price.
    """
    verify_freeze(frozen_spec)
    spec = frozen_spec['strategy']
    observed = pd.Timestamp.now(tz='UTC') if observed_at is None else _utc(observed_at, 'Observed time')
    span = TIMEFRAMES[spec['timeframe']]
    if frame.attrs.get('timeframe', spec['timeframe']) != spec['timeframe']:
        raise ValueError('Input candle timeframe differs from frozen specification')
    target = _completed_frame(frame, span, observed, 'Signal data')
    target.attrs.update(frame.attrs)
    target.attrs['timeframe'] = spec['timeframe']
    completed_context = {}
    for symbol, source in (context or {}).items():
        label = source.attrs.get('timeframe')
        if label:
            if label not in TIMEFRAMES:
                raise ValueError('Unsupported context timeframe')
            source_span = TIMEFRAMES[label]
        elif len(source) > 1:
            source_span = pd.Timestamp(source.timestamp.iloc[1])-pd.Timestamp(source.timestamp.iloc[0])
        else:
            source_span = span
        completed_context[symbol] = _completed_frame(source, source_span, observed, f'{symbol} context')
        completed_context[symbol].attrs.update(source.attrs)
    # Recompute features with frozen code. Never trust caller-supplied signal,
    # ATR, regime, normalization, or higher-timeframe feature columns.
    raw_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'ticker',
                   'funding_rate', 'settled_funding']
    target = target[[name for name in raw_columns if name in target]].copy()
    target.attrs['timeframe'] = spec['timeframe']
    output = build_signal(target, spec, completed_context or None)
    signal = output.signal.iloc[-1]
    if pd.isna(signal) or int(signal) not in [-1, 0, 1]:
        raise ValueError('Frozen signal did not produce a valid paper direction')
    direction = int(signal)
    opened = pd.Timestamp(output.timestamp.iloc[-1])
    return dict(mode='paper_only', execution_enabled=False, action={-1: 'paper_short', 0: 'paper_flat', 1: 'paper_long'}[direction],
                desired_paper_direction=direction, strategy_id=spec['id'],
                signal_bar_open=opened.isoformat(), available_at=(opened+span).isoformat(),
                observed_at=observed.isoformat(), freeze_sha256=frozen_spec['freeze_sha256'],
                evidence='Desired paper exposure only; no orders, fills or performance claims')


def _read_bars(path, timeframe=None):
    path = Path(path)
    if path.suffix == '.parquet':
        frame = pd.read_parquet(path)
    elif path.suffix == '.csv':
        frame = pd.read_csv(path)
    else:
        raise ValueError('Paper input must be local CSV or Parquet')
    frame['timestamp'] = pd.to_datetime(frame.timestamp, utc=True)
    if timeframe:
        frame.attrs['timeframe'] = timeframe
    return frame


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--bars', type=Path, required=True)
    parser.add_argument('--context', type=Path, help='Local JSON map of BTC/ETH/BNB to CSV/Parquet paths')
    parser.add_argument('--asof', required=True, help='Explicit UTC-aware observation time')
    parser.add_argument('--root', type=Path, default=ROOT, help='Research directory holding frozen code/manifests')
    parser.add_argument('--output', choices=['stdout', 'paper_signals.jsonl'], default='stdout')
    args = parser.parse_args(argv)
    config = load_frozen_config(args.config, args.root)
    frame = _read_bars(args.bars, config['strategy']['timeframe'])
    context = None
    if args.context:
        paths = json.loads(args.context.read_text(encoding='utf-8'))
        context = {symbol: _read_bars(args.context.parent/path) for symbol, path in paths.items()}
    signal = emit_paper_signal(frame, config, context, args.asof)
    text = json.dumps(signal, sort_keys=True, allow_nan=False)
    if args.output == 'stdout':
        print(text)
    else:
        # Local append only. No service, scheduled task or external transport.
        with (args.config.parent/'paper_signals.jsonl').open('a', encoding='utf-8') as handle:
            handle.write(text+'\n')
    return signal


if __name__ == '__main__':
    main()
