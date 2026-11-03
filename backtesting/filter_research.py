"""Fixed-risk entry-filter research after the saved ETH v1.4.

All periods have been inspected. 2026 participates in selection; no result
here is independent validation. This module never changes saved profiles.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import random

from .alternative_strategies import SignalRule, simulate
from .config import StrategyConfig
from .exit_research import freeze
from .market_data import load_history, utc
from .optimize import append, pnl, resume_rows, subset, write_json
from .paths import PARQUET, ROOT
from .regime_filters import RegimeFilter, apply_filter, prepare_features


def candidates(count=48, seed=1407):
    rows, seen = [], set()

    def add(label, settings):
        key = json.dumps(asdict(settings), sort_keys=True)
        if key not in seen:
            seen.add(key)
            rows.append(dict(id=len(rows), label=label, filters=asdict(settings)))

    add('unchanged_v1_4', RegimeFilter())
    for direction in ['long', 'short']:
        add(f'direction_{direction}', RegimeFilter(direction=direction))
    add('weekdays', RegimeFilter(weekends=False))
    for key, values in {'min_trend_gap_bps': [25., 50., 100., 200.], 'min_atr_bps': [20., 40., 60., 80.],
                        'max_atr_bps': [80., 120., 160.], 'min_signed_slope_bps': [0., 2.5, 5., 10.],
                        'min_rvol': [.8, 1.2, 1.5]}.items():
        for value in values:
            add(f'{key}_{value}', RegimeFilter(**{key: value}))
    rng = random.Random(seed)
    while len(rows) < count:
        proposal = RegimeFilter(direction=rng.choice(['both', 'both', 'long', 'short']),
                               min_atr_bps=rng.choice([0., 20., 40., 60.]), max_atr_bps=rng.choice([0., 120., 160.]),
                               min_trend_gap_bps=rng.choice([0., 50., 100.]), min_signed_slope_bps=rng.choice([None, 0., 5.]),
                               min_rvol=rng.choice([0., .8, 1.2]), weekends=rng.choice([True, True, False]))
        add(f'combined_{len(rows)}', proposal)
    return rows[:count]


def eligible(metrics, checks, parent, parent_stress):
    return (pnl(metrics) > pnl(parent) and metrics['entries'] >= 100
            and metrics['max_intrabar_drawdown'] <= parent['max_intrabar_drawdown']
            and metrics['margin_call_events'] == 0
            and all(pnl(checks[k]) > 0 for k in ['2025_h1', '2025_h2', '2026_selection', 'earlier_2020_2022'])
            and min(checks[k]['entries'] for k in ['2025_h1', '2025_h2']) >= 6
            and pnl(checks['full_4bp']) > pnl(parent_stress)
            and all(m['margin_call_events'] == 0 for m in checks.values()))


def run(args):
    from .generalization_policy import assert_search_allowed
    assert_search_allowed(ROOT)
    args.output.mkdir(parents=True, exist_ok=True)
    snapshot = args.output/'parent_v1_4.json'
    if not snapshot.exists():
        snapshot.write_bytes((ROOT/'configs/eth_strategy_v1_4.json').read_bytes())
    parent = json.loads(snapshot.read_text(encoding='utf-8'))
    rule, cfg = SignalRule(**parent['rule']), StrategyConfig(**parent['execution'])
    universe = candidates()
    earlier_path = ROOT/'data/ethusd/perpetual_2020_2022/candles.parquet'
    protected = [ROOT/'configs/eth_strategy_v1_4.json', ROOT/'configs/eth_strategy_v1_4.metadata.json', ROOT/'reference/ETH_Strategy_v1_4.pine']
    plan = dict(name='ETH v1.4 causal entry-filter research', candidate_count=len(universe), candidates=universe,
                rule=asdict(rule), execution=asdict(cfg), historical_profit_selection=True, prior_search_slots=572,
                selection_window=['2023-01-01', '2026-10-28'], shortlist=6, seed=1407,
                source_hashes={name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
                               ['filter_research.py', 'regime_filters.py', 'alternative_strategies.py', 'engine.py', 'config.py', 'indicators.py', 'market_data.py', 'optimize.py', 'exit_research.py']},
                data_hashes={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [PARQUET, earlier_path]},
                saved_profile_hashes={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected},
                gate='Net above saved v1.4 at identical dates/risk/costs; >=100 entries; drawdown <= parent; positive 2025 halves, 2026 selection account and earlier 2020-2022 aggregate; >=6 trades per 2025 half; higher 4bp net than parent at 4bp; no margin calls.',
                decision='Rank full historical net profit; shortlist with exposure/risk eligibility; choose highest net passing fixed checks. If none passes, retain best diagnostic candidate with failed-gate status, never export/promote it as an improvement.',
                warning='All years were inspected/reused. 2026 participates in selection. Filters do not create an untouched holdout or future performance evidence. No risk, capital, fee or fill assumption changes; no saved profile overwrites.')
    freeze(args.output/'manifest.json', plan)
    bars, _ = load_history(PARQUET)
    bars = bars[(bars.timestamp >= utc(plan['selection_window'][0])) & (bars.timestamp < utc(plan['selection_window'][1]))].reset_index(drop=True)
    features = prepare_features(bars, rule)
    benchmark_path = args.output/'benchmark.json'
    if benchmark_path.exists():
        benchmark = json.loads(benchmark_path.read_text(encoding='utf-8'))
    else:
        neutral = apply_filter(features, RegimeFilter())
        benchmark = dict(main=simulate(bars, rule, cfg, signals=neutral)[0], stress4=simulate(bars, rule, replace(cfg, slippage_bps=4.), signals=neutral)[0])
        write_json(benchmark_path, benchmark)
    training = resume_rows(args.output/'training.jsonl')
    done = {row['id'] for row in training}
    for candidate in universe:
        if candidate['id'] in done:
            continue
        filtered = apply_filter(features, RegimeFilter(**candidate['filters']))
        metrics = simulate(bars, rule, cfg, signals=filtered)[0]
        row = dict(id=candidate['id'], label=candidate['label'], metrics=metrics, score=pnl(metrics))
        training.append(row)
        append(args.output/'training.jsonl', row)
        print(f"FILTER {len(training)}/{len(universe)} {candidate['label']} net=${pnl(metrics):.2f} entries={metrics['entries']} DD={metrics['max_intrabar_drawdown']:.2%}", flush=True)
    ranked = sorted(training, key=lambda r: (-r['score'], r['id']))
    ids = [r['id'] for r in ranked if r['id'] and r['metrics']['entries'] >= 100 and r['metrics']['margin_call_events'] == 0
           and r['metrics']['max_intrabar_drawdown'] <= benchmark['main']['max_intrabar_drawdown']][:plan['shortlist']]
    write_json(args.output/'shortlist.json', dict(candidate_ids=ids, selection_uses='Inspected full-period net and drawdown'))
    earlier, _ = load_history(earlier_path)
    earlier_features = prepare_features(earlier, rule)
    validation = resume_rows(args.output/'validation.jsonl')
    done = {row['id'] for row in validation}
    by_id = {r['id']: r for r in training}
    for candidate_id in ids:
        if candidate_id in done:
            continue
        settings = RegimeFilter(**universe[candidate_id]['filters'])
        filtered = apply_filter(features, settings)
        checks = {}
        for name, start, end in [('2025_h1', '2025-01-01', '2025-07-01'), ('2025_h2', '2025-07-01', '2026-01-01'),
                                 ('2026_selection', '2026-01-01', '2026-10-28')]:
            b, f = subset(bars, filtered, start, end)
            checks[name] = simulate(b, rule, cfg, signals=f)[0]
        checks['earlier_2020_2022'] = simulate(earlier, rule, cfg, signals=apply_filter(earlier_features, settings))[0]
        checks['full_4bp'] = simulate(bars, rule, replace(cfg, slippage_bps=4.), signals=filtered)[0]
        passed = eligible(by_id[candidate_id]['metrics'], checks, benchmark['main'], benchmark['stress4'])
        row = dict(id=candidate_id, label=universe[candidate_id]['label'], checks=checks, passed_historical_gate=passed, score=by_id[candidate_id]['score'])
        validation.append(row)
        append(args.output/'validation.jsonl', row)
        print(f"FILTER CHECK {row['label']} gate={passed} 2026=${pnl(checks['2026_selection']):.2f} old=${pnl(checks['earlier_2020_2022']):.2f} stressed=${pnl(checks['full_4bp']):.2f}", flush=True)
    passed = [r for r in validation if r['passed_historical_gate']]
    if not validation:
        raise ValueError('No changed candidate meets even the exposure/drawdown screen; checkpoints retained')
    winner = max(passed or validation, key=lambda r: (r['score'], -r['id']))
    candidate = dict(**universe[winner['id']], rule=asdict(rule))
    selection = dict(candidate=candidate, execution_config=asdict(cfg), validation=winner, passed_predeclared_validation_gate=bool(passed),
                     selection_is_historical_profit_optimization=True, independent_validation=False, ready_for_funded_trading=False)
    freeze(args.output/'selection.json', selection)
    filtered = apply_filter(features, RegimeFilter(**candidate['filters']))
    metrics, trades, events = simulate(bars, rule, cfg, signals=filtered)
    trades.to_csv(args.output/'selected_trades.csv', index=False)
    events.to_csv(args.output/'selected_events.csv', index=False)
    write_json(args.output/'summary.json', dict(selection=selection, benchmark=benchmark, evaluation=dict(full_period=metrics, **winner['checks']), saved_v1_4_unchanged=True))
    rows = []
    for row in ranked:
        checked = next((v for v in validation if v['id'] == row['id']), None)
        rows.append(dict(id=row['id'], label=row['label'], net_pnl=row['score'], entries=row['metrics']['entries'], drawdown=row['metrics']['max_intrabar_drawdown'], historical_gate=checked['passed_historical_gate'] if checked else None))
    import pandas as pd
    pd.DataFrame(rows).to_csv(args.output/'leaderboard.csv', index=False)
    lines = ['# Entry-filter research after ETH v1.4', '', plan['warning'], '',
             f"Screened {len(universe)} fixed filter configurations. Selected diagnostic: **{candidate['label']}**. Historical improvement gate passed: **{bool(passed)}**.", '',
             '| Full 2023-01-01 to 2026-10-28 exclusive | Net P&L | Entries | Intrabar drawdown |', '| --- | ---: | ---: | ---: |']
    for name, m in [('Saved v1.4', benchmark['main']), ('Filtered candidate', metrics), ('Saved v1.4 at 4bp', benchmark['stress4']), ('Filtered at 4bp', winner['checks']['full_4bp'])]:
        lines.append(f"| {name} | ${pnl(m):,.2f} | {m['entries']} | {m['max_intrabar_drawdown']:.2%} |")
    lines.extend(['', f"Selected filter settings: `{json.dumps(candidate['filters'], sort_keys=True)}`.", '',
                  '| Reused-data check, independently reset accounts | Net P&L |', '| --- | ---: |'])
    for name, m in winner['checks'].items():
        if name != 'full_4bp':
            lines.append(f'| {name} | ${pnl(m):,.2f} |')
    lines.extend(['', 'Entry filters use only completed-hour ATR, signed close-to-EMA distance, signed six-hour EMA slope, prior-20-hour relative volume and UTC day/direction. Neutral-filter replay was regression-tested against the original simulator. Entries can differ after a rejected setup because flat-position availability changes; this is a full broker replay, not deletion of losing ledger rows.', '',
                  'The saved v1.4 profile is unchanged. A generic exporter explicitly rejects filtered candidates so that no filtered backtest can silently become an unfiltered Pine strategy. A passed historical gate would still require a filter-aware export, reconciliation and future observations before any deployment claim. Earlier/half-year checks reset accounts; fold sums are not continuous account performance. No live orders occur.', ''])
    text = '\n'.join(lines)
    (args.output/'report.md').write_text(text, encoding='utf-8')
    (ROOT/'reports/v1_4_entry_filters.md').write_text(text, encoding='utf-8')
    for name, digest in plan['saved_profile_hashes'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != digest:
            raise ValueError('Saved v1.4 changed during this experiment')
    print(f"FILTER FINISHED net=${pnl(metrics):.2f} improvement=${pnl(metrics)-pnl(benchmark['main']):.2f} gate={bool(passed)}", flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'artifacts/optimization/round7_v1_4_entry_filters')
    run(parser.parse_args())
