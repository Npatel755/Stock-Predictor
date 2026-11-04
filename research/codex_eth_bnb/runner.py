"""Bounded, checkpointed retrospective experiments; contaminated final is sealed."""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd

from .analytics import block_statistics, combine_sleeves, daily_returns, holm, metric_extras
from .data_pipeline import HERE, BAR, freeze, load, resample, sha
from .execution import simulate
from .paper import freeze_payload
from .strategies import build_features, build_signal, library

SEED = 20261103
OUTPUT = HERE/'outputs'


def safe(value):
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, (pd.Timestamp, Path)):
        return str(value)
    return value


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(safe(value), indent=2, sort_keys=True, allow_nan=False)+'\n', encoding='utf-8')


def code_hashes():
    return {p.name: sha(p) for p in sorted(HERE.glob('*.py'))}


def config_for(spec, symbol, **changes):
    cfg = dict(initial_capital=50000., risk_fraction=.0025, max_leverage=1., fee_bps=5., slippage_bps=2.,
               spread_bps=1., participation_cap=.001, qty_step=.001 if symbol == 'ETH' else .01, tick_size=.01,
               funding_bps_daily=0., **spec.get('execution', {}))
    if spec['family'] == 'buy_hold':
        cfg.update(sizing_mode='notional', notional_fraction=1.)
    elif spec['family'] == 'flat':
        cfg.update(stop_atr=2., reward_r=3.)
    cfg.update(changes)
    return cfg


