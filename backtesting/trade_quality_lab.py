"""Bounded regression filters for frozen ETH entries; no future test access.

Train on closed 2020-2022 trades; choose among six fixed model/threshold pairs
using 2023 only. Freeze the choice before inspecting 2024 and later diagnostics.
"""
from dataclasses import replace
import hashlib
import json
import warnings

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import Ridge
from sklearn.exceptions import ConvergenceWarning
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import RobustScaler
import xgboost
from xgboost import XGBRegressor

from .cost_reserve import simulate
from .exit_research import freeze
from .forward_collection import collection_lock, atomic_json
from .generalization_policy import assert_historical_period, digest, frozen_profile
from .independent_visuals import equity_curve
from .indicators import resample_complete
from .market_data import BAR, utc
from .optimize import pnl, subset
from .paths import ROOT
from .regime_filters import RegimeFilter, apply_filter, prepare_features
from .reporting import safe_value
from .strategy_lab import plan as parent_plan, load_development, sha, detailed


NAME = 'trade_quality_round1'
FEATURES = ['direction', 'atr_pct', 'signed_ema_gap', 'signed_slope', 'log_rvol',
            'signed_return_6h', 'signed_return_24h', 'signed_body_atr', 'range_atr',
            'hour_sin', 'hour_cos', 'weekday_sin', 'weekday_cos']
MODELS = ('ridge', 'xgboost', 'neural_mlp')
SEED = 20261103


def directory(root):
    return root/'artifacts/strategy_lab'/NAME


def matrix(frame):
    """Price-scale-independent context known at the signal candle close."""
    hours = resample_complete(frame, '1h')
    aligned = pd.DataFrame(dict(r6=(hours.close/hours.close.shift(6)-1).to_numpy(),
                                r24=(hours.close/hours.close.shift(24)-1).to_numpy()),
                           index=hours.index+pd.Timedelta(minutes=55)).reindex(pd.DatetimeIndex(frame.timestamp))
    d = frame.signal.to_numpy()
    hour = frame.timestamp.dt.hour.to_numpy()
    day = frame.timestamp.dt.dayofweek.to_numpy()
    return pd.DataFrame(dict(direction=d, atr_pct=frame.hourly_atr_bps.to_numpy()/100,
        signed_ema_gap=d*frame.trend_gap_bps.to_numpy()/100,
        signed_slope=d*frame.ema_slope_6h_bps.to_numpy()/100,
        log_rvol=np.log1p(frame.hourly_rvol.to_numpy()),
        signed_return_6h=d*aligned.r6.to_numpy()*100,
        signed_return_24h=d*aligned.r24.to_numpy()*100,
        signed_body_atr=d*(frame.close-frame.open).to_numpy()/frame.signal_atr.to_numpy(),
        range_atr=(frame.high-frame.low).to_numpy()/frame.signal_atr.to_numpy(),
        hour_sin=np.sin(2*np.pi*hour/24), hour_cos=np.cos(2*np.pi*hour/24),
        weekday_sin=np.sin(2*np.pi*day/7), weekday_cos=np.cos(2*np.pi*day/7)), index=frame.index)[FEATURES]


def labels(frame, trades, cutoff):
    """No open or overlapping outcomes; target is net P&L in $100 risk units."""
    x = matrix(frame)
    lookup = pd.Series(frame.index, index=frame.timestamp)
    rows = []
    if len(trades):
        for entry, legs in trades.groupby('entry_bar_open', sort=True):
            exit_time = pd.to_datetime(legs.exit_time, utc=True).max()
            if exit_time > utc(cutoff):
                continue
            signal_time = pd.Timestamp(entry)-BAR
            index = lookup.loc[signal_time]
            values = x.loc[index]
            if not np.isfinite(values.to_numpy()).all() or frame.loc[index, 'signal'] == 0:
                raise ValueError('Training label has no finite causal entry features')
            rows.append(dict(signal_time=str(signal_time), outcome_available_at=str(exit_time),
                             target_r=float(legs.net_pnl.sum()/100), **values.to_dict()))
    return pd.DataFrame(rows)


