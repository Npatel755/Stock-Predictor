"""v2 funding-crowding fade: a return source the breakout never uses.

Settled perpetual funding measures positioning crowding. When the trailing
24-hour mean of the last settled 8h rate sits in the top tail of its own
trailing 30-day distribution and price breaks the prior 24-hour low, the
crowded longs are faded short (mirrored for crowded shorts). Signals use only
settlements published at least one hour earlier and completed hourly candles;
fixed geometry (2 ATR stop, 3R target, 96-hour time stop, no trail). The
candidate is evaluated standalone and as a second $100-risk sleeve beside the
unchanged v1.11 account. Pre-registered chronological research on consumed
history; no future access, no automatic promotion.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json

import numpy as np
import pandas as pd

from .alternative_strategies import SignalRule
from .cost_reserve import simulate
from .exit_research import freeze
from .forward_collection import atomic_json, collection_lock
from .funding_data import collect
from .generalization_policy import assert_historical_period, digest, frozen_profile
from .indicators import resample_complete, rma
from .market_data import BAR, utc
from .optimize import pnl, subset
from .paths import ROOT
from .reporting import safe_value
from .robust_structure_lab import Features, combine
from .strategy_lab import plan as parent_plan, load_development, training_rank, validation_rank, choose_family, detailed, sha


NAME = 'v2_funding_fade_round1'
VERSION = 'ETH v2.0 research candidate (v1.11 + funding-crowding fade sleeve)'
TRAIN_YEARS = (2020, 2021, 2022, 2023)
PERCENTILES, CONFIRMS = (.90, .95, .98), ('break24h', 'none')
WINDOW_HOURS, CROWD_HOURS, PUBLICATION_HOURS = 720, 24, 1
FADE_RULE = SignalRule('channel_breakout', lookback=72, slow=250, stop_atr=2., reward_r=3., trail_atr=0., max_holding_bars=96*12)
AUDIT_PERIODS = [('audit_2025', '2025-01-01', '2026-01-01'), ('audit_2026', '2026-01-01', '2026-10-28'),
                 ('full_development', '2023-01-01', '2026-10-28')]


def directory(root):
    return root/'artifacts/strategy_lab'/NAME


def candidates():
    return [dict(id=f'fade_p{int(round(p*100))}_{confirm}', group=confirm, percentile=p, confirm=confirm)
            for p in PERCENTILES for confirm in CONFIRMS]


def settled_rate_by_hour(hours, settlements, publication_hours=PUBLICATION_HOURS):
    """Last settled 8h-normalized rate published before each completed hour's final 5m close."""
    availability = (hours.index+pd.Timedelta(hours=1)-BAR).as_unit('ns')
    source = settlements[['timestamp', 'rate_8h_bps']].copy()
    source['available_at'] = (source.timestamp+pd.Timedelta(hours=publication_hours)).dt.as_unit('ns')
    merged = pd.merge_asof(pd.DataFrame(dict(t=availability)), source.sort_values('available_at'),
                           left_on='t', right_on='available_at', direction='backward')
    stale = merged.t-merged.available_at > pd.Timedelta(hours=16)
    return pd.Series(merged.rate_8h_bps.where(~stale).to_numpy(), index=hours.index)


def fade_signals(bars, settlements, candidate):
    hours = resample_complete(bars, '1h')
    c = hours.close
    tr = pd.concat([hours.high-hours.low, (hours.high-c.shift()).abs(), (hours.low-c.shift()).abs()], axis=1).max(axis=1)
    atr = rma(tr, 14)
    rate = settled_rate_by_hour(hours, settlements)
    crowd = rate.rolling(CROWD_HOURS, min_periods=CROWD_HOURS).mean()
    percentile = crowd.rolling(WINDOW_HOURS, min_periods=WINDOW_HOURS).rank(pct=True)
    ready = (c.expanding().count() >= WINDOW_HOURS+CROWD_HOURS+1) & percentile.notna() & atr.notna()
    prior_high = hours.high.shift().rolling(CROWD_HOURS).max()
    prior_low = hours.low.shift().rolling(CROWD_HOURS).min()
    crowded_long = percentile >= candidate['percentile']
    crowded_short = percentile <= 1-candidate['percentile']
    if candidate['confirm'] == 'break24h':
        short_state, long_state = crowded_long & (c < prior_low), crowded_short & (c > prior_high)
    else:
        short_state, long_state = crowded_long, crowded_short
    short = short_state & ~short_state.shift(fill_value=False)
    long = long_state & ~long_state.shift(fill_value=False)
    availability = hours.index+pd.Timedelta(hours=1)-BAR
    hourly = pd.DataFrame(dict(signal=np.where(ready & long, 1, np.where(ready & short, -1, 0)), signal_atr=atr.to_numpy(),
                               crowd_percentile=percentile.to_numpy()), index=availability)
    mapped = hourly.reindex(pd.DatetimeIndex(bars.timestamp))
    output = bars.copy()
    output['signal'] = mapped.signal.fillna(0).to_numpy(dtype=int)
    output['signal_atr'] = mapped.signal_atr.to_numpy()
    output['crowd_percentile'] = mapped.crowd_percentile.to_numpy()
    output['management_atr'] = pd.Series(atr.to_numpy(), index=availability).reindex(pd.DatetimeIndex(bars.timestamp), method='ffill').to_numpy()
    return output


