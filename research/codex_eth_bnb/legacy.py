"""Untouched historical baselines under their ORIGINAL, separate cost model."""
from __future__ import annotations

from dataclasses import asdict
import json
import pandas as pd

from .data_pipeline import HERE, SOURCE, sha


def run():
    from backtesting.alternative_strategies import simulate as eth_simulate
    from backtesting.crypto_research.lab import evaluate, geometry
    from backtesting.numbered_profiles import load_profile
    from backtesting.regime_filters import RegimeFilter, prepare_features, apply_filter

    split = json.loads((HERE/'split_manifest.json').read_text())
    manifest = json.loads((HERE/'data_manifest.json').read_text())
    begin, end = pd.Timestamp(split['validation_eval_start']), pd.Timestamp(split['validation'][1])
    rule, cfg, meta, _ = load_profile(version='v1.11')
    rows = []
    for symbol in ['ETH', 'BNB']:
        chunks = []
        for source in manifest['assets'][symbol]['inputs']:
            if sha(source['path']) != source['sha256']:
                raise ValueError('External baseline input changed')
            raw = pd.read_parquet(source['path'])
            chunks.append(raw[(raw.timestamp >= pd.Timestamp(split['train'][0])) & (raw.timestamp < end)])
        bars = pd.concat(chunks, ignore_index=True).sort_values('timestamp').reset_index(drop=True)
        if symbol == 'ETH':
            features = apply_filter(prepare_features(bars, rule), RegimeFilter(**meta['entry_filters']))
            active_rule, name = rule, 'ETH v1.11 untouched'
        else:
            payload = json.loads((SOURCE/'backtesting/candidates/crypto_v0_1/config.json').read_text())
            builder, active_rule = geometry(payload['candidate'], rule, meta)
            features = builder(bars)
            name = 'BNB crypto_v0_1 untouched'
        mask = (bars.timestamp >= begin) & (bars.timestamp+pd.Timedelta('5min') <= end)
        b, f = bars.loc[mask].reset_index(drop=True), features.loc[mask].reset_index(drop=True)
        if symbol == 'ETH':
            metrics, trades, events = eth_simulate(b, active_rule, cfg, signals=f)
        else:
            outcome, trades, events = evaluate(symbol, b, f, active_rule, cfg, sizing=8.)
            metrics = outcome['metrics']
        folder = HERE/'outputs/legacy'/symbol
        folder.mkdir(parents=True, exist_ok=True)
        trades.to_parquet(folder/'trades.parquet', index=False)
        events.to_parquet(folder/'events.parquet', index=False)
        rows.append(dict(symbol=symbol, name=name, phase='VALIDATION', start=str(begin), end=str(end), metrics=metrics,
                         rule=asdict(active_rule), execution=asdict(cfg),
                         caveat='Original Breakout research model: fixed $100 risk, up to5x, 4bp fees, financing3.3bp/day both sides; not comparable exchange-funding economics. No model edits.'))
    from .runner import write
    write(HERE/'legacy_comparisons.json', rows)
    return rows
