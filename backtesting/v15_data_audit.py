"""Freeze ETH v1.5 before requesting additional native perpetual data.

New data never selects parameters in this audit. Missing archives and losing
results remain in the record. Existing training data/profile files are intact.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import pandas as pd
import requests

from .alternative_strategies import SignalRule, simulate
from .config import StrategyConfig
from .exit_research import freeze
from .market_data import BAR, clean_candles, load_history, read_archive, utc
from .optimize import pnl, subset, write_json
from .paths import ROOT, PARQUET
from .regime_filters import RegimeFilter, apply_filter, prepare_features


def run(args):
    args.output.mkdir(parents=True, exist_ok=True)
    snapshot = args.output/'frozen_selection.json'
    if not snapshot.exists():
        snapshot.write_bytes(args.selection.read_bytes())
    chosen = json.loads(snapshot.read_text(encoding='utf-8'))
    parent_path = ROOT/'configs/eth_strategy_v1_4.json'
    parent = json.loads(parent_path.read_text(encoding='utf-8'))
    scenarios = {'v1_4': dict(rule=parent['rule'], execution=parent['execution'], filters=asdict(RegimeFilter())),
                 'v1_5': dict(rule=chosen['candidate']['rule'], execution=chosen['execution_config'], filters=chosen['candidate']['filters'])}
    plan = dict(name='Frozen ETH v1.5 additional-data audit', baseline_net_usd=6000.,
                baseline_period=['2023-01-01', '2026-10-28'], risk_usd=100., scenarios=scenarios,
                selection_sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest(),
                parent_sha256=hashlib.sha256(parent_path.read_bytes()).hexdigest(),
                source_hashes={name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
                               ['v15_data_audit.py', 'alternative_strategies.py', 'regime_filters.py', 'engine.py', 'market_data.py', 'config.py', 'indicators.py', 'optimize.py', 'exit_research.py']},
                fetch_early_months=['2019-11', '2019-12'], fetch_recent_days=[f'2026-10-{day}' for day in range(28, 32)]+['2026-11-01', '2026-11-02'],
                source='Binance official ETHUSDT USD-M perpetual archives with SHA256 checksum verification',
                before_fetch=True,
                warning='Rules are frozen before new archive requests. 2019 is earlier-regime retrospective evidence; new late-2026 data is a short chronological extension, not enough for reliable inference. Newly fetched rows already in the old dataset do not count as new information. Missing candles are never fabricated. No parameter selection, account execution or saved-profile overwrite.')
    freeze(args.output/'manifest.json', plan)
    data_dir = ROOT/'data/ethusd/v1_5_additional'
    data_dir.mkdir(parents=True, exist_ok=True)
    fetched, availability = {'early': [], 'recent': []}, []
    with requests.Session() as session:
        for bucket, frequency, periods in [('early', 'monthly', plan['fetch_early_months']), ('recent', 'daily', plan['fetch_recent_days'])]:
            for period in periods:
                frame = read_archive(session, period, frequency, data_dir)
                availability.append(dict(period=period, frequency=frequency, available=frame is not None, rows=len(frame) if frame is not None else 0))
                if frame is not None:
                    fetched[bucket].append(frame)
                write_json(args.output/'archive_availability.json', availability)
                print(f"DATA {frequency} {period}: {len(frame) if frame is not None else 'unavailable'}", flush=True)
    original, _ = load_history(PARQUET)
    outcomes, qualities = {}, {}
    for bucket, chunks in fetched.items():
        if not chunks:
            outcomes[bucket] = dict(status='unavailable', note='No requested archives available; no synthetic backfill')
            continue
        raw = pd.concat(chunks, ignore_index=True)
        frame, quality = clean_candles(raw)
        qualities[bucket] = quality
        overlap = frame.timestamp.isin(original.timestamp)
        fresh_count = int((~overlap).sum())
        path = data_dir/f'{bucket}.parquet'
        frame.to_parquet(path, index=False)
        record = dict(rows=len(frame), unseen_timestamps=fresh_count, already_present_timestamps=int(overlap.sum()),
                      first=str(frame.timestamp.min()), end_exclusive=str(frame.available_at.max()),
                      gaps=quality['gaps'], data_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        if bucket == 'recent':
            # Request the whole extension, including boundaries, so absent
            # first/last days cannot disappear from the quality report.
            frame, quality = clean_candles(frame, '2026-10-28', '2026-11-03')
            qualities[bucket] = quality
            record['requested_missing_bars'] = quality['missing_bars']
            record['gaps'] = quality['gaps']
        if quality['missing_bars'] or len(frame) < 2000:
            record.update(status='rejected_for_replay', note='Requires complete candles and enough hourly warm-up. Coverage/availability preserved without invented data.')
            outcomes[bucket] = record
            continue
        # For a recent extension, keep pre-boundary signal/ATR history while
        # starting accounts flat exactly at the extension boundary.
        if bucket == 'recent':
            warmup = original[(original.timestamp >= utc('2026-09-01')) & (original.timestamp < utc('2026-10-28'))]
            combined, complete = clean_candles(pd.concat([warmup, frame], ignore_index=True))
            if complete['missing_bars']:
                record.update(status='rejected_for_replay', note='Gap between warm-up and new extension')
                outcomes[bucket] = record
                continue
        else:
            combined = frame
        results = {}
        for name, profile in scenarios.items():
            rule, cfg, filters = SignalRule(**profile['rule']), StrategyConfig(**profile['execution']), RegimeFilter(**profile['filters'])
            features = apply_filter(prepare_features(combined, rule), filters)
            b, f = subset(combined, features, str(frame.timestamp.min()), str(frame.available_at.max()))
            metrics, trades, _ = simulate(b, rule, cfg, signals=f)
            directory = args.output/bucket/name
            directory.mkdir(parents=True, exist_ok=True)
            trades.to_csv(directory/'trades.csv', index=False)
            write_json(directory/'metrics.json', metrics)
            results[name] = metrics
            print(f"NEW-DATA {bucket} {name}: net=${pnl(metrics):.2f} entries={metrics['entries']}", flush=True)
        record.update(status='replayed_frozen_rules', results=results)
        outcomes[bucket] = record
    write_json(args.output/'summary.json', dict(plan=plan, archive_availability=availability, outcomes=outcomes, quality=qualities, selection_unchanged=True))
    lines = ['# ETH v1.5 additional native-perpetual data', '', plan['warning'], '',
             'Rules and comparators were frozen before archive requests. The baseline remains $6,000 on the original comparison dates; new dates cannot be added to inflate that benchmark.', '',
             '| Requested archive | Frequency | Available | Rows |', '| --- | --- | --- | ---: |']
    for row in availability:
        lines.append(f"| {row['period']} | {row['frequency']} | {row['available']} | {row['rows']} |")
    for bucket, record in outcomes.items():
        lines.extend(['', f'## {bucket}', '', f"Status: **{record['status']}**."])
        if 'rows' in record:
            lines.append(f"Coverage: {record['first']} to {record['end_exclusive']} exclusive; {record['rows']:,} rows, {record['unseen_timestamps']:,} timestamps absent from the previous main dataset.")
        if record.get('note'):
            lines.append(record['note'])
        if record.get('gaps'):
            lines.append(f"Unavailable periods: `{json.dumps(record['gaps'])}`.")
        if 'results' in record:
            lines.extend(['', '| Frozen strategy | Net P&L | Entries | Intrabar drawdown |', '| --- | ---: | ---: | ---: |'])
            for name, m in record['results'].items():
                lines.append(f"| {name} | ${pnl(m):,.2f} | {m['entries']} | {m['max_intrabar_drawdown']:.2%} |")
    lines.extend(['', 'There is no guarantee that native history extends before the exchange listed the contract. Additional spot or other-venue ETH data must be labeled separately and must not masquerade as Binance perpetual or Breakout execution. Extra historical data does not erase the selection bias from tuning the existing years. The old datasets and all saved numbered versions remain unchanged.', ''])
    report = '\n'.join(lines)
    (args.output/'report.md').write_text(report, encoding='utf-8')
    (ROOT/'reports/v1_5_additional_data.md').write_text(report, encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection', type=Path, default=ROOT/'artifacts/optimization/round8_volume_geometry/selection.json')
    parser.add_argument('--output', type=Path, default=ROOT/'artifacts/optimization/v1_5_additional_data')
    run(parser.parse_args())
