"""Frozen exit-management follow-up after v1.5; no saved profile overwrite."""
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
from .exit_research import freeze
from .market_data import load_history, utc
from .optimize import append, pnl, resume_rows, subset, write_json
from .paths import ROOT, PARQUET
from .regime_filters import RegimeFilter, apply_filter, prepare_features


def candidates(parent):
    rules = [parent]
    for trailing, holding in product([2., 2.5, 3., 3.5], [0, 72, 144, 288, 576]):
        rule = replace(parent, trail_atr=trailing, max_holding_bars=holding)
        if rule not in rules:
            rules.append(rule)
    return [dict(id=i, label=f'trail{r.trail_atr}_hold{r.max_holding_bars}', rule=asdict(r)) for i, r in enumerate(rules)]


def eligible(metrics, checks, parent, parent_stress):
    return (pnl(metrics) > pnl(parent) and metrics['entries'] >= 100
            and metrics['max_intrabar_drawdown'] <= parent['max_intrabar_drawdown']
            and all(m['margin_call_events'] == 0 for m in [metrics, *checks.values()])
            and all(pnl(checks[k]) > 0 for k in ['2025_h1', '2025_h2', '2026_h1', '2026_h2', 'earlier_2020_2022'])
            and min(checks[k]['entries'] for k in ['2025_h1', '2025_h2', '2026_h1', '2026_h2']) >= 6
            and pnl(checks['full_4bp']) > pnl(parent_stress)
            and pnl(checks['full_8bp']) > 6000)


