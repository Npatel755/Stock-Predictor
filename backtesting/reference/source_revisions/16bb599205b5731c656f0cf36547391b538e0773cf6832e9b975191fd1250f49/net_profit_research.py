"""Explicit historical-profit search requested after v1.3 trailed v1.2.

The inspected 2026 period is now part of selection. Never call these results
independent validation or an untouched audit. Keep costs and dollar risk fixed.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
from itertools import product
import json
from pathlib import Path
import random

import pandas as pd

from .alternative_strategies import SignalRule, prepare_signals, simulate
from .config import StrategyConfig
from .engine import backtest
from .exit_research import freeze
from .market_data import load_history, utc
from .optimize import append, baseline, pnl, resume_rows, subset, write_json
from .paths import PARQUET, ROOT


def candidates(count=64, seed=1305):
    if count < 4 or count > 1200:
        raise ValueError('Candidate count must be between 4 and 1200')
    rules = [SignalRule('channel_breakout', lookback=n, slow=200, stop_atr=2., reward_r=3., trail_atr=3.)
             for n in [80, 64, 96, 55]]
    grid = list(product([40, 55, 64, 80, 96, 120], [100, 200], [1.5, 2., 2.5, 3.], [2., 3., 4., 4.5, 5.], [0., 2., 3., 4., 5.]))
    random.Random(seed).shuffle(grid)
    for length, slow, stop, reward, trailing in grid:
        if slow <= length:
            continue
        r = SignalRule('channel_breakout', lookback=length, slow=slow, stop_atr=stop, reward_r=reward, trail_atr=trailing)
        if r not in rules:
            rules.append(r)
        if len(rules) >= count:
            break
    return [dict(id=i, label=f'channel{r.lookback}_ema{r.slow}_stop{r.stop_atr}_rr{r.reward_r}_trail{r.trail_atr}', rule=asdict(r)) for i, r in enumerate(rules)]


def eligible(metrics, checks, benchmark):
    """Historical improvement gate; all periods are reused selection data."""
    return (pnl(metrics) > benchmark and metrics['entries'] >= 100
            and metrics['margin_call_events'] == 0 and metrics['max_intrabar_drawdown'] <= .05
            and all(pnl(checks[name]) > 0 for name in ['2025_h1', '2025_h2', 'earlier_2020_2022'])
            and pnl(checks['full_4bp']) > benchmark
            and all(m['margin_call_events'] == 0 for m in checks.values()))


def run(args):
    args.output.mkdir(parents=True, exist_ok=True)
    parent_snapshot = args.output/'parent_v13.json'
    baseline_snapshot = args.output/'baseline_v12.json'
    for source, target in [(ROOT/'configs/eth_strategy_v1_3.json', parent_snapshot), (ROOT/'configs/dvs_eth_v1_2.json', baseline_snapshot)]:
        if not target.exists():
            target.write_bytes(source.read_bytes())
    parent = json.loads(parent_snapshot.read_text(encoding='utf-8'))
    base = StrategyConfig(**json.loads(baseline_snapshot.read_text(encoding='utf-8')))
    cfg = replace(baseline(), risk_includes_costs=True)
    earlier_path = ROOT/'data/ethusd/perpetual_2020_2022/candles.parquet'
    universe = candidates(args.candidates)
    plan = dict(name='Explicit historical net-profit improvement', candidate_count=len(universe), candidates=universe,
                execution_config=asdict(cfg), start='2023-01-01', end_exclusive='2026-10-28', shortlist=args.finalists,
                source_hashes={n: hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in
                               ['net_profit_research.py', 'alternative_strategies.py', 'engine.py', 'indicators.py', 'config.py', 'market_data.py', 'optimize.py', 'exit_research.py']},
                data_hashes={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [PARQUET, earlier_path]},
                parent_sha256=hashlib.sha256(parent_snapshot.read_bytes()).hexdigest(),
                baseline_sha256=hashlib.sha256(baseline_snapshot.read_bytes()).hexdigest(),
                prior_search_slots=444, seed=1305,
                selection='Rank all full 2023-2026 inspected-period replays by net P&L; shortlist then historical cost/regime checks. Choose highest net among eligible. Lower candidate ID breaks ties.',
                gate='Beat both saved v1.2 and v1.3 on identical dates after costs, >=100 entries, <=5% intrabar running-peak drawdown, no margin calls; both 2025 halves and earlier 2020-2022 aggregate positive; full-period 4bp-extra-slippage net also exceeds original benchmark.',
                important='2026 now explicitly participates in model selection at user request. All years are inspected/reused. This objective is historical P&L, not independent validation or future profitability. Risk remains $100; costs and account size cannot be optimized away.')
    freeze(args.output/'manifest.json', plan)
    bars, _ = load_history(PARQUET)
    bars = bars[(bars.timestamp >= utc(plan['start'])) & (bars.timestamp < utc(plan['end_exclusive']))].reset_index(drop=True)
    comparators_path = args.output/'comparators.json'
    if comparators_path.exists():
        comparators = json.loads(comparators_path.read_text(encoding='utf-8'))
    else:
        comparators = dict(v1_2=backtest(bars, base, capture_details=False).metrics,
                           v1_3=simulate(bars, SignalRule(**parent['rule']), StrategyConfig(**parent['execution']))[0])
        write_json(comparators_path, comparators)
    benchmark = max(pnl(m) for m in comparators.values())
    print(f'BENCHMARK ${benchmark:.2f}', flush=True)
    training = resume_rows(args.output/'training.jsonl')
    done = {r['id'] for r in training}
    cache_key, features = None, None
    # Reuse signal calculations across exit variants without keeping many
    # copies of the full candle history in memory.
    for candidate in sorted(universe, key=lambda c: (c['rule']['lookback'], c['rule']['slow'], c['id'])):
        if candidate['id'] in done:
            continue
        rule = SignalRule(**candidate['rule'])
        key = (rule.lookback, rule.slow)
        if key != cache_key:
            features, cache_key = prepare_signals(bars, rule), key
        metrics, _, _ = simulate(bars, rule, cfg, signals=features)
        row = dict(id=candidate['id'], label=candidate['label'], metrics=metrics, score=pnl(metrics))
        training.append(row)
        append(args.output/'training.jsonl', row)
        print(f"SCREEN {len(training)}/{len(universe)} {row['label']} net=${pnl(metrics):.2f} DD={metrics['max_intrabar_drawdown']:.2%}", flush=True)
    ranked = sorted(training, key=lambda r: (-r['score'], r['id']))
    shortlist = [r['id'] for r in ranked if r['metrics']['entries'] >= 100 and r['metrics']['margin_call_events'] == 0 and r['metrics']['max_intrabar_drawdown'] <= .05][:args.finalists]
    write_json(args.output/'shortlist.json', dict(candidate_ids=shortlist, benchmark_net=benchmark, selection_uses='Inspected full 2023-2026 net profit'))
    old_bars, _ = load_history(earlier_path)
    validation = resume_rows(args.output/'validation.jsonl')
    done = {r['id'] for r in validation}
    by_id = {r['id']: r for r in training}
    for candidate_id in shortlist:
        if candidate_id in done:
            continue
        candidate = universe[candidate_id]
        rule = SignalRule(**candidate['rule'])
        features = prepare_signals(bars, rule)
        checks = {}
        for label, start, end in [('2025_h1', '2025-01-01', '2025-07-01'), ('2025_h2', '2025-07-01', '2026-01-01'),
                                  ('2026_selected_period', '2026-01-01', plan['end_exclusive'])]:
            b, f = subset(bars, features, start, end)
            checks[label] = simulate(b, rule, cfg, signals=f)[0]
        checks['earlier_2020_2022'] = simulate(old_bars, rule, cfg)[0]
        checks['full_4bp'] = simulate(bars, rule, replace(cfg, slippage_bps=4.), signals=features)[0]
        passed = eligible(by_id[candidate_id]['metrics'], checks, benchmark)
        row = dict(id=candidate_id, label=candidate['label'], checks=checks, score=by_id[candidate_id]['score'], passed_historical_gate=passed)
        validation.append(row)
        append(args.output/'validation.jsonl', row)
        print(f"CHECK {candidate['label']} gate={passed} old=${pnl(checks['earlier_2020_2022']):.2f} 2025={[round(pnl(checks[k]),2) for k in ['2025_h1','2025_h2']]} 2026=${pnl(checks['2026_selected_period']):.2f} stressed=${pnl(checks['full_4bp']):.2f}", flush=True)
    passed = [r for r in validation if r['passed_historical_gate']]
    winner = max(passed or validation, key=lambda r: (r['score'], -r['id']))
    candidate = universe[winner['id']]
    selection = dict(candidate=candidate, execution_config=asdict(cfg), training=by_id[winner['id']], validation=winner,
                     passed_predeclared_validation_gate=bool(passed), selection_is_historical_profit_optimization=True,
                     independent_validation=False, ready_for_funded_trading=False, benchmark_net=benchmark)
    freeze(args.output/'selection.json', selection)
    rule = SignalRule(**candidate['rule'])
    metrics, trades, events = simulate(bars, rule, cfg)
    trades.to_csv(args.output/'selected_trades.csv', index=False)
    events.to_csv(args.output/'selected_events.csv', index=False)
    evaluation = dict(full_2023_2026=metrics, **winner['checks'])
    write_json(args.output/'summary.json', dict(selection=selection, evaluation=evaluation, comparators=comparators, not_independent_validation=True))
    rows = []
    for row in ranked:
        m = row['metrics']
        check = next((r for r in validation if r['id'] == row['id']), None)
        rows.append(dict(id=row['id'], label=row['label'], net_pnl=pnl(m), entries=m['entries'], drawdown=m['max_intrabar_drawdown'],
                         historical_gate=check['passed_historical_gate'] if check else None))
    pd.DataFrame(rows).to_csv(args.output/'leaderboard.csv', index=False)
    lines = ['# Historical net-profit improvement search', '', plan['important'], '',
             f"Compared {len(universe)} fixed configurations at the same costs and $100 risk. Selected **{candidate['label']}**. Historical gate passed: **{bool(passed)}**.", '',
             '| Same continuous UTC period: 2023-01-01 to 2026-10-28 exclusive | Net P&L | Entries | Intrabar drawdown |', '| --- | ---: | ---: | ---: |']
    for name, m in [*comparators.items(), ('selected', metrics), ('selected at 4bp extra slippage', winner['checks']['full_4bp'])]:
        lines.append(f"| {name} | ${pnl(m):,.2f} | {m['entries']} | {m['max_intrabar_drawdown']:.2%} |")
    lines.extend(['', f"Improvement above the previous saved-profit benchmark: **${pnl(metrics)-benchmark:,.2f}**.", '',
                  '| Additional reused-data check, independent accounts | Net P&L |', '| --- | ---: |'])
    for name, m in winner['checks'].items():
        if name != 'full_4bp':
            lines.append(f'| {name} | ${pnl(m):,.2f} |')
    lines.extend(['', 'The 2026 result is selection-period performance, not an independent audit. Half-year and earlier-period accounts reset position/cash state; they do not sum to the continuous replay. All failures and all candidates remain in checkpoints. No candle fabrication, fee reduction, larger account or risk increase is used to cross the benchmark. Missing later days remain excluded. This historical optimization does not establish a durable future edge.', ''])
    report = '\n'.join(lines)
    (args.output/'report.md').write_text(report, encoding='utf-8')
    (ROOT/'reports/net_profit_improvement.md').write_text(report, encoding='utf-8')
    print(f"FINISHED net=${pnl(metrics):.2f} improvement=${pnl(metrics)-benchmark:.2f} gate={bool(passed)}", flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'artifacts/optimization/round5_historical_profit')
    parser.add_argument('--candidates', type=int, default=64)
    parser.add_argument('--finalists', type=int, default=8)
    args = parser.parse_args()
    if args.finalists < 1:
        parser.error('At least one finalist is required')
    run(args)