class FadeFeatures:
    def __init__(self, bars, rule, filters, settlements):
        self.base = Features(bars, rule, filters)
        self.bars, self.settlements, self.cache = self.base.bars, settlements, {}

    def baseline(self):
        return self.base.member(self.base.rule.lookback, self.base.filters['min_rvol'], False)

    def fade(self, candidate):
        if candidate['id'] not in self.cache:
            self.cache[candidate['id']] = fade_signals(self.bars, self.settlements, candidate)
        return self.cache[candidate['id']]


def dump(out, trades, events, curve=None):
    out.mkdir(parents=True, exist_ok=True)
    trades.to_csv(out/'trades.csv', index=False)
    events.to_csv(out/'events.csv', index=False)
    if curve is not None:
        curve.to_parquet(out/'equity.parquet', index=False)


def evaluate(features, candidate, start, end, cfg, out=None, sizing=8., portfolio=False):
    base_rule, base_frame = features.baseline()
    if candidate is None:
        b, f = subset(features.bars, base_frame, start, end)
        if out is not None:
            return detailed(b, f, base_rule, cfg, out, sizing)
        metrics, trades, _ = simulate(b, base_rule, cfg, f, sizing_slippage_bps=sizing)
        return dict(metrics=safe_value(metrics), closed_net=float(trades.net_pnl.sum()) if len(trades) else 0.)
    b, f = subset(features.bars, features.fade(candidate), start, end)
    fade = simulate(b, FADE_RULE, cfg, f, sizing_slippage_bps=sizing)
    if not portfolio:
        metrics, trades, events = fade
        if out is not None:
            dump(out, trades, events)
        return dict(metrics=safe_value(metrics), closed_net=float(trades.net_pnl.sum()) if len(trades) else 0.)
    _, bf = subset(features.bars, base_frame, start, end)
    core = simulate(b, base_rule, cfg, bf, sizing_slippage_bps=sizing)
    metrics, trades, events, curve = combine([core, fade], b, cfg)
    metrics['drawdown_basis'] = 'summed v1.11+fade bar-close curve plus member intrabar excess (upper bound)'
    if out is not None:
        dump(out, trades, events, curve)
    return dict(metrics=safe_value(metrics), closed_net=float(trades.net_pnl.sum()) if len(trades) else 0.)


