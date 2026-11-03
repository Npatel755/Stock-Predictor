"""Rule-only crowding guard: use already-settled funding, not forecasts.

Three fixed thresholds. Select on closed 2020-2023 outcomes, check 2024 once,
then replay fixed later diagnostics. No model or neural network is trained.
"""
from dataclasses import replace
import json

from .exit_research import freeze
from .forward_collection import collection_lock, atomic_json
from .funding_data import collect, align, filter_entries
from .generalization_policy import digest, frozen_profile
from .market_data import utc
from .optimize import subset, pnl
from .paths import ROOT
from .regime_filters import prepare_features, apply_filter, RegimeFilter
from .strategy_lab import plan as parent_plan, load_development, training_rank, validation_rank, detailed, sha


NAME = 'settled_funding_rules_round1'


def directory(root):
    return root/'artifacts/strategy_lab'/NAME


def register(root=ROOT):
    import pandas as pd
    p = parent_plan(root)
    out = directory(root); out.mkdir(parents=True, exist_ok=True)
    path = out/'manifest.json'
    previous = json.loads(path.read_text()) if path.exists() else None
    plan = dict(name=NAME, created_at_utc=previous['created_at_utc'] if previous else str(pd.Timestamp.now(tz='UTC')),
        thresholds_signed_8h_bps=[0., 1., 2.], candidate_count=3,
        strategy='Only accept an original entry if direction * last known settled funding, normalized to eight hours, is <= the fixed threshold.',
        data_policy='Published-checksum verified monthly ETHUSDT funding ZIPs; preserve integer millisecond settlement timestamps. No predicted next funding rate and no price fabrication.',
        publication_lag_hours=1, diagnostic_publication_lag_hours=8,
        stale_rate_limit='Two recorded settlement intervals after assumed availability; any unknown rate at a potential entry rejects the experiment, not just that losing trade.',
        execution_note='Funding is a crowding feature. It does not replace the modeled Breakout fee or 3.3bp/day financing.',
        availability_probe='Only January 2020 schema/availability was inspected before registration; no strategy outcomes on funding were inspected.',
        source='https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History',
        parent_protocol_sha256=p['parent_protocol_sha256'],
        source_sha256={**p['source_sha256'], 'funding_data.py':sha(root/'funding_data.py'), 'funding_rule_lab.py':sha(root/'funding_rule_lab.py')},
        data_hashes=p['data_hashes'], train_period=p['train_period'], validation_period=p['validation_period'],
        selection='Same fixed annual training gate and penalized score. Must improve baseline training score. Freeze the top eligible threshold before checking 2024; audit remains diagnostic even if 2024 fails.',
        chronological_gap_days=7, train_actual_fill_bps=8., sizing_budget_bps=8.,
        all_price_history_consumed=True, independent_future_validation=False,
        future_holdout_access=False, automatic_promotion=False)
    freeze(path, plan)
    return plan


def run(root=ROOT, verify=False):
    with collection_lock(directory(root)/'writer.lock'):
        return _run(root, verify)