def registry(row):
    path = HERE/'experiment_registry.csv'
    columns = ['trial_key', 'phase', 'symbol', 'strategy_id', 'family', 'timeframe', 'start', 'end',
               'config_json', 'data_manifest_sha256', 'code_revision', 'code_hashes_json', 'seed', 'metrics_json']
    exists = path.exists()
    with path.open('a', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        if not exists:
            writer.writeheader()
        writer.writerow({k: row[k] for k in columns})


class Lab:
    def __init__(self):
        self.split = json.loads((HERE/'split_manifest.json').read_text())
        self.manifest = json.loads((HERE/'candidate_manifest.json').read_text())
        if self.manifest['specifications'] != library():
            raise ValueError('Strategy library differs from preregistration')
        self.hashes = code_hashes()
        self.revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=HERE, text=True).strip()
        self.raw = {s: load(s) for s in ['ETH', 'BNB', 'BTC']}
        self.frames = {}
        self.features = {}
        self.results = {}

    def features_for(self, symbol, timeframe):
        key = (symbol, timeframe)
        if key not in self.features:
            for name in ['ETH', 'BNB', 'BTC']:
                if (name, timeframe) not in self.frames:
                    frame = resample(self.raw[name], timeframe, name)
                    frame.attrs['timeframe'] = timeframe
                    self.frames[name, timeframe] = frame
            context = {name: self.frames[name, timeframe] for name in ['ETH', 'BNB', 'BTC']}
            self.features[key] = build_features(self.frames[key], context)
        return self.features[key]

    def signal(self, symbol, spec):
        return build_signal(self.features_for(symbol, spec['timeframe']), dict(spec, symbol=symbol))

    def trial(self, symbol, spec, begin, end, phase, *, frame=None, cfg=None):
        begin, end = pd.Timestamp(begin), pd.Timestamp(end)
        if end > pd.Timestamp(self.split['nominal_final'][0]):
            raise ValueError('Contaminated nominal final performance access is disabled')
        if frame is None:
            frame = self.signal(symbol, spec)
        duration = pd.Timedelta(spec['timeframe'])
        subset = frame[(frame.timestamp >= begin) & (frame.timestamp+duration <= end)].copy().reset_index(drop=True)
        cfg = config_for(spec, symbol) if cfg is None else cfg
        identity = dict(symbol=symbol, spec=spec, begin=str(begin), end=str(end), phase=phase, cfg=cfg,
                        code_hashes=self.hashes, data_manifest_sha256=sha(HERE/'data_manifest.json'))
        key = hashlib.sha256(json.dumps(identity, sort_keys=True, default=str).encode()).hexdigest()[:20]
        folder = OUTPUT/key
        if (folder/'result.json').exists():
            saved = json.loads((folder/'result.json').read_text())
            result = dict(metrics=saved['metrics'], trades=pd.read_parquet(folder/'trades.parquet'),
                          equity=pd.read_parquet(folder/'equity.parquet'))
        else:
            result = simulate(subset, cfg)
            daily = daily_returns(result['equity'], cfg['initial_capital'])
            std = daily.std(ddof=1)
            result['metrics']['sharpe'] = float(daily.mean()/std*np.sqrt(365.25)) if std > 0 else None
            result['metrics']['sharpe_sampling'] = '365.25 calendar days, P&L owned by bar-open date, includes initial day'
            folder.mkdir(parents=True, exist_ok=True)
            result['trades'].to_parquet(folder/'trades.parquet', index=False)
            result['equity'].to_parquet(folder/'equity.parquet', index=False)
            daily.rename('daily_return').to_csv(folder/'daily_returns.csv', index_label='date')
            write(folder/'result.json', dict(identity=identity, metrics=result['metrics']))
            registry(dict(trial_key=key, phase=phase, symbol=symbol, strategy_id=spec['id'], family=spec['family'],
                          timeframe=spec['timeframe'], start=str(begin), end=str(end), config_json=json.dumps(safe(cfg), sort_keys=True),
                          data_manifest_sha256=identity['data_manifest_sha256'], code_revision=self.revision,
                          code_hashes_json=json.dumps(self.hashes, sort_keys=True), seed=SEED,
                          metrics_json=json.dumps(safe(result['metrics']), sort_keys=True)))
        self.results[symbol, spec['id'], phase] = (folder, result)
        return folder, result

    def train(self):
        rows, returns = [], {}
        for symbol in ['ETH', 'BNB']:
            for number, spec in enumerate(self.manifest['specifications']):
                folds, daily = [], []
                frame = self.signal(symbol, spec)
                for fold in self.split['folds']:
                    _, result = self.trial(symbol, spec, fold['eval_start'], fold['eval_end'], fold['id'], frame=frame)
                    folds.append(dict(fold=fold['id'], **result['metrics']))
                    daily.append(daily_returns(result['equity']))
                combined = pd.concat(daily)
                stats = block_statistics(combined)
                positive = sum(f['net_pnl'] > 0 for f in folds)
                trades = sum(f['trades'] for f in folds)
                dd = max(f['max_intrabar_drawdown'] for f in folds)
                eligible = positive >= 2 and trades >= 50 and dd <= .20 and not any(f['liquidation_events'] for f in folds)
                sharpes = [f['sharpe'] if f['sharpe'] is not None else -1e9 for f in folds]
                row = dict(symbol=symbol, id=spec['id'], family=spec['family'], timeframe=spec['timeframe'], baseline=spec['baseline'],
                           train_positive_folds=positive, train_trades=trades, train_worst_drawdown=dd,
                           train_sum_reset_account_pnl=sum(f['net_pnl'] for f in folds),
                           train_worst_sharpe=min(sharpes), train_median_sharpe=float(np.median(sharpes)),
                           train_eligible=eligible, train_block_p=stats['pvalue_centered_1s'],
                           train_mean_daily_ci_lower=stats['mean_daily_lower'], folds=folds)
                rows.append(row)
                returns[symbol, spec['id']] = combined
                print(f'TRAIN {symbol} {number+1}/60 {spec["id"]}: positive folds {positive}/3, eligible={eligible}', flush=True)
                write(OUTPUT/'status.json', dict(stage='training', symbol=symbol, completed=number+1, per_asset=60))
        # Includes all120 concrete baseline+primary trials and4 unused conditional slots.
        adjusted = holm([r['train_block_p'] for r in rows], family_size=124)
        for row, p in zip(rows, adjusted):
            row['train_holm_p'] = p
        write(HERE/'training_results.json', rows)
        pd.DataFrame([{k: v for k, v in r.items() if k != 'folds'} for r in rows]).to_csv(HERE/'strategy_comparison.csv', index=False)
        pd.DataFrame([dict(symbol=r['symbol'], strategy_id=r['id'], **f) for r in rows for f in r['folds']]).drop(columns=['cost_config'], errors='ignore').to_csv(HERE/'walkforward_results.csv', index=False)
        return rows, returns

    def selection(self, training):
        chosen = []
        for symbol in ['ETH', 'BNB']:
            pool = sorted([r for r in training if r['symbol'] == symbol and r['train_eligible'] and not r['baseline']],
                          key=lambda r: (-r['train_worst_sharpe'], -r['train_median_sharpe'], r['id']))
            families = set()
            for row in pool:
                if row['family'] not in families:
                    chosen.append(dict(symbol=symbol, id=row['id'], family=row['family']))
                    families.add(row['family'])
                if len(families) == 3:
                    break
        freeze(HERE/'validation_shortlist.json', dict(selected=chosen, no_replacements=True,
                                                     training_sha256=sha(HERE/'training_results.json'), code_hashes=self.hashes))
        return chosen

    def validate(self, training, chosen):
        results = []
        specs = {s['id']: s for s in library()}
        for selected in chosen:
            symbol, spec = selected['symbol'], specs[selected['id']]
            origin = next(r for r in training if r['symbol'] == symbol and r['id'] == spec['id'])
            frame = self.signal(symbol, spec)
            start, end = self.split['validation_eval_start'], self.split['validation'][1]
            folder, base = self.trial(symbol, spec, start, end, 'VALIDATION', frame=frame)
            _, adverse = self.trial(symbol, spec, start, end, 'VALIDATION_adverse', frame=frame,
                                    cfg=config_for(spec, symbol, fee_bps=7., slippage_bps=8., spread_bps=4.))
            extras = metric_extras(base)
            write(folder/'attribution.json', extras)
            gates = dict(minimum_trades=base['metrics']['trades'] >= 20,
                         positive_base=base['metrics']['net_pnl'] > 0,
                         positive_adverse=adverse['metrics']['net_pnl'] > 0,
                         drawdown=base['metrics']['max_intrabar_drawdown'] <= .15 and adverse['metrics']['max_intrabar_drawdown'] <= .15,
                         no_liquidation=not base['metrics']['liquidation_events'] and not adverse['metrics']['liquidation_events'],
                         block_lower_positive=extras['block_statistics']['mean_daily_lower'] > 0,
                         training_holm=origin['train_holm_p'] <= .05)
            row = dict(symbol=symbol, id=spec['id'], family=spec['family'], timeframe=spec['timeframe'],
                       phase='VALIDATION', accepted=all(gates.values()), gates=gates, metrics=base['metrics'],
                       adverse_metrics=adverse['metrics'], bootstrap=extras['block_statistics'], output=str(folder.relative_to(HERE)))
            results.append(row)
            print(f'VALIDATION {symbol} {spec["id"]}: base ${base["metrics"]["net_pnl"]:.0f}, adverse ${adverse["metrics"]["net_pnl"]:.0f}, accepted={row["accepted"]}', flush=True)
        # Fixed baseline comparisons have no opportunity to replace shortlisted failures.
        baselines = []
        for symbol in ['ETH', 'BNB']:
            for spec in [s for s in library() if s['baseline'] and s['timeframe'] in ['1h', '4h']]:
                _, result = self.trial(symbol, spec, self.split['validation_eval_start'], self.split['validation'][1], 'VALIDATION_baseline')
                baselines.append(dict(symbol=symbol, id=spec['id'], phase='VALIDATION', metrics=result['metrics']))
        write(HERE/'validation_results.json', dict(candidates=results, baselines=baselines))
        return results

    def robustness(self, validated):
        specs = {s['id']: s for s in library()}
        rows = []
        for symbol in ['ETH', 'BNB']:
            # Always the first2 training-selected configurations, not validation winners.
            for row in [r for r in validated if r['symbol'] == symbol][:2]:
                spec = specs[row['id']]
                base_frame = self.signal(symbol, spec)
                start, end = self.split['validation_eval_start'], self.split['validation'][1]
                scenarios = [('risk_050', dict(risk_fraction=.005)), ('risk_100', dict(risk_fraction=.01)),
                             ('crisis_costs', dict(fee_bps=10., slippage_bps=20., spread_bps=10.)),
                             ('delay_one_extra_bar', dict(execution_delay_bars=2)),
                             ('low_capacity', dict(participation_cap=.0002)),
                             ('outage_every20bars', dict(skip_entry_timestamps=[str(t) for t in base_frame.timestamp.iloc[::20]])),
                             ('trailing_stop', dict(trail_atr=3.))]
                if row['gates']['positive_base'] and row['gates']['positive_adverse']:
                    scenarios.append(('leverage_2x', dict(max_leverage=2.)))
                for label, changes in scenarios:
                    _, result = self.trial(symbol, spec, start, end, 'ROBUST_'+label, frame=base_frame, cfg=config_for(spec, symbol, **changes))
                    rows.append(dict(symbol=symbol, id=spec['id'], scenario=label, **result['metrics']))
                for label in ['long_only', 'short_only', 'lag24h', 'null_blocks', 'neighbor', 'ablate_regime']:
                    variant = base_frame.copy()
                    if label == 'long_only':
                        variant.signal = variant.signal.clip(lower=0)
                    elif label == 'short_only':
                        variant.signal = variant.signal.clip(upper=0)
                    elif label == 'lag24h':
                        variant.signal = variant.signal.shift(max(1, int(pd.Timedelta(days=1)/pd.Timedelta(spec['timeframe'])))).fillna(0)
                    elif label == 'null_blocks':
                        # Reordering a frozen day's signal blocks is a nondeployable null control.
                        rng = np.random.default_rng(SEED)
                        day = variant.timestamp.dt.floor('D')
                        signs = pd.Series(rng.choice([-1, 1], size=day.nunique()), index=day.unique())
                        variant.signal = variant.signal*day.map(signs).to_numpy()
                    elif label == 'neighbor':
                        neighbor = copy.deepcopy(spec)
                        parameters = neighbor['parameters']
                        parameter = 'lookback' if 'lookback' in parameters else next(iter(parameters))
                        parameters[parameter] = max(2, int(parameters[parameter]*1.1)) if isinstance(parameters[parameter], int) else parameters[parameter]*1.1
                        variant = build_signal(self.features_for(symbol, spec['timeframe']), dict(neighbor, symbol=symbol))
                    else:
                        features = self.features_for(symbol, spec['timeframe']).copy()
                        features.regime = 'range' if spec['family'] in ['zscore', 'vwap_reversion'] else features.regime
                        variant = build_signal(features, dict(spec, symbol=symbol))
                    _, result = self.trial(symbol, spec, start, end, 'ROBUST_'+label, frame=variant)
                    rows.append(dict(symbol=symbol, id=spec['id'], scenario=label, **result['metrics']))
                peer = 'BNB' if symbol == 'ETH' else 'ETH'
                _, result = self.trial(peer, spec, start, end, f'TRANSFER_from_{symbol}', frame=self.signal(peer, spec))
                rows.append(dict(symbol=peer, id=spec['id'], scenario=f'no_refit_transfer_from_{symbol}', **result['metrics']))
        write(HERE/'robustness_results.json', rows)
        return rows

    def conditional(self, training, train_returns, chosen):
        from .fitted import fit_logistic_signal, ensemble_weights
        rows = []
        specs = {s['id']: s for s in library()}
        for symbol in ['ETH', 'BNB']:
            baseline = next(r for r in training if r['symbol'] == symbol and r['id'] == 'simple_momentum_1h')
            if baseline['train_eligible']:
                spec = dict(id='logistic_1h_C1', family='logistic', timeframe='1h', parameters=dict(C=1., threshold=.55),
                            baseline=False, execution=dict(stop_atr=2., reward_r=3., max_hold_bars=48))
                features = self.features_for(symbol, '1h')
                for fold in self.split['folds']:
                    signal = fit_logistic_signal(features, pd.Timestamp(fold['fit_end']), pd.Timestamp(fold['eval_start']))
                    _, result = self.trial(symbol, spec, fold['eval_start'], fold['eval_end'], 'MODEL_'+fold['id'], frame=signal)
                    rows.append(dict(symbol=symbol, kind='logistic', phase='TRAIN_internal_forward', fold=fold['id'], metrics=result['metrics']))
                signal = fit_logistic_signal(features, pd.Timestamp(self.split['train'][1]), pd.Timestamp(self.split['validation_eval_start']))
                _, result = self.trial(symbol, spec, self.split['validation_eval_start'], self.split['validation'][1], 'MODEL_VALIDATION', frame=signal)
                rows.append(dict(symbol=symbol, kind='logistic', phase='VALIDATION', metrics=result['metrics'],
                                 accepted=False, note='Conditional fixed model diagnostic; no multiplicity-controlled independent acceptance claim.'))
            else:
                rows.append(dict(symbol=symbol, kind='logistic', phase='SKIPPED', reason='Simple1h momentum failed training eligibility; no legitimate baseline established.'))
            members = [r for r in chosen if r['symbol'] == symbol]
            if len(members) < 2:
                rows.append(dict(symbol=symbol, kind='ensemble', phase='SKIPPED', reason='Fewer than two distinct training-eligible families.'))
                continue
            returns = {r['id']: train_returns[symbol, r['id']] for r in members}
            weights = ensemble_weights(returns)
            sleeve_series = []
            for member in members:
                spec = specs[member['id']]
                capital = 50000*weights[member['id']]
                _, result = self.trial(symbol, spec, self.split['validation_eval_start'], self.split['validation'][1], 'ENSEMBLE_VALIDATION',
                                       cfg=config_for(spec, symbol, initial_capital=capital))
                daily = result['equity'].set_index('bar_open').equity.resample('D').last()
                sleeve_series.append(daily)
            total = pd.concat(sleeve_series, axis=1, join='inner').sum(axis=1)
            ret = daily_returns(total)
            stats = block_statistics(ret)
            rows.append(dict(symbol=symbol, kind='ensemble', phase='VALIDATION', weights=weights,
                             net_pnl=float(total.iloc[-1]-50000), net_return=float(total.iloc[-1]/50000-1),
                             max_drawdown=float((1-total/np.maximum(50000,total.cummax())).max()), bootstrap=stats,
                             accepted=False, note='Weights fitted only to internal TRAIN returns; diagnostic, not independent significance.'))
        write(HERE/'conditional_results.json', rows)
        return rows

    def portfolio(self, chosen):
        curves, members = [], []
        specs = {s['id']: s for s in library()}
        for symbol in ['ETH', 'BNB']:
            selected = next((r for r in chosen if r['symbol'] == symbol), None)
            spec = specs[selected['id']] if selected else next(s for s in library() if s['id'] == 'flat_1h')
            _, result = self.trial(symbol, spec, self.split['validation_eval_start'], self.split['validation'][1], 'COMBINED_VALIDATION',
                                   cfg=config_for(spec, symbol, initial_capital=25000.))
            curves.append(result['equity'])
            members.append(dict(symbol=symbol, id=spec['id'], allocated_initial_capital=25000.))
        combined = combine_sleeves(curves)
        combined['equity'].to_csv(HERE/'combined_validation_equity.csv', index=False)
        payload = dict(members=members, metrics=combined['metrics'], correlation=combined['correlation'].to_dict(),
                       bootstrap=block_statistics(combined['daily_returns']), phase='VALIDATION',
                       selection='First frozen training-selected candidate per asset; no validation replacements.')
        # A portfolio entry circuit-breaker is replayed causally from each day's
        # prior marked high-water drawdown. Stops/exits continue; no lookahead.
        halted = []
        for symbol, curve, member in zip(['ETH', 'BNB'], curves, members):
            spec = specs[member['id']]
            signal = self.signal(symbol, spec)
            prior = curve.set_index('bar_open').equity
            dd = 1-prior/np.maximum(25000.,prior.cummax())
            # Freeze exposure off from the first observed5% drawdown onward.
            breach = dd[dd >= .05]
            skips = signal.timestamp[signal.timestamp > breach.index[0]].astype(str).tolist() if len(breach) else []
            _, result = self.trial(symbol, spec, self.split['validation_eval_start'], self.split['validation'][1], 'PORTFOLIO_DD_HALT',
                                   cfg=config_for(spec, symbol, initial_capital=25000., skip_entry_timestamps=skips))
            halted.append(result['equity'])
        payload['drawdown_halt_diagnostic'] = combine_sleeves(halted)['metrics']
        payload['drawdown_halt_note'] = '5% per-sleeve entry lock; combined policy is conservative separate sleeve halt, exits continue. Trigger based on prior observed baseline path until first halt.'
        write(HERE/'combined_validation_results.json', payload)
        return payload

    def freeze_candidates(self, validated):
        shortlist = []
        for row in validated:
            if row['accepted']:
                spec = next(s for s in library() if s['id'] == row['id'])
                envelope = freeze_payload(dict(mode='paper_only', strategy=dict(spec, symbol=row['symbol']), code_hashes=self.hashes,
                                               data_manifest_sha256=sha(HERE/'data_manifest.json'), split_manifest_sha256=sha(HERE/'split_manifest.json'),
                                               prospective_reservation=dict(zip(['start','end'], self.split['new_prospective_reservation'])),
                                               execution=config_for(spec, row['symbol']), ready_for_live_trading=False))
                freeze(HERE/'frozen_candidates'/f'{row["symbol"]}_{row["id"]}.json', envelope)
                shortlist.append(dict(symbol=row['symbol'], id=row['id'], freeze_sha256=envelope['freeze_sha256']))
        freeze(HERE/'freeze_manifest.json', dict(shortlist=shortlist, code_hashes=self.hashes,
                                                validation_results_sha256=sha(HERE/'validation_results.json'),
                                                nominal_final='CONTAMINATED_NOT_EVALUATED', paper_results='PENDING', production_integration=False))
        return shortlist


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--train-only', action='store_true')
    parser.add_argument('--report-only', action='store_true')
    args = parser.parse_args()
    if args.report_only:
        from .reporting import report
        report()
        return
    lab = Lab()
    freeze(HERE/'code_freeze.json', dict(code_hashes=lab.hashes, parent_commit=lab.revision,
                                        candidate_manifest_sha256=sha(HERE/'candidate_manifest.json'),
                                        data_manifest_sha256=sha(HERE/'data_manifest.json'), funding_manifest_sha256=sha(HERE/'funding_manifest.json')))
    training, train_returns = lab.train()
    if args.train_only:
        return
    chosen = lab.selection(training)
    lab.conditional(training, train_returns, chosen)
    validated = lab.validate(training, chosen)
    lab.robustness(validated)
    lab.portfolio(chosen)
    from .legacy import run as legacy_run
    legacy_run()
    lab.freeze_candidates(validated)
    from .reporting import report
    report()
    write(OUTPUT/'status.json', dict(stage='complete', final_holdout='CONTAMINATED_NOT_EVALUATED'))


if __name__ == '__main__':
    main()
