"""Compare non-DVS ETH families under a frozen, reused-data protocol."""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path

import pandas as pd

from .alternative_strategies import SignalRule, prepare_signals, simulate
from .config import StrategyConfig
from .engine import backtest
from .exit_research import freeze, passes_gate, training_score, validation_score
from .market_data import clean_candles, load_history, utc
from .optimize import append, baseline, pnl, resume_rows, subset, write_json
from .paths import PARQUET, ROOT


def candidates():
    rules = []
    for fast, slow in [(20, 50), (50, 200)]:
        for reward in [2., 3.]:
            rules.append(SignalRule('ema_cross', lookback=fast, slow=slow, stop_atr=2., reward_r=reward))
    for length in [20, 55]:
        for trail in [0., 3.]:
            rules.append(SignalRule('channel_breakout', lookback=length, slow=200, stop_atr=2., reward_r=3., trail_atr=trail))
    for reward in [1., 1.5]:
        for holding in [144, 288]:
            rules.append(SignalRule('bollinger_reversion', lookback=20, slow=50, stop_atr=2., reward_r=reward, max_holding_bars=holding))
    return [dict(id=i, label=f'{r.family}_{i}', rule=asdict(r)) for i, r in enumerate(rules)]


def run(args, *, candidate_universe=None, followup_protocol=None):
    args.output.mkdir(parents=True, exist_ok=True)
    parent_path = args.output/'parent_config.json'
    if not parent_path.exists():
        parent_path.write_bytes((ROOT/'configs/dvs_eth_v1_2.json').read_bytes())
    parent = StrategyConfig(**json.loads(parent_path.read_text(encoding='utf-8')))
    universe = candidates() if candidate_universe is None else candidate_universe
    if not universe or [r['id'] for r in universe] != list(range(len(universe))):
        raise ValueError('Candidates require nonempty consecutive IDs')
    earlier = ROOT/'data/ethusd/perpetual_2020_2022/candles.parquet'
    cfg = replace(baseline(), risk_includes_costs=True)
    plan = dict(name='Independent ETH strategy families for v1.3 research', candidates=universe,
                execution_config=asdict(cfg), finalists=4,
                training=[[f'{y}-01-01', f'{y+1}-01-01'] for y in range(2020, 2025)],
                validation=[['2025-01-01', '2025-07-01'], ['2025-07-01', '2026-01-01']],
                audit=['2026-01-01', '2026-10-28'],
                data_hashes={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [earlier, args.data]},
                source_hashes={name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
                               ['alternative_research.py', 'alternative_strategies.py', 'exit_research.py', 'engine.py', 'config.py', 'indicators.py', 'market_data.py', 'optimize.py']},
                parent_sha256=hashlib.sha256(parent_path.read_bytes()).hexdigest(),
                prior_search_slots=384, other_current_search_slots=24,
                selection='Top four by 2020-2024 training score. Prefer gate-eligible candidate by 2025 score; otherwise best unpromoted research. Audit cannot reselect.',
                gate='Same annual-regime, validation, trade-count, margin and 4bp stress gates as exit_research.passes_gate.',
                combined_v13_decision='If either experiment passes its gate, prefer highest 2025 score among passing winners; otherwise retain DVS exit candidate as unpromoted experimental v1.3. 2026 cannot select the strategy family.',
                warning='All historical years are reused/inspected; this is additional model selection, not untouched forward validation. Independent signal families still share market exposure and broker assumptions.')
    if followup_protocol is not None:
        plan['followup'] = followup_protocol
        plan['name'] = followup_protocol['name']
        plan['finalists'] = followup_protocol['finalists']
        plan['prior_search_slots'] = followup_protocol['prior_search_slots']
        plan['other_current_search_slots'] = 0
        plan['combined_v13_decision'] = 'This is a new search after both first v1.3 experiments failed. Historical gate remains unchanged; a failed gate cannot be represented as promotion. Audit cannot select or replace the chosen candidate.'
    freeze(args.output/'manifest.json', plan)
    old, _ = load_history(earlier)
    new, _ = load_history(args.data)
    bars, quality = clean_candles(pd.concat([old, new[new.timestamp < utc(plan['audit'][1])]], ignore_index=True))
    if quality['missing_bars']:
        raise ValueError('Independent experiments require complete historical bars')
    training = resume_rows(args.output/'training.jsonl')
    done = {row['id'] for row in training}
    for candidate in universe:
        if candidate['id'] in done:
            continue
        rule = SignalRule(**candidate['rule'])
        features = prepare_signals(bars, rule)
        folds = []
        for window in plan['training']:
            b, f = subset(bars, features, *window)
            folds.append(simulate(b, rule, cfg, signals=f)[0])
        row = dict(id=candidate['id'], label=candidate['label'], folds=folds, score=training_score(folds))
        training.append(row)
        append(args.output/'training.jsonl', row)
        print(f"ALT TRAIN {len(training)}/{len(universe)} {row['label']} years={[round(pnl(m), 2) for m in folds]} score={row['score']:.2f}", flush=True)
    ranked = sorted(training, key=lambda row: (-row['score'], row['id']))
    ids = [row['id'] for row in ranked[:plan['finalists']]]
    write_json(args.output/'shortlist.json', dict(candidate_ids=ids, selection_uses='2020-2024 only'))
    validation = resume_rows(args.output/'validation.jsonl')
    done = {row['id'] for row in validation}
    for candidate_id in ids:
        if candidate_id in done:
            continue
        candidate = universe[candidate_id]
        rule = SignalRule(**candidate['rule'])
        features = prepare_signals(bars, rule)
        folds = []
        for window in plan['validation']:
            b, f = subset(bars, features, *window)
            folds.append(simulate(b, rule, cfg, signals=f)[0])
        row = dict(id=candidate_id, label=candidate['label'], folds=folds, score=validation_score(folds))
        validation.append(row)
        append(args.output/'validation.jsonl', row)
        print(f"ALT VALIDATION {row['label']} halves={[round(pnl(m), 2) for m in folds]}", flush=True)
    # Same parent and indicator initialization as the exit experiment, recomputed
    # here rather than trusting an unrelated saved summary's settings.
    from .indicators import prepare_indicators
    parent_features = prepare_indicators(bars)
    parent_train, parent_valid = [], []
    for windows, results in [(plan['training'], parent_train), (plan['validation'], parent_valid)]:
        for window in windows:
            b, f = subset(bars, parent_features, *window)
            results.append(backtest(b, parent, indicators=f, capture_details=False).metrics)
    del parent_features
    train_by_id = {r['id']: r for r in training}
    eligible = [r for r in validation if passes_gate(train_by_id[r['id']]['folds'], r['folds'], parent_train, parent_valid)]
    winner = max(eligible or validation, key=lambda r: (r['score'], -r['id']))
    candidate = universe[winner['id']]
    rule = SignalRule(**candidate['rule'])
    features = prepare_signals(bars, rule)
    b, f = subset(bars, features, '2025-01-01', '2026-01-01')
    stress = simulate(b, rule, replace(cfg, slippage_bps=4.), signals=f)[0]
    selection = dict(candidate=candidate, execution_config=asdict(cfg), training=train_by_id[winner['id']], validation=winner,
                     passed_predeclared_validation_gate=bool(eligible) and pnl(stress) > 0,
                     eligible_before_stress=len(eligible), stress_2025_4bp=stress,
                     audit_cannot_change_selection=True, ready_for_funded_trading=False)
    freeze(args.output/'selection.json', selection)
    evaluation = {}
    for label, window in [('audit_2026', plan['audit']), ('continuous_2020_2026', ['2020-01-01', plan['audit'][1]]),
                          ('recent_october', ['2026-10-11', plan['audit'][1]])]:
        b, f = subset(bars, features, *window)
        metrics, trades, events = simulate(b, rule, cfg, signals=f)
        directory = args.output/label
        directory.mkdir(parents=True, exist_ok=True)
        write_json(directory/'metrics.json', metrics)
        trades.to_csv(directory/'trades.csv', index=False)
        events.to_csv(directory/'events.csv', index=False)
        evaluation[label] = metrics
        print(f"ALT AUDIT {label}: ${pnl(metrics):.2f}", flush=True)
    write_json(args.output/'summary.json', dict(selection=selection, evaluation=evaluation, quality=quality, not_independent_validation=True))
    rows = []
    for row in ranked:
        item = dict(id=row['id'], label=row['label'], training_score=row['score'])
        item.update({f'pnl_{year}': pnl(m) for year, m in zip(range(2020, 2025), row['folds'])})
        v = next((v for v in validation if v['id'] == row['id']), None)
        if v:
            item.update(validation_h1=pnl(v['folds'][0]), validation_h2=pnl(v['folds'][1]))
        rows.append(item)
    pd.DataFrame(rows).to_csv(args.output/'leaderboard.csv', index=False)
    families = ', '.join(sorted({row['rule']['family'] for row in universe}))
    lines = [f"# {plan['name']}", '', plan['warning'], '',
             f"Screened {len(universe)} fixed configurations across {families}. Selected **{candidate['label']}** using training shortlist and reused 2025 selection, before the 2026 audit.", '',
             f"Historical promotion gate passed: **{selection['passed_predeclared_validation_gate']}**.", '',
             '| Period | DVS v1.2 | Independent candidate |', '| --- | ---: | ---: |']
    for year, p, s in zip(range(2020, 2025), parent_train, train_by_id[winner['id']]['folds']):
        lines.append(f'| {year}, independent accounts | ${pnl(p):,.2f} | ${pnl(s):,.2f} |')
    for half, p, s in zip(['2025 H1', '2025 H2'], parent_valid, winner['folds']):
        lines.append(f'| {half}, independent accounts | ${pnl(p):,.2f} | ${pnl(s):,.2f} |')
    for label, m in evaluation.items():
        lines.append(f'| {label} | Not recomputed in this run | ${pnl(m):,.2f} |')
    lines.extend(['', f"2025 continuous 4bp-extra-slippage stress: ${pnl(stress):,.2f}.", '',
                  f"Frozen selected rule: `{json.dumps(candidate['rule'], sort_keys=True)}`.", '',
                  'Every rule uses confirmed hourly signals and five-minute OHLC execution, next-open entries, $100 planned risk including estimated costs, $50,000 capital, max 5x leverage, 4bp/side commission, two ticks plus 2bp extra market/stop slippage, financing and stop-first ambiguity handling. Shared personal daily gates are not contractual funded-account compliance checks. Annual folds reset accounts; their sum is not a continuous account return. Cash is a zero-return alternative.', '',
                  'Stops/targets are based on the hourly signal close and ATR, not a future fill. Trailing updates occur only after the current five-minute candle closes. There are no DVS pivot/bias/retest requirements. No independent strategy is promoted solely for winning this reused-data search. Signals, fills and Pine compilation still require external reconciliation. No live orders or v1.2 edits occur.', ''])
    report = '\n'.join(lines)
    (args.output/'report.md').write_text(report, encoding='utf-8')
    report_name = 'v1_3_channel_refinement.md' if followup_protocol else 'independent_eth_strategies.md'
    (ROOT/'reports'/report_name).write_text(report, encoding='utf-8')
    print(f"ALT FINISHED selected={candidate['label']} historical_gate={selection['passed_predeclared_validation_gate']}", flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=PARQUET)
    parser.add_argument('--output', type=Path, default=ROOT/'artifacts/optimization/round3_independent_families')
    run(parser.parse_args())
