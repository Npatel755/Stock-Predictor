"""Two bounded, interpretable fitted components; no search or outcome selection.

Chronological windows and whether a baseline warrants these components are
owned by the experiment runner. This module never reads a holdout file, tunes
thresholds, selects families, or normalizes across the evaluation period.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd


SEED = 20261103
FEATURES = ('return', 'rv', 'rv_ratio', 'autocorr', 'trend_strength', 'rvol', 'return_lag1', 'return_lag2')


def _utc(value):
    result = pd.Timestamp(value)
    return result.tz_localize('UTC') if result.tzinfo is None else result.tz_convert('UTC')


def fit_logistic_signal(features: pd.DataFrame, fit_end, eval_start):
    """Fit L2 logistic C=1 on permitted past, predict a later fixed window.

    ``timestamp`` means candle open; features become available at its close.
    A training row requires feature availability STRICTLY before ``fit_end``
    and next-close label availability no later than ``fit_end``. The last
    unknown next-close label is excluded. The caller separately enforces its
    event-horizon purge/embargo. Evaluation rows have bar OPEN >= eval_start.

    Labels use the next close only within this bounded training construction.
    Missing/nonfinite feature rows remain untraded; there is no imputation.
    Prediction thresholds are fixed .55 long and .45 short, otherwise flat.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    required = {'timestamp', 'close', *FEATURES[:6]}
    if features.empty or not required.issubset(features.columns):
        raise ValueError('Logistic inputs require nonempty causal features and candle close')
    fit_end, eval_start = _utc(fit_end), _utc(eval_start)
    if eval_start < fit_end:
        raise ValueError('Evaluation must start at or after the training cutoff')
    out = features.copy().reset_index(drop=True)
    out['timestamp'] = pd.to_datetime(out.timestamp, utc=True)
    times = pd.DatetimeIndex(out.timestamp)
    if times.has_duplicates or not times.is_monotonic_increasing:
        raise ValueError('Logistic timestamps must be ordered and unique')
    span = pd.Timedelta(features.attrs['feature_duration']) if 'feature_duration' in features.attrs else times[1]-times[0] if len(times) > 1 else pd.Timedelta(hours=1)
    if span <= pd.Timedelta(0) or (len(times) > 1 and not out.timestamp.diff().dropna().eq(span).all()):
        raise ValueError('Logistic training requires a regular chronological candle grid')
    out['return_lag1'] = out['return'].shift(1)
    out['return_lag2'] = out['return'].shift(2)
    matrix = out[list(FEATURES)].to_numpy(dtype=float)
    finite = np.isfinite(matrix).all(axis=1)
    available = out.timestamp+span
    # This forward shift creates TRAINING LABELS only. No signal/feature uses it.
    next_close = out.close.shift(-1)
    next_available = available.shift(-1)
    label = (next_close > out.close).astype(np.int8)
    train = finite & (available < fit_end) & (next_available <= fit_end) & next_close.notna()
    if int(train.sum()) < 100:
        raise ValueError('At least 100 finite completed training labels are required')
    y_train = label.loc[train].to_numpy()
    if len(np.unique(y_train)) != 2:
        raise ValueError('Both target classes are required in permitted training history')
    scaler = StandardScaler()
    x_train = scaler.fit_transform(matrix[train])
    # lbfgs with finite C and the default penalty is L2; omitting the legacy
    # penalty keyword also supports sklearn's newer regularization interface.
    model = LogisticRegression(C=1., solver='lbfgs', max_iter=1000, random_state=SEED)
    model.fit(x_train, y_train)
    evaluate = finite & (out.timestamp >= eval_start)
    probability = np.full(len(out), np.nan)
    if evaluate.any():
        probability[evaluate] = model.predict_proba(scaler.transform(matrix[evaluate]))[:, 1]
    signal = np.where(probability >= .55, 1, np.where(probability <= .45, -1, 0)).astype(np.int8)
    out['model_probability'] = probability
    out['signal'] = signal
    fitted_values = dict(feature_columns=list(FEATURES), coefficients=model.coef_[0].tolist(),
                         intercept=float(model.intercept_[0]), scaler_mean=scaler.mean_.tolist(),
                         scaler_scale=scaler.scale_.tolist(), classes=model.classes_.tolist(),
                         C=1., seed=SEED, thresholds=[.45, .55])
    coefficient_hash = hashlib.sha256(json.dumps(fitted_values, sort_keys=True, allow_nan=False).encode()).hexdigest()
    metadata = dict(**fitted_values, sample_count=int(train.sum()),
                    trained_through=str(next_available.loc[train].max()),
                    training_features_through=str(available.loc[train].max()),
                    training_cutoff=str(fit_end), evaluation_start=str(eval_start),
                    prediction_rows=int(evaluate.sum()), coefhash=coefficient_hash,
                    label='next completed candle close strictly above current close; ties non-UP',
                    scaler_fit='permitted training rows only', evaluation_outcomes_used=False)
    out.attrs.update(features.attrs)
    out.attrs.update(trained_through=metadata['trained_through'], coefhash=coefficient_hash,
                     fitted_columns=list(FEATURES), sample_count=metadata['sample_count'], fitted_model=metadata)
    return out


def ensemble_weights(daily_returns: dict[str, pd.Series]):
    """Inverse-volatility fixed weights from caller-provided TRAIN returns.

    Series must have identical full consecutive UTC daily calendars, finite
    values, and at least 30 observations. Missing dates/returns are rejected,
    never filled or silently intersected. The caller must verify distinct
    mechanisms and ensure every supplied observation lies in its TRAIN window.
    Zero-volatility/cash series receive zero weight. No mean-return ranking,
    Sharpe optimization, leverage, or evaluation-period fitting is performed.
    """
    if len(daily_returns) < 2:
        raise ValueError('At least two distinct strategy return series are required')
    reference = None
    volatilities = {}
    for identifier, series in daily_returns.items():
        if not isinstance(series, pd.Series) or not isinstance(series.index, pd.DatetimeIndex):
            raise ValueError('Ensemble inputs must be dated daily-return Series')
        index = series.index
        if index.tz is None or str(index.tz) not in ('UTC', 'utc') or index.has_duplicates or not index.is_monotonic_increasing:
            raise ValueError('Ensemble return dates must be unique, ordered, and UTC-aware')
        if len(series) < 30 or not np.isfinite(series.to_numpy(dtype=float)).all():
            raise ValueError('At least 30 finite training daily returns are required; missing returns cannot be filled')
        if not index.equals(index.floor('D')) or not np.all(np.diff(index.as_unit('ns').asi8) == pd.Timedelta(days=1).value):
            raise ValueError('Missing calendar days are not allowed in ensemble fitting')
        if reference is not None and not reference.equals(index):
            raise ValueError('Ensemble TRAIN calendars must match exactly; no silent intersection')
        reference = index
        volatilities[identifier] = float(series.std(ddof=1))
    active = {key: 1/value for key, value in volatilities.items() if np.isfinite(value) and value > 1e-12}
    if len(active) < 2:
        raise ValueError('At least two nonzero-volatility strategy series are required')
    total = sum(active.values())
    weights = {key: active.get(key, 0.)/total for key in daily_returns}
    # Avoid allocating an epsilon more than total capital through float roundoff.
    normalization = max(1., sum(weights.values()))
    weights = {key: value/normalization for key, value in weights.items()}
    if any(not np.isfinite(value) or value < 0 for value in weights.values()) or sum(weights.values()) > 1.+1e-12:
        raise AssertionError('Invalid fitted ensemble allocation')
    return weights
