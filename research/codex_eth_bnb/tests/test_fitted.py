import numpy as np
import pandas as pd
import pytest

from research.codex_eth_bnb.fitted import ensemble_weights, fit_logistic_signal
from research.codex_eth_bnb.strategies import build_features


def sample(n=1000):
    rng = np.random.default_rng(29)
    close = 100*np.exp(np.cumsum(rng.normal(0., .004, n)))
    open_ = np.r_[100., close[:-1]]
    frame = pd.DataFrame(dict(timestamp=pd.date_range('2021-01-01', periods=n, freq='1h', tz='UTC'),
                               open=open_, high=np.maximum(open_, close)*1.002,
                               low=np.minimum(open_, close)*.998, close=close,
                               volume=rng.uniform(50, 200, n)))
    return build_features(frame)


def test_model_cutoffs_metadata_and_fixed_thresholds():
    features = sample()
    end = features.timestamp.iloc[650]
    start = features.timestamp.iloc[700]
    result = fit_logistic_signal(features, end, start)
    metadata = result.attrs['fitted_model']
    assert pd.Timestamp(metadata['trained_through']) <= end
    assert pd.Timestamp(metadata['training_features_through']) < end
    assert metadata['sample_count'] >= 100
    assert len(metadata['feature_columns']) == len(metadata['coefficients']) == 8
    assert metadata['evaluation_outcomes_used'] is False
    assert result.loc[result.timestamp < start, 'signal'].eq(0).all()
    assert result.loc[result.model_probability.ge(.55), 'signal'].eq(1).all()
    assert result.loc[result.model_probability.le(.45), 'signal'].eq(-1).all()
    assert result.signal.isin([-1, 0, 1]).all()


def test_future_fit_data_poisoning_does_not_change_scaler_or_coefficients():
    original = sample()
    end, start = original.timestamp.iloc[650], original.timestamp.iloc[700]
    changed = original.copy()
    feature_columns = ['return', 'rv', 'rv_ratio', 'autocorr', 'trend_strength', 'rvol']
    changed.loc[changed.timestamp >= end, feature_columns] *= 100.
    changed.loc[changed.timestamp >= end, 'close'] *= 100.
    first = fit_logistic_signal(original, end, start)
    second = fit_logistic_signal(changed, end, start)
    assert first.attrs['coefhash'] == second.attrs['coefhash']
    assert first.attrs['fitted_model']['scaler_mean'] == second.attrs['fitted_model']['scaler_mean']


def test_evaluation_labels_are_never_used_and_unknown_last_label_is_excluded():
    original = sample()
    end, start = original.timestamp.iloc[650], original.timestamp.iloc[700]
    changed = original.copy()
    changed.loc[changed.timestamp >= start, 'close'] = np.arange((changed.timestamp >= start).sum())+10000.
    first = fit_logistic_signal(original, end, start)
    second = fit_logistic_signal(changed, end, start)
    np.testing.assert_allclose(first.model_probability, second.model_probability, equal_nan=True)
    assert first.attrs['coefhash'] == second.attrs['coefhash']
    last_end = original.timestamp.iloc[-1]+pd.Timedelta(hours=1)
    last = fit_logistic_signal(original, last_end, last_end)
    assert last.attrs['fitted_model']['prediction_rows'] == 0
    assert last.attrs['fitted_model']['sample_count'] < len(original)-1


def test_missing_eval_features_are_left_untraded_without_imputation():
    features = sample()
    end, start = features.timestamp.iloc[650], features.timestamp.iloc[700]
    features.loc[800, 'autocorr'] = np.nan
    result = fit_logistic_signal(features, end, start)
    assert result.signal.iloc[800] == 0 and pd.isna(result.model_probability.iloc[800])


def test_invalid_or_insufficient_fit_windows_fail():
    features = sample()
    with pytest.raises(ValueError, match='at or after'):
        fit_logistic_signal(features, features.timestamp.iloc[800], features.timestamp.iloc[600])
    with pytest.raises(ValueError, match='100 finite'):
        fit_logistic_signal(features, features.timestamp.iloc[100], features.timestamp.iloc[200])
    with pytest.raises(ValueError, match='regular'):
        fit_logistic_signal(features.drop(index=300), features.timestamp.iloc[650], features.timestamp.iloc[700])


def returns():
    index = pd.date_range('2021-01-01', periods=90, freq='D', tz='UTC')
    pattern = np.tile([-.01, .0, .01], 30)
    return dict(first=pd.Series(pattern, index=index), second=pd.Series(pattern*2, index=index))


def test_inverse_volatility_weights_are_deterministic_bounded_and_mean_agnostic():
    inputs = returns()
    weights = ensemble_weights(inputs)
    assert weights['first'] == pytest.approx(2/3)
    assert weights['second'] == pytest.approx(1/3)
    assert weights == ensemble_weights(inputs)
    assert sum(weights.values()) <= 1.+1e-12
    changed_mean = {key: value+.01 for key, value in inputs.items()}
    for key, value in ensemble_weights(changed_mean).items():
        assert value == pytest.approx(weights[key])


def test_ensemble_never_fills_missing_dates_or_returns_or_intersects_calendars():
    inputs = returns()
    with pytest.raises(ValueError, match='calendar'):
        ensemble_weights({**inputs, 'second': inputs['second'].drop(inputs['second'].index[40])})
    invalid = inputs['second'].copy()
    invalid.iloc[40] = np.nan
    with pytest.raises(ValueError, match='finite'):
        ensemble_weights({**inputs, 'second': invalid})
    shifted = inputs['second'].copy()
    shifted.index += pd.Timedelta(days=1)
    with pytest.raises(ValueError, match='match exactly'):
        ensemble_weights({**inputs, 'second': shifted})


def test_flat_sleeve_gets_zero_weight_and_two_live_sources_are_required():
    inputs = returns()
    zero = inputs['first']*0
    weights = ensemble_weights({**inputs, 'flat': zero})
    assert weights['flat'] == 0.
    with pytest.raises(ValueError, match='two nonzero'):
        ensemble_weights(dict(first=inputs['first'], flat=zero))
