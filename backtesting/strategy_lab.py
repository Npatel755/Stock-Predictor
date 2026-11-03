"""Bounded alternative-strategy experiment; chronological development only.

User-authorized new strategy research does not reopen whole-history profit
campaigns or the sealed future test. Every failed candidate is retained.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import json

import numpy as np
import pandas as pd

from .cost_reserve import simulate
from .exit_research import freeze
from .forward_collection import atomic_json, collection_lock
from .frozen_inputs import recorded_path
from .generalization_policy import assert_historical_period, digest, frozen_profile
from .independent_visuals import equity_curve
from .market_data import BAR, load_history, utc
from .optimize import pnl, subset
from .paths import ROOT
from .regime_filters import RegimeFilter, apply_filter, prepare_features
from .reporting import safe_value
from .strategy_lab_signals import FAMILIES, LabRule, prepare


NAME = 'alternative_families_round1'
TRAIN_YEARS = (2020, 2021, 2022, 2023)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidates():
    return [dict(id=f'{family}_{hours}h_{profile}', rule=asdict(LabRule(family, hours, *geometry)))
            for family in FAMILIES for hours in [1, 4]
            for profile, geometry in [('balanced', (2., 3., 3.)), ('patient', (3., 5., 4.))]]


def directory(root):
    return root/'artifacts/strategy_lab'/NAME


def plan(root=ROOT):
    policy, _, _, meta = frozen_profile(root)
    assert_historical_period('2026-10-28', root)
    parent = json.loads((root/f"artifacts/optimization/{meta['experiment']}/manifest.json").read_text())
    out = directory(root)
    previous = json.loads((out/'manifest.json').read_text()) if (out/'manifest.json').exists() else None
    sources = list(policy['algorithms']) + ['strategy_lab.py', 'strategy_lab_signals.py',
        'cost_reserve.py', 'market_data.py', 'eth_research/data.py', 'independent_visuals.py',
        'generalization_policy.py', 'optimize.py', 'forward_collection.py', 'frozen_inputs.py']
    manifest = dict(name=NAME, parent_protocol_sha256=digest(policy),
        created_at_utc=previous['created_at_utc'] if previous else str(pd.Timestamp.now(tz='UTC')),
        authorization='User requested continued improvement and new strategies on 2026-11-03. This scope permits a bounded training-only experiment, not historical-profit-only promotion or future holdout access.',
        candidates=candidates(), candidate_count=24,
        train_period=['2020-01-01', '2023-12-25'], train_folds='Four independently reset annual accounts; 2023 ends December 25; causal prior indicator history within training only.',
        validation_period=['2024-01-01', '2024-12-25'], chronological_gap_days=7,
        audit_period=['2025-01-01', '2026-10-28'],
        scoring='Use CLOSED net at 8bp actual slippage and fixed 8bp sizing. median(annual closed net) - worst annual loss - 0.5*max(annual intrabar drawdown*$50000).',
        train_gate='>=4 closed trades per year, >=30 total, >=3 of 4 years positive, no margin calls, <=5% drawdown in every year, positive penalized score.',
        validation='Only the top training candidate per family enters 2024; a candidate also needs positive closed net, >=10 closed trades, <=5% drawdown, no margin calls.',
        final_choice='Among eligible training/2024 candidates choose max(min(median training closed net, validation closed net) - 0.5*validation drawdown*$50000); tie by lexicographic candidate id. No audit outcome selects this choice.',
        cost_scenarios_bps=[2., 4., 8.], sizing_budget_bps=8.,
        risk_usd=100., initial_capital=50000.,
        full_development_period=['2023-01-01', '2026-10-28'],
        improvement_gate='Selected challenger must beat original v1.11 full-development main net and its fixed-2bp-budget 8bp stress net, keep <=5% drawdown at every cost, and have positive annual closed net in 2025 and 2026 at 8bp. This is still consumed historical evidence, not future validation.',
        all_dates_previously_inspected=True, independent_out_of_sample=False,
        threshold_changes_after_results=False, whole_history_profit_selection=False,
        future_holdout_access=False, automatic_version_promotion=False,
        data_hashes=parent['data_hashes'],
        source_sha256={name: sha(root/name) for name in sources})
    out.mkdir(parents=True, exist_ok=True)
    freeze(out/'manifest.json', manifest)
    return manifest


def load_development(root, manifest):
    parts = []
    for name, expected in manifest['data_hashes'].items():
        path = recorded_path(root, name, expected)
        bars, _ = load_history(path)
        parts.append(bars)
    bars = pd.concat(parts, ignore_index=True).sort_values('timestamp').reset_index(drop=True)
    bars = bars[(bars.timestamp >= utc('2020-01-01')) & (bars.timestamp < utc('2026-10-28'))].reset_index(drop=True)
    if bars.timestamp.duplicated().any() or not bars.timestamp.diff().dropna().eq(BAR).all():
        raise ValueError('Lab requires exact, continuous native ETH candles through the declared cutoff')
    return bars


def training_rank(folds):
    profits = [f['closed_net'] for f in folds]
    eligible = (len(folds) == 4 and min(f['metrics']['closed_trade_legs'] for f in folds) >= 4
                and sum(f['metrics']['closed_trade_legs'] for f in folds) >= 30
                and sum(p > 0 for p in profits) >= 3
                and all(f['metrics']['margin_call_events'] == 0 and f['metrics']['max_intrabar_drawdown'] <= .05 for f in folds))
    score = float(np.median(profits)-max(0., -min(profits))
                  -.5*max(f['metrics']['max_intrabar_drawdown']*50000 for f in folds))
    return dict(score=score, eligible=bool(eligible and score > 0), median_closed_net=float(np.median(profits)))


def choose_family(rows):
    """One winner per family, even if all failed; failures stay ineligible."""
    return max(rows, key=lambda r: (r['rank']['eligible'], r['rank']['score'], r['candidate']['id']))


def validation_rank(training, result):
    metrics = result['metrics']
    eligible = (training['rank']['eligible'] and result['closed_net'] > 0
                and metrics['closed_trade_legs'] >= 10 and metrics['max_intrabar_drawdown'] <= .05
                and metrics['margin_call_events'] == 0)
    score = min(training['rank']['median_closed_net'], result['closed_net'])-.5*metrics['max_intrabar_drawdown']*50000
    return dict(eligible=bool(eligible), score=float(score))


def evaluate(bars, signals, rule, cfg, sizing=8.):
    metrics, trades, events = simulate(bars, rule, cfg, signals, sizing_slippage_bps=sizing)
    return dict(metrics=safe_value(metrics), closed_net=float(trades.net_pnl.sum()) if len(trades) else 0.), trades, events


def detailed(bars, features, rule, cfg, out, sizing=8.):
    out.mkdir(parents=True, exist_ok=True)
    result, trades, events = evaluate(bars, features, rule, cfg, sizing)
    curve = equity_curve(bars, events, cfg)
    if abs(curve.equity.iloc[-1]-result['metrics']['final_equity']) > 1e-6:
        raise ValueError('Lab visual equity does not reconcile with fills')
    trades.to_csv(out/'trades.csv', index=False)
    events.to_csv(out/'events.csv', index=False)
    curve.to_parquet(out/'equity.parquet', index=False)
    return result


def run(root=ROOT, verify=False):
    with collection_lock(directory(root)/'writer.lock'):
        return _run(root, verify)


def _run(root, verify):
    manifest = plan(root)
    out = directory(root)
    old_results = out/'results.json'
    if old_results.exists() and not verify:
        result = json.loads(old_results.read_text())
        if result['manifest_sha256'] != digest(manifest):
            raise ValueError('Lab results do not match the pinned experiment')
        return result
    _, baseline_rule, cfg, meta = frozen_profile(root)
    cfg = replace(cfg, slippage_bps=8.)
    bars = load_development(root, manifest)
    train_bars = bars[bars.timestamp < utc(manifest['train_period'][1])].reset_index(drop=True)
    rows = []
    for family in FAMILIES:
        for hours in [1, 4]:
            group = [c for c in manifest['candidates'] if c['rule']['family'] == family and c['rule']['timeframe_hours'] == hours]
            features = None
            for candidate in group:
                path = out/'training'/f"{candidate['id']}.json"
                if path.exists() and not verify:
                    row = json.loads(path.read_text())
                    if row['candidate'] != candidate or row['manifest_sha256'] != digest(manifest):
                        raise ValueError('Training checkpoint changed identity')
                    rows.append(row)
                    continue
                rule = LabRule(**candidate['rule'])
                if features is None:
                    features = prepare(train_bars, rule)
                folds = []
                for year in TRAIN_YEARS:
                    b, f = subset(train_bars, features, f'{year}-01-01', min(utc(f'{year+1}-01-01'), utc(manifest['train_period'][1])))
                    result, _, _ = evaluate(b, f, rule.execution_rule(), cfg)
                    folds.append(dict(year=year, **result))
                row = dict(candidate=candidate, folds=folds, rank=training_rank(folds), manifest_sha256=digest(manifest))
                path.parent.mkdir(parents=True, exist_ok=True)
                freeze(path, row)
                rows.append(row)
                print(f"TRAIN {candidate['id']} score={row['rank']['score']:.2f} eligible={row['rank']['eligible']}", flush=True)
                atomic_json(out/'status.json', dict(stage='training', complete=len(rows), total=24))
    family_winners = [choose_family([r for r in rows if r['candidate']['rule']['family'] == family]) for family in FAMILIES]
    # This freezes the family shortlist before any validation outcome is read.
    freeze(out/'training_selection.json', dict(manifest_sha256=digest(manifest),
                                               candidate_ids=[r['candidate']['id'] for r in family_winners]))
    preceding = bars[bars.timestamp < utc(manifest['validation_period'][1])].reset_index(drop=True)
    validation = []
    for training in family_winners:
        candidate = training['candidate']
        rule = LabRule(**candidate['rule'])
        features = prepare(preceding, rule)
        b, f = subset(preceding, features, *manifest['validation_period'])
        result = detailed(b, f, rule.execution_rule(), cfg, out/'validation'/candidate['id'])
        row = dict(candidate=candidate, result=result, rank=validation_rank(training, result))
        freeze(out/'validation'/f"{candidate['id']}.json", row)
        validation.append(row)
        print(f"VALIDATION {candidate['id']} closed={result['closed_net']:.2f} eligible={row['rank']['eligible']}", flush=True)
    eligible = [r for r in validation if r['rank']['eligible']]
    selected = max(eligible, key=lambda r: (r['rank']['score'], r['candidate']['id']))['candidate'] if eligible else None
    freeze(out/'selection.json', dict(manifest_sha256=digest(manifest), candidate=selected,
                                      reason='Passed fixed train/2024 gates' if selected else 'No new family passed both fixed gates',
                                      selected_before_audit=True, historical_selection=True,
                                      independent_validation=False, promoted=False))
    audit, comparison = [], []
    if selected:
        rule = LabRule(**selected['rule'])
        features = prepare(bars, rule)
        base_features = apply_filter(prepare_features(bars, baseline_rule), RegimeFilter(**meta['entry_filters']))
        for label, begin, end in [('audit_2025', '2025-01-01', '2026-01-01'),
                                   ('audit_2026', '2026-01-01', '2026-10-28'),
                                   ('full_development', '2023-01-01', '2026-10-28')]:
            b, f = subset(bars, features, begin, end)
            _, base = subset(bars, base_features, begin, end)
            for slip in [2., 4., 8.]:
                actual = replace(cfg, slippage_bps=slip)
                for name, signal, geometry, budget in [('challenger', f, rule.execution_rule(), 8.),
                                                       ('v1.11_original_budget', base, baseline_rule, 2.),
                                                       ('v1.12_8bp_budget', base, baseline_rule, 8.)]:
                    result = detailed(b, signal, geometry, actual, out/'audit'/label/f'{name}_fill{int(slip)}', budget)
                    audit.append(dict(period=label, strategy=name, actual_fill_slippage_bps=slip,
                                      sizing_budget_bps=budget, **result))
            print(f'AUDIT {label} complete; selection remains frozen', flush=True)
        full = [r for r in audit if r['period'] == 'full_development']
        cmain = next(r for r in full if r['strategy'] == 'challenger' and r['actual_fill_slippage_bps'] == 2.)
        bmain = next(r for r in full if r['strategy'] == 'v1.11_original_budget' and r['actual_fill_slippage_bps'] == 2.)
        cstress = next(r for r in full if r['strategy'] == 'challenger' and r['actual_fill_slippage_bps'] == 8.)
        bstress = next(r for r in full if r['strategy'] == 'v1.11_original_budget' and r['actual_fill_slippage_bps'] == 8.)
        # Historical benchmark also depends on indicator initialization. This
        # lab fairly gives every rule causal 2020-2022 warm-up before 2023.
        comparison = dict(higher_main=pnl(cmain['metrics']) > pnl(bmain['metrics']),
                          higher_stressed=pnl(cstress['metrics']) > pnl(bstress['metrics']),
                          drawdown_limit=all(r['metrics']['max_intrabar_drawdown'] <= .05 for r in full if r['strategy'] == 'challenger'),
                          positive_later_annual_closed=all(r['closed_net'] > 0 for r in audit if r['strategy'] == 'challenger' and r['period'] != 'full_development' and r['actual_fill_slippage_bps'] == 8.))
    result = dict(manifest_sha256=digest(manifest), training=rows, validation=validation,
                  selected=selected, audit=audit, comparison_checks=comparison,
                  historical_comparison_passed=bool(comparison and all(comparison.values())),
                  prospective_validation_complete=False, promoted=False,
                  prior_history_selection_slots=848, new_candidate_slots=24,
                  sources_already_consumed=True)
    freeze(old_results, result)
    atomic_json(out/'status.json', dict(stage='complete', candidates=24, selected=selected,
                                       historical_comparison_passed=result['historical_comparison_passed']))
    report(root, result)
    if verify:
        freeze(out/'verification.json', dict(results_sha256=sha(old_results), all_training_replayed=True,
                                            validation_and_audit_replayed=True,
                                            reproduced_exactly=True, forward_validation=False))
    return result


def report(root, result):
    lines = ['# Alternative strategy families: bounded chronological development', '',
             '24 predefined candidates: six families, 1h/4h signals, two fixed exit profiles. Fixed $100 planned risk, 8bp sizing budget, real five-minute ETH futures execution, fees, financing and stop-first ambiguity handling. No future data is used.', '',
             '**All dates were previously inspected. This is development research, not an untouched holdout or evidence of future profitability.** The original strategy and forward protocols are preserved. Failed candidates and the exact shortlist/selection are retained.', '',
             'Training selection uses 2020-2023 annual closed outcomes at 8bp fills. The top training candidate per family is checked on 2024. Both 2023 and 2024 execution end December 25, leaving a seven-day gap before the next selection/evaluation stage. Open outcomes are excluded from selection. The final choice is frozen before 2025-2026 diagnostic outcomes. These diagnostics never change that choice.', '',
             '| Candidate | Training score | Eligible training | 2024 closed net | Eligible 2024 |',
             '| --- | ---: | --- | ---: | --- |']
    validation = {r['candidate']['id']: r for r in result['validation']}
    for row in result['training']:
        name = row['candidate']['id']; v = validation.get(name)
        lines.append(f"| {name} | {row['rank']['score']:.2f} | {row['rank']['eligible']} | {('$'+format(v['result']['closed_net'], ',.2f')) if v else 'Not shortlisted'} | {v['rank']['eligible'] if v else 'Not evaluated'} |")
    lines += ['', f"Selected before audit: **{result['selected']['id'] if result['selected'] else 'None: no family passed both gates'}**.", '',
              '| Period | Strategy | Actual slippage | Net including open marks | Closed net | Intrabar drawdown | Entries |',
              '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for row in result['audit']:
        m = row['metrics']
        lines.append(f"| {row['period']} | {row['strategy']} | {row['actual_fill_slippage_bps']}bp | ${pnl(m):,.2f} | ${row['closed_net']:,.2f} | {m['max_intrabar_drawdown']:.2%} | {m['entries']} |")
    lines += ['', f"Historical comparison checks: `{result['comparison_checks']}`. Historical comparison passed: **{result['historical_comparison_passed']}**. No version is automatically promoted.", '',
              'All comparisons have causal prior 2020-2022 indicator warm-up before the 2023 benchmark. This can differ from the saved $12,814.03 run, which initialized indicators at the start of 2023; neither history nor initialization is adjusted after outcomes. Annual accounts reset and their nets are not summed as a continuous return.', '',
              '848 earlier logged search slots, plus one cost-reserve hypothesis and these 24 alternatives, are known research exposure. This is not a complete independent trial count. A new winner would need its own preregistered future test; consumed venue/asset data cannot become unseen again.', '']
    (root/'reports/alternative_families_round1.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    result = run(verify=parser.parse_args().verify)
    print(json.dumps(dict(selected=result['selected'], historical_comparison_passed=result['historical_comparison_passed'],
                          comparison_checks=result['comparison_checks']), indent=2))