def _run(root, verify):
    plan = register(root)
    out = directory(root)
    if (out/'results.json').exists() and not verify:
        return json.loads((out/'results.json').read_text())
    atomic_json(out/'status.json', dict(stage='collecting_pinned_funding_sources'))
    settlements, sources = collect(root)
    freeze(out/'sources.json', dict(sources=sources, rows=len(settlements)))
    settlements.to_parquet(out/'funding.parquet', index=False)
    _, rule, cfg, meta = frozen_profile(root)
    bars = load_development(root, plan)
    cfg = replace(cfg, slippage_bps=8.)
    training_bars = bars[bars.timestamp < utc(plan['train_period'][1])].reset_index(drop=True)
    training = apply_filter(prepare_features(training_bars, rule), RegimeFilter(**meta['entry_filters']))
    rate = align(training, settlements)
    baselines = []
    for year in [2020, 2021, 2022, 2023]:
        b, f = subset(training_bars, training, f'{year}-01-01', min(utc(f'{year+1}-01-01'), utc(plan['train_period'][1])))
        result = detailed(b, f, rule, cfg, out/'training/baseline'/str(year))
        baselines.append(dict(year=year, **result))
    base_rank = training_rank(baselines)
    rows = []
    for threshold in plan['thresholds_signed_8h_bps']:
        filtered = filter_entries(training, rate, threshold)
        folds = []
        for year in [2020, 2021, 2022, 2023]:
            b, f = subset(training_bars, filtered, f'{year}-01-01', min(utc(f'{year+1}-01-01'), utc(plan['train_period'][1])))
            result = detailed(b, f, rule, cfg, out/'training'/f'threshold{threshold}'/str(year))
            folds.append(dict(year=year, **result))
        rank = training_rank(folds)
        rank['eligible'] = rank['eligible'] and rank['score'] > base_rank['score']
        row = dict(threshold_bps=threshold, folds=folds, rank=rank)
        freeze(out/'training'/f'threshold{threshold}.json', row)
        rows.append(row)
        print(f"FUNDING RULE threshold={threshold} score={rank['score']:.2f} eligible={rank['eligible']}", flush=True)
    eligible = [r for r in rows if r['rank']['eligible']]
    selected = max(eligible, key=lambda r: (r['rank']['score'], -r['threshold_bps'])) if eligible else None
    choice = selected['threshold_bps'] if selected else None
    freeze(out/'selection.json', dict(threshold_bps=choice, manifest_sha256=digest(plan), selected_before_validation=True))
    validation = None; audit = []
    if selected:
        previous = bars[bars.timestamp < utc(plan['validation_period'][1])].reset_index(drop=True)
        features = apply_filter(prepare_features(previous, rule), RegimeFilter(**meta['entry_filters']))
        filtered = filter_entries(features, align(features, settlements), choice)
        b, f = subset(previous, filtered, *plan['validation_period'])
        outcome = detailed(b, f, rule, cfg, out/'validation')
        validation = dict(result=outcome, rank=validation_rank(selected, outcome))
        freeze(out/'validation.json', validation)
        features = apply_filter(prepare_features(bars, rule), RegimeFilter(**meta['entry_filters']))
        for lag in [1, 8]:
            filtered = filter_entries(features, align(features, settlements, lag), choice)
            for label, start, end in [('audit_2025', '2025-01-01', '2026-01-01'), ('audit_2026', '2026-01-01', '2026-10-28'), ('full_development', '2023-01-01', '2026-10-28')]:
                b, f = subset(bars, filtered, start, end)
                _, base = subset(bars, features, start, end)
                for slip in [2., 4., 8.]:
                    actual = replace(cfg, slippage_bps=slip)
                    for name, signals, budget in [('funding_rule', f, 8.), ('baseline_8bp_budget', base, 8.), ('original_2bp_budget', base, 2.)]:
                        if lag == 8 and name != 'funding_rule':
                            continue
                        result = detailed(b, signals, rule, actual, out/'audit'/f'lag{lag}'/label/f'{name}_fill{int(slip)}', budget)
                        audit.append(dict(publication_lag_hours=lag, period=label, strategy=name, fill_bps=slip, **result))
                print(f'FUNDING AUDIT lag={lag} {label} complete', flush=True)
    result = dict(manifest_sha256=digest(plan), funding_rows=len(settlements), source_months=len(sources),
                  baseline_training=baselines, baseline_rank=base_rank, training=rows,
                  selected_threshold_bps=choice, validation=validation, audit=audit,
                  independent_future_validation=False, promoted=False)
    freeze(out/'results.json', result)
    atomic_json(out/'status.json', dict(stage='complete', selected_threshold_bps=choice))
    report(root, result)
    if verify:
        freeze(out/'verification.json', dict(results_sha256=sha(out/'results.json'),
            artifacts_sha256={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.suffix in {'.csv','.parquet'}},
            all_candidates_replayed=True, reproduced_exactly=True, independent_future_validation=False))
    return result


def report(root, result):
    lines = ['# Settled-funding entry rules: no learned models', '',
        'Three fixed thresholds (0, 1, 2 basis points per eight hours). Accept an original trade only when its direction times the last known settled funding rate is below the threshold. Funding is normalized using each recorded settlement interval. Assumed publication delay is one hour; a fixed eight-hour delay is a later robustness diagnostic.', '',
        'Raw monthly ETH funding ZIPs and published checksums are retained. Millisecond timestamps, including settlement jitter, are preserved. Missing/stale funding at a potential entry rejects the experiment. This feature does not replace the broker financing or certify Breakout fills.', '',
        f"Source months: {result['source_months']}; real settlements: {result['funding_rows']}. All price outcomes were previously inspected; this is development research, not future validation.", '',
        '| Signed funding cap | Training score | Eligible |', '| --- | ---: | --- |']
    for r in result['training']:
        lines.append(f"| {r['threshold_bps']}bp | {r['rank']['score']:.2f} | {r['rank']['eligible']} |")
    lines += ['', f"Unfiltered training score: {result['baseline_rank']['score']:.2f}. Selected cap: **{result['selected_threshold_bps']}**. 2024 check: `{result['validation']['rank'] if result['validation'] else 'not evaluated: no eligible training candidate'}`.", '',
        '| Period | Delay | Strategy | Fill cost | Net including open marks | Closed net | Drawdown |', '| --- | ---: | --- | ---: | ---: | ---: | ---: |']
    for r in result['audit']:
        m = r['metrics']
        lines.append(f"| {r['period']} | {r['publication_lag_hours']}h | {r['strategy']} | {r['fill_bps']}bp | ${pnl(m):,.2f} | ${r['closed_net']:,.2f} | {m['max_intrabar_drawdown']:.2%} |")
    lines += ['', 'Training and 2024 checks end December 25, leaving seven-day gaps before the next stage. The threshold freezes before 2024 and never changes on later outcomes. Every comparison receives causal 2020-2022 warm-up. No version is promoted and the future holdout remains sealed.', '',
        '[Official funding-history API semantics](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History).', '']
    (root/'reports/settled_funding_rules_round1.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--verify', action='store_true')
    result = run(verify=parser.parse_args().verify)
    print(json.dumps(dict(selected_threshold_bps=result['selected_threshold_bps'], funding_rows=result['funding_rows']), indent=2))
