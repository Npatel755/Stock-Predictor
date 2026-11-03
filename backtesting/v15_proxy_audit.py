"""Freeze v1.5 before adding older ETH spot data as a separate proxy test."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json

import pandas as pd

from .alternative_strategies import SignalRule, simulate
from .config import StrategyConfig
from .exit_research import freeze
from .market_data import BAR
from .optimize import pnl, write_json
from .paths import ROOT
from .regime_filters import RegimeFilter, apply_filter, prepare_features
from .spot_proxy_data import SOURCE, fetch, validate_proxy


def run(args):
    args.output.mkdir(parents=True, exist_ok=True)
    selected_path = ROOT/'artifacts/optimization/round8_volume_geometry/selection.json'
    selection = json.loads(selected_path.read_text(encoding='utf-8'))
    parent_path = ROOT/'configs/eth_strategy_v1_4.json'
    parent = json.loads(parent_path.read_text(encoding='utf-8'))
    scenarios = dict(v1_4=dict(**parent, filters=asdict(RegimeFilter())),
                     v1_5=dict(rule=selection['candidate']['rule'], execution=selection['execution_config'], filters=selection['candidate']['filters']))
    plan = dict(name='Frozen v1.5 earlier ETH spot-proxy audit', source=SOURCE, start='2018-01-01', end_exclusive='2020-01-01',
                scenarios=scenarios, baseline_net_usd=6000., before_data_fetch=True, parameter_selection_permitted=False,
                source_hashes={name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
                               ['v15_proxy_audit.py', 'spot_proxy_data.py', 'alternative_strategies.py', 'engine.py', 'config.py', 'indicators.py', 'regime_filters.py', 'optimize.py', 'exit_research.py']},
                selection_sha256=hashlib.sha256(selected_path.read_bytes()).hexdigest(),
                missing_data_policy='Split at actual gaps into independent accounts; features and warm-up restart in each segment. Reject segments shorter than 2400 five-minute bars. No invented bars, no ticker substitution.',
                warning='Different market/feed: ETHUSDT spot. This tests transfer of frozen signals under an explicitly hypothetical leveraged execution-cost scenario, not observed spot/futures/Breakout fills. No tuning to the new data. 2018-2019 is an earlier-regime test, not prospective validation.')
    freeze(args.output/'manifest.json', plan)
    frame, metadata = fetch(plan['start'], plan['end_exclusive'], ROOT/'data/ethusd/v1_5_spot_2018_2019')
    results, skipped = [], []
    for year, annual in frame.groupby(frame.timestamp.dt.year):
        groups = annual.timestamp.diff().ne(BAR).cumsum()
        for index, part in annual.groupby(groups):
            part = part.reset_index(drop=True)
            if len(part) < 2400:
                skipped.append(dict(year=int(year), start=str(part.timestamp.min()), end=str(part.available_at.max()), rows=len(part)))
                continue
            for name, profile in scenarios.items():
                rule, cfg, settings = SignalRule(**profile['rule']), StrategyConfig(**profile['execution']), RegimeFilter(**profile['filters'])
                signals = apply_filter(prepare_features(part, rule), settings)
                metrics, trades, _ = simulate(part, rule, cfg, signals=signals, validator=validate_proxy)
                label = f'{year}_segment{index}_{name}'
                trades.to_csv(args.output/f'{label}_trades.csv', index=False)
                row = dict(year=int(year), segment=int(index), start=str(part.timestamp.min()), end=str(part.available_at.max()), rows=len(part), scenario=name, metrics=metrics)
                results.append(row)
                write_json(args.output/'checkpoint.json', dict(results=results, skipped=skipped, metadata=metadata))
                print(f'PROXY AUDIT {label}: net=${pnl(metrics):.2f} entries={metrics["entries"]}', flush=True)
    aggregates = {}
    for name in scenarios:
        metrics = [row['metrics'] for row in results if row['scenario'] == name]
        aggregates[name] = dict(sum_independent_account_pnl=sum(pnl(m) for m in metrics), entries=sum(m['entries'] for m in metrics),
                                eligible_segments=len(metrics), max_segment_intrabar_drawdown=max((m['max_intrabar_drawdown'] for m in metrics), default=None))
    write_json(args.output/'summary.json', dict(plan=plan, metadata=metadata, results=results, skipped_segments=skipped,
                                               aggregates=aggregates, selection_unchanged=True, is_native_perpetual=False))
    lines = ['# ETH v1.5 additional 2018-2019 spot-proxy test', '', plan['warning'], '',
             f"Fetched **{len(frame):,}** checksum-verified five-minute ETHUSDT **spot** bars. Instrument labels remain `BINANCE:ETHUSDT`; none were relabeled as perpetual futures. {metadata['quality']['missing_bars']} missing intervals were not fabricated. Excluded off-grid source records: {sum(a['excluded_off_grid_rows'] for a in metadata['archives'])}; original ZIPs remain intact and no timestamps were shifted.", '',
             plan['missing_data_policy'], '', '| Frozen strategy | Sum of independent segment-account net P&L | Entries | Eligible segments | Worst segment intrabar drawdown |', '| --- | ---: | ---: | ---: | ---: |']
    for name, m in aggregates.items():
        dd = f"{m['max_segment_intrabar_drawdown']:.2%}" if m['max_segment_intrabar_drawdown'] is not None else 'N/A'
        lines.append(f"| {name} | ${m['sum_independent_account_pnl']:,.2f} | {m['entries']} | {m['eligible_segments']} | {dd} |")
    lines.extend(['', '**The segment sums are not a continuous account return.** Annual/gap boundaries start a new $50,000 account and reset indicator warm-up. Open positions stay marked at each endpoint. Hypothetical futures-style fees, leverage, slippage and financing are held fixed for comparison; they are not actual spot funding or Breakout execution.', '',
                  '| Year / segment | Strategy | Rows | Net P&L | Entries |', '| --- | --- | ---: | ---: | ---: |'])
    for row in results:
        lines.append(f"| {row['year']} / {row['segment']} | {row['scenario']} | {row['rows']} | ${pnl(row['metrics']):,.2f} | {row['metrics']['entries']} |")
    lines.extend(['', f"Skipped short segments: {len(skipped)}. All raw archive hashes, exact coverage, omitted segment sizes and ledgers are saved with the audit. These new rows are kept separate from the original Binance perpetual comparison. The $6,000 baseline is still judged only on the original 2023-2026 perpetual dates.", '',
                  'The candidate was frozen before fetching this data. Results cannot reselect its parameters in this audit. Cross-market transfer success or failure does not erase historical selection bias, certify funded-account compliance or establish future profitability. No orders or profile changes occurred.', ''])
    report = '\n'.join(lines)
    (args.output/'report.md').write_text(report, encoding='utf-8')
    (ROOT/'reports/v1_5_spot_proxy.md').write_text(report, encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=type(ROOT), default=ROOT/'artifacts/optimization/v1_5_spot_proxy')
    run(parser.parse_args())
