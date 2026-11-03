"""Post-selection v1.3 robustness checks; never select or change parameters."""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path

import pandas as pd

from .alternative_strategies import SignalRule, prepare_signals, simulate
from .config import StrategyConfig
from .exit_research import freeze
from .market_data import clean_candles, load_history, utc
from .optimize import append, pnl, resume_rows, subset, write_json
from .paths import PARQUET, ROOT


def audit(directory: Path):
    source = json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    for name, digest in source['source_hashes'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Frozen experiment source changed: {name}')
    for name, digest in source['data_hashes'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Frozen experiment data changed: {name}')
    selection_path = directory/'selection.json'
    selection = json.loads(selection_path.read_text(encoding='utf-8'))
    rule = SignalRule(**selection['candidate']['rule'])
    cfg = StrategyConfig(**selection['execution_config'])
    output = directory/'robustness'
    output.mkdir(exist_ok=True)
    plan = dict(selection_sha256=hashlib.sha256(selection_path.read_bytes()).hexdigest(),
                audit_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                slippage_bps=[2., 4., 8.], windows=[['2025-01-01', '2026-01-01'], ['2026-01-01', '2026-10-28']],
                neighbors={'lookback': [64, 96], 'stop_atr': [1.6, 2.4], 'trail_atr': [2.4, 3.6]},
                neighborhood_window=['2020-01-01', '2026-01-01'],
                policy='Diagnostics only, on reused history. No rule selection or profile overwrite. Closed-leg concentration omits marked open P&L and is not a strategy replay.')
    freeze(output/'manifest.json', plan)
    earlier, _ = load_history(ROOT/'data/ethusd/perpetual_2020_2022/candles.parquet')
    recent, _ = load_history(PARQUET)
    bars, quality = clean_candles(pd.concat([earlier, recent[recent.timestamp < utc('2026-10-28')]], ignore_index=True))
    if quality['missing_bars']:
        raise ValueError('Audit requires complete candles')
    features = prepare_signals(bars, rule)
    rows = resume_rows(output/'checks.jsonl')
    done = {row['label'] for row in rows}

    def evaluate(label, window, variant, config, signals):
        if label in done:
            return
        b, f = subset(bars, signals, *window)
        metrics, trades, _ = simulate(b, variant, config, signals=f)
        net = trades.net_pnl if len(trades) else pd.Series(dtype=float)
        concentration = dict(closed_net_pnl=float(net.sum()), largest_three_winners=float(net.clip(lower=0).nlargest(3).sum()),
                             closed_net_without_three_largest_winners=float(net.sum()-net.clip(lower=0).nlargest(3).sum()))
        row = dict(label=label, window=window, rule=asdict(variant), config=asdict(config), metrics=metrics,
                   closed_leg_concentration=concentration)
        rows.append(row)
        append(output/'checks.jsonl', row)
        trades.to_csv(output/f'{label}_trades.csv', index=False)
        print(f"ROBUSTNESS {label}: ${pnl(metrics):.2f}", flush=True)

    for window in plan['windows']:
        for bps in plan['slippage_bps']:
            evaluate(f'{window[0][:4]}_slip{bps}', window, rule, replace(cfg, slippage_bps=bps), features)
    evaluate('development_selected', plan['neighborhood_window'], rule, cfg, features)
    for field, values in plan['neighbors'].items():
        for value in values:
            variant = replace(rule, **{field: value})
            other_features = prepare_signals(bars, variant)
            evaluate(f'development_{field}{value}', plan['neighborhood_window'], variant, cfg, other_features)
    write_json(output/'summary.json', dict(checks=rows, selected_rule_unchanged=asdict(rule), all_history_reused=True))
    lines = ['# v1.3 post-selection robustness', '', plan['policy'], '',
             '| Check | Net P&L | Entries | Running-peak drawdown | Closed net without three largest winners |',
             '| --- | ---: | ---: | ---: | ---: |']
    for row in rows:
        m, c = row['metrics'], row['closed_leg_concentration']
        lines.append(f"| {row['label']} | ${pnl(m):,.2f} | {m['entries']} | {m['max_intrabar_drawdown']:.2%} | ${c['closed_net_without_three_largest_winners']:,.2f} |")
    lines.extend(['', 'The 2026 audit is already inspected. Neighborhood checks use development history only and cannot replace the frozen rule. A negative 2026 result remains a material failure even if training neighborhoods and 2025 slippage tests are positive. Removing winners is diagnostic subtraction, not a simulated deployable strategy. No future paper observations, actual Breakout fills or TradingView export reconciliation are included.', ''])
    text = '\n'.join(lines)
    (output/'report.md').write_text(text, encoding='utf-8')
    (ROOT/'reports/v1_3_robustness.md').write_text(text, encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    audit(parser.parse_args().directory)
