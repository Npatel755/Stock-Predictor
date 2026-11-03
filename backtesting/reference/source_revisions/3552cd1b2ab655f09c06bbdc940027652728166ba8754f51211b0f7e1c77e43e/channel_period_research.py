"""Frozen channel/EMA period research against immutable ETH v1.7."""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
from itertools import product
import json
from pathlib import Path

import pandas as pd

from .alternative_strategies import SignalRule, simulate
from .config import StrategyConfig
from .entry_neighborhood import eligible
from .exit_research import freeze
from .market_data import load_history, utc
from .numbered_profiles import load_profile
from .optimize import append, pnl, resume_rows, subset, write_json
from .paths import ROOT, PARQUET
from .regime_filters import RegimeFilter, apply_filter, prepare_features


def period_candidates(parent, filters):
    rules=[parent]
    for lookback,slow in product([72,96,120],[125,150,200,250]):
        rule=replace(parent,lookback=lookback,slow=slow)
        if rule not in rules: rules.append(rule)
    return [dict(id=i,label=f'channel{r.lookback}_ema{r.slow}',rule=asdict(r),filters=asdict(filters))
            for i,r in enumerate(rules)]


def initial_screen(metrics, benchmark, requested):
    return (pnl(metrics) > max(requested, pnl(benchmark['main'])) and metrics['entries'] >= 100
            and metrics['max_intrabar_drawdown'] <= benchmark['main']['max_intrabar_drawdown']
            and not metrics['margin_call_events'])


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args):
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    suffix = args.parent.replace('.', '_')
    snapshot = output/'parent.json'
    if not snapshot.exists():
        load_profile(ROOT, args.parent)
        snapshot.write_bytes((ROOT/f'configs/eth_strategy_{suffix}.json').read_bytes())
    if not (output/'baseline.json').exists():
        (output/'baseline.json').write_bytes((ROOT/'configs/research_baseline.json').read_bytes())
    parent = json.loads(snapshot.read_text(encoding='utf-8'))
    baseline = json.loads((output/'baseline.json').read_text(encoding='utf-8'))
    rule, cfg, filters = SignalRule(**parent['rule']), StrategyConfig(**parent['execution']), RegimeFilter(**parent['filters'])
    universe = period_candidates(rule, filters)
    earlier_path = ROOT/'data/ethusd/perpetual_2020_2022/candles.parquet'
    protected = [p for p in (ROOT/'configs').glob('eth_strategy_v1_*.json')]
    protected += list((ROOT/'reference').glob('ETH_Strategy_v1_*.pine'))
    sources = ['channel_period_research.py', 'entry_neighborhood.py', 'alternative_strategies.py', 'regime_filters.py',
               'engine.py', 'config.py', 'indicators.py', 'market_data.py', 'optimize.py', 'exit_research.py', 'numbered_profiles.py']
    plan = dict(name=f'{args.parent} channel / EMA period follow-up', parent_version=args.parent,
                candidate_count=len(universe), candidates=universe, execution=asdict(cfg),
                historical_profit_selection=True, prior_search_slots=736, selection_window=['2023-01-01', '2026-10-28'],
                requested_baseline_net=baseline['requested_net_profit_usd'], exact_reference_net=baseline['prior_reference_net_profit_usd'],
                source_hashes={name: sha(ROOT/name) for name in sources},
                data_hashes={str(p.relative_to(ROOT)): sha(p) for p in [PARQUET, earlier_path]},
                protected_profile_hashes={str(p.relative_to(ROOT)): sha(p) for p in protected},
                parent_sha256=sha(snapshot), baseline_sha256=sha(output/'baseline.json'),
                gate='Main net above exact saved reference and requested baseline; drawdown no worse; >=100 entries; no margin calls; positive reset 2025/2026 halves with >=6 entries each; positive 2026 H1 under 4bp extra slippage; positive 2020-2022; full-period 4bp and 8bp net above matching parent stress.',
                selection='Test all 12 channel/EMA period pairs, including the parent control. Fully check every changed candidate passing the main screen; choose the highest-net complete-gate pass. Preserve every failure; no automatic version replacement.',
                warning='All 2023-2026 observations are reused selection history. The 2018-2019 spot proxy was previously inspected and is not used in this search. No fresh forward-validation claim. RVOL2.4 and signed 200bp trend thresholds, exit geometry, account size, risk, costs and execution code remain fixed. Each period pair recomputes its own channel, EMA, warm-up and signed trend distance.')
    freeze(output/'manifest.json', plan)
    bars, _ = load_history(PARQUET)
    bars = bars[(bars.timestamp >= utc('2023-01-01')) & (bars.timestamp < utc('2026-10-28'))].reset_index(drop=True)
    earlier, _ = load_history(earlier_path)
    # These features are the unchanged benchmark only. Each candidate below
    # recomputes its own channel/EMA signals and trend-distance filter.
    features = apply_filter(prepare_features(bars, rule), filters)
    earlier_features = apply_filter(prepare_features(earlier, rule), filters)
    if (output/'benchmark.json').exists():
        benchmark = json.loads((output/'benchmark.json').read_text(encoding='utf-8'))
    else:
        benchmark = {name: simulate(bars, rule, replace(cfg, slippage_bps=bps), signals=features)[0]
                     for name, bps in [('main', 2.), ('stress4', 4.), ('stress8', 8.)]}
        if abs(pnl(benchmark['main'])-plan['exact_reference_net']) > 1e-6:
            raise ValueError('Parent replay does not reproduce the exact reference')
        write_json(output/'benchmark.json', benchmark)
    print(f"PERIODS reference=${pnl(benchmark['main']):.2f}; DD={benchmark['main']['max_intrabar_drawdown']:.2%}", flush=True)
    training = resume_rows(output/'training.jsonl')
    done = {r['id'] for r in training}
    for candidate in universe:
        if candidate['id'] in done:
            continue
        chosen_rule = SignalRule(**candidate['rule'])
        selected_features = apply_filter(prepare_features(bars, chosen_rule), filters)
        m = simulate(bars, chosen_rule, cfg, signals=selected_features)[0]
        row = dict(id=candidate['id'], label=candidate['label'], metrics=m, score=pnl(m))
        training.append(row)
        append(output/'training.jsonl', row)
        print(f"PERIODS {len(training)}/{len(universe)} {row['label']}: net=${pnl(m):.2f} DD={m['max_intrabar_drawdown']:.2%}", flush=True)
    ranked = sorted(training, key=lambda r: (-r['score'], r['id']))
    ids = [r['id'] for r in ranked if r['id'] and initial_screen(r['metrics'], benchmark, plan['requested_baseline_net'])]
    write_json(output/'shortlist.json', dict(candidate_ids=ids, selection_uses='Inspected full-period net/drawdown; all main-screen passes'))
    validation = resume_rows(output/'validation.jsonl')
    done = {r['id'] for r in validation}
    by_id = {r['id']: r for r in training}
    for index in ids:
        if index in done:
            continue
        candidate = universe[index]
        chosen_rule = SignalRule(**candidate['rule'])
        features = apply_filter(prepare_features(bars, chosen_rule), filters)
        earlier_features = apply_filter(prepare_features(earlier, chosen_rule), filters)
        checks = {}
        for name, start, end in [('2025_h1', '2025-01-01', '2025-07-01'), ('2025_h2', '2025-07-01', '2026-01-01'),
                                 ('2026_h1', '2026-01-01', '2026-07-01'), ('2026_h2', '2026-07-01', '2026-10-28')]:
            b, f = subset(bars, features, start, end)
            checks[name] = simulate(b, chosen_rule, cfg, signals=f)[0]
        b, f = subset(bars, features, '2026-01-01', '2026-07-01')
        checks['2026_h1_4bp'] = simulate(b, chosen_rule, replace(cfg, slippage_bps=4.), signals=f)[0]
        checks['earlier_2020_2022'] = simulate(earlier, chosen_rule, cfg, signals=earlier_features)[0]
        for bps in [4., 8.]:
            checks[f'full_{int(bps)}bp'] = simulate(bars, chosen_rule, replace(cfg, slippage_bps=bps), signals=features)[0]
        passed = eligible(by_id[index]['metrics'], checks, benchmark, plan['requested_baseline_net'])
        row = dict(id=index, label=candidate['label'], checks=checks, passed_historical_gate=passed, score=by_id[index]['score'])
        validation.append(row)
        append(output/'validation.jsonl', row)
        print(f"PERIODS CHECK {row['label']} gate={passed} weak4bp=${pnl(checks['2026_h1_4bp']):.2f} full4=${pnl(checks['full_4bp']):.2f} full8=${pnl(checks['full_8bp']):.2f}", flush=True)
    passing = [r for r in validation if r['passed_historical_gate']]
    winner = max(passing or validation, key=lambda r: (r['score'], -r['id'])) if validation else next(r for r in ranked if r['id'])
    selection = dict(candidate=universe[winner['id']], execution_config=asdict(cfg),
                     passed_predeclared_validation_gate=bool(passing), selection_is_historical_profit_optimization=True,
                     requested_baseline=plan['requested_baseline_net'], exact_reference_net=pnl(benchmark['main']),
                     independent_validation=False, ready_for_funded_trading=False)
    freeze(output/'selection.json', selection)
    chosen_rule = SignalRule(**selection['candidate']['rule'])
    features = apply_filter(prepare_features(bars, chosen_rule), filters)
    m, trades, events = simulate(bars, chosen_rule, cfg, signals=features)
    trades.to_csv(output/'selected_trades.csv', index=False)
    events.to_csv(output/'selected_events.csv', index=False)
    checks = winner.get('checks', {})
    write_json(output/'summary.json', dict(selection=selection, benchmark=benchmark, evaluation=dict(full_period=m, **checks),
                                         saved_versions_unchanged=True, main_screen_count=len(ids), gate_pass_count=len(passing)))
    pd.DataFrame([dict(id=r['id'], label=r['label'], net_pnl=r['score'], entries=r['metrics']['entries'], drawdown=r['metrics']['max_intrabar_drawdown']) for r in ranked]).to_csv(output/'leaderboard.csv', index=False)
    lines = [f'# Channel/EMA period research after ETH {args.parent}', '', plan['warning'], '',
             f"Frozen {len(universe)}-configuration grid, including the unchanged control. {len(ids)} passed the main screen; {len(passing)} passed the complete gate. Selection: **{selection['candidate']['label']}**. Gate: **{bool(passing)}**.", '',
             '| Same original perpetual period | Net P&L | Entries | Intrabar drawdown |', '| --- | ---: | ---: | ---: |']
    for name, value in [(f'Saved {args.parent}', benchmark['main']), ('Selected diagnostic', m),
                        (f'Saved {args.parent} at 4bp', benchmark['stress4']), (f'Saved {args.parent} at 8bp', benchmark['stress8']), *checks.items()]:
        lines.append(f"| {name} | ${pnl(value):,.2f} | {value['entries']} | {value['max_intrabar_drawdown']:.2%} |")
    lines += ['', f"Selected rule: `{json.dumps(selection['candidate']['rule'], sort_keys=True)}`.", '',
              f"Fixed filters: `{json.dumps(asdict(filters), sort_keys=True)}`.", '',
              'Stops and targets are fixed from the signal close; entries use the next open. Trailing changes occur only after completed closes and affect later ticks. Replaying every candidate permits changed exit timing to alter later entry availability and financing. Reset-fold sums are not continuous account returns.', '',
              'The highest-net complete-gate pass can be verified and saved separately under the next version. A failed candidate never replaces a numbered strategy. Pine compilation and TradingView matching remain unverified.', '']
    report = '\n'.join(lines)
    (output/'report.md').write_text(report, encoding='utf-8')
    (ROOT/f'reports/{output.name}.md').write_text(report, encoding='utf-8')
    for name, digest in plan['protected_profile_hashes'].items():
        if sha(ROOT/name) != digest:
            raise ValueError(f'Protected numbered file changed: {name}')
    print(f"PERIODS FINISHED net=${pnl(m):.2f} improvement=${pnl(m)-pnl(benchmark['main']):.2f} gate={bool(passing)}", flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent', default='v1.7')
    parser.add_argument('--output', type=Path, default=ROOT/'artifacts/optimization/round13_v1_7_periods')
    run(parser.parse_args())