def make_model(name):
    if name == 'ridge':
        estimator = Ridge(alpha=10.)
    elif name == 'xgboost':
        estimator = XGBRegressor(n_estimators=120, max_depth=2, min_child_weight=15,
            learning_rate=.03, reg_alpha=1., reg_lambda=20., subsample=1.,
            colsample_bytree=1., tree_method='hist', objective='reg:squarederror',
            random_state=SEED, n_jobs=2)
    elif name == 'neural_mlp':
        estimator = MLPRegressor(hidden_layer_sizes=(16, 8), activation='tanh',
            alpha=10., max_iter=500, learning_rate_init=.001, shuffle=False,
            early_stopping=False, tol=1e-5, n_iter_no_change=50, random_state=SEED)
    else:
        raise ValueError('Unknown predefined trade-quality model')
    return make_pipeline(RobustScaler(), estimator)


def predictions(frame, model):
    x = matrix(frame)
    mask = frame.signal.ne(0) & np.isfinite(x).all(axis=1)
    result = pd.Series(np.nan, index=frame.index)
    if mask.any():
        result.loc[mask] = model.predict(x.loc[mask])
    return result


def filter_entries(frame, prediction, threshold):
    if not frame.index.equals(prediction.index):
        raise ValueError('Prediction rows differ from signal rows')
    result = frame.copy()
    result['signal'] = result.signal.where(prediction.ge(threshold), 0).astype(int)
    return result


def score(rows, baseline_rows):
    net = sum(r['closed_net'] for r in rows)
    parent = sum(r['closed_net'] for r in baseline_rows)
    eligible = (all(r['closed_net'] > 0 for r in rows)
                and sum(r['metrics']['closed_trade_legs'] for r in rows) >= 25
                and net > parent
                and all(r['metrics']['max_intrabar_drawdown'] <= .05 and r['metrics']['margin_call_events'] == 0 for r in rows))
    return dict(eligible=bool(eligible), closed_net=net, parent_closed_net=parent,
                score=float(net-.5*max(r['metrics']['max_intrabar_drawdown'] for r in rows)*50000))


def register(root=ROOT):
    p, _, _, _ = frozen_profile(root)
    assert_historical_period('2026-10-28', root)
    inherited = parent_plan(root)
    out = directory(root); out.mkdir(parents=True, exist_ok=True)
    path = out/'manifest.json'
    previous = json.loads(path.read_text()) if path.exists() else None
    models = {name: safe_value(make_model(name).get_params(deep=False)['steps'][-1][1].get_params()) for name in MODELS}
    sources = list(inherited['source_sha256'])+['trade_quality_lab.py']
    manifest = dict(name=NAME, parent_protocol_sha256=digest(p),
        created_at_utc=previous['created_at_utc'] if previous else str(pd.Timestamp.now(tz='UTC')),
        model_parameters=models, scaler='RobustScaler fitted on closed training labels only',
        thresholds_r=[0., .25], candidate_count=6, features=FEATURES,
        target='Actual closed trade net divided by $100 planned risk; no target clipping or classification-accuracy optimization.',
        training_period=['2020-01-01', '2022-12-25'], selection_period=['2023-01-01', '2023-12-25'],
        selection='Both 2023 halves positive closed net, >=25 closed trades total, higher 2023 closed net than unfiltered same-budget baseline, <=5% drawdown, no margin calls. Choose highest closed net minus 0.5*max drawdown*$50000. Tie by candidate id.',
        later_period=['2024-01-01', '2026-10-28'], model_refit_after_selection=False,
        actual_fill_bps=[2., 4., 8.], sizing_budget_bps=8.,
        minimum_closed_training_samples=100,
        convergence_gate='A model emitting a ConvergenceWarning is ineligible; warnings and its diagnostic outcomes are retained.',
        train_labels_end_before_next_stage_by_days=7,
        original_rules_change='Only entry acceptance; shared broker, exit geometry and $100 risk stay fixed.',
        data_hashes=inherited['data_hashes'], source_sha256={name: sha(root/name) for name in sources},
        library_versions=dict(sklearn=sklearn.__version__, xgboost=xgboost.__version__, numpy=np.__version__, pandas=pd.__version__),
        all_history_consumed=True, independent_validation=False,
        future_holdout_access=False, automatic_promotion=False)
    freeze(path, manifest)
    return manifest