def run(args):
    from .generalization_policy import assert_search_allowed
    assert_search_allowed(ROOT)
    args.output.mkdir(parents=True, exist_ok=True)
    snapshot = args.output/'parent_v1_5.json'
    if not snapshot.exists():
        snapshot.write_bytes((ROOT/'configs/eth_strategy_v1_5.json').read_bytes())
    parent = json.loads(snapshot.read_text(encoding='utf-8'))
    parent_rule, cfg, filters = SignalRule(**parent['rule']), StrategyConfig(**parent['execution']), RegimeFilter(**parent['filters'])
    universe = candidates(parent_rule)
    earlier_path = ROOT/'data/ethusd/perpetual_2020_2022/candles.parquet'
    protected = [ROOT/'configs/eth_strategy_v1_5.json', ROOT/'configs/eth_strategy_v1_5.metadata.json', ROOT/'reference/ETH_Strategy_v1_5.pine']
    plan = dict(name='ETH v1.5 exit-management follow-up', candidate_count=len(universe), candidates=universe,
                execution=asdict(cfg), filters=asdict(filters), historical_profit_selection=True, prior_search_slots=638,
                selection_window=['2023-01-01', '2026-10-28'], shortlist=6,
                protected_profile_hashes={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected},
                data_hashes={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [PARQUET, earlier_path]},
                source_hashes={name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
                               ['management_research.py', 'alternative_strategies.py', 'regime_filters.py', 'engine.py', 'config.py', 'indicators.py', 'market_data.py', 'optimize.py', 'exit_research.py']},
                prior_evidence='Saved v1.5 net $9971.43 at 4.02% drawdown. Its inspected 2026 H1 lost $240.43. 2018-2019 spot data also inspected; it does not select this follow-up.',
                gate='Net above v1.5; drawdown no worse; >=100 entries; positive independently reset 2025/2026 halves with >=6 entries each; positive earlier 2020-2022 aggregate; full4bp profit above parent4bp; full8bp above requested $6000 baseline; no margin calls.',
                selection='Top six changed drawdown/exposure-eligible rules by inspected-period net. Choose highest complete-gate pass. If none passes, retain best changed diagnostic with failed-gate status. Do not promote failed winners.',
                warning='All 2023-2026 observations including 2026 participate in reused-data selection. No fresh validation or future-performance claim. Risk, account size, fees, slippage, financing, entry logic and RVOL2 filter are fixed; only trailing distance and maximum holding duration vary.')
    freeze(args.output/'manifest.json', plan)
    bars, _ = load_history(PARQUET)
    bars = bars[(bars.timestamp >= utc('2023-01-01')) & (bars.timestamp < utc('2026-10-28'))].reset_index(drop=True)
    features = apply_filter(prepare_features(bars, parent_rule), filters)
    earlier, _ = load_history(earlier_path)
    earlier_features = apply_filter(prepare_features(earlier, parent_rule), filters)
    path = args.output/'benchmark.json'
    if path.exists():
        benchmark = json.loads(path.read_text(encoding='utf-8'))
    else:
        benchmark = dict(main=simulate(bars, parent_rule, cfg, signals=features)[0],
                         stress4=simulate(bars, parent_rule, replace(cfg, slippage_bps=4.), signals=features)[0])
        write_json(path, benchmark)
    training = resume_rows(args.output/'training.jsonl')
    done = {r['id'] for r in training}
    for candidate in universe:
        if candidate['id'] in done:
            continue
        rule = SignalRule(**candidate['rule'])
        m = simulate(bars, rule, cfg, signals=features)[0]
        row = dict(id=candidate['id'], label=candidate['label'], metrics=m, score=pnl(m))
        training.append(row)
        append(args.output/'training.jsonl', row)
        print(f"MANAGEMENT {len(training)}/{len(universe)} {row['label']}: net=${pnl(m):.2f} DD={m['max_intrabar_drawdown']:.2%}", flush=True)
    ranked = sorted(training, key=lambda r: (-r['score'], r['id']))
    ids = [r['id'] for r in ranked if r['id'] and r['metrics']['entries'] >= 100 and r['metrics']['margin_call_events'] == 0
           and r['metrics']['max_intrabar_drawdown'] <= benchmark['main']['max_intrabar_drawdown']][:plan['shortlist']]
    write_json(args.output/'shortlist.json', dict(candidate_ids=ids, selection_uses='Inspected full-period net and drawdown'))
    validation = resume_rows(args.output/'validation.jsonl')
    done = {r['id'] for r in validation}
    by_id = {r['id']: r for r in training}
    for candidate_id in ids:
        if candidate_id in done:
            continue
        candidate = universe[candidate_id]
        rule = SignalRule(**candidate['rule'])
        checks = {}
        for name, start, end in [('2025_h1', '2025-01-01', '2025-07-01'), ('2025_h2', '2025-07-01', '2026-01-01'),
                                 ('2026_h1', '2026-01-01', '2026-07-01'), ('2026_h2', '2026-07-01', '2026-10-28')]:
            b, f = subset(bars, features, start, end)
            checks[name] = simulate(b, rule, cfg, signals=f)[0]
        checks['earlier_2020_2022'] = simulate(earlier, rule, cfg, signals=earlier_features)[0]
        for bps in [4., 8.]:
            checks[f'full_{int(bps)}bp'] = simulate(bars, rule, replace(cfg, slippage_bps=bps), signals=features)[0]
        passed = eligible(by_id[candidate_id]['metrics'], checks, benchmark['main'], benchmark['stress4'])
        row = dict(id=candidate_id, label=candidate['label'], checks=checks, passed_historical_gate=passed, score=by_id[candidate_id]['score'])
        validation.append(row)
        append(args.output/'validation.jsonl', row)
        print(f"MANAGEMENT CHECK {row['label']} gate={passed} 2026H1=${pnl(checks['2026_h1']):.2f} full4=${pnl(checks['full_4bp']):.2f} full8=${pnl(checks['full_8bp']):.2f}", flush=True)
    passing = [r for r in validation if r['passed_historical_gate']]
    if not validation:
        raise ValueError('No changed rule meets the initial exposure/drawdown screen; checkpoints retained')
    winner = max(passing or validation, key=lambda r: (r['score'], -r['id']))
    selection = dict(candidate={**universe[winner['id']], 'filters': asdict(filters)}, execution_config=asdict(cfg),
                     validation=winner, passed_predeclared_validation_gate=bool(passing), selection_is_historical_profit_optimization=True,
                     independent_validation=False, ready_for_funded_trading=False)
    freeze(args.output/'selection.json', selection)
    rule = SignalRule(**selection['candidate']['rule'])
    m, trades, events = simulate(bars, rule, cfg, signals=features)
    trades.to_csv(args.output/'selected_trades.csv', index=False)
    events.to_csv(args.output/'selected_events.csv', index=False)
    write_json(args.output/'summary.json', dict(selection=selection, benchmark=benchmark,
                                              evaluation=dict(full_period=m, **winner['checks']), saved_v1_5_unchanged=True))
    pd.DataFrame([dict(id=r['id'], label=r['label'], net_pnl=r['score'], entries=r['metrics']['entries'], drawdown=r['metrics']['max_intrabar_drawdown']) for r in ranked]).to_csv(args.output/'leaderboard.csv', index=False)
    lines = ['# Exit-management follow-up after ETH v1.5', '', plan['warning'], '',
             f"Screened {len(universe)} fixed exit configurations. Selected diagnostic: **{selection['candidate']['label']}**. Full historical improvement gate: **{bool(passing)}**.", '',
             '| Same original 2023-01-01 to 2026-10-28 exclusive period | Net P&L | Entries | Intrabar drawdown |', '| --- | ---: | ---: | ---: |']
    for name, metrics in [('Saved v1.5', benchmark['main']), ('Changed exit candidate', m), ('Saved v1.5 at 4bp', benchmark['stress4']), ('Candidate at 4bp', winner['checks']['full_4bp']), ('Candidate at 8bp', winner['checks']['full_8bp'])]:
        lines.append(f"| {name} | ${pnl(metrics):,.2f} | {metrics['entries']} | {metrics['max_intrabar_drawdown']:.2%} |")
    lines.extend(['', f"Rule: `{json.dumps(selection['candidate']['rule'], sort_keys=True)}`.", '',
                  '| Reused-data check, independently reset account | Net P&L | Entries |', '| --- | ---: | ---: |'])
    for name, metrics in winner['checks'].items():
        if name not in {'full_4bp', 'full_8bp'}:
            lines.append(f"| {name} | ${pnl(metrics):,.2f} | {metrics['entries']} |")
    lines.extend(['', 'Completed-close management updates cannot retroactively consume the same candle. Maximum-duration exits use market slippage and fees; longer or shorter holding periods can alter financing and later entry availability. The existing broker simulator is unchanged. Independent half-year/earlier accounts are not a continuous account sum.', '',
                  'The saved v1.5 Pine/profile/metadata/downloads remain unchanged. This is reused historical research, including the inspected weak 2026 half. There is no new forward evidence and no live trading. Failed historical gates remain failures even if a headline total improves.', ''])
    report = '\n'.join(lines)
    (args.output/'report.md').write_text(report, encoding='utf-8')
    (ROOT/'reports/v1_5_management_followup.md').write_text(report, encoding='utf-8')
    for name, digest in plan['protected_profile_hashes'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != digest:
            raise ValueError('Protected v1.5 changed during this run')
    print(f"MANAGEMENT FINISHED net=${pnl(m):.2f} gate={bool(passing)}", flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'artifacts/optimization/round9_v1_5_management')
    run(parser.parse_args())
