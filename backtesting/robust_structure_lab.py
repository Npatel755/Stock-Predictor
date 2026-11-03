"""Structural robustness lab: wider stops, a fresh-breakout guard, parameter ensembles.

Pre-registered chronological development research on consumed history. The
candidates change trade structure rather than tuning another entry threshold:
most v1.11 losses are stops hit within two hours of a breakout whose own range
exceeds the 1.5 ATR stop. Nothing here reopens whole-history profit search or
reads the sealed future test, and every failed candidate is retained.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import json

import numpy as np
import pandas as pd

from .cost_reserve import simulate
from .exit_research import freeze
from .forward_collection import atomic_json, collection_lock
from .generalization_policy import assert_historical_period, digest, frozen_profile
from .independent_visuals import equity_curve
from .indicators import resample_complete
from .market_data import utc
from .optimize import pnl, subset
from .paths import ROOT
from .regime_filters import RegimeFilter, apply_filter, prepare_features
from .reporting import safe_value
from .strategy_lab import (plan as parent_plan, load_development, training_rank, validation_rank,
                           choose_family, detailed, sha)


NAME = 'robust_structure_round1'
TARGET_ATR = 8.25  # v1.11 target distance: 1.5 ATR stop * 5.5R, held fixed while the stop widens
GROUPS = ('stop_geometry', 'fresh_breakout_guard', 'parameter_ensemble')
TRAIN_YEARS = (2020, 2021, 2022, 2023)
FRESH_WINDOW_HOURS, FRESH_MAX_PRIOR = 72, 2
AUDIT_PERIODS = [('audit_2025', '2025-01-01', '2026-01-01'), ('audit_2026', '2026-01-01', '2026-10-28'),
                 ('full_development', '2023-01-01', '2026-10-28')]


def directory(root):
    return root/'artifacts/strategy_lab'/NAME


def candidates():
    rows = [dict(id=f'stop{stop:g}_target{TARGET_ATR:g}', group='stop_geometry', stop_atr=stop, fresh_guard=False, members=None)
            for stop in [2., 2.5, 3.]]
    rows += [dict(id=f'fresh72_stop{stop:g}', group='fresh_breakout_guard', stop_atr=stop, fresh_guard=True, members=None)
             for stop in [1.5, 2., 2.5, 3.]]
    grids = dict(lookback=[(length, 2.8) for length in (48, 72, 96)],
                 rvol=[(72, rvol) for rvol in (2.4, 2.8, 3.2)],
                 grid=[(length, rvol) for length in (48, 72, 96) for rvol in (2.4, 2.8, 3.2)])
    rows += [dict(id=f'ensemble_{name}_{len(members)}', group='parameter_ensemble', stop_atr=1.5, fresh_guard=False,
                  members=[dict(lookback=length, min_rvol=rvol) for length, rvol in members]) for name, members in grids.items()]
    return rows


def baseline_candidate():
    return dict(id='v1.11', group='baseline', stop_atr=1.5, fresh_guard=False, members=None)


def geometry(rule, candidate):
    return replace(rule, stop_atr=candidate['stop_atr'], reward_r=TARGET_ATR/candidate['stop_atr'])


def fresh_guard(bars, features, rule, window=FRESH_WINDOW_HOURS, max_prior=FRESH_MAX_PRIOR):
    """Reject an entry preceded by more than max_prior same-direction raw channel breakouts in the prior completed hours."""
    hours = resample_complete(bars, '1h')
    c = hours.close
    upper = hours.high.shift().rolling(rule.lookback).max()
    lower = hours.low.shift().rolling(rule.lookback).min()
    slow = c.ewm(span=rule.slow, adjust=False).mean()
    raw = pd.Series(np.where((c > upper) & (c > slow), 1, np.where((c < lower) & (c < slow), -1, 0)), index=hours.index)
    counts = pd.DataFrame(dict(up=raw.eq(1).astype(float).shift().rolling(window, min_periods=1).sum().to_numpy(),
                               down=raw.eq(-1).astype(float).shift().rolling(window, min_periods=1).sum().to_numpy()),
                          index=hours.index+pd.Timedelta(minutes=55)).reindex(pd.DatetimeIndex(features.timestamp))
    frame = features.copy()
    prior = np.where(frame.signal.eq(1), counts.up.to_numpy(), np.where(frame.signal.eq(-1), counts.down.to_numpy(), 0.))
    prior = pd.Series(prior, index=frame.index).fillna(0.)
    frame['prior_same_direction_breakouts'] = prior.to_numpy()
    frame['signal'] = frame.signal.where(frame.signal.eq(0) | prior.le(max_prior), 0).astype(int)
    return frame


class Features:
    """Causal member signals prepared once per history window and reused across candidates."""

    def __init__(self, bars, rule, filters):
        self.bars, self.rule, self.filters, self.cache = bars, rule, filters, {}

    def member(self, lookback, min_rvol, guard):
        key = (lookback, min_rvol, guard)
        if key not in self.cache:
            rule = replace(self.rule, lookback=lookback)
            frame = apply_filter(prepare_features(self.bars, rule), RegimeFilter(**{**self.filters, 'min_rvol': min_rvol}))
            self.cache[key] = (rule, fresh_guard(self.bars, frame, rule) if guard else frame)
        return self.cache[key]

    def members(self, candidate):
        members = candidate['members'] or [dict(lookback=self.rule.lookback, min_rvol=self.filters['min_rvol'])]
        return [self.member(m['lookback'], m['min_rvol'], candidate['fresh_guard']) for m in members]


def closed_equity_drawdown(trades):
    if not len(trades):
        return 0.
    closed = trades.sort_values('exit_time').net_pnl.cumsum()
    return float((closed.cummax().clip(lower=0.)-closed).max())


def combine(parts, bars, cfg):
    """Sum independent equal-risk sub-accounts into one initial-capital account.

    Drawdown is measured on the summed bar-close curve plus every member's own
    intrabar excess, an upper bound because member extremes need not coincide.
    """
    capital = cfg.initial_capital
    curves = [equity_curve(bars, events, cfg) for _, _, events in parts]
    combined = curves[0][['timestamp']].copy()
    combined['cash'] = sum(c.cash.to_numpy() for c in curves)-(len(curves)-1)*capital
    combined['equity'] = sum(c.equity.to_numpy() for c in curves)-(len(curves)-1)*capital
    combined['position_qty'] = sum(c.position_qty.to_numpy() for c in curves)
    equity = combined.equity.to_numpy()
    peak = np.maximum(capital, np.maximum.accumulate(equity))
    combined['close_drawdown_pct'] = (peak-equity)/peak*100
    bar_close_dd = float(((peak-equity)/peak).max())
    excess = 0.
    for (metrics, _, _), curve in zip(parts, curves):
        member_peak = np.maximum(capital, np.maximum.accumulate(curve.equity.to_numpy()))
        member_close_dd = float(((member_peak-curve.equity.to_numpy())/member_peak).max())
        excess += max(0., metrics['max_intrabar_drawdown']-member_close_dd)
    frames = [t.assign(member=i) for i, (_, t, _) in enumerate(parts) if len(t)]
    trades = pd.concat(frames, ignore_index=True).sort_values(['entry_time', 'member']).reset_index(drop=True) if frames else pd.DataFrame()
    event_frames = [e.assign(member=i) for i, (_, _, e) in enumerate(parts) if len(e)]
    events = (pd.concat(event_frames, ignore_index=True).sort_values(['bar_open', 'member'], kind='stable').reset_index(drop=True)
              if event_frames else pd.DataFrame())
    net = trades.net_pnl if len(trades) else pd.Series(dtype=float)
    gains, losses = net.clip(lower=0).sum(), -net.clip(upper=0).sum()
    metrics = dict(initial_capital=capital, final_equity=float(equity[-1]),
                   entries=int(sum(m['entries'] for m, _, _ in parts)), closed_trade_legs=int(len(trades)),
                   win_rate=float((net > 0).mean()) if len(net) else None,
                   profit_factor=float(gains/losses) if losses else None,
                   max_intrabar_drawdown=bar_close_dd+excess, bar_close_combined_drawdown=bar_close_dd,
                   drawdown_basis='summed bar-close curve plus member intrabar excess (upper bound)',
                   max_closed_equity_drawdown_usd=closed_equity_drawdown(trades),
                   total_commission=float(sum(m['total_commission'] for m, _, _ in parts)),
                   total_swap=float(sum(m['total_swap'] for m, _, _ in parts)),
                   margin_call_events=int(sum(m['margin_call_events'] for m, _, _ in parts)),
                   open_position=[m['open_position'] for m, _, _ in parts if m['open_position']] or None,
                   members=[safe_value(m) for m, _, _ in parts])
    return metrics, trades, events, combined


def evaluate(features, candidate, start, end, cfg, out=None, sizing=8.):
    members = features.members(candidate)
    if len(members) == 1:
        rule, frame = members[0]
        b, f = subset(features.bars, frame, start, end)
        if out is None:
            metrics, trades, _ = simulate(b, geometry(rule, candidate), cfg, f, sizing_slippage_bps=sizing)
            return dict(metrics=safe_value(metrics), closed_net=float(trades.net_pnl.sum()) if len(trades) else 0.)
        return detailed(b, f, geometry(rule, candidate), cfg, out, sizing)
    member_cfg = replace(cfg, risk_usd=cfg.risk_usd/len(members))
    parts, b = [], None
    for rule, frame in members:
        b, f = subset(features.bars, frame, start, end)
        parts.append(simulate(b, geometry(rule, candidate), member_cfg, f, sizing_slippage_bps=sizing))
    metrics, trades, events, curve = combine(parts, b, cfg)
    result = dict(metrics=safe_value(metrics), closed_net=float(trades.net_pnl.sum()) if len(trades) else 0.)
    if out is not None:
        out.mkdir(parents=True, exist_ok=True)
        trades.to_csv(out/'trades.csv', index=False)
        events.to_csv(out/'events.csv', index=False)
        curve.to_parquet(out/'equity.parquet', index=False)
    return result


def plan(root=ROOT):
    parent = parent_plan(root)
    assert_historical_period('2026-10-28', root)
    out = directory(root)
    previous = json.loads((out/'manifest.json').read_text()) if (out/'manifest.json').exists() else None
    manifest = dict(name=NAME, parent_protocol_sha256=parent['parent_protocol_sha256'], parent_lab=parent['name'],
        created_at_utc=previous['created_at_utc'] if previous else str(pd.Timestamp.now(tz='UTC')),
        authorization='User requested continued improvement of the strategy for unseen data on 2026-11-03. Bounded training-only experiment; no historical-profit promotion and no future holdout access.',
        motivation='In the consumed 2023-2026 v1.11 ledger, trades stopped within two hours lose about $4.8k of $9.4k total stop losses at a 5% win rate; the 1.5 ATR stop sits inside the median 2.8 ATR breakout candle. No single causal entry feature had Spearman |rho| above 0.14 with trade R, so this round changes structure, not entry thresholds.',
        candidates=candidates(), candidate_count=len(candidates()), groups=list(GROUPS),
        structure=dict(target_distance_atr=TARGET_ATR, trail_atr_unchanged=True,
                       fresh_guard=f'Reject an entry when more than {FRESH_MAX_PRIOR} same-direction raw channel breakouts occurred in the prior {FRESH_WINDOW_HOURS} completed hours.',
                       ensemble='Members are v1.11 with neighbouring channel length / RVOL settings traded as independent sub-accounts at risk $100/n each; sums form one $50,000 account. Ensemble drawdown is the summed bar-close curve plus each member intrabar excess (an upper bound).'),
        train_period=parent['train_period'], train_folds=parent['train_folds'],
        validation_period=parent['validation_period'], chronological_gap_days=7, audit_period=parent['audit_period'],
        scoring=parent['scoring'],
        train_gate=parent['train_gate']+' The penalized training score must also exceed the same-budget v1.11 replica.',
        validation='The top eligible training candidate per group enters 2024; it also needs positive closed net, >=10 closed trades, <=5% drawdown and no margin calls.',
        final_choice='Among eligible 2024 candidates choose max(min(median training closed net, validation closed net) - 0.5*validation drawdown*$50000); tie by lexicographic candidate id. No audit outcome selects this choice.',
        cost_scenarios_bps=[2., 4., 8.], sizing_budget_bps=8., risk_usd=100., initial_capital=50000.,
        full_development_period=['2023-01-01', '2026-10-28'],
        improvement_gate=parent['improvement_gate'],
        all_dates_previously_inspected=True, independent_out_of_sample=False, threshold_changes_after_results=False,
        whole_history_profit_selection=False, future_holdout_access=False, automatic_version_promotion=False,
        data_hashes=parent['data_hashes'],
        source_sha256={**parent['source_sha256'], 'robust_structure_lab.py': sha(root/'robust_structure_lab.py')})
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
        rows = []
        for year in TRAIN_YEARS:
            result = evaluate(training_features, candidate, f'{year}-01-01', min(utc(f'{year+1}-01-01'), train_end), cfg)
            rows.append(dict(year=year, **result))
        return rows

    baseline_folds = folds(baseline_candidate())
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
    shortlist = [choose_family([r for r in rows if r['candidate']['group'] == group]) for group in GROUPS]
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
                for name, candidate, budget in [('challenger', selected, 8.), ('v1.11_original_budget', baseline_candidate(), 2.),
                                                ('v1.12_8bp_budget', baseline_candidate(), 8.)]:
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
    result = dict(manifest_sha256=digest(manifest), baseline_training=dict(folds=baseline_folds, rank=base_rank),
                  training=rows, shortlist=[r['candidate']['id'] for r in shortlist], validation=validation, selected=selected,
                  audit=audit, comparison_checks=comparison,
                  historical_comparison_passed=bool(comparison and all(comparison.values())),
                  prospective_validation_complete=False, promoted=False,
                  prior_history_selection_slots=848, prior_lab_slots=24+12+3+6+1, new_candidate_slots=len(manifest['candidates']),
                  sources_already_consumed=True)
    freeze(out/'results.json', result)
    atomic_json(out/'status.json', dict(stage='complete', candidates=len(manifest['candidates']), selected=selected,
                                       historical_comparison_passed=result['historical_comparison_passed']))
    report(root, result)
    if verify:
        freeze(out/'verification.json', dict(results_sha256=sha(out/'results.json'),
            artifacts_sha256={str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.suffix in {'.csv', '.parquet'}},
            all_training_replayed=True, validation_and_audit_replayed=True, reproduced_exactly=True, forward_validation=False))
    return result


def money(value):
    return '$'+format(value, ',.2f')


def report(root, result):
    lines = ['# Structural robustness: wider stops, fresh-breakout guard, parameter ensembles', '',
             'Ten predefined candidates keep the frozen v1.11 channel/EMA250/RVOL/trend-gap entries and change structure only: (a) initial stop 2.0/2.5/3.0 ATR with the target distance held at 8.25 ATR and the 3 ATR trail unchanged; (b) a guard that rejects an entry preceded by more than two same-direction raw channel breakouts in the prior 72 completed hours, with each stop width; (c) ensembles of neighbouring channel-length/RVOL settings traded as independent $100/n-risk sub-accounts. Fixed $100 planned risk, 8bp sizing budget, real five-minute ETH futures execution, fees, financing and stop-first ambiguity handling. No future data is used.', '',
             '**All dates were previously inspected. This is development research, not an untouched holdout or evidence of future profitability.** The original strategy and forward protocols are preserved. Failed candidates and the exact shortlist/selection are retained.', '',
             'Motivation from the consumed v1.11 ledger: trades stopped within two hours lose about $4.8k of $9.4k total stop losses at a 5% win rate because the 1.5 ATR stop sits inside the median 2.8 ATR breakout candle, while no causal entry feature predicts trade R well enough to filter on.', '',
             'Training selection uses 2020-2023 annual closed outcomes at 8bp fills and must beat the same-budget v1.11 replica. The top eligible candidate per group is checked on 2024. Both 2023 and 2024 execution end December 25, leaving a seven-day gap before the next stage. The final choice is frozen before 2025-2026 diagnostic outcomes, which never change it.', '',
             'Same-budget v1.11 replica training score: '+format(result['baseline_training']['rank']['score'], '.2f')+' (median annual closed net '+money(result['baseline_training']['rank']['median_closed_net'])+').', '',
             '| Candidate | Group | Training score | Median annual closed | Eligible training | 2024 closed net | 2024 drawdown | Eligible 2024 |',
             '| --- | --- | ---: | ---: | --- | ---: | ---: | --- |']
    validation = {r['candidate']['id']: r for r in result['validation']}
    for row in result['training']:
        name = row['candidate']['id']; v = validation.get(name)
        lines.append('| '+' | '.join([name, row['candidate']['group'], format(row['rank']['score'], '.2f'), money(row['rank']['median_closed_net']),
                                      str(row['rank']['eligible']), money(v['result']['closed_net']) if v else 'Not shortlisted',
                                      format(v['result']['metrics']['max_intrabar_drawdown'], '.2%') if v else '',
                                      str(v['rank']['eligible']) if v else 'Not evaluated'])+' |')
    lines += ['', 'Selected before audit: **'+(result['selected']['id'] if result['selected'] else 'None: no candidate passed both gates')+'**.', '',
              '| Period | Strategy | Actual slippage | Net including open marks | Closed net | Drawdown | Entries | Closed trades |',
              '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for row in result['audit']:
        m = row['metrics']
        lines.append('| '+' | '.join([row['period'], row['strategy'], f"{row['fill_bps']}bp", money(pnl(m)), money(row['closed_net']),
                                      format(m['max_intrabar_drawdown'], '.2%'), str(m['entries']), str(m['closed_trade_legs'])])+' |')
    lines += ['', f"Historical comparison checks: `{result['comparison_checks']}`. Historical comparison passed: **{result['historical_comparison_passed']}**. No version is automatically promoted.", '',
              'Ensemble drawdowns are the summed bar-close curve plus each member intrabar excess, an upper bound; single-rule drawdowns are intrabar. All comparisons have causal prior 2020-2022 indicator warm-up before the 2023 benchmark and can differ from the saved $12,814.03 run. Annual accounts reset and their nets are not summed as a continuous return.', '',
              f"848 earlier logged search slots, {result['prior_lab_slots']} earlier lab candidates and these {result['new_candidate_slots']} are known research exposure, not a complete independent trial count. A selected candidate would need its own preregistered future test; consumed data cannot become unseen again.", '']
    (root/'reports'/f'{NAME}.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    outcome = run(verify=parser.parse_args().verify)
    print(json.dumps(dict(selected=outcome['selected'], historical_comparison_passed=outcome['historical_comparison_passed'],
                          comparison_checks=outcome['comparison_checks']), indent=2))