def plan(root=ROOT):
    parent = parent_plan(root)
    assert_historical_period('2026-10-28', root)
    out = directory(root)
    previous = json.loads((out/'manifest.json').read_text()) if (out/'manifest.json').exists() else None
    manifest = dict(name=NAME, version_if_selected=VERSION, parent_version='v1.11', parent_protocol_sha256=parent['parent_protocol_sha256'],
        created_at_utc=previous['created_at_utc'] if previous else str(pd.Timestamp.now(tz='UTC')),
        authorization='User chose on 2026-11-03 one more pre-registered round on a different return source after breakout variants (robust_structure_round1, v2_scale_in_round1) failed. v1.11 stays frozen.',
        return_source='Positioning crowding from settled perpetual funding, faded on a same-direction price failure; independent of the channel breakout.',
        signal=dict(rate='last settled 8h-normalized ETHUSDT funding published >=1h before the completed hour, stale after 16h',
                    crowd=f'{CROWD_HOURS}h mean of that rate', percentile=f'rank within the trailing {WINDOW_HOURS}h of crowd values',
                    short='crowd percentile >= p (and hourly close below the prior 24h low for break24h), first hour the state appears',
                    long='mirror: crowd percentile <= 1-p (and close above the prior 24h high for break24h)',
                    execution='signal on the hour\'s final 5m close, next-open fill, shared Broker costs/financing/stop-first'),
        geometry=asdict(FADE_RULE), geometry_note='Fixed before any outcome: 2 ATR stop, 3R target, 96-hour time stop, no trail; family label is unused because signals are supplied.',
        candidates=candidates(), candidate_count=len(candidates()), groups=list(CONFIRMS),
        funding_source='Pinned checksum-verified monthly ETHUSDT funding ZIPs already in data/eth_funding; no forecasts, no price fabrication.',
        train_period=parent['train_period'], train_folds=parent['train_folds'], validation_period=parent['validation_period'],
        chronological_gap_days=7, audit_period=parent['audit_period'], scoring=parent['scoring'],
        train_gate=parent['train_gate']+' A new return source is standalone: the penalized training score must be positive (not compared with v1.11).',
        validation='Top eligible training candidate per confirmation group enters 2024 standalone; needs positive closed net, >=10 closed trades, <=5% drawdown, no margin calls.',
        final_choice='Among eligible 2024 candidates choose max(min(median training closed net, validation closed net) - 0.5*validation drawdown*$50000); tie by lexicographic id. No audit outcome selects this choice.',
        cost_scenarios_bps=[2., 4., 8.], sizing_budget_bps=8., risk_usd=100., initial_capital=50000.,
        full_development_period=['2023-01-01', '2026-10-28'],
        improvement_gate='Portfolio (unchanged v1.11 at $100 risk + fade sleeve at $100 risk, independent sub-accounts summed) beats v1.11 alone on 2023-2026 net at 2bp and at 8bp actual fills, portfolio drawdown <= 5%, and the fade sleeve alone has positive closed net in 2025 and in 2026 at 8bp.',
        registration='Only if the frozen selection passes the improvement gate is candidates/eth_v2_0 written, unpromoted, with its own prospective protocol.',
        all_dates_previously_inspected=True, independent_out_of_sample=False, threshold_changes_after_results=False,
        whole_history_profit_selection=False, future_holdout_access=False, automatic_version_promotion=False,
        data_hashes=parent['data_hashes'],
        source_sha256={**parent['source_sha256'], 'funding_data.py': sha(root/'funding_data.py'), 'robust_structure_lab.py': sha(root/'robust_structure_lab.py'),
                       'funding_fade_lab.py': sha(root/'funding_fade_lab.py')})
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
    settlements, sources = collect(root)
    freeze(out/'sources.json', dict(sources=sources, rows=len(settlements)))
    bars = load_development(root, manifest)
    train_end = utc(manifest['train_period'][1])
    training_features = FadeFeatures(bars[bars.timestamp < train_end].reset_index(drop=True), baseline_rule, filters, settlements)

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
            rank['eligible'] = bool(rank['eligible'] and rank['score'] > 0)
            row = dict(candidate=candidate, folds=fold_rows, rank=rank, manifest_sha256=digest(manifest))
            freeze(path, row)
        rows.append(row)
        print(f"TRAIN {candidate['id']} score={row['rank']['score']:.2f} entries={sum(f['metrics']['entries'] for f in row['folds'])} eligible={row['rank']['eligible']}", flush=True)
        atomic_json(out/'status.json', dict(stage='training', complete=len(rows), total=len(manifest['candidates'])))
    shortlist = [choose_family([r for r in rows if r['candidate']['group'] == group]) for group in CONFIRMS]
    freeze(out/'training_selection.json', dict(manifest_sha256=digest(manifest), baseline_training_score=base_rank['score'],
                                               candidate_ids=[r['candidate']['id'] for r in shortlist]))
    preceding = FadeFeatures(bars[bars.timestamp < utc(manifest['validation_period'][1])].reset_index(drop=True), baseline_rule, filters, settlements)
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
        full = FadeFeatures(bars, baseline_rule, filters, settlements)
        for label, begin, end in AUDIT_PERIODS:
            for slip in manifest['cost_scenarios_bps']:
                actual = replace(cfg, slippage_bps=slip)
                for name, candidate, budget, portfolio in [('fade_sleeve', selected, 8., False), ('portfolio_v1_11_plus_fade', selected, 8., True),
                                                           ('v1.11_original_budget', None, 2., False), ('v1.12_8bp_budget', None, 8., False)]:
                    result = evaluate(full, candidate, begin, end, actual, out/'audit'/label/f'{name}_fill{int(slip)}', budget, portfolio)
                    audit.append(dict(period=label, strategy=name, fill_bps=slip, sizing_budget_bps=budget, **result))
            print(f'AUDIT {label} complete; selection remains frozen', flush=True)
        development = [r for r in audit if r['period'] == 'full_development']
        pick = lambda strategy, slip: next(r for r in development if r['strategy'] == strategy and r['fill_bps'] == slip)
        comparison = dict(higher_main=pnl(pick('portfolio_v1_11_plus_fade', 2.)['metrics']) > pnl(pick('v1.11_original_budget', 2.)['metrics']),
                          higher_stressed=pnl(pick('portfolio_v1_11_plus_fade', 8.)['metrics']) > pnl(pick('v1.11_original_budget', 8.)['metrics']),
                          drawdown_limit=all(r['metrics']['max_intrabar_drawdown'] <= .05 for r in development if r['strategy'] == 'portfolio_v1_11_plus_fade'),
                          positive_later_annual_closed=all(r['closed_net'] > 0 for r in audit if r['strategy'] == 'fade_sleeve'
                                                           and r['period'] != 'full_development' and r['fill_bps'] == 8.))
    passed = bool(comparison and all(comparison.values()))
    result = dict(manifest_sha256=digest(manifest), funding_rows=len(settlements), baseline_training=dict(folds=baseline_folds, rank=base_rank),
                  baseline_validation=baseline_validation, training=rows, shortlist=[r['candidate']['id'] for r in shortlist],
                  validation=validation, selected=selected, audit=audit, comparison_checks=comparison,
                  historical_comparison_passed=passed, candidate_registered=passed, candidate_directory='candidates/eth_v2_0' if passed else None,
                  prospective_validation_complete=False, promoted=False, prior_history_selection_slots=848,
                  prior_lab_slots=24+12+3+6+1+10+6, new_candidate_slots=len(manifest['candidates']), sources_already_consumed=True)
    freeze(out/'results.json', result)
    if passed:
        register(root, manifest, result)
    atomic_json(out/'status.json', dict(stage='complete', candidates=len(manifest['candidates']), selected=selected, historical_comparison_passed=passed))
    report(root, result)
    if verify:
        freeze(out/'verification.json', dict(results_sha256=sha(out/'results.json'),
            artifacts_sha256={str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.suffix in {'.csv', '.parquet'}},
            all_training_replayed=True, validation_and_audit_replayed=True, reproduced_exactly=True, forward_validation=False))
    return result


