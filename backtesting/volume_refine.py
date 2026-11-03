"""Small volume/geometry follow-up; saved v1.4 is never overwritten.

The former 2026 audit is reused selection data. Repeated tuning cannot be
called independent validation, even if every historical gate passes.
"""
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
from .filter_research import eligible
from .market_data import load_history, utc
from .optimize import append, pnl, resume_rows, subset, write_json
from .paths import PARQUET, ROOT
from .regime_filters import RegimeFilter, apply_filter, prepare_features


def candidates(parent):
    rules = [parent, replace(parent, lookback=64, slow=200, stop_atr=1.75, reward_r=3.5)]
    result = []
    for geometry, rule in enumerate(rules):
        options = [RegimeFilter()] + [RegimeFilter(min_rvol=volume, weekends=weekends)
                                     for volume, weekends in product([1.2, 1.5, 2., 2.5], [True, False])]
        for settings in options:
            result.append(dict(id=len(result), label=f"geometry{geometry}_rvol{settings.min_rvol}_weekends{settings.weekends}",
                               rule=asdict(rule), filters=asdict(settings)))
    return result


def run(args):
    args.output.mkdir(parents=True, exist_ok=True)
    snapshot = args.output/'parent_v1_4.json'
    if not snapshot.exists():
        snapshot.write_bytes((ROOT/'configs/eth_strategy_v1_4.json').read_bytes())
    parent = json.loads(snapshot.read_text(encoding='utf-8'))
    parent_rule, cfg = SignalRule(**parent['rule']), StrategyConfig(**parent['execution'])
    universe = candidates(parent_rule)
    earlier_path = ROOT/'data/ethusd/perpetual_2020_2022/candles.parquet'
    protected = [ROOT/'configs/eth_strategy_v1_4.json', ROOT/'configs/eth_strategy_v1_4.metadata.json', ROOT/'reference/ETH_Strategy_v1_4.pine']
    plan = dict(name='ETH volume and geometry follow-up', candidate_count=len(universe), candidates=universe,
                execution=asdict(cfg), historical_profit_selection=True, prior_search_slots=620,
                selection_window=['2023-01-01', '2026-10-28'], shortlist=6,
                source_hashes={name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
                               ['volume_refine.py', 'filter_research.py', 'regime_filters.py', 'alternative_strategies.py', 'engine.py', 'config.py', 'indicators.py', 'market_data.py', 'optimize.py', 'exit_research.py']},
                data_hashes={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [PARQUET, earlier_path]},
                protected_profile_hashes={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected},
                prior_evidence='48 filters: parent geometry with RVOL1.5 net $7793.34, DD4.78%, but independently reset 2026 -$218.57. Earlier geometry64/EMA200/1.75ATR/3.5R/trail3 had net $5863.93, DD2.83%, 2026 +$440.04. Both are inspected.',
                gate='Same filter_research.eligible gate: net > v1.4; drawdown <= v1.4; >=100 entries; positive 2025 halves, 2026 and earlier 2020-2022; >=6 entries per validation half; stress4 net > parent stress4; no margin calls.',
                selection='Screen fixed universe on inspected 2023-2026; shortlist six by highest net meeting main drawdown/exposure eligibility, excluding unchanged parent; choose highest net passing complete gate. If none passes, record unpromoted diagnostic.',
                warning='All years including 2026 are reused selection data. No independent future validation, no live orders, no saved profile overwrite. Extra filters never modify sizing, costs or broker fills.')
    freeze(args.output/'manifest.json', plan)
    bars, _ = load_history(PARQUET)
    bars = bars[(bars.timestamp >= utc('2023-01-01')) & (bars.timestamp < utc('2026-10-28'))].reset_index(drop=True)
    earlier, _ = load_history(earlier_path)
    cache = {}

    def features(rule, old=False):
        key = (rule.lookback, rule.slow, old)
        if key not in cache:
            cache[key] = prepare_features(earlier if old else bars, rule)
        return cache[key]

    path = args.output/'benchmark.json'
    if path.exists():
        benchmark = json.loads(path.read_text(encoding='utf-8'))
    else:
        neutral = apply_filter(features(parent_rule), RegimeFilter())
        benchmark = dict(main=simulate(bars, parent_rule, cfg, signals=neutral)[0],
                         stress4=simulate(bars, parent_rule, replace(cfg, slippage_bps=4.), signals=neutral)[0])
        write_json(path, benchmark)
    training = resume_rows(args.output/'training.jsonl')
    done = {r['id'] for r in training}
    for candidate in universe:
        if candidate['id'] in done:
            continue
        rule = SignalRule(**candidate['rule'])
        f = apply_filter(features(rule), RegimeFilter(**candidate['filters']))
        m = simulate(bars, rule, cfg, signals=f)[0]
        row = dict(id=candidate['id'], label=candidate['label'], metrics=m, score=pnl(m))
        training.append(row)
        append(args.output/'training.jsonl', row)
        print(f"VOLUME {len(training)}/{len(universe)} {row['label']} net=${pnl(m):.2f} DD={m['max_intrabar_drawdown']:.2%}", flush=True)
    ranked = sorted(training, key=lambda r: (-r['score'], r['id']))
    ids = [r['id'] for r in ranked if r['id'] != 0 and r['metrics']['entries'] >= 100 and r['metrics']['margin_call_events'] == 0
           and r['metrics']['max_intrabar_drawdown'] <= benchmark['main']['max_intrabar_drawdown']][:plan['shortlist']]
    write_json(args.output/'shortlist.json', dict(candidate_ids=ids, selection_uses='Inspected full-period net and drawdown'))
    validation = resume_rows(args.output/'validation.jsonl')
    done = {r['id'] for r in validation}
    by_id = {r['id']: r for r in training}
    for candidate_id in ids:
        if candidate_id in done:
            continue
        candidate = universe[candidate_id]
        rule, settings = SignalRule(**candidate['rule']), RegimeFilter(**candidate['filters'])
        f = apply_filter(features(rule), settings)
        checks = {}
        for name, start, end in [('2025_h1', '2025-01-01', '2025-07-01'), ('2025_h2', '2025-07-01', '2026-01-01'),
                                 ('2026_selection', '2026-01-01', '2026-10-28')]:
            b, part = subset(bars, f, start, end)
            checks[name] = simulate(b, rule, cfg, signals=part)[0]
        checks['earlier_2020_2022'] = simulate(earlier, rule, cfg, signals=apply_filter(features(rule, old=True), settings))[0]
        checks['full_4bp'] = simulate(bars, rule, replace(cfg, slippage_bps=4.), signals=f)[0]
        passed = eligible(by_id[candidate_id]['metrics'], checks, benchmark['main'], benchmark['stress4'])
        row = dict(id=candidate_id, label=candidate['label'], checks=checks, passed_historical_gate=passed, score=by_id[candidate_id]['score'])
        validation.append(row)
        append(args.output/'validation.jsonl', row)
        print(f"VOLUME CHECK {row['label']} gate={passed} 2026=${pnl(checks['2026_selection']):.2f} old=${pnl(checks['earlier_2020_2022']):.2f} stress=${pnl(checks['full_4bp']):.2f}", flush=True)
    passing = [r for r in validation if r['passed_historical_gate']]
    winner = max(passing or validation, key=lambda r: (r['score'], -r['id']))
    selection = dict(candidate=universe[winner['id']], execution_config=asdict(cfg), validation=winner,
                     passed_predeclared_validation_gate=bool(passing), selection_is_historical_profit_optimization=True,
                     independent_validation=False, ready_for_funded_trading=False)
    freeze(args.output/'selection.json', selection)
    rule, settings = SignalRule(**selection['candidate']['rule']), RegimeFilter(**selection['candidate']['filters'])
    m, trades, events = simulate(bars, rule, cfg, signals=apply_filter(features(rule), settings))
    trades.to_csv(args.output/'selected_trades.csv', index=False)
    events.to_csv(args.output/'selected_events.csv', index=False)
    write_json(args.output/'summary.json', dict(selection=selection, benchmark=benchmark,
                                              evaluation=dict(full_period=m, **winner['checks']), saved_v1_4_unchanged=True))
    pd.DataFrame([dict(id=r['id'], label=r['label'], net_pnl=r['score'], entries=r['metrics']['entries'], drawdown=r['metrics']['max_intrabar_drawdown']) for r in ranked]).to_csv(args.output/'leaderboard.csv', index=False)
    lines = ['# Volume-filter and geometry follow-up', '', plan['warning'], '',
             f"Screened {len(universe)} fixed configurations. Frozen selection: **{selection['candidate']['label']}**. Historical improvement gate: **{bool(passing)}**.", '',
             '| Same 2023-01-01 to 2026-10-28 exclusive period | Net P&L | Entries | Intrabar drawdown |', '| --- | ---: | ---: | ---: |']
    for name, metrics in [('Saved v1.4', benchmark['main']), ('Candidate', m), ('Saved v1.4 at 4bp', benchmark['stress4']), ('Candidate at 4bp', winner['checks']['full_4bp'])]:
        lines.append(f"| {name} | ${pnl(metrics):,.2f} | {metrics['entries']} | {metrics['max_intrabar_drawdown']:.2%} |")
    lines.extend(['', f"Rule: `{json.dumps(selection['candidate']['rule'], sort_keys=True)}`.", '',
                  f"Filters: `{json.dumps(selection['candidate']['filters'], sort_keys=True)}`.", '',
                  '| Reused-data check, independently reset accounts | Net P&L |', '| --- | ---: |'])
    for name, metrics in winner['checks'].items():
        if name != 'full_4bp':
            lines.append(f'| {name} | ${pnl(metrics):,.2f} |')
    lines.extend(['', 'No profile/export was changed. These are reused historical selection checks, including 2026; fold sums are not a continuous account return. Filters operate on completed hourly signals and use prior-20-hour mean volume. The same broker simulation recalculates position availability, fees, slippage, financing and daily gates. Pine/export reconciliation and future observations remain absent. The generic exporter refuses to omit filters; a faithful export is required before a filtered candidate can be offered for TradingView.', ''])
    report = '\n'.join(lines)
    (args.output/'report.md').write_text(report, encoding='utf-8')
    (ROOT/'reports/v1_4_volume_followup.md').write_text(report, encoding='utf-8')
    for name, digest in plan['protected_profile_hashes'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != digest:
            raise ValueError('Protected v1.4 changed during this run')
    print(f"VOLUME FINISHED net=${pnl(m):.2f} gate={bool(passing)}", flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'artifacts/optimization/round8_volume_geometry')
    run(parser.parse_args())