def run(root=ROOT, verify=False):
    with collection_lock(directory(root)/'writer.lock'):
        return _run(root, verify)


def _run(root, verify):
    manifest = register(root)
    out = directory(root)
    result_path = out/'results.json'
    if result_path.exists() and not verify:
        return json.loads(result_path.read_text())
    _, rule, cfg, meta = frozen_profile(root)
    actual = replace(cfg, slippage_bps=8.)
    bars = load_development(root, manifest)
    training_bars = bars[bars.timestamp < utc('2023-01-01')].reset_index(drop=True)
    train_features = apply_filter(prepare_features(training_bars, rule), RegimeFilter(**meta['entry_filters']))
    _, trades, _ = simulate(training_bars, rule, actual, train_features, sizing_slippage_bps=8.)
    training = labels(train_features, trades, manifest['training_period'][1])
    if len(training) < manifest['minimum_closed_training_samples']:
        raise ValueError('Insufficient closed training trades; do not fit an undersampled model')
    training.to_csv(out/'training_labels.csv', index=False)
    models, selection_rows = {}, []
    fitting_warnings, converged = {}, {}
    for name in MODELS:
        model = make_model(name)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            model.fit(training[FEATURES], training.target_r)
        fitting_warnings[name] = [str(w.message) for w in caught]
        converged[name] = not any(issubclass(w.category, ConvergenceWarning) for w in caught)
        models[name] = model
        if not verify:
            joblib.dump(model, out/f'{name}.joblib')
        print(f'FIT {name}: closed training samples={len(training)}; warnings={len(caught)}', flush=True)
    # Feature construction uses only causal history. Model fit and scaling have
    # already ended before selection-year prices are introduced here.
    preceding = bars[bars.timestamp < utc(manifest['selection_period'][1])].reset_index(drop=True)
    features = apply_filter(prepare_features(preceding, rule), RegimeFilter(**meta['entry_filters']))
    baseline_rows = []
    for start, end in [('2023-01-01', '2023-07-01'), ('2023-07-01', '2023-12-25')]:
        b, f = subset(preceding, features, start, end)
        baseline_rows.append(detailed(b, f, rule, actual, out/'selection_baseline'/start))
    for name, model in models.items():
        prediction = predictions(features, model)
        for threshold in manifest['thresholds_r']:
            label = f'{name}_threshold{threshold}'
            filtered = filter_entries(features, prediction, threshold)
            folds = []
            for start, end in [('2023-01-01', '2023-07-01'), ('2023-07-01', '2023-12-25')]:
                b, f = subset(preceding, filtered, start, end)
                folds.append(detailed(b, f, rule, actual, out/'selection'/label/start))
            row = dict(id=label, model=name, threshold_r=threshold, folds=folds, rank=score(folds, baseline_rows))
            row['fit_converged'] = converged[name]
            row['rank']['eligible'] = row['rank']['eligible'] and converged[name]
            freeze(out/'selection'/f'{label}.json', row)
            selection_rows.append(row)
            print(f"SELECT {label}: net={row['rank']['closed_net']:.2f} eligible={row['rank']['eligible']}", flush=True)
    eligible = [r for r in selection_rows if r['rank']['eligible']]
    selected = max(eligible, key=lambda r: (r['rank']['score'], r['id'])) if eligible else None
    freeze(out/'selection.json', dict(candidate={k: selected[k] for k in ['id', 'model', 'threshold_r']} if selected else None,
                                      selected_before_later_diagnostics=True, manifest_sha256=digest(manifest)))
    audit = []
    if selected:
        full_features = apply_filter(prepare_features(bars, rule), RegimeFilter(**meta['entry_filters']))
        prediction = predictions(full_features, models[selected['model']])
        filtered = filter_entries(full_features, prediction, selected['threshold_r'])
        pd.DataFrame(dict(timestamp=bars.timestamp, baseline_signal=full_features.signal,
                          predicted_r=prediction, filtered_signal=filtered.signal)).to_parquet(out/'predictions.parquet', index=False)
        for period, begin, end in [('validation_2024', '2024-01-01', '2025-01-01'),
                                   ('audit_2025', '2025-01-01', '2026-01-01'),
                                   ('audit_2026', '2026-01-01', '2026-10-28'),
                                   ('full_development', '2023-01-01', '2026-10-28')]:
            b, f = subset(bars, filtered, begin, end)
            _, parent = subset(bars, full_features, begin, end)
            for slip in [2., 4., 8.]:
                for label, frame, budget in [('filtered', f, 8.), ('baseline_8bp_budget', parent, 8.),
                                              ('original_2bp_budget', parent, 2.)]:
                    outcome = detailed(b, frame, rule, replace(cfg, slippage_bps=slip),
                                       out/'audit'/period/f'{label}_fill{int(slip)}', budget)
                    audit.append(dict(period=period, strategy=label, fill_bps=slip, **outcome))
            print(f'ML LATER DIAGNOSTIC {period} complete; model and threshold unchanged', flush=True)
    result = dict(manifest_sha256=digest(manifest), training_samples=len(training), fitting_warnings=fitting_warnings,
                  selection=selection_rows, selected={k: selected[k] for k in ['id', 'model', 'threshold_r']} if selected else None,
                  audit=audit, independent_future_validation=False, promoted=False,
                  target_is_profit_not_accuracy=True)
    freeze(result_path, result)
    report(root, result)
    if verify:
        freeze(out/'verification.json', dict(results_sha256=sha(result_path),
                training_labels_sha256=sha(out/'training_labels.csv'),
                artifacts_sha256={str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.suffix in {'.parquet', '.csv'}},
                models_refit_and_all_scenarios_replayed=True, reproduced_exactly=True,
                independent_future_validation=False))
    return result