def register(root, manifest, result):
    """Write the unpromoted v2.0 research candidate with its own prospective protocol; never touches v1.11."""
    _, rule, base_cfg, meta = frozen_profile(root)
    folder = root/'candidates/eth_v2_0'
    folder.mkdir(parents=True, exist_ok=True)
    config = dict(version=VERSION, parent_version='v1.11', parent_configuration_sha256=meta['configuration_sha256'],
                  sleeves=dict(v1_11=dict(rule=asdict(rule), execution=asdict(base_cfg), filters=meta['entry_filters'], risk_usd=100., unchanged=True),
                               funding_fade=dict(rule=asdict(FADE_RULE), execution=asdict(base_cfg), signal=manifest['signal'],
                                                 percentile=result['selected']['percentile'], confirm=result['selected']['confirm'], risk_usd=100.)),
                  accounting='Independent sub-accounts summed into one $50,000 account; drawdown reported as an upper bound.',
                  sizing_slippage_bps=8., promoted=False, independent_forward_validation=False, ready_for_funded_trading=False,
                  selected_by=f'{NAME} frozen train/2024 gates; 2025-2026 are consumed diagnostics')
    freeze(folder/'config.json', config)
    protocol = dict(candidate=VERSION, created_at_utc=str(pd.Timestamp.now(tz='UTC')), lab=NAME, lab_manifest_sha256=result['manifest_sha256'],
                    candidate_sha256=sha(folder/'config.json'), change='Adds an independent funding-crowding fade sleeve beside unchanged v1.11; no v1.11 rule changes.',
                    number_of_candidate_hypotheses=len(manifest['candidates']), optimizer_enabled=False,
                    historical_period=['2023-01-01', '2026-10-28'], historical_data_already_inspected=True, development_outcomes_may_change_candidate=False,
                    future_period=['2026-11-04 00:00:00+00:00', '2027-05-03 00:00:00+00:00'], final_evaluation_only=True,
                    minimum_closed_trades=30, maximum_drawdown=.05,
                    primary_comparison='At 8bp actual fills over the future period: portfolio net above the unchanged v1.11 run on the same data, portfolio drawdown <= 5%, fade sleeve net positive on its own.',
                    additional_checks='Positive fade-sleeve net at 2/4/8bp fills, no margin calls, >=30 closed fade trades, positive lower seven-day-block bootstrap interval at 8bp.',
                    bootstrap=dict(seed=20261104, draws=10000, block_days=7), promotion_automatic=False, ready_for_funded_trading=False,
                    source_sha256=manifest['source_sha256'])
    freeze(folder/'protocol.json', protocol)
    (folder/'README.md').write_text('\n'.join([f'# {VERSION}', '',
        f'Unpromoted research candidate produced by the pre-registered {NAME} lab. v1.11 is unchanged; the candidate adds a second $100-risk sleeve that fades positioning crowding measured from settled funding.', '',
        'All 2020-2026 data used to select it was previously inspected; the only admissible evidence of generalization is the sealed future period in protocol.json, evaluated once after 2027-05-03. Nothing here is live-trading or funded-account readiness.', '']), encoding='utf-8')


