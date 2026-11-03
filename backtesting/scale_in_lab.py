"""v2 scale-in lab: defer half of the planned risk until a breakout shows follow-through.

The consumed v1.11 ledger loses most at stops hit within two hours of entry.
Each candidate opens half of the $100 planned risk at the frozen v1.11 signal
and adds the second half only after price has moved trigger_r initial-risk
units in favour, either moving the core stop to breakeven with the add-on
stopped at the core entry ('breakeven') or keeping the original stop for both
('original'). Entries, filters, target distance and the 3 ATR trail are the
frozen v1.11 rules. Two independent Broker sub-accounts (core, add-on) are
summed into one $50,000 account; the shared Broker forbids pyramiding, so
execution, fees, financing and stop-first ambiguity handling are unchanged.
Pre-registered chronological research on consumed history; no future access.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
import math

import pandas as pd

from .cost_reserve import BAR, Broker, clean_candles, estimated_round_trip_cost, simulate, sizing_config
from .exit_research import freeze
from .forward_collection import atomic_json, collection_lock
from .generalization_policy import assert_historical_period, digest, frozen_profile
from .market_data import utc
from .optimize import pnl, subset
from .paths import ROOT
from .reporting import safe_value
from .robust_structure_lab import Features, combine
from .strategy_lab import plan as parent_plan, load_development, training_rank, validation_rank, choose_family, detailed, sha


NAME = 'v2_scale_in_round1'
VERSION = 'ETH v2.0 research candidate (scale-in)'
TRAIN_YEARS = (2020, 2021, 2022, 2023)
TRIGGERS, ADDON_STOPS = (.5, 1., 1.5), ('breakeven', 'original')
AUDIT_PERIODS = [('audit_2025', '2025-01-01', '2026-01-01'), ('audit_2026', '2026-01-01', '2026-10-28'),
                 ('full_development', '2023-01-01', '2026-10-28')]


def directory(root):
    return root/'artifacts/strategy_lab'/NAME


def candidates():
    return [dict(id=f'scalein_t{trigger:g}_{stop}', group=stop, trigger_r=trigger, addon_stop=stop)
            for trigger in TRIGGERS for stop in ADDON_STOPS]


def manage(broker, row, rule, cfg):
    p = broker.position
    if p is None:
        return
    held = (row.timestamp+BAR-p.entry_time)/BAR
    if rule.max_holding_bars and held >= rule.max_holding_bars:
        broker.exit(row.close, row.timestamp, 'time_stop', 'research_close')
    elif rule.trail_atr and math.isfinite(row.management_atr):
        proposed = row.close-p.direction*rule.trail_atr*row.management_atr
        tighter = proposed > p.stop if p.direction == 1 else proposed < p.stop
        if tighter and p.direction*(row.close-proposed) > cfg.tick_size:
            p.stop = proposed
            broker.events.append(dict(bar_open=row.timestamp, event='stop_update', price=proposed, effective_at=row.timestamp+BAR))


def quantity_for(cfg, reserve, equity, price, distance):
    risk_distance = distance+estimated_round_trip_cost(reserve, price)
    return math.floor(min(cfg.risk_usd/(risk_distance*cfg.point_value), equity*cfg.max_leverage/(price*cfg.point_value))*1000)/1000


def part(broker, entries, frame, cfg):
    trades = pd.DataFrame(broker.trades)
    net = trades.net_pnl if len(trades) else pd.Series(dtype=float)
    gains, losses = net.clip(lower=0).sum(), -net.clip(upper=0).sum()
    metrics = dict(initial_capital=cfg.initial_capital, final_equity=broker.equity_at(frame.close.iloc[-1]), entries=entries,
                   closed_trade_legs=len(trades), win_rate=float((net > 0).mean()) if len(net) else None,
                   profit_factor=float(gains/losses) if losses else None, max_intrabar_drawdown=broker.max_drawdown,
                   max_closed_equity_drawdown_usd=broker.closed_equity_drawdown_usd, total_commission=broker.total_commission,
                   total_swap=broker.total_swap, margin_call_events=broker.margin_calls,
                   open_position=asdict(broker.position) if broker.position else None)
    return metrics, trades, pd.DataFrame(broker.events)


def simulate_scale_in(bars, rule, cfg, signals, candidate, sizing_slippage_bps=8.):
    """Core half at the v1.11 signal; add-on half after trigger_r of follow-through, next-open fills for both."""
    if cfg.mode != 'research' or cfg.entry_timing != 'next_open':
        raise ValueError('Scale-in research requires next-open Research execution')
    member_cfg = replace(cfg, risk_usd=cfg.risk_usd/2, max_daily_loss=cfg.max_daily_loss/2)
    reserve = sizing_config(member_cfg, sizing_slippage_bps)
    bars, quality = clean_candles(bars)
    if quality['missing_bars']:
        raise ValueError('Scale-in research rejects missing candles')
    frame = signals.reset_index(drop=True)
    if len(frame) != len(bars) or not frame.timestamp.equals(bars.timestamp):
        raise ValueError('Signal rows must match candle timestamps')
    core, addon = Broker(member_cfg), Broker(member_cfg)
    pending_core = pending_addon = plan = None
    counts = dict(core=0, addon=0)
    day, start_equity, entries_today, locked = None, cfg.initial_capital, 0, False
    for row in frame.itertuples(index=False):
        core.bar(row)
        addon.bar(row)
        if pending_core is not None:
            direction, quantity, stop, target, distance = pending_core
            core.enter(direction, quantity, row.open, stop, target, row.timestamp, row.timestamp)
            core.bar(row)
            p = core.position
            plan = None if p is None else dict(direction=direction, entry=p.entry_price, stop=stop, target=target,
                                               level=p.entry_price+direction*candidate['trigger_r']*distance, armed=True)
            pending_core = None
        if pending_addon is not None:
            addon.enter(*pending_addon, row.timestamp, row.timestamp)
            addon.bar(row)
            pending_addon = None
        manage(core, row, rule, member_cfg)
        manage(addon, row, rule, member_cfg)
        if plan is not None and core.position is None:
            plan['armed'] = False
        if plan is not None and plan['armed'] and addon.position is None and plan['direction']*(row.close-plan['level']) >= 0:
            plan['armed'] = False
            d = plan['direction']
            stop = plan['entry'] if candidate['addon_stop'] == 'breakeven' else plan['stop']
            distance = abs(row.close-stop)
            quantity = quantity_for(member_cfg, reserve, addon.equity_at(row.close), row.close, distance) if distance > member_cfg.tick_size else 0.
            if quantity > 0 and not locked and d*(plan['target']-row.close) > member_cfg.tick_size:
                pending_addon = (d, quantity, row.close, stop, plan['target'])
                counts['addon'] += 1
            if candidate['addon_stop'] == 'breakeven':
                p = core.position
                tighter = plan['entry'] > p.stop if d == 1 else plan['entry'] < p.stop
                if tighter:
                    p.stop = plan['entry']
                    core.events.append(dict(bar_open=row.timestamp, event='stop_update', price=plan['entry'], effective_at=row.timestamp+BAR))
        equity = core.equity_at(row.close)+addon.equity_at(row.close)-cfg.initial_capital
        if day != row.timestamp.date():
            day, start_equity, entries_today, locked = row.timestamp.date(), equity, 0, False
        if equity <= start_equity-cfg.max_daily_loss:
            locked = True
        if (row.signal and core.position is None and addon.position is None and pending_addon is None and not locked
                and entries_today < cfg.max_trades_day and math.isfinite(row.signal_atr)):
            direction = int(row.signal)
            distance = rule.stop_atr*row.signal_atr
            quantity = quantity_for(member_cfg, reserve, core.equity_at(row.close), row.close, distance)
            if distance > member_cfg.tick_size and quantity > 0:
                pending_core = (direction, quantity, row.close-direction*distance, row.close+direction*rule.reward_r*distance, distance)
                entries_today += 1
                counts['core'] += 1
        core.mark(row.close)
        addon.mark(row.close)
    parts = [part(core, counts['core'], frame, member_cfg), part(addon, counts['addon'], frame, member_cfg)]
    metrics, trades, events, curve = combine(parts, bars, cfg)
    metrics.update(core_entries=counts['core'], addon_entries=counts['addon'], entries=counts['core'],
                   drawdown_basis='summed core+add-on bar-close curve plus member intrabar excess (upper bound)')
    if len(trades):
        trades['leg'] = trades.member.map({0: 'core', 1: 'addon'})
    return metrics, trades, events, curve


def evaluate(features, candidate, start, end, cfg, out=None, sizing=8.):
    rule, frame = features.member(features.rule.lookback, features.filters['min_rvol'], False)
    b, f = subset(features.bars, frame, start, end)
    if candidate is None:
        if out is not None:
            return detailed(b, f, rule, cfg, out, sizing)
        metrics, trades, _ = simulate(b, rule, cfg, f, sizing_slippage_bps=sizing)
    else:
        metrics, trades, events, curve = simulate_scale_in(b, rule, cfg, f, candidate, sizing)
        if out is not None:
            out.mkdir(parents=True, exist_ok=True)
            trades.to_csv(out/'trades.csv', index=False)
            events.to_csv(out/'events.csv', index=False)
            curve.to_parquet(out/'equity.parquet', index=False)
    return dict(metrics=safe_value(metrics), closed_net=float(trades.net_pnl.sum()) if len(trades) else 0.)


def plan(root=ROOT):
    parent = parent_plan(root)
    assert_historical_period('2026-10-28', root)
    out = directory(root)
    previous = json.loads((out/'manifest.json').read_text()) if (out/'manifest.json').exists() else None
    manifest = dict(name=NAME, version_if_selected=VERSION, parent_version='v1.11', parent_protocol_sha256=parent['parent_protocol_sha256'],
        created_at_utc=previous['created_at_utc'] if previous else str(pd.Timestamp.now(tz='UTC')),
        authorization='User granted discretion on 2026-11-03 to pursue any profitable direction under proper versioning; v1.11 stays frozen and any winner becomes a separately registered v2.0 research candidate.',
        motivation='Consumed v1.11 ledger: stops within two hours lose about $4.8k of $9.4k total stop losses at a 5% win rate; trades that progress are strongly positive. Deferring half the risk until follow-through targets that asymmetry without changing entries or thresholds. robust_structure_round1 showed wider stops, de-chasing and parameter ensembles do not help.',
        candidates=candidates(), candidate_count=len(candidates()), groups=list(ADDON_STOPS),
        structure=dict(core_risk_usd=50., addon_risk_usd=50., trigger_r=list(TRIGGERS), addon_stops=list(ADDON_STOPS),
                       addon_trigger='bar close beyond core entry + trigger_r * initial stop distance while the core trade is open; add-on fills at the next open',
                       addon_target='same price as the core target; 3 ATR trail applies to both legs', member_daily_loss_usd=150., combined_daily_loss_usd=300.),
        train_period=parent['train_period'], train_folds=parent['train_folds'], validation_period=parent['validation_period'],
        chronological_gap_days=7, audit_period=parent['audit_period'], scoring=parent['scoring'],
        train_gate=parent['train_gate']+' The penalized training score must also exceed the same-budget v1.11 replica.',
        validation='The top eligible training candidate per add-on stop group enters 2024; it also needs positive closed net, >=10 closed trades, <=5% drawdown and no margin calls.',
        final_choice='Among eligible 2024 candidates choose max(min(median training closed net, validation closed net) - 0.5*validation drawdown*$50000); tie by lexicographic id. No audit outcome selects this choice.',
        cost_scenarios_bps=[2., 4., 8.], sizing_budget_bps=8., risk_usd=100., initial_capital=50000.,
        full_development_period=['2023-01-01', '2026-10-28'], improvement_gate=parent['improvement_gate'],
        registration='Only if the frozen selection also passes the historical improvement gate is candidates/eth_v2_0 written, unpromoted, with its own prospective protocol.',
        all_dates_previously_inspected=True, independent_out_of_sample=False, threshold_changes_after_results=False,
        whole_history_profit_selection=False, future_holdout_access=False, automatic_version_promotion=False,
        data_hashes=parent['data_hashes'],
        source_sha256={**parent['source_sha256'], 'robust_structure_lab.py': sha(root/'robust_structure_lab.py'), 'scale_in_lab.py': sha(root/'scale_in_lab.py')})
    out.mkdir(parents=True, exist_ok=True)
    freeze(out/'manifest.json', manifest)
    return manifest


def run(root=ROOT, verify=False):
    with collection_lock(directory(root)/'writer.lock'):
        return _run(root, verify)


def _run(root, verify):
    manifest = plan(root)
    out = directory(root)
    if (out/'results.json').exists() and not verify:
        result = json.loads((out/'results.json').read_text())
        if result['manifest_sha256'] != digest(manifest):
            raise ValueError('Lab results do not match the pinned experiment')
        return result
    _, baseline_rule, cfg, meta = frozen_profile(root)
    filters = meta['entry_filters']
    cfg = replace(cfg, slippage_bps=8.)
    bars = load_development(root, manifest)
    train_end = utc(manifest['train_period'][1])
    training_features = Features(bars[bars.timestamp < train_end].reset_index(drop=True), baseline_rule, filters)

    def folds(candidate):
        return [dict(year=year, **evaluate(training_features, candidate, f'{year}-01-01', min(utc(f'{year+1}-01-01'), train_end), cfg))
                for year in TRAIN_YEARS]

    baseline_folds = folds(None)
    base_rank = training_rank(baseline_folds)
    (out/'training').mkdir(parents=True, exist_ok=True)
    freeze(out/'training'/'baseline_v1_11_8bp_budget.json', dict(folds=baseline_folds, rank=base_rank, manifest_sha256=digest(manifest)))
    rows = []
    for candidate in manifest['candidates']:
        path = out/'training'/f"{candidate['id']}.json"
        if path.exists() and not verify:
            row = json.loads(path.read_text())
            if row['candidate'] != candidate or row['manifest_sha256'] != digest(manifest):
                raise ValueError('Training checkpoint changed identity')
        else:
            fold_rows = folds(candidate)
            rank = training_rank(fold_rows)
            rank['eligible'] = bool(rank['eligible'] and rank['score'] > base_rank['score'])
            row = dict(candidate=candidate, folds=fold_rows, rank=rank, manifest_sha256=digest(manifest))
            freeze(path, row)
        rows.append(row)
        print(f"TRAIN {candidate['id']} score={row['rank']['score']:.2f} eligible={row['rank']['eligible']}", flush=True)
        atomic_json(out/'status.json', dict(stage='training', complete=len(rows), total=len(manifest['candidates'])))
    shortlist = [choose_family([r for r in rows if r['candidate']['group'] == group]) for group in ADDON_STOPS]
    freeze(out/'training_selection.json', dict(manifest_sha256=digest(manifest), baseline_training_score=base_rank['score'],
                                               candidate_ids=[r['candidate']['id'] for r in shortlist]))
    preceding = Features(bars[bars.timestamp < utc(manifest['validation_period'][1])].reset_index(drop=True), baseline_rule, filters)
    validation = []
    for training in shortlist:
        candidate = training['candidate']
        result = evaluate(preceding, candidate, *manifest['validation_period'], cfg, out/'validation'/candidate['id'])
        row = dict(candidate=candidate, result=result, rank=validation_rank(training, result))
        freeze(out/'validation'/f"{candidate['id']}.json", row)
        validation.append(row)
        print(f"VALIDATION {candidate['id']} closed={result['closed_net']:.2f} eligible={row['rank']['eligible']}", flush=True)
    baseline_validation = evaluate(preceding, None, *manifest['validation_period'], cfg)
    eligible = [r for r in validation if r['rank']['eligible']]
    selected = max(eligible, key=lambda r: (r['rank']['score'], r['candidate']['id']))['candidate'] if eligible else None
    freeze(out/'selection.json', dict(manifest_sha256=digest(manifest), candidate=selected,
                                      reason='Passed fixed train/2024 gates' if selected else 'No candidate passed both fixed gates',
                                      selected_before_audit=True, historical_selection=True, independent_validation=False, promoted=False))
    audit, comparison = [], {}
    if selected:
        full = Features(bars, baseline_rule, filters)
        for label, begin, end in AUDIT_PERIODS:
            for slip in manifest['cost_scenarios_bps']:
                actual = replace(cfg, slippage_bps=slip)
                for name, candidate, budget in [('challenger', selected, 8.), ('v1.11_original_budget', None, 2.), ('v1.12_8bp_budget', None, 8.)]:
                    result = evaluate(full, candidate, begin, end, actual, out/'audit'/label/f'{name}_fill{int(slip)}', budget)
                    audit.append(dict(period=label, strategy=name, fill_bps=slip, sizing_budget_bps=budget, **result))
            print(f'AUDIT {label} complete; selection remains frozen', flush=True)
        development = [r for r in audit if r['period'] == 'full_development']
        pick = lambda strategy, slip: next(r for r in development if r['strategy'] == strategy and r['fill_bps'] == slip)
        comparison = dict(higher_main=pnl(pick('challenger', 2.)['metrics']) > pnl(pick('v1.11_original_budget', 2.)['metrics']),
                          higher_stressed=pnl(pick('challenger', 8.)['metrics']) > pnl(pick('v1.11_original_budget', 8.)['metrics']),
                          drawdown_limit=all(r['metrics']['max_intrabar_drawdown'] <= .05 for r in development if r['strategy'] == 'challenger'),
                          positive_later_annual_closed=all(r['closed_net'] > 0 for r in audit if r['strategy'] == 'challenger'
                                                           and r['period'] != 'full_development' and r['fill_bps'] == 8.))
    passed = bool(comparison and all(comparison.values()))
    result = dict(manifest_sha256=digest(manifest), baseline_training=dict(folds=baseline_folds, rank=base_rank),
                  baseline_validation=baseline_validation, training=rows, shortlist=[r['candidate']['id'] for r in shortlist],
                  validation=validation, selected=selected, audit=audit, comparison_checks=comparison,
                  historical_comparison_passed=passed, candidate_registered=passed, candidate_directory='candidates/eth_v2_0' if passed else None,
                  prospective_validation_complete=False, promoted=False, prior_history_selection_slots=848,
                  prior_lab_slots=24+12+3+6+1+10, new_candidate_slots=len(manifest['candidates']), sources_already_consumed=True)
    freeze(out/'results.json', result)
    if passed:
        register(root, manifest, result, cfg)
    atomic_json(out/'status.json', dict(stage='complete', candidates=len(manifest['candidates']), selected=selected, historical_comparison_passed=passed))
    report(root, result)
    if verify:
        freeze(out/'verification.json', dict(results_sha256=sha(out/'results.json'),
            artifacts_sha256={str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.suffix in {'.csv', '.parquet'}},
            all_training_replayed=True, validation_and_audit_replayed=True, reproduced_exactly=True, forward_validation=False))
    return result


def register(root, manifest, result, cfg):
    """Write the unpromoted v2.0 research candidate with its own prospective protocol; never touches v1.11."""
    _, rule, base_cfg, meta = frozen_profile(root)
    folder = root/'candidates/eth_v2_0'
    folder.mkdir(parents=True, exist_ok=True)
    config = dict(version=VERSION, parent_version='v1.11', parent_configuration_sha256=meta['configuration_sha256'],
                  strategy=dict(rule=asdict(rule), execution=asdict(base_cfg), filters=meta['entry_filters']),
                  scale_in=dict(core_risk_usd=50., addon_risk_usd=50., trigger_r=result['selected']['trigger_r'], addon_stop=result['selected']['addon_stop'],
                                addon_entry='next open after a bar closes beyond core entry + trigger_r * initial stop distance while the core trade is open',
                                addon_target='core target', trail_atr=rule.trail_atr, member_daily_loss_usd=150.),
                  sizing_slippage_bps=8., promoted=False, independent_forward_validation=False, ready_for_funded_trading=False,
                  selected_by='v2_scale_in_round1 frozen train/2024 gates; 2025-2026 are consumed diagnostics')
    freeze(folder/'config.json', config)
    protocol = dict(candidate=VERSION, created_at_utc=str(pd.Timestamp.now(tz='UTC')), lab=NAME, lab_manifest_sha256=result['manifest_sha256'],
                    candidate_sha256=sha(folder/'config.json'), change='Half risk at the v1.11 signal, half after follow-through; no entry, filter, target or trail changes.',
                    number_of_candidate_hypotheses=len(manifest['candidates']), optimizer_enabled=False,
                    historical_period=['2023-01-01', '2026-10-28'], historical_data_already_inspected=True, development_outcomes_may_change_candidate=False,
                    future_period=['2026-11-04 00:00:00+00:00', '2027-05-03 00:00:00+00:00'], final_evaluation_only=True,
                    minimum_closed_trades=30, maximum_drawdown=.05,
                    primary_comparison='At 8bp actual fills over the future period: net above the unchanged v1.11 run on the same data and <=5% drawdown; v1.11 net must be positive for a relative claim.',
                    additional_checks='Positive net at 2/4/8bp fills, no margin calls, >=30 closed legs, positive lower seven-day-block bootstrap interval at 8bp.',
                    bootstrap=dict(seed=20261104, draws=10000, block_days=7), promotion_automatic=False, ready_for_funded_trading=False,
                    source_sha256=manifest['source_sha256'])
    freeze(folder/'protocol.json', protocol)
    (folder/'README.md').write_text('\n'.join([f'# {VERSION}', '',
        'Unpromoted research candidate produced by the pre-registered v2_scale_in_round1 lab. It keeps every v1.11 entry, filter, target and trailing rule and changes only how the $100 planned risk is deployed: $50 at the signal and $50 after follow-through.', '',
        'All 2020-2026 data used to select it was previously inspected; the only admissible evidence of generalization is the sealed future period in protocol.json, evaluated once after 2027-05-03. v1.11 remains the frozen strategy. Nothing here is live-trading or funded-account readiness.', '']), encoding='utf-8')


def money(value):
    return '$'+format(value, ',.2f')


def report(root, result):
    base = result['baseline_training']['rank']
    lines = ['# v2 scale-in candidates: half risk at the signal, half after follow-through', '',
             'Six predefined candidates keep every frozen v1.11 entry, filter, target and trailing rule and change only how the $100 planned risk is deployed: a $50 core leg at the signal and a $50 add-on leg after price closes trigger_r (0.5/1.0/1.5) initial-risk units in favour, either moving the core stop to breakeven with the add-on stopped at the core entry, or keeping the original stop for both. Both legs fill at the next open and target the core target. Two independent Broker sub-accounts are summed into one $50,000 account, so execution, fees, financing and stop-first handling are the shared frozen code.', '',
             '**All dates were previously inspected. This is development research, not an untouched holdout or evidence of future profitability.** v1.11 and its forward protocol are untouched. Failed candidates and the frozen shortlist/selection are retained.', '',
             'Training uses 2020-2023 annual closed outcomes at 8bp fills and must beat the same-budget v1.11 replica (score '+format(base['score'], '.2f')+', median annual closed '+money(base['median_closed_net'])+'). The top eligible candidate per add-on-stop group is checked on 2024 (v1.11 same budget: '+money(result['baseline_validation']['closed_net'])+'). Execution ends December 25 in 2023 and 2024, leaving seven-day gaps. The selection is frozen before 2025-2026 outcomes.', '',
             '| Candidate | Training score | Median annual closed | Eligible training | 2024 closed net | 2024 drawdown | Eligible 2024 |', '| --- | ---: | ---: | --- | ---: | ---: | --- |']
    validation = {r['candidate']['id']: r for r in result['validation']}
    for row in result['training']:
        name = row['candidate']['id']; v = validation.get(name)
        lines.append('| '+' | '.join([name, format(row['rank']['score'], '.2f'), money(row['rank']['median_closed_net']), str(row['rank']['eligible']),
                                      money(v['result']['closed_net']) if v else 'Not shortlisted', format(v['result']['metrics']['max_intrabar_drawdown'], '.2%') if v else '',
                                      str(v['rank']['eligible']) if v else 'Not evaluated'])+' |')
    lines += ['', 'Selected before audit: **'+(result['selected']['id'] if result['selected'] else 'None: no candidate passed both gates')+'**.', '',
              '| Period | Strategy | Actual slippage | Net including open marks | Closed net | Drawdown | Core entries | Closed legs |', '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for row in result['audit']:
        m = row['metrics']
        lines.append('| '+' | '.join([row['period'], row['strategy'], f"{row['fill_bps']}bp", money(pnl(m)), money(row['closed_net']), format(m['max_intrabar_drawdown'], '.2%'), str(m['entries']), str(m['closed_trade_legs'])])+' |')
    lines += ['', f"Historical comparison checks: `{result['comparison_checks']}`. Historical comparison passed: **{result['historical_comparison_passed']}**. "
              + ('The frozen selection was registered as an unpromoted research candidate in `candidates/eth_v2_0` with its own sealed prospective protocol.' if result['candidate_registered'] else 'No candidate was registered or promoted.'), '',
              'Scale-in drawdowns are the summed core+add-on bar-close curve plus each leg\'s intrabar excess, an upper bound; v1.11 drawdowns are intrabar. Closed legs count core and add-on exits separately. Annual accounts reset and are not summed as a continuous return.', '',
              f"848 earlier logged search slots, {result['prior_lab_slots']} earlier lab candidates and these {result['new_candidate_slots']} are known research exposure, not a complete trial count. Consumed data cannot become unseen again; only the sealed future period can validate the candidate.", '']
    (root/'reports'/f'{NAME}.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    outcome = run(verify=parser.parse_args().verify)
    print(json.dumps(dict(selected=outcome['selected'], historical_comparison_passed=outcome['historical_comparison_passed'],
                          comparison_checks=outcome['comparison_checks'], candidate_registered=outcome['candidate_registered']), indent=2))