def report(root, result):
    lines = ['# Trade-quality regression filters', '',
             'Ridge, XGBoost and a small two-layer neural network; two fixed expected-net thresholds each. Models and RobustScaler fit closed 2020-2022 baseline trades only. Outcomes overlapping December 25, 2022 are excluded, leaving a seven-day gap before 2023. No target clipping. Inputs are causal, price-scale-independent signal context.', '',
             '**All dates are consumed research history, not a new holdout.** Six fixed candidates use the two 2023 halves for selection. The selected model/threshold are frozen before 2024-2026 diagnostics and are never refit on their outcomes. Entry filtering is fully re-simulated, including new opportunities after rejected trades, with original exits and broker costs.', '',
             f"Closed training trades: {result['training_samples']}. Fitting warnings: `{result['fitting_warnings']}`.", '',
             '| Filter | Selection closed net at 8bp | Unfiltered baseline | Eligible |',
             '| --- | ---: | ---: | --- |']
    for row in result['selection']:
        rank = row['rank']
        lines.append(f"| {row['id']} | ${rank['closed_net']:,.2f} | ${rank['parent_closed_net']:,.2f} | {rank['eligible']} |")
    lines += ['', f"Selected before later diagnostics: **{result['selected']['id'] if result['selected'] else 'None: no model passed the fixed selection gate'}**.", '',
              '| Period | Strategy | Actual fill cost | Net including open marks | Closed net | Drawdown | Entries |',
              '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for row in result['audit']:
        m = row['metrics']
        lines.append(f"| {row['period']} | {row['strategy']} | {row['fill_bps']}bp | ${pnl(m):,.2f} | ${row['closed_net']:,.2f} | {m['max_intrabar_drawdown']:.2%} | {m['entries']} |")
    lines += ['', 'Shared comparisons have causal 2020-2022 indicator warm-up. Annual accounts reset; annual sums are not full-period returns. Original 2bp sizing and conservative 8bp sizing are labeled separately. A forecast is not a calibrated profit guarantee. A small neural network does not establish a deep-learning advantage on a few hundred trades.', '',
              'No strategy version is promoted. Frozen baseline, external tests and prospective protocols remain intact. Additional research slots: six model/threshold pairs, beyond the 24-family experiment and earlier history.', '',
              '[XGBoost Python API](https://xgboost.readthedocs.io/en/stable/python/python_api.html).', '']
    (root/'reports/trade_quality_round1.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    result = run(verify=parser.parse_args().verify)
    print(json.dumps(dict(selected=result['selected'], training_samples=result['training_samples']), indent=2))