def money(value):
    return '$'+format(value, ',.2f')


def report(root, result):
    base = result['baseline_training']['rank']
    lines = ['# v2 funding-crowding fade: a second return source beside v1.11', '',
             'Six predefined candidates fade positioning crowding: when the 24h mean of the last settled 8h funding rate ranks at or above the 90th/95th/98th percentile of its trailing 30 days (crowded longs) and, for break24h, the hour closes below the prior 24h low, go short at the next open; mirrored for crowded shorts. Geometry is fixed (2 ATR stop, 3R target, 96-hour time stop). Signals use settlements published at least one hour earlier and completed hourly candles only.', '',
             '**All dates were previously inspected. This is development research, not an untouched holdout or evidence of future profitability.** v1.11 and its forward protocol are untouched. Failed candidates and the frozen shortlist/selection are retained.', '',
             'Training uses 2020-2023 annual closed outcomes at 8bp fills and must be positive standalone (same-budget v1.11 replica for reference: score '+format(base['score'], '.2f')+', median annual closed '+money(base['median_closed_net'])+'). The top eligible candidate per confirmation group is checked on 2024 (v1.11 same budget: '+money(result['baseline_validation']['closed_net'])+'). Execution ends December 25 in 2023 and 2024, leaving seven-day gaps. The selection is frozen before 2025-2026 outcomes.', '',
             '| Candidate | Training score | Median annual closed | Training entries | Eligible training | 2024 closed net | 2024 drawdown | Eligible 2024 |', '| --- | ---: | ---: | ---: | --- | ---: | ---: | --- |']
    validation = {r['candidate']['id']: r for r in result['validation']}
    for row in result['training']:
        name = row['candidate']['id']; v = validation.get(name)
        lines.append('| '+' | '.join([name, format(row['rank']['score'], '.2f'), money(row['rank']['median_closed_net']), str(sum(f['metrics']['entries'] for f in row['folds'])), str(row['rank']['eligible']),
                                      money(v['result']['closed_net']) if v else 'Not shortlisted', format(v['result']['metrics']['max_intrabar_drawdown'], '.2%') if v else '',
                                      str(v['rank']['eligible']) if v else 'Not evaluated'])+' |')
    lines += ['', 'Selected before audit: **'+(result['selected']['id'] if result['selected'] else 'None: no candidate passed both gates')+'**.', '',
              '| Period | Strategy | Actual slippage | Net including open marks | Closed net | Drawdown | Entries | Closed legs |', '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for row in result['audit']:
        m = row['metrics']
        lines.append('| '+' | '.join([row['period'], row['strategy'], f"{row['fill_bps']}bp", money(pnl(m)), money(row['closed_net']), format(m['max_intrabar_drawdown'], '.2%'), str(m['entries']), str(m['closed_trade_legs'])])+' |')
    lines += ['', f"Improvement gate (portfolio v1.11 + fade against v1.11 alone): `{result['comparison_checks']}`. Passed: **{result['historical_comparison_passed']}**. "
              + ('The frozen selection was registered as an unpromoted research candidate in `candidates/eth_v2_0` with its own sealed prospective protocol.' if result['candidate_registered'] else 'No candidate was registered or promoted.'), '',
              'Portfolio drawdowns are the summed bar-close curve plus each sleeve\'s intrabar excess, an upper bound; single-sleeve drawdowns are intrabar. Annual accounts reset and are not summed as a continuous return. Funding is a crowding feature only; modeled Breakout fees and 3.3bp/day financing are unchanged.', '',
              f"848 earlier logged search slots, {result['prior_lab_slots']} earlier lab candidates and these {result['new_candidate_slots']} are known research exposure, not a complete trial count. Consumed data cannot become unseen again; only the sealed future period can validate the candidate.", '']
    (root/'reports'/f'{NAME}.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    outcome = run(verify=parser.parse_args().verify)
    print(json.dumps(dict(selected=outcome['selected'], historical_comparison_passed=outcome['historical_comparison_passed'],
                          comparison_checks=outcome['comparison_checks'], candidate_registered=outcome['candidate_registered']), indent=2))
